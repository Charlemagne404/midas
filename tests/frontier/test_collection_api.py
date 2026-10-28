from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.collection import (
    CollectionCheckpoint,
    CollectionJournal,
    CollectionRunSpec,
    capability_manifest_sha256,
)
from midas.frontier.models import AdapterConfig
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router
from tests.frontier.builders import T0
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
        assert payload["adapter_request_upper_bound_per_attempt"] == 4
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

        history = client.get("/api/frontier/collection-runs?limit=20")
        assert history.status_code == 200, history.text
        assert history.json()["network_called"] is False
        assert history.json()["items"][0]["run_id"] == run["run_id"]
        assert history.json()["items"][0]["checkpoint_sha256"]
        assert history.json()["items"][0]["state"] == "completed"
        assert history.json()["items"][0]["resumable"] is False
        assert history.json()["items"][0]["resume_block_reason"] == "Collection run is terminal."

        request_count_before_terminal_resume = adapter.transport.request_count
        terminal_resume = client.post(f"/api/frontier/collect/polymarket/{run['run_id']}/resume")
        assert terminal_resume.status_code == 200, terminal_resume.text
        assert terminal_resume.json()["collection_run"]["state"] == "completed"
        assert adapter.transport.request_count == request_count_before_terminal_resume
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
        empty_runs = disabled_client.get("/api/frontier/collection-runs")
        assert empty_runs.status_code == 200
        assert empty_runs.json()["items"] == []
        assert empty_runs.json()["network_called"] is False
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


def test_finite_collection_api_resumes_one_paused_checkpointed_run(tmp_path):
    adapter = FakeAdapter()
    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    spec = CollectionRunSpec(
        run_id="3ec62758-5272-4b47-bf26-0acb72d1773c",
        venue=adapter.venue,
        adapter_version=adapter.capabilities.adapter_version,
        capability_manifest_sha256=capability_manifest_sha256(adapter.capabilities),
        adapter_config=adapter.config,
        market_limit=1,
        book_limit=1,
        book_depth=3,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(spec)
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=spec.run_id,
            sequence=0,
            updated_at_utc=T0,
            state="paused",
        )
    )
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,))))
    client = TestClient(app)
    try:
        history = client.get("/api/frontier/collection-runs")
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["state"] == "paused"
        assert history.json()["items"][0]["resumable"] is True
        assert history.json()["items"][0]["resume_block_reason"] is None
        assert adapter.transport.request_count == 0

        response = client.post(f"/api/frontier/collect/polymarket/{spec.run_id}/resume")
        assert response.status_code == 200, response.text
        run = response.json()["collection_run"]
        assert run["state"] == "completed"
        assert run["market_count"] == 1
        assert run["book_count"] == 1
        assert adapter.transport.request_count == 2
        assert response.json()["adapter_request_upper_bound_per_attempt"] == 4
        assert journal.latest_checkpoint(spec.run_id).state == "completed"

        updated_history = client.get("/api/frontier/collection-runs")
        assert updated_history.json()["items"][0]["state"] == "completed"
        assert updated_history.json()["items"][0]["resumable"] is False
    finally:
        client.close()


def test_collection_api_rejects_resume_when_capability_manifest_changed(tmp_path):
    adapter = FakeAdapter()
    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    spec = CollectionRunSpec(
        run_id="402628e3-6b7c-480e-8096-37e1ff8646f8",
        venue=adapter.venue,
        adapter_version=adapter.capabilities.adapter_version,
        capability_manifest_sha256=capability_manifest_sha256(adapter.capabilities),
        adapter_config=adapter.config,
        market_limit=1,
        book_limit=1,
        book_depth=3,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(spec)
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=spec.run_id,
            sequence=0,
            updated_at_utc=T0,
            state="paused",
        )
    )
    declaration = adapter.capabilities.declarations[0]
    adapter.capabilities = adapter.capabilities.model_copy(
        update={
            "declarations": (
                declaration.model_copy(update={"reason": "Changed fixture contract"}),
                *adapter.capabilities.declarations[1:],
            )
        }
    )
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,))))
    client = TestClient(app)
    try:
        history = client.get("/api/frontier/collection-runs")
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["resumable"] is False
        assert history.json()["items"][0]["resume_block_reason"] == (
            "Current capability manifest differs from the pinned run."
        )

        response = client.post(f"/api/frontier/collect/polymarket/{spec.run_id}/resume")
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "Collection capability manifest differs from the pinned run"
        )
        assert adapter.transport.request_count == 0
    finally:
        client.close()


def test_collection_run_history_filters_a_source_that_is_now_held(tmp_path):
    adapter = FakeAdapter()
    store = FrontierStore(tmp_path / "frontier")
    journal = CollectionJournal(store.root)
    spec = CollectionRunSpec(
        run_id="cbceae27-a5f6-441e-a648-01c88c908134",
        venue=adapter.venue,
        adapter_version=adapter.capabilities.adapter_version,
        capability_manifest_sha256=capability_manifest_sha256(adapter.capabilities),
        adapter_config=adapter.config,
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(spec)
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=spec.run_id,
            sequence=0,
            updated_at_utc=T0,
            state="paused",
        )
    )
    adapter.config = AdapterConfig(
        enabled=True,
        live_public_probe_enabled=True,
        probe_policy_block_reason="Fixture source-use hold",
    )
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry((adapter,))))
    client = TestClient(app)
    try:
        response = client.get("/api/frontier/collection-runs")
        assert response.status_code == 200, response.text
        assert response.json()["items"] == []
        assert response.json()["network_called"] is False
        assert adapter.transport.request_count == 0
    finally:
        client.close()


def test_source_routes_report_an_unregistered_adapter_before_journal_access(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    app = FastAPI()
    app.include_router(router(store, AdapterRegistry(())))
    client = TestClient(app)
    run_id = "196bf42b-6483-49df-8f2c-844a5875c17f"
    try:
        start = client.post(
            "/api/frontier/collect/polymarket",
            json={"market_limit": 1},
        )
        resume = client.post(f"/api/frontier/collect/polymarket/{run_id}/resume")
        probe = client.post("/api/frontier/probe/polymarket", json={"limit": 1})
        for response in (start, resume, probe):
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == (
                "The polymarket source adapter is not registered."
            )
        assert not CollectionJournal(store.root).path.exists()
    finally:
        client.close()
