from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.collection import CollectionJournal
from midas.frontier.models import AdapterConfig
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.test_collection import FakeAdapter


def test_finite_collection_api_persists_one_bounded_fixture_run(tmp_path):
    adapter = FakeAdapter()
    store = FrontierStore(tmp_path / "frontier")
    arena_root = tmp_path / "arena"
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,)), arena_root=arena_root))
    client = TestClient(app)
    try:
        invalid = client.post(
            "/api/frontier/collect/polymarket",
            json={"market_limit": 6, "book_limit": 1},
        )
        assert invalid.status_code == 422
        assert adapter.discovery_calls == 0
        assert not CollectionJournal(store.root).path.exists()

        response = client.post(
            "/api/frontier/collect/polymarket",
            json={
                "market_limit": 1,
                "book_limit": 1,
                "book_depth": 3,
                "max_wall_seconds": 10,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        run = payload["collection_run"]
        assert run["state"] == "completed"
        assert run["market_count"] == 1
        assert run["book_count"] == 1
        assert run["research_only"] is True
        assert run["live_orders"] is False
        assert payload["adapter_request_count"] == 2
        assert payload["adapter_request_upper_bound"] == 4
        assert payload["research_only"] is True
        assert payload["live_orders"] is False
        assert payload["source_health_scope"] == "adapter_local_checkpoint"
        assert adapter.discovery_calls == 1
        assert len(adapter.book_calls) == 1
        assert len(store.observations(venue="polymarket")) == 2

        journal = CollectionJournal(store.root)
        spec = journal.run_spec(run["run_id"])
        checkpoints = journal.checkpoints(run["run_id"])
        assert spec.market_limit == 1
        assert spec.book_limit == 1
        assert checkpoints[-1].state == "completed"
        assert not arena_root.exists()
    finally:
        client.close()


def test_finite_collection_api_rejects_disabled_and_held_sources_before_journal_or_request(
    tmp_path,
):
    disabled = FakeAdapter(enabled=False)
    disabled_store = FrontierStore(tmp_path / "disabled-frontier")
    disabled_app = FastAPI()
    disabled_app.include_router(router(disabled_store, AdapterRegistry((disabled,))))
    disabled_client = TestClient(disabled_app)
    try:
        response = disabled_client.post(
            "/api/frontier/collect/polymarket", json={"market_limit": 1}
        )
        assert response.status_code == 409
        assert disabled.discovery_calls == 0
        assert not CollectionJournal(disabled_store.root).path.exists()
    finally:
        disabled_client.close()

    held = FakeAdapter()
    held.config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        probe_policy_block_reason="Fixture source-use hold",
    )
    held_store = FrontierStore(tmp_path / "held-frontier")
    held_app = FastAPI()
    held_app.include_router(router(held_store, AdapterRegistry((held,))))
    held_client = TestClient(held_app)
    try:
        response = held_client.post("/api/frontier/collect/polymarket", json={"market_limit": 1})
        assert response.status_code == 409
        assert response.json()["detail"] == "Fixture source-use hold"
        assert held.discovery_calls == 0
        assert not CollectionJournal(held_store.root).path.exists()
    finally:
        held_client.close()
