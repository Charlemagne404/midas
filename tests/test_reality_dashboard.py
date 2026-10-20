"""Interface reads are bounded and cannot gain writer or arbitrary command authority."""

import hashlib
import json
import sqlite3
import struct
import time
import zlib
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.reality.storage import MAGIC

from apps.api.reality import router


@pytest.fixture
def dashboard(tmp_path):
    raw = tmp_path / "data/recordings/reality"
    raw.mkdir(parents=True)
    now_ns = time.time_ns()
    (raw / "status.json").write_text(
        json.dumps(
            dict(
                state="RECORDING_UNSEQUENCED",
                updated_ns=now_ns,
                last_observation_ns=now_ns,
                config={"stale_seconds": 60},
                backpressure_active=False,
                failures=0,
                books={},
                selection_audit={"large": "excluded"},
                ordinal=42,
            )
        )
    )
    forward = tmp_path / "data/research/reality/forward/mission2"
    forward.mkdir(parents=True)
    db = sqlite3.connect(forward / "shadow.sqlite")
    db.executescript("""create table events(seq integer primary key,body blob);
    create table decisions(id text,ns integer,condition text,event_seq integer,commit_ns integer);
    create table outcomes(decision_id text,horizon integer,event_seq integer);
    create table observations(ns integer,condition text,event_seq integer);""")
    uid = "a" * 64
    row = dict(
        decision_ns=100,
        market_title="Fixture only",
        condition="condition",
        baseline=dict(
            acquisition={"yes": {"value": "2"}, "no": {"value": "3"}},
            opportunity=False,
            views={"large": "not in list"},
        ),
        quality_reason=None,
        policies=[],
        decision_ordinal=42,
    )
    db.execute("insert into events values(1,?)", (zlib.compress(json.dumps(row).encode()),))
    db.execute("insert into decisions values(?,100,?,1,110)", (uid, "condition"))
    for i in range(2, 5):
        db.execute(
            "insert into events values(?,?)",
            (i, zlib.compress(json.dumps({"ns": i, "quality_reason": "stale_book"}).encode())),
        )
        db.execute("insert into observations values(?,?,?)", (i, "condition", i))
    db.commit()
    db.close()
    app = FastAPI()
    app.include_router(router(tmp_path))
    return TestClient(app), tmp_path, uid


def test_missing_evidence_is_explicit(tmp_path):
    app = FastAPI()
    app.include_router(router(tmp_path))
    c = TestClient(app)
    assert c.get("/api/reality/overview").json()["health"] == "unavailable"
    assert c.get("/api/reality/decisions").status_code == 404
    assert c.get("/api/reality/artifacts/training").status_code == 404


def test_stale_status_not_reported_as_healthy(dashboard):
    c, root, _ = dashboard
    assert c.get("/api/reality/overview").json()["health"] == "recording"
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data["updated_ns"] = time.time_ns() - 40_000_000_000
    path.write_text(json.dumps(data))
    r = c.get("/api/reality/overview").json()
    assert r["health"] == "degraded"
    assert r["health_reasons"] == ["status_stale"]
    assert "selection_audit" not in r["collector"]


def test_recovered_capture_does_not_remain_degraded_for_lifetime_failures(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data["failures"] = 1
    data["error"] = "ConnectionClosedOK: received 1001 (going away) server shutting down"
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["health"] == "recording"
    assert result["health_reasons"] == []
    assert result["collector"]["failures"] == 1
    assert "ConnectionClosedOK" in result["collector"]["error"]


def test_fresh_status_with_stale_observations_is_degraded(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data["last_observation_ns"] = time.time_ns() - 61_000_000_000
    data["updated_ns"] = time.time_ns()
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["health"] == "degraded"
    assert result["health_reasons"] == ["observations_stale"]


def test_backpressure_is_reported_as_degraded(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data["backpressure_active"] = True
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["health"] == "degraded"
    assert result["health_reasons"] == ["backpressured"]


def test_index_bounds_and_exact_decision_evidence(dashboard):
    c, _, uid = dashboard
    r = c.get("/api/reality/decisions?limit=1").json()["rows"][0]
    assert r["market_title"] == "Fixture only" and "views" not in r["baseline"]
    assert c.get(f"/api/reality/decisions/{uid}").json()["decision"]["baseline"]["views"]
    assert c.get("/api/reality/decisions/invalid").status_code == 422
    assert c.get("/api/reality/decisions?limit=101").status_code == 422
    assert c.get("/api/reality/decisions?before_ns=100").json()["rows"] == []
    r = c.get("/api/reality/history?condition=condition&start_ns=0&end_ns=10&limit=2").json()
    assert len(r["rows"]) == 2 and r["truncated"]
    assert all(x["quality_reason"] == "stale_book" for x in r["rows"])
    assert (
        c.get(
            "/api/reality/history?condition=condition&start_ns=0&end_ns=86400000000001"
        ).status_code
        == 422
    )
    assert c.get("/api/reality/history?condition=condition&start_ns=10&end_ns=1").status_code == 422
    assert c.get("/api/reality/artifacts/unknown").status_code == 404


def test_raw_input_offsets_hashes_and_traversal(dashboard):
    c, root, _ = dashboard
    segment = "00000000000000000042-" + "a" * 32 + ".seg"
    body = json.dumps({"ordinal": 42, "payload": {"observed": "fixture"}, "kind": "frame"}).encode()
    compressed = zlib.compress(body)
    path = root / "data/recordings/reality" / segment
    path.write_bytes(
        MAGIC
        + struct.pack(">I", len(compressed))
        + hashlib.sha256(compressed).digest()
        + compressed
    )
    url = f"/api/reality/records/42?segment={segment}&offset=8"
    # Shadow references retain the eventual .seg identity while the writer still owns .open.
    active = path.with_suffix(".open")
    path.rename(active)
    r = c.get(url)
    assert r.status_code == 200 and r.json()["segment"].endswith(".open")
    active.rename(path)
    assert c.get(url.replace(".seg&offset", ".open&offset")).status_code == 200
    assert r.json()["canonical_record_sha256"] == hashlib.sha256(body).hexdigest()
    assert c.get(url.replace("/42?", "/43?")).status_code == 409
    assert c.get("/api/reality/records/42?segment=../../status.json&offset=8").status_code == 422
    path.write_bytes(path.read_bytes()[:-1] + b"x")
    assert c.get(url).status_code == 409


def test_operations_no_arbitrary_command_or_cross_origin(dashboard, monkeypatch):
    c, root, _ = dashboard
    run = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("apps.api.reality.subprocess.run", run)
    assert c.post("/api/reality/operations/check-capacity").status_code == 403
    assert (
        c.post(
            "/api/reality/operations/check-capacity", headers={"Origin": "https://elsewhere.test"}
        ).status_code
        == 403
    )
    assert (
        c.post(
            "/api/reality/operations/restart-collector", headers={"Origin": "http://testserver"}
        ).status_code
        == 422
    )
    run.assert_not_called()
    assert (
        c.post(
            "/api/reality/operations/check-capacity", headers={"Origin": "http://testserver"}
        ).status_code
        == 200
    )
    assert run.call_args.args[0] == [
        "systemctl",
        "--user",
        "start",
        "--no-block",
        "midas-reality-capacity.service",
    ]
    assert json.loads((root / "data/research/reality/interface/operations.jsonl").read_text())[
        "accepted"
    ]
