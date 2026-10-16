from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from midas.veritas.coverage_pilot import (
    MAX_STUDY_SCANS,
    STUDY_ID,
    VERSION,
    _canonical,
    build_plan,
    record_coverage_pilot,
)
from midas.veritas.coverage_pilot_v2 import (
    STUDY_ID as STUDY_ID_V2,
)
from midas.veritas.coverage_pilot_v2 import (
    VERSION as VERSION_V2,
)
from midas.veritas.coverage_pilot_v2 import (
    build_plan as build_plan_v2,
)
from midas.veritas.coverage_pilot_v2 import (
    record_coverage_pilot_v2,
)


def _write_scan(root: Path, index: int, captured: datetime) -> dict:
    scan_id = f"scan-{index:03d}"
    snapshot_relative = f"snapshots/{scan_id}.json.gz"
    snapshot_path = root / snapshot_relative
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(f"immutable snapshot {scan_id}".encode())
    evidence_sha256 = f"evidence-{index}"
    selected = [
        {
            "market_id": "control-1",
            "cohort_role": "stable_random_control",
            "selection_stratum": None,
            "selection_probability": "1 conditional on frozen controls",
            "primary_category": "Politics",
        },
        {
            "market_id": "rotate-1",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "tight_le_0.01",
            "selection_probability": "0.25",
            "primary_category": "Sports",
        },
        {
            "market_id": "rotate-2",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "wide_gt_0.05",
            "selection_probability": "0.5",
            "primary_category": "Economics",
        },
    ]
    quality = [True, (index + 1) % 2 == 0, False]
    reasons = [None, None if quality[1] else "empty_ask_side", "empty_ask_side"]
    observations = [
        {
            "market_id": row["market_id"],
            "cohort_role": row["cohort_role"],
            "selection_stratum": row["selection_stratum"],
            "audit": {
                "valid": quality[position],
                "quality": {
                    "batch_atomicity_verified": position == 0,
                    "sequence_verified": position == 1,
                }
                if quality[position]
                else None,
            },
        }
        for position, row in enumerate(selected)
    ]
    analysis = {
        "analysis_version": "veritas-finalized-snapshot-analysis-v4",
        "scan_id": scan_id,
        "snapshot_evidence_sha256": evidence_sha256,
        "attempted_market_pairs": len(observations),
        "valid_quality_pairs": sum(quality),
        "positive_top_gross_pairs": 0,
        "legacy_freshness_valid_pairs": sum(quality),
        "analysis_source_code_sha256": "analysis-source",
        "counts": {
            "invalid_reasons": {"empty_ask_side": quality.count(False)},
            "positive_full_depth_gross_by_quantity": {"20": 0},
            "positive_minimum_notional_by_quantity": {"20": 0},
        },
        "market_rows": [
            {
                "market_id": row["market_id"],
                "cohort_role": row["cohort_role"],
                "valid": quality[position],
                "invalid_reason": reasons[position],
            }
            for position, row in enumerate(selected)
        ],
    }
    analysis["analysis_event_sha256"] = _canonical_digest(analysis)
    event_path = root / "analysis-events" / "v4" / f"{scan_id}.json"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_bytes(_canonical(analysis))
    return {
        "scan_id": scan_id,
        "captured_at_utc": captured.isoformat(),
        "snapshot_file": snapshot_relative,
        "snapshot_evidence_sha256": evidence_sha256,
        "source_code_sha256": "observer-source",
        "counts": {
            "reported_update_age_above_5s_by_leg": {"yes": 1, "no": 0},
            "reported_update_age_bands_by_leg": {"yes": {"over_5s": 1}, "no": {"under_1s": 2}},
            "reported_update_timestamp_skew_above_250ms_pairs": 1,
            "reported_update_timestamp_skew_bands": {"over_250ms": 1, "under_50ms": 2},
        },
        "discovery": {
            "eligible_pair_markets": 30,
            "unique_market_ids": 50,
            "excluded_market_ids": 20,
            "exclusion_reasons": {"unsupported_outcome_relationship": 20},
        },
        "selection": {
            "plan": {
                "sequence": index + 1,
                "phase": "liquidity",
                "stable_control_available_this_scan": 1,
                "stable_control_missing_this_scan": ["control-2"],
                "rotation_strata": {
                    "tight_le_0.01": {"population": 8, "quota": 1},
                    "wide_gt_0.05": {"population": 4, "quota": 1},
                },
            },
            "selected_markets": selected,
        },
        "market_observations": observations,
    }


