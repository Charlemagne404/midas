from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.registry import default_registry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import router

CAPTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "data/frontier-live-evidence-polymarket-20261028T170445Z"
)


def test_saved_polymarket_capture_is_read_only_and_hypothesis_labeled(tmp_path: Path) -> None:
    source_database = CAPTURE_ROOT / "research-store/frontier.sqlite3"
    copied_root = tmp_path / "frontier-store"
    copied_root.mkdir()
    shutil.copyfile(source_database, copied_root / "frontier.sqlite3")

    capture = json.loads((CAPTURE_ROOT / "live_event_group_observation.json").read_text())
    store = FrontierStore(copied_root, max_bytes=4 * 1024 * 1024)
    app = FastAPI()
    app.include_router(router(store, default_registry()))

    with TestClient(app) as client:
        overview = client.get("/api/frontier/overview")
        markets = client.get("/api/frontier/markets?limit=10")
        books = client.get("/api/frontier/books?limit=10")
        relationships = client.get("/api/frontier/relationships?limit=50")
        graph = client.get(
            "/api/frontier/graph",
            params={"center_market_id": "polymarket:2589810", "depth": 1, "limit": 20},
        )
        evidence = client.get(f"/api/frontier/observations/{capture['store_observation_id']}")

    assert overview.status_code == 200
    assert overview.json()["network_called_by_this_request"] is False
    assert overview.json()["summary"]["observations"] == 3

    market_result = markets.json()
    assert markets.status_code == 200
    assert market_result["source_state"] == "recorded observations only"
    assert {item["native_market_id"] for item in market_result["items"]} == {
        "2589810",
        "2589811",
        "2589812",
        "2589813",
        "2589814",
    }
    assert all(item["payoff"]["verified"] is False for item in market_result["items"])
    assert all(item["payoff"]["exhaustive"] is False for item in market_result["items"])
    assert all(item["resolution"]["verified"] is False for item in market_result["items"])

    assert books.status_code == 200
    assert len(books.json()["items"]) == 1

    relationship_result = relationships.json()
    assert relationships.status_code == 200
    assert len(relationship_result["items"]) == 10
    assert {item["state"] for item in relationship_result["items"]} == {"hypothesis"}

    graph_result = graph.json()
    assert graph.status_code == 200
    assert len(graph_result["edges"]) == 4
    assert all(edge["state"] == "hypothesis" for edge in graph_result["edges"])

    assert evidence.status_code == 200
    assert evidence.json()["observation_id"] == capture["store_observation_id"]
    assert evidence.json()["raw_sha256"] == capture["raw_sha256"]
    assert evidence.json()["row_sha256"] == capture["store_row_sha256"]
