from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from midas.frontier.models import Venue
from midas.frontier.registry import AdapterRegistry
from midas.frontier.source_gate import BoundedSourceOperationGate, SourceOperationBusy
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.test_collection import FakeAdapter


@pytest.mark.asyncio
async def test_source_gate_caps_cross_venue_operations_and_fails_fast():
    gate = BoundedSourceOperationGate(max_concurrent=2, acquire_timeout_seconds=0.01)
    entered: asyncio.Queue[Venue] = asyncio.Queue()
    release = asyncio.Event()

    async def hold(venue: Venue) -> None:
        async with gate.operation(venue):
            entered.put_nowait(venue)
            await release.wait()

    first = asyncio.create_task(hold(Venue.POLYMARKET))
    second = asyncio.create_task(hold(Venue.KALSHI))
    try:
        assert await asyncio.wait_for(entered.get(), timeout=0.5) == Venue.POLYMARKET
        assert await asyncio.wait_for(entered.get(), timeout=0.5) == Venue.KALSHI
        with pytest.raises(SourceOperationBusy) as busy:
            async with gate.operation(Venue.KRAKEN):
                pytest.fail("A third source must not enter while both slots are occupied")
        assert busy.value.scope == "capacity"
        assert busy.value.venue == Venue.KRAKEN
    finally:
        release.set()
        await asyncio.gather(first, second)

    async with gate.operation(Venue.KRAKEN):
        pass


@pytest.mark.asyncio
async def test_source_gate_rejects_same_venue_and_releases_after_exception():
    gate = BoundedSourceOperationGate(max_concurrent=2, acquire_timeout_seconds=0.01)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with gate.operation(Venue.POLYMARKET):
            entered.set()
            await release.wait()

    active = asyncio.create_task(hold())
    try:
        await asyncio.wait_for(entered.wait(), timeout=0.5)
        with pytest.raises(SourceOperationBusy) as busy:
            async with gate.operation(Venue.POLYMARKET):
                pytest.fail("A second operation for one venue must be rejected")
        assert busy.value.scope == "venue"
        assert gate.runtime_snapshot() == {
            "active_operations": 1,
            "active_venues": ["polymarket"],
            "admitted_operations_total": 1,
            "busy_rejections_total": 1,
            "busy_rejections_by_scope": {"venue": 1, "capacity": 0},
        }
    finally:
        release.set()
        await active

    with pytest.raises(RuntimeError, match="fixture failure"):
        async with gate.operation(Venue.POLYMARKET):
            raise RuntimeError("fixture failure")

    async with gate.operation(Venue.POLYMARKET):
        pass
    assert gate.runtime_snapshot() == {
        "active_operations": 0,
        "active_venues": [],
        "admitted_operations_total": 3,
        "busy_rejections_total": 1,
        "busy_rejections_by_scope": {"venue": 1, "capacity": 0},
    }


class _BlockingProbeAdapter(FakeAdapter):
    def __init__(self, venue: Venue) -> None:
        super().__init__(venue=venue)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def discover_markets(self, limit: int = 20):
        self.entered.set()
        await self.release.wait()
        return await super().discover_markets(limit)


@pytest.mark.asyncio
async def test_frontier_probe_api_applies_shared_gate_and_reports_policy(tmp_path):
    adapters = tuple(
        _BlockingProbeAdapter(venue) for venue in (Venue.POLYMARKET, Venue.KALSHI, Venue.KRAKEN)
    )
    registry = AdapterRegistry(adapters)
    app = FastAPI()
    app.include_router(router(FrontierStore(tmp_path / "frontier"), registry))
    tasks: list[asyncio.Task[httpx.Response]] = []

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://frontier.test"
    ) as client:
        try:
            inventory = await client.get("/api/frontier/sources")
            assert inventory.status_code == 200
            assert inventory.json()["network_called"] is False
            admission = inventory.json()["operation_admission"]
            assert {
                key: admission[key]
                for key in (
                    "scope",
                    "max_concurrent_source_operations",
                    "single_flight_per_venue",
                    "maximum_acquire_wait_ms",
                    "overload_status",
                    "overload_behavior",
                )
            } == {
                "scope": "frontier_router_instance",
                "max_concurrent_source_operations": 2,
                "single_flight_per_venue": True,
                "maximum_acquire_wait_ms": 50,
                "overload_status": 429,
                "overload_behavior": "fail_fast_no_request_queued",
            }
            initial_runtime = admission["runtime_snapshot"]
            assert initial_runtime["sampled_at_utc"].endswith("+00:00")
            assert initial_runtime["active_operations"] == 0
            assert initial_runtime["active_venues"] == []
            assert initial_runtime["admitted_operations_total"] == 0
            assert initial_runtime["busy_rejections_total"] == 0
            assert initial_runtime["busy_rejections_by_scope"] == {"venue": 0, "capacity": 0}

            first = asyncio.create_task(
                client.post("/api/frontier/probe/polymarket", json={"limit": 1})
            )
            tasks.append(first)
            await asyncio.wait_for(adapters[0].entered.wait(), timeout=0.5)

            second = asyncio.create_task(
                client.post("/api/frontier/probe/kalshi", json={"limit": 1})
            )
            tasks.append(second)
            await asyncio.wait_for(adapters[1].entered.wait(), timeout=0.5)

            third = await client.post("/api/frontier/probe/kraken", json={"limit": 1})
            assert third.status_code == 429
            assert third.headers["retry-after"] == "1"
            assert third.json()["detail"] == {
                "code": "SOURCE_OPERATION_BUSY",
                "venue": Venue.KRAKEN.value,
                "scope": "capacity",
                "message": "Public source operation is busy: the shared source-operation capacity is full",
            }
            assert adapters[2].discovery_calls == 0
            active_snapshot = (await client.get("/api/frontier/sources")).json()[
                "operation_admission"
            ]["runtime_snapshot"]
            assert active_snapshot["active_operations"] == 2
            assert active_snapshot["active_venues"] == ["kalshi", "polymarket"]
            assert active_snapshot["admitted_operations_total"] == 2
            assert active_snapshot["busy_rejections_total"] == 1
            assert active_snapshot["busy_rejections_by_scope"] == {"venue": 0, "capacity": 1}

            adapters[0].release.set()
            adapters[1].release.set()
            responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=2)
            assert [response.status_code for response in responses] == [200, 200]
            assert adapters[0].discovery_calls == adapters[1].discovery_calls == 1
            final_snapshot = (await client.get("/api/frontier/sources")).json()[
                "operation_admission"
            ]["runtime_snapshot"]
            assert final_snapshot["active_operations"] == 0
            assert final_snapshot["active_venues"] == []
            assert final_snapshot["admitted_operations_total"] == 2
            assert final_snapshot["busy_rejections_total"] == 1
        finally:
            for adapter in adapters:
                adapter.release.set()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await registry.aclose()
