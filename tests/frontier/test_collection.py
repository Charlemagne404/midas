from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from midas.frontier.adapters.base import AdapterError, build_capabilities
from midas.frontier.collection import BoundedSourceCollector, CollectionJournal
from midas.frontier.models import (
    AdapterConfig,
    BookLevel,
    Capability,
    FrontierModel,
    MarketBatch,
    RawObservation,
    SourceHealth,
    SourceState,
    Venue,
)
from midas.frontier.storage import FrontierStore, FrontierStoreError

from tests.frontier.builders import T0, book, market


class FakeTransport:
    def __init__(self) -> None:
        self.request_count = 0


class FakeAdapter:
    venue = Venue.POLYMARKET

    def __init__(
        self,
        *,
        fail_instruments: set[str] | None = None,
        fail_discovery: bool = False,
        enabled: bool = True,
    ) -> None:
        self.config = AdapterConfig(enabled=enabled, live_public_probe_enabled=enabled)
        self.capabilities = build_capabilities(
            Venue.POLYMARKET,
            "fixture-adapter-1",
            {
                Capability.MARKET_DISCOVERY: ("Fixture discovery", None),
                Capability.BOOK_SNAPSHOT: ("Fixture book snapshot", None),
            },
        )
        self.transport = FakeTransport()
        self.fail_instruments = fail_instruments or set()
        self.fail_discovery = fail_discovery
        self.failures: list[tuple[str, str]] = []
        self.market_values = (market(Venue.POLYMARKET, "collection-fixture"),)
        self.market_capture: RawObservation | None = None
        self.pending_captures: list[RawObservation] = []
        self.discovery_calls = 0
        self.book_calls: list[str] = []

    @staticmethod
    def _raw(kind: str, identity: str) -> RawObservation:
        body = json.dumps({"kind": kind, "identity": identity}, sort_keys=True)
        return RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind=kind,
            request_url=f"https://fixture.example/{kind}/{identity}",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="fixture-adapter-1",
        )

    async def health(self) -> SourceHealth:
        return SourceHealth(
            venue=self.venue,
            state=SourceState.DEGRADED if self.failures else SourceState.HEALTHY,
            supported_capabilities=(Capability.MARKET_DISCOVERY, Capability.BOOK_SNAPSHOT),
            unsupported_capabilities=tuple(
                item
                for item in Capability
                if item not in {Capability.MARKET_DISCOVERY, Capability.BOOK_SNAPSHOT}
            ),
        )

    async def discover_markets(self, limit: int = 20):
        self.transport.request_count += 1
        self.discovery_calls += 1
        if self.fail_discovery:
            raise AdapterError("FIXTURE_DISCOVERY_FAILURE", "Fixture source discovery failed")
        self.market_capture = self._raw("market_listing", "one")
        self.pending_captures.append(self.market_capture)
        value = self.market_values[0]
        provenance = value.provenance.model_copy(
            update={
                "raw_sha256": self.market_capture.raw_sha256,
                "observation_id": "fixture-market",
            }
        )
        self.market_values = (value.model_copy(update={"provenance": provenance}),)
        return self.market_values[:limit]

    async def fetch_book(self, market_value, instrument_id: str, depth: int = 20):
        self.transport.request_count += 1
        self.book_calls.append(instrument_id)
        if instrument_id in self.fail_instruments:
            raise AdapterError("FIXTURE_BOOK_FAILURE", "Fixture book request failed")
        capture = self._raw("book_snapshot", instrument_id)
        self.pending_captures.append(capture)
        value = book(market_value, instrument_id, "0.40")
        provenance = value.provenance.model_copy(
            update={"raw_sha256": capture.raw_sha256, "observation_id": capture.raw_sha256}
        )
        return value.model_copy(update={"provenance": provenance})

    def take_captures(self) -> tuple[RawObservation, ...]:
        result = tuple(self.pending_captures)
        self.pending_captures.clear()
        return result

    def report_failure(self, code: str, message: str) -> None:
        self.failures.append((code, message))


