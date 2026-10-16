from __future__ import annotations

import hashlib
import json

import pytest
from midas.arena.jobs import JobSpec
from midas.veritas.arena_qualification import VeritasQualificationSpec, run_qualification
from midas.veritas.continuous_analysis import VERSION


def _event(scan_id: str, captured_ns: int) -> dict:
    event = {
        "analysis_version": VERSION,
        "scan_id": scan_id,
        "snapshot_file": f"snapshots/{scan_id}.json.gz",
        "snapshot_evidence_sha256": f"evidence-{scan_id}",
        "snapshot_source_code_sha256": f"scanner-{scan_id}",
        "captured_ns": captured_ns,
        "captured_at_utc": "2026-10-15T06:00:00+00:00",
        "attempted_market_pairs": 2,
        "valid_quality_pairs": 1,
        "positive_top_gross_pairs": 0,
        "counts": {
            "positive_full_depth_gross_by_quantity": {"20": 0},
            "positive_minimum_notional_by_quantity": {"20": 0},
            "positive_single_match_fee_sensitivity_by_quantity": {"20": 0},
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {"20": 0},
        },
        "market_rows": [
            {
                "market_id": f"market-{scan_id}",
                "valid": True,
                "top_pair_gross_edge_per_share": "-0.01",
            }
        ],
    }
    event["analysis_event_sha256"] = hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return event


def test_arena_qualification_is_bounded_pinned_idempotent_and_source_read_only(tmp_path):
    first_id = "scan-20261015T090047Z-6f98ffeaecab"
    latest_id = "scan-20261015T093047Z-9c98ffeaecab"
    source_root = tmp_path / "veritas"
    event_dir = source_root / "analysis-events" / "v4"
    event_dir.mkdir(parents=True)
    older = _event(first_id, 1_800_000_000_000_000_000)
    latest = _event(latest_id, 1_800_001_800_000_000_000)
    (event_dir / f"{first_id}.json").write_text(json.dumps(older))
    (event_dir / f"{latest_id}.json").write_text(json.dumps(latest))
    source_before = {path.name: path.read_bytes() for path in event_dir.iterdir()}
    spec = VeritasQualificationSpec(expected_latest_scan_id=latest_id)
    job_spec = JobSpec(kind="veritas_qualification", veritas_qualification=spec)
    assert job_spec.veritas_qualification == spec

    first = run_qualification(tmp_path / "arena", spec, source_root=source_root)
    second = run_qualification(tmp_path / "arena", spec, source_root=source_root)

    assert first["artifact_id"] == second["artifact_id"]
    assert first["experiment_sha256"] == second["experiment_sha256"]
    assert first["expected_latest_scan_id"] == latest_id
    assert first["source_event_count"] == 2
    assert first["result"]["sample"]["snapshot_count"] == 2
    assert first["orders_submitted"] is False
    assert {path.name: path.read_bytes() for path in event_dir.iterdir()} == source_before


def test_arena_qualification_rejects_missing_scan_and_source_byte_overrun(tmp_path):
    first_id = "scan-20261015T090047Z-6f98ffeaecab"
    source_root = tmp_path / "veritas"
    event_dir = source_root / "analysis-events" / "v4"
    event_dir.mkdir(parents=True)
    (event_dir / f"{first_id}.json").write_text(
        json.dumps(_event(first_id, 1_800_000_000_000_000_000))
    )

    with pytest.raises(ValueError, match="not indexed"):
        run_qualification(
            tmp_path / "arena",
            VeritasQualificationSpec(expected_latest_scan_id="scan-20261015T093047Z-9c98ffeaecab"),
            source_root=source_root,
        )

    with pytest.raises(ValueError, match="source-byte bound"):
        run_qualification(
            tmp_path / "arena",
            VeritasQualificationSpec(expected_latest_scan_id=first_id, max_source_bytes=1),
            source_root=source_root,
        )
