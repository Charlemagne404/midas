"""Interface reads are bounded and cannot gain writer or arbitrary command authority."""

import hashlib
import json
import sqlite3
import struct
import subprocess
import time
import zlib
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.reality.storage import MAGIC

from apps.api.reality import (
    classify_capacity_freshness,
    classify_collector_health,
    router,
    source_quality_report,
)


def test_capacity_report_freshness_uses_two_timer_intervals_and_fails_closed():
    now_ns = 10_000_000_000_000
    assert classify_capacity_freshness({"measured_ns": now_ns}, now_ns)["state"] == "fresh"
    assert (
        classify_capacity_freshness({"measured_ns": now_ns - 3600 * 10**9}, now_ns)["state"]
        == "fresh"
    )
    assert (
        classify_capacity_freshness({"measured_ns": now_ns - 3601 * 10**9}, now_ns)["state"]
        == "stale"
    )
    assert (
        classify_capacity_freshness({"measured_ns": now_ns + 1}, now_ns)["state"]
        == "clock_uncertain"
    )
    for report in ({}, {"measured_ns": True}, {"measured_ns": 0}, {"measured_ns": "bad"}):
        assert classify_capacity_freshness(report, now_ns)["state"] == "unavailable"


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
                markets=8,
                expected_books=16,
                fresh_books=16,
                sequence_verified=False,
                gaps=0,
                book_comparisons={
                    "stable_local_lineage_divergence": 0,
                    "stable_local_lineage_match_unsequenced": 1,
                },
                last_book_comparison={
                    "response_ns": now_ns,
                    "assessment": "stable_local_lineage_match_unsequenced",
                    "raw_ordinal": 1,
                },
                recent_append_sample_count=1,
                recent_max_append_seconds=0.01,
                recent_p95_append_seconds=0.01,
                recent_max_persist_seconds=0.01,
                recent_p95_persist_seconds=0.01,
                persistence_latency_window_seconds=60,
                persistence_latency_window_covered_seconds=60,
                persistence_latency_window_complete=True,
                recovery_status="CHECKPOINT_VERIFIED",
                transport_queue_depth=0,
                transport_queue_bound=32,
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