def _canonical_digest(value: dict) -> str:
    import hashlib

    return hashlib.sha256(_canonical(value)).hexdigest()


def test_coverage_pilot_is_prospective_idempotent_and_descriptive(tmp_path):
    documented_plan = json.loads(
        (
            Path(__file__).parents[1] / "docs" / "VERITAS_MISSION2_COVERAGE_PILOT_001.json"
        ).read_text()
    )
    assert documented_plan == build_plan()
    root = tmp_path / "observatory"
    root.mkdir()
    (root / "control-cohort.json").write_text('{"market_ids":["control-1"]}')
    start = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    # Pre-existing files are not discovered or backfilled by pilot enrollment.
    (root / "snapshots").mkdir()
    (root / "snapshots" / "scan-000.json.gz").write_bytes(b"prior snapshot")

    first_report = _write_scan(root, 1, start)
    first = record_coverage_pilot(root, first_report)
    repeated = record_coverage_pilot(root, first_report)

    assert first["study_id"] == STUDY_ID
    assert first["protocol_version"] == VERSION
    assert first["status"] == "running"
    assert first["completed_scans"] == 1
    assert first["selected_market_pair_slots"] == 3
    assert first["quality_valid_pairs"] == 2
    assert first["quality_valid_yield"] == pytest.approx(2 / 3)
    assert first["distinct_selected_market_ids"] == 3
    assert first["by_cohort_role"]["stable_random_control"]["quality_valid_yield"] == 1.0
    assert first["by_cohort_role"]["rotating_stratified"]["selected"] == 2
    assert first["by_selection_stratum"]["tight_le_0.01"]["quality_valid"] == 1
    assert repeated["completed_scans"] == 1
    assert repeated["quality_valid_pairs"] == 2
    assert repeated["comparison_interpretation"].startswith("same-scan control")
    assert repeated["orders_submitted"] is False
    assert repeated["authenticated_requests"] is False

    plan = json.loads((root / "measurement-pilots" / STUDY_ID / "plan.json").read_text())
    frozen_plan = plan.pop("plan_sha256")
    assert plan == build_plan()
    assert len(frozen_plan) == 64
    assert len(list((root / "measurement-pilots" / STUDY_ID / "events").glob("*.json"))) == 1


def test_coverage_pilot_stops_at_fixed_window_without_extension(tmp_path):
    root = tmp_path / "observatory"
    root.mkdir()
    start = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    record_coverage_pilot(root, _write_scan(root, 1, start))

    after_window = _write_scan(root, 2, start + timedelta(hours=24, seconds=1))
    summary = record_coverage_pilot(root, after_window)

    assert summary["status"] == "completed"
    assert summary["completion_reason"] == "fixed_24_hour_window_elapsed"
    assert summary["completed_scans"] == 1
    assert len(list((root / "measurement-pilots" / STUDY_ID / "events").glob("*.json"))) == 1