class FailOnceStore(FrontierStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.fail_once = True

    def append_observation(self, raw: RawObservation, normalized: FrontierModel) -> str:
        if self.fail_once:
            self.fail_once = False
            raise FrontierStoreError("Fixture storage interruption")
        return super().append_observation(raw, normalized)


class BlockingAdapter(FakeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.discovery_entered = asyncio.Event()
        self.block_discovery = True

    async def discover_markets(self, limit: int = 20):
        if self.block_discovery:
            self.block_discovery = False
            self.discovery_entered.set()
            await asyncio.Event().wait()
        return await super().discover_markets(limit)


class WrongLineageAdapter(FakeAdapter):
    async def discover_markets(self, limit: int = 20):
        markets = await super().discover_markets(limit)
        return tuple(
            item.model_copy(
                update={"provenance": item.provenance.model_copy(update={"raw_sha256": "0" * 64})}
            )
            for item in markets
        )


class OversizedBookAdapter(FakeAdapter):
    async def fetch_book(self, market_value, instrument_id: str, depth: int = 20):
        value = await super().fetch_book(market_value, instrument_id, depth)
        extra_level = BookLevel(price=Decimal("0.41"), quantity=Decimal(1))
        return value.model_copy(update={"asks": (*value.asks, extra_level)})


@pytest.mark.asyncio
async def test_finite_collection_persists_market_books_and_is_idempotent_on_resume(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)

    result = await collector.start(market_limit=1, book_limit=2)
    assert result.state == "completed"
    assert result.market_count == 1
    assert result.book_count == 2
    assert result.failed_book_count == 0
    assert result.request_count == 3
    assert len(result.market_observation_ids) == 1
    assert len(result.book_observation_ids) == 2
    assert len(result.diagnostic_observation_ids) == 0
    assert store.summary()["observations"] == 3

    resumed = await collector.resume(result.run_id)
    assert resumed == result
    assert adapter.discovery_calls == 1
    assert len(adapter.book_calls) == 2
    checkpoints = CollectionJournal(store.root).checkpoints(result.run_id)
    assert checkpoints[-1].state == "completed"
    assert [item.sequence for item in checkpoints] == list(range(len(checkpoints)))
    assert checkpoints[-1].completed_book_task_ids == tuple(
        task.task_id for task in checkpoints[-1].book_tasks
    )


@pytest.mark.asyncio
async def test_one_book_failure_is_recorded_without_stopping_other_source_tasks(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter(fail_instruments={"POLYMARKET:collection-fixture:YES"})
    collector = BoundedSourceCollector(adapter, store)

    result = await collector.start(market_limit=1, book_limit=2)
    assert result.state == "partial"
    assert result.book_count == 1
    assert result.failed_book_count == 1
    assert result.failures[0].code == "FIXTURE_BOOK_FAILURE"
    assert result.source_health is not None
    assert result.source_health.state == SourceState.DEGRADED
    assert len(adapter.book_calls) == 2
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_persisted_pending_capture_resumes_without_repeating_discovery(tmp_path):
    store = FailOnceStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)

    paused = await collector.start(market_limit=1, book_limit=1)
    assert paused.state == "paused"
    assert paused.pending_observation_count == 1
    assert adapter.discovery_calls == 1
    assert store.summary()["observations"] == 0
    latest_before = CollectionJournal(store.root).latest_checkpoint(paused.run_id)
    assert latest_before.pending_target == "market"
    assert latest_before.pending_observations[0].raw.observation_kind == "market_listing"

    resumed = await collector.resume(paused.run_id)
    assert resumed.state == "completed"
    assert resumed.pending_observation_count == 0
    assert resumed.market_count == 1
    assert resumed.book_count == 1
    assert adapter.discovery_calls == 1
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_pending_capture_resumes_with_a_reconstructed_collector(tmp_path):
    root = tmp_path / "frontier"
    interrupted_store = FailOnceStore(root)
    original_adapter = FakeAdapter()
    paused = await BoundedSourceCollector(original_adapter, interrupted_store).start(
        market_limit=1, book_limit=1
    )
    assert paused.state == "paused"

    restarted_adapter = FakeAdapter()
    restarted_store = FrontierStore(root)
    resumed = await BoundedSourceCollector(restarted_adapter, restarted_store).resume(paused.run_id)
    assert resumed.state == "completed"
    assert resumed.market_count == 1
    assert resumed.book_count == 1
    assert restarted_adapter.discovery_calls == 0
    assert len(restarted_adapter.book_calls) == 1
    assert restarted_store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_disabled_source_makes_no_adapter_call_and_failures_are_source_local(tmp_path):
    disabled_store = FrontierStore(tmp_path / "disabled")
    disabled_adapter = FakeAdapter(enabled=False)
    disabled = BoundedSourceCollector(disabled_adapter, disabled_store)
    with pytest.raises(AdapterError, match="public-probe flag"):
        await disabled.start(market_limit=1, book_limit=0)
    assert disabled_adapter.discovery_calls == 0
    assert not CollectionJournal(disabled_store.root).path.exists()

    failed_store = FrontierStore(tmp_path / "failed-source")
    failed_adapter = FakeAdapter(fail_discovery=True)
    failed = await BoundedSourceCollector(failed_adapter, failed_store).start(
        market_limit=1, book_limit=0
    )
    assert failed.state == "failed"
    assert failed.market_count == 0
    assert failed.failures[0].code == "FIXTURE_DISCOVERY_FAILURE"

    healthy_store = FrontierStore(tmp_path / "healthy-source")
    healthy_adapter = FakeAdapter()
    healthy = await BoundedSourceCollector(healthy_adapter, healthy_store).start(
        market_limit=1, book_limit=0
    )
    assert healthy.state == "completed"
    assert healthy.market_count == 1
    assert healthy_adapter.discovery_calls == 1


def test_collection_journal_detects_checkpoint_tampering_and_enforces_append_only(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    # A created run has a durable, independently verifiable first checkpoint.
    import asyncio

    result = asyncio.run(BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0))
    journal = CollectionJournal(store.root)
    checkpoints = journal.checkpoints(result.run_id)
    assert checkpoints[-1].state == "completed"

    import sqlite3

    with sqlite3.connect(journal.path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE collection_checkpoints SET checkpoint_json='{}' WHERE run_id=? AND sequence=0",
            (result.run_id,),
        )
    with sqlite3.connect(journal.path) as connection:
        connection.execute(
            "INSERT INTO collection_checkpoints VALUES(?,?,?,?,?)",
            (result.run_id, len(checkpoints), "0" * 64, "{}", "0" * 64),
        )
    with pytest.raises(FrontierStoreError, match="chain integrity"):
        journal.checkpoints(result.run_id)


def test_latest_pinned_market_metadata_wins_without_discarding_capture_rows(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)
    earlier_raw = FakeAdapter._raw("market_listing", "earlier")
    later_raw = FakeAdapter._raw("market_listing", "later")
    base_market = market(Venue.POLYMARKET, "same-native-market")

    def captured_market(raw: RawObservation, title: str):
        provenance = base_market.provenance.model_copy(
            update={"raw_sha256": raw.raw_sha256, "observation_id": raw.raw_sha256}
        )
        return base_market.model_copy(update={"title": title, "provenance": provenance})

    earlier_id = store.append_observation(
        earlier_raw,
        MarketBatch(venue=Venue.POLYMARKET, markets=(captured_market(earlier_raw, "Earlier"),)),
    )
    later_id = store.append_observation(
        later_raw,
        MarketBatch(venue=Venue.POLYMARKET, markets=(captured_market(later_raw, "Latest"),)),
    )

    selected = collector._load_markets((earlier_id, later_id), Venue.POLYMARKET)
    assert len(selected) == 1
    assert selected[0].title == "Latest"
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_cancellation_is_checkpointed_and_run_can_resume(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = BlockingAdapter()
    collector = BoundedSourceCollector(adapter, store)
    task = asyncio.create_task(collector.start(market_limit=1, book_limit=0, max_wall_seconds=60))
    await asyncio.wait_for(adapter.discovery_entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    journal = CollectionJournal(store.root)
    with sqlite3.connect(journal.path) as connection:
        run_id = str(connection.execute("SELECT run_id FROM collection_runs").fetchone()[0])
    paused = journal.latest_checkpoint(run_id)
    assert paused.state == "paused"
    assert paused.failures[-1].code == "COLLECTION_CANCELLED"
    resumed = await collector.resume(paused.run_id)
    assert resumed.state == "completed"
    assert adapter.discovery_calls == 1


@pytest.mark.asyncio
async def test_market_lineage_failure_keeps_the_raw_capture_as_diagnostic(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = WrongLineageAdapter()
    result = await BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0)

    assert result.state == "failed"
    assert result.failures[0].code == "CAPTURE_LINEAGE_MISMATCH"
    assert len(result.diagnostic_observation_ids) == 1
    row = store.observation(result.diagnostic_observation_ids[0])
    assert row is not None
    assert row["raw"]["raw_sha256"] == adapter.market_capture.raw_sha256
    assert row["normalized"]["error_code"] == "CAPTURE_LINEAGE_MISMATCH"


@pytest.mark.asyncio
async def test_book_depth_violation_is_rejected_with_raw_evidence(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = OversizedBookAdapter()
    result = await BoundedSourceCollector(adapter, store).start(
        market_limit=1, book_limit=1, book_depth=1
    )

    assert result.state == "partial"
    assert result.book_count == 0
    assert result.failed_book_count == 1
    assert result.failures[-1].code == "BOOK_DEPTH_EXCEEDED"
    assert len(result.diagnostic_observation_ids) == 1
    diagnostic = store.observation(result.diagnostic_observation_ids[0])
    assert diagnostic is not None
    assert diagnostic["normalized"]["error_code"] == "BOOK_DEPTH_EXCEEDED"


@pytest.mark.asyncio
async def test_oversized_store_row_is_terminal_partial_and_remains_checkpointed(tmp_path):
    class OversizedMarketAdapter(FakeAdapter):
        async def discover_markets(self, limit: int = 20):
            markets = await super().discover_markets(limit)
            payload = markets[0].model_dump(mode="python")
            payload["description"] = "x" * 600_000
            return (type(markets[0]).model_validate(payload),)

    store = FrontierStore(tmp_path / "frontier")
    adapter = OversizedMarketAdapter()
    collector = BoundedSourceCollector(adapter, store)
    result = await collector.start(market_limit=1, book_limit=0)

    assert result.state == "partial"
    assert result.failures[-1].code == "COLLECTION_ROW_LIMIT"
    assert result.pending_observation_count == 1
    assert store.summary()["observations"] == 0
    resumed = await collector.resume(result.run_id)
    assert resumed == result