def test_capacity_report_freshness_is_projected_without_mutating_saved_evidence(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/capacity.json"
    saved = {"measured_ns": time.time_ns() - 2 * 60 * 60 * 1_000_000_000, "alerts": []}
    path.write_text(json.dumps(saved))

    overview = c.get("/api/reality/overview").json()
    artifact = c.get("/api/reality/artifacts/capacity").json()

    assert overview["capacity"]["freshness"]["state"] == "stale"
    assert artifact["data"]["freshness"]["state"] == "stale"
    assert json.loads(path.read_text()) == saved


def test_recovered_capture_projects_last_error_as_historical(dashboard):
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
    assert result["collector"]["error"] is None
    assert "ConnectionClosedOK" in result["collector"]["last_error"]
    assert "ConnectionClosedOK" in json.loads(path.read_text())["error"]


def test_fresh_book_status_exposes_unsequenced_quality_and_unverified_latency(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data.update(
        expected_books=16,
        fresh_books=16,
        sequence_verified=False,
        max_append_seconds=1.98,
        book_comparisons={
            "stable_local_lineage_divergence": 118,
            "stable_local_lineage_match_unsequenced": 200,
        },
        gaps=10099,
        counts={
            "duplicate": 101,
            "timestamp_regression": 47,
            "snapshot_divergence": 29312,
        },
        last_book_comparison={
            "response_ns": time.time_ns(),
            "assessment": "stable_local_lineage_match_unsequenced",
            "raw_ordinal": 10100,
        },
    )
    for key in (
        "recent_append_sample_count",
        "recent_max_append_seconds",
        "recent_p95_append_seconds",
        "recent_max_persist_seconds",
        "recent_p95_persist_seconds",
        "persistence_latency_window_seconds",
        "persistence_latency_window_covered_seconds",
        "persistence_latency_window_complete",
        "recovery_status",
        "transport_queue_depth",
    ):
        data.pop(key, None)
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["capture_health"] == "recording"
    assert result["health"] == "degraded"
    assert result["health_reasons"] == [
        "recent_persistence_window_incomplete",
        "recovery_state_unreported",
        "transport_queue_depth_unreported",
    ]
    quality = result["source_quality"]
    assert quality["book_coverage"] == {
        "state": "complete_current_books",
        "expected": 16,
        "fresh": 16,
        "missing": 0,
    }
    assert quality["sequence_state"] == "unsequenced"
    assert quality["secondary_comparison"]["state"] == "fresh"
    assert (
        quality["secondary_comparison"]["assessment_count_scope"]
        == "current_collector_process; full archive totals require a durable-history audit"
    )
    assert quality["secondary_comparison"]["raw_body_reference"] == (
        "independent_book_record_at_raw_ordinal"
    )
    assert quality["lineage"]["stable_local_divergences"] == 118
    assert quality["lineage"]["stable_divergence_count_scope"] == "current_collector_process"
    assert quality["lineage"]["latest_assessment"] == "stable_local_lineage_match_unsequenced"
    assert quality["recorded_gaps"]["count"] == 10099
    assert quality["event_integrity_signals"]["duplicate_event_hashes_recent_window"] == 101
    assert quality["event_integrity_signals"]["duplicate_window_capacity"] == 4096
    assert quality["event_integrity_signals"]["timestamp_regressions"] == 47
    assert quality["event_integrity_signals"]["count_scope"] == (
        "current_collector_process; counters reset when the collector starts"
    )
    assert (
        "raw records remain stored"
        in quality["event_integrity_signals"]["interpretations"][
            "duplicate_event_hashes_recent_window"
        ]
    )
    assert (
        "does not prove local event loss"
        in quality["event_integrity_signals"]["interpretations"]["snapshot_divergences"]
    )
    assert quality["persistence"]["state"] == "recent_window_unavailable"
    assert quality["persistence"]["lifetime_max_exceeded_threshold"] is True
    assert quality["recovery_state"] == "not_reported"
    assert quality["status"] == "incomplete_observability"
    assert "historical_lineage_divergences_exist" in quality["known_limitations"]
    assert "snapshot_reconstruction_differences_observed" in quality["known_limitations"]
    assert (
        "does not prove local event loss"
        in quality["event_integrity_signals"]["interpretations"]["snapshot_divergences"]
    )
    assert "transport_queue_depth_unreported" in quality["observability_gaps"]


def test_source_quality_handles_missing_and_malformed_legacy_metrics(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data.update(
        markets=8,
        fresh_books=20,
        gaps="unknown",
        counts={"duplicate": "unknown"},
        book_comparisons={"stable_local_lineage_divergence": "unknown"},
    )
    path.write_text(json.dumps(data))

    quality = c.get("/api/reality/overview").json()["source_quality"]

    assert quality["book_coverage"]["state"] == "inconsistent_current_books"
    assert quality["recorded_gaps"]["count"] is None
    assert quality["lineage"]["stable_local_divergences"] is None
    assert quality["event_integrity_signals"]["duplicate_event_hashes_recent_window"] is None


def test_queue_saturation_degrades_health_but_unavailable_depth_stays_unknown(dashboard):
    _client, root, _ = dashboard
    now_ns = time.time_ns()
    saturated = {
        "state": "RECORDING_UNSEQUENCED",
        "updated_ns": now_ns,
        "last_observation_ns": now_ns,
        "config": {"stale_seconds": 60},
        "expected_books": 2,
        "fresh_books": 2,
        "sequence_verified": False,
        "backpressure_active": False,
        "transport_queue_observation_available": True,
        "transport_queue_depth": 32,
        "transport_queue_bound": 32,
        "transport_queue_saturated": True,
        "recovery": {"state": "verified"},
    }
    health, reasons = classify_collector_health(saturated, now_ns)
    quality = source_quality_report(saturated, now_ns)
    assert health == "degraded"
    assert reasons == ["transport_queue_saturated"]
    assert "transport_queue_saturated" in quality["current_issues"]
    assert quality["transport_queue"]["depth"] == 32
    assert quality["transport_queue"]["saturated"] is True

    unavailable = dict(saturated)
    unavailable.update(
        transport_queue_observation_available=False,
        transport_queue_depth=None,
        transport_queue_saturated=False,
    )
    health, reasons = classify_collector_health(unavailable, now_ns)
    quality = source_quality_report(unavailable, now_ns)
    assert health == "recording"
    assert reasons == []
    assert "transport_queue_depth_unreported" in quality["observability_gaps"]
    assert quality["transport_queue"]["observation_available"] is False


def test_recent_persistence_window_is_reported_with_its_coverage(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data.update(
        backpressure_active=False,
        recent_append_sample_count=12,
        recent_max_append_seconds=0.8,
        recent_p95_append_seconds=0.2,
        recent_max_persist_seconds=0.7,
        recent_p95_persist_seconds=0.15,
        persistence_latency_window_seconds=60,
        persistence_latency_window_covered_seconds=20,
        persistence_latency_window_complete=False,
    )
    path.write_text(json.dumps(data))

    quality = c.get("/api/reality/overview").json()["source_quality"]["persistence"]

    assert quality["state"] == "partial_recent_window"
    assert quality["recent_sample_count"] == 12
    assert quality["recent_max_append_seconds"] == 0.8
    assert quality["recent_p95_append_seconds"] == 0.2
    assert quality["recent_max_persist_seconds"] == 0.7
    assert quality["recent_window_covered_seconds"] == 20
    assert quality["recent_window_complete"] is False


def test_stale_secondary_comparison_degrades_health_without_reviving_old_error(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data.update(
        expected_books=16,
        fresh_books=16,
        sequence_verified=False,
        error="ConnectionClosedOK: previous server shutdown",
        last_book_comparison={
            "response_ns": time.time_ns() - 31_000_000_000,
            "assessment": "stable_local_lineage_match_unsequenced",
        },
    )
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["capture_health"] == "recording"
    assert result["health"] == "degraded"
    assert result["health_reasons"] == ["secondary_comparison_stale"]
    assert result["source_quality"]["status"] == "degraded"
    assert result["collector"]["error"] is None
    assert "ConnectionClosedOK" in result["collector"]["last_error"]


def test_current_stable_lineage_divergence_degrades_source_quality(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data.update(
        expected_books=16,
        fresh_books=16,
        sequence_verified=False,
        book_comparisons={"stable_local_lineage_divergence": 118},
        last_book_comparison={
            "response_ns": time.time_ns(),
            "assessment": "stable_local_lineage_divergence",
        },
    )
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["health"] == "degraded"
    assert result["health_reasons"] == ["current_lineage_divergence"]
    assert result["source_quality"]["status"] == "degraded"


def test_websocket_subscription_wait_is_reported_as_a_transition(dashboard):
    c, root, _ = dashboard
    path = root / "data/recordings/reality/status.json"
    data = json.loads(path.read_text())
    data["state"] = "AWAITING_DATA"
    data["updated_ns"] = time.time_ns()
    data["last_observation_ns"] = time.time_ns() - 1_000_000_000
    path.write_text(json.dumps(data))

    result = c.get("/api/reality/overview").json()

    assert result["health"] == "degraded"
    assert result["health_reasons"] == ["collector_state"]
    assert result["collector"]["state"] == "AWAITING_DATA"


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


def test_operations_expose_failed_analysis_and_timer_diagnostics_read_only(dashboard, monkeypatch):
    c, _, _ = dashboard

    def show_unit(args, **_kwargs):
        unit = args[3]
        output = "ActiveState=failed\nSubState=failed\nNRestarts=0\n"
        if unit == "midas-veritas-source-analysis.service":
            output += "Result=oom-kill\nExecMainStatus=9\nExecMainExitTimestamp=Thu 2026-11-05 17:41:16 CET\n"
        if unit == "midas-reality-capacity.service":
            output += "Result=timeout\nExecMainStatus=0\n"
        if unit == "midas-veritas-source-analysis.timer":
            output += "LastTriggerUSec=Thu 2026-11-05 17:30:00 CET\nNextElapseUSecRealtime=Thu 2026-11-05 18:00:00 CET\n"
        return Mock(returncode=0, stdout=output, stderr="")

    run = Mock(side_effect=show_unit)
    monkeypatch.setattr("apps.api.reality.subprocess.run", run)

    services = c.get("/api/reality/operations").json()["services"]
    by_unit = {service["unit"]: service for service in services}

    assert by_unit["midas-veritas-source-analysis.service"]["properties"]["Result"] == "oom-kill"
    assert by_unit["midas-reality-capacity.service"]["properties"]["Result"] == "timeout"
    assert by_unit["midas-veritas-source-analysis.timer"]["properties"]["LastTriggerUSec"]
    assert all(call.args[0][0:3] == ["systemctl", "--user", "show"] for call in run.call_args_list)


def test_operations_report_systemd_query_timeout_without_failing_endpoint(dashboard, monkeypatch):
    c, _, _ = dashboard
    unit = "midas-veritas-source-analysis.service"

    def show_unit(args, **_kwargs):
        if args[3] == unit:
            raise subprocess.TimeoutExpired(args, 2)
        return Mock(returncode=0, stdout="ActiveState=active\n", stderr="")

    monkeypatch.setattr("apps.api.reality.subprocess.run", show_unit)
    services = c.get("/api/reality/operations").json()["services"]
    service = next(item for item in services if item["unit"] == unit)
    assert service["available"] is False
    assert service["error"] == "systemd_query_timeout"
    assert service["properties"] == {}