def test_coverage_pilot_caps_scans_and_verifies_append_only_events(tmp_path):
    root = tmp_path / "observatory"
    root.mkdir()
    start = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    summary = None
    for index in range(1, MAX_STUDY_SCANS + 1):
        summary = record_coverage_pilot(
            root,
            _write_scan(root, index, start + timedelta(minutes=30 * (index - 1))),
        )
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["completion_reason"] == "48_scan_cap_reached"
    assert summary["completed_scans"] == MAX_STUDY_SCANS

    event_path = root / "measurement-pilots" / STUDY_ID / "events" / "scan-001.json"
    event = json.loads(event_path.read_text())
    event["quality_valid_pairs"] = 0
    event_path.write_text(json.dumps(event))
    with pytest.raises(ValueError, match="digest mismatch"):
        record_coverage_pilot(root, _write_scan(root, 49, start + timedelta(hours=24)))


def test_coverage_pilot_v2_is_prospective_isolated_and_records_measurement_lineage(tmp_path):
    documented_plan = json.loads(
        (
            Path(__file__).parents[1] / "docs" / "VERITAS_MISSION2_COVERAGE_PILOT_002.json"
        ).read_text()
    )
    assert documented_plan == build_plan_v2()
    root = tmp_path / "observatory"
    root.mkdir()
    start = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    # A pre-existing source scan is intentionally not enrolled or backfilled.
    _write_scan(root, 0, start - timedelta(minutes=30))
    v1 = record_coverage_pilot(root, _write_scan(root, 0, start - timedelta(minutes=30)))
    v1_path = root / "measurement-pilots" / STUDY_ID / "summary.json"
    v1_before = v1_path.read_bytes()

    report = _write_scan(root, 1, start)
    first = record_coverage_pilot_v2(root, report)
    repeated = record_coverage_pilot_v2(root, report)

    assert first["study_id"] == STUDY_ID_V2
    assert first["protocol_version"] == VERSION_V2
    assert first["status"] == "running"
    assert first["completed_scans"] == 1
    assert first["selected_market_pair_slots"] == 3
    assert first["quality_valid_pairs"] == 2
    assert first["measurement_diagnostics"]["strict_reported_fresh_pairs"] == 2
    assert first["measurement_diagnostics"]["reported_update_age_above_5s_by_leg"] == {
        "no": 0,
        "yes": 1,
    }
    assert first["measurement_diagnostics"]["batch_atomicity_verified_pairs"] == 1
    assert first["measurement_diagnostics"]["sequence_verified_pairs"] == 1
    assert repeated["completed_scans"] == 1
    assert repeated["summary_sha256"] == first["summary_sha256"]
    assert v1_path.read_bytes() == v1_before
    assert v1["study_id"] == STUDY_ID

    event_path = root / "measurement-pilots" / STUDY_ID_V2 / "events" / "scan-001.json"
    event = json.loads(event_path.read_text())
    assert event["snapshot_file_sha256"]
    assert event["analysis_event_file_sha256"]
    assert event["analysis_event_sha256"]
    assert event["snapshot_source_code_sha256"] == "observer-source"
    assert event["analysis_source_code_sha256"] == "analysis-source"
    assert set(event["implementation_files"]) == {"coverage_pilot.py", "coverage_pilot_v2.py"}
    assert len(list((event_path.parent).glob("*.json"))) == 1


def test_coverage_pilot_v2_caps_at_48_and_rejects_tampered_event(tmp_path):
    root = tmp_path / "observatory"
    root.mkdir()
    start = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    summary = None
    for index in range(1, 49):
        summary = record_coverage_pilot_v2(
            root,
            _write_scan(root, index, start + timedelta(minutes=30 * (index - 1))),
        )
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["completion_reason"] == "48_scan_cap_reached"
    assert summary["completed_scans"] == 48

    event_path = root / "measurement-pilots" / STUDY_ID_V2 / "events" / "scan-001.json"
    event = json.loads(event_path.read_text())
    event["quality_valid_pairs"] = 0
    event_path.write_text(json.dumps(event))
    with pytest.raises(ValueError, match="digest mismatch"):
        record_coverage_pilot_v2(
            root,
            _write_scan(root, 49, start + timedelta(hours=24)),
        )
