from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.models import Venue

from apps.api.config import Settings
from apps.api.frontier import router as frontier_router
from apps.api.main import create_app


def test_kalshi_and_kraken_live_capture_require_recorded_permission_references(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'midas.db'}",
        frontier_root=tmp_path / "frontier",
        arena_root=tmp_path / "arena",
        frontier_kalshi_public_probe_enabled=True,
        frontier_kraken_public_probe_enabled=True,
    )
    assert settings.frontier_kalshi_probe_allowed is False
    assert settings.frontier_kraken_probe_allowed is False

    app = create_app(settings)
    try:
        api = FastAPI()
        api.include_router(frontier_router(app.state.frontier_store, app.state.frontier_registry))
        with TestClient(api) as client:
            sources = client.get("/api/frontier/sources")
            assert sources.status_code == 200
            source_by_venue = {item["venue"]: item for item in sources.json()["items"]}
            for venue in (Venue.KALSHI, Venue.KRAKEN):
                item = source_by_venue[venue.value]
                assert item["public_probe_enabled"] is False
                assert item["probe_policy_block_reason"]
                assert item["probe_policy_block_reason"] in item["health"]["notes"]
                response = client.post(f"/api/frontier/probe/{venue.value}", json={})
                assert response.status_code == 409
                assert response.json()["detail"] == item["probe_policy_block_reason"]
                assert app.state.frontier_registry.get(venue).transport.request_count == 0
            readiness = client.get("/api/frontier/readiness")
            assert readiness.status_code == 200
            permission_gate = next(
                gate
                for gate in readiness.json()["gates"]
                if gate["name"] == "source_data_use_permissions"
            )
            assert permission_gate["state"] == "BLOCKED"

        for venue in (Venue.KALSHI, Venue.KRAKEN):
            config = app.state.frontier_registry.get(venue).config
            assert config.enabled is False
            assert config.live_public_probe_enabled is False
            assert config.probe_policy_block_reason
    finally:
        asyncio.run(app.state.frontier_registry.aclose())


def test_permission_references_do_not_enable_sources_unless_probe_is_requested():
    settings = Settings(
        _env_file=None,
        frontier_kalshi_research_authorization_ref="source-approval-record-1",
        frontier_kraken_market_data_permission_ref="terms-review-record-1",
    )
    assert settings.frontier_kalshi_probe_allowed is False
    assert settings.frontier_kraken_probe_allowed is False

    requested = Settings(
        _env_file=None,
        frontier_kalshi_public_probe_enabled=True,
        frontier_kalshi_research_authorization_ref="source-approval-record-1",
        frontier_kraken_public_probe_enabled=True,
        frontier_kraken_market_data_permission_ref="terms-review-record-1",
    )
    assert requested.frontier_kalshi_probe_allowed is True
    assert requested.frontier_kraken_probe_allowed is True
