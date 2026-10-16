from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_veritas_coverage_design import audit_selection_design, run_audit


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _seal(value: dict[str, object], field: str) -> dict[str, object]:
    value[field] = hashlib.sha256(_canonical(value)).hexdigest()
    return value


def _event(
    *,
    scan_id: str = "scan-20261016T010000Z-0123456789ab",
    sequence: int = 1,
    strata: dict[str, dict[str, int]] | None = None,
    rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    strata = strata or {"high": {"population": 4, "quota": 2}, "low": {"population": 2, "quota": 1}}
    rows = rows or [
        {
            "market_id": "m1",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "high",
            "selection_probability": "0.5",
            "quality_valid": True,
        },
        {
            "market_id": "m2",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "high",
            "selection_probability": "0.5",
            "quality_valid": False,
        },
        {
            "market_id": "m3",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "low",
            "selection_probability": "0.5",
            "quality_valid": False,
        },
        {
            "market_id": "c1",
            "cohort_role": "stable_random_control",
            "selection_stratum": "unclassified",
            "selection_probability": "1 conditional on frozen control cohort",
            "quality_valid": True,
        },
    ]
    controls = [row for row in rows if row["cohort_role"] == "stable_random_control"]
    population = sum(row["population"] for row in strata.values())
    return {
        "scan_id": scan_id,
        "captured_at_utc": "2026-10-16T01:00:00+00:00",
        "selection_sequence": sequence,
        "phase": "liquidity",
        "bounded_eligible_markets": population + len(controls),
        "stable_control_available": len(controls),
        "selected_market_pairs": len(rows),
        "quality_valid_pairs": sum(bool(row["quality_valid"]) for row in rows),
        "rotating_strata": strata,
        "market_rows": rows,
        "orders_submitted": False,
        "authenticated_requests": False,
    }


def test_design_weighted_yield_uses_inclusion_probability_and_separates_controls():
    result = audit_selection_design([_event()])
    scan = result["scans"][0]
    assert scan["rotating_selected"] == 3
    assert scan["rotating_quality_valid"] == 1
    assert scan["rotating_population_support_fraction"] == 1.0
    assert scan["design_weighted_valid_count_estimate_on_supported_population"] == 2.0
    assert scan["design_weighted_quality_yield_on_supported_population"] == pytest.approx(1 / 3)
    assert result["role_totals"]["stable_random_control"] == {
        "selected": 1,
        "valid": 1,
        "yield": 1.0,
    }


def test_zero_quota_stratum_is_reported_outside_design_weighted_support():
    event = _event(
        strata={"sampled": {"population": 2, "quota": 1}, "omitted": {"population": 3, "quota": 0}},
        rows=[
            {
                "market_id": "m1",
                "cohort_role": "rotating_stratified",
                "selection_stratum": "sampled",
                "selection_probability": "0.5",
                "quality_valid": True,
            }
        ],
    )
    result = audit_selection_design([event])
    scan = result["scans"][0]
    assert scan["rotating_population_support_fraction"] == pytest.approx(0.4)
    assert scan["unsupported_positive_population_strata"] == ["omitted"]
    assert result["fully_supported_scan_count"] == 0
    assert result["partially_supported_scan_count"] == 1


def test_inclusion_probability_mismatch_fails_closed():
    event = _event()
    event["market_rows"][0]["selection_probability"] = "0.25"
    with pytest.raises(ValueError, match="Selection probability mismatch"):
        audit_selection_design([event])


def _write_json(path: Path, value: dict[str, object], *, digest_field: str | None = None) -> str:
    if digest_field:
        _seal(value, digest_field)
    payload = _canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def test_run_audit_verifies_event_snapshot_and_analysis_lineage(tmp_path: Path):
    observatory = tmp_path / "observatory"
    pilot = tmp_path / "pilot"
    scan_id = "scan-20261016T010000Z-0123456789ab"
    evidence_sha = "a" * 64
    source_sha = "b" * 64
    selected = [
        {
            "market_id": "m1",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "high",
            "selection_probability": "1",
            "primary_category": "test",
        }
    ]
    snapshot = {
        "scan_id": scan_id,
        "snapshot_evidence_sha256": evidence_sha,
        "source_code_sha256": source_sha,
        "selection": {
            "selected_markets": selected,
            "plan": {
                "phase": "liquidity",
                "sequence": 1,
                "stable_control_available_this_scan": 0,
                "stable_control_missing_this_scan": [],
                "rotation_strata": {"high": {"population": 1, "quota": 1}},
            },
        },
        "discovery": {
            "eligible_pair_markets": 1,
            "unique_market_ids": 1,
            "excluded_market_ids": 0,
        },
        "market_observations": [{"market_id": "m1"}],
    }
    snapshot_path = observatory / "snapshots" / f"{scan_id}.json.gz"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_bytes(gzip.compress(_canonical(snapshot)))
    snapshot_file_sha = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    analysis_event = {
        "analysis_version": "veritas-finalized-snapshot-analysis-v4",
        "scan_id": scan_id,
        "snapshot_evidence_sha256": evidence_sha,
        "attempted_market_pairs": 1,
        "valid_quality_pairs": 1,
        "market_rows": [{"market_id": "m1", "valid": True, "invalid_reason": None}],
    }
    analysis_path = observatory / "analysis-events" / "v4" / f"{scan_id}.json"
    analysis_sha = _write_json(analysis_path, analysis_event, digest_field="analysis_event_sha256")
    plan = {"study_id": "fixture"}
    _write_json(pilot / "plan.json", plan, digest_field="plan_sha256")
    plan_sha = str(plan["plan_sha256"])
    implementation_sha = "c" * 64
    state = {
        "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
        "protocol_version": "veritas-coverage-pilot-v1",
        "plan_sha256": plan_sha,
        "implementation_sha256": implementation_sha,
        "status": "running",
    }
    _write_json(pilot / "state.json", state)
    row = {
        "market_id": "m1",
        "cohort_role": "rotating_stratified",
        "selection_stratum": "high",
        "selection_probability": "1",
        "primary_category": "test",
        "quality_valid": True,
        "invalid_reason": None,
    }
    event: dict[str, object] = {
        "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
        "protocol_version": "veritas-coverage-pilot-v1",
        "plan_sha256": plan_sha,
        "implementation_sha256": implementation_sha,
        "scan_id": scan_id,
        "previous_event_sha256": None,
        "snapshot_file": f"snapshots/{scan_id}.json.gz",
        "snapshot_file_sha256": snapshot_file_sha,
        "snapshot_evidence_sha256": evidence_sha,
        "snapshot_source_code_sha256": source_sha,
        "analysis_event_file_sha256": analysis_sha,
        "analysis_event_sha256": analysis_event["analysis_event_sha256"],
        "phase": "liquidity",
        "selection_sequence": 1,
        "bounded_eligible_markets": 1,
        "discovered_unique_market_ids": 1,
        "excluded_market_ids": 0,
        "selected_market_pairs": 1,
        "quality_valid_pairs": 1,
        "stable_control_available": 0,
        "stable_control_missing": [],
        "rotating_strata": {"high": {"population": 1, "quota": 1}},
        "orders_submitted": False,
        "authenticated_requests": False,
        "market_rows": [row],
    }
    _seal(event, "event_sha256")
    _write_json(pilot / "events" / f"{scan_id}.json", event)
    summary = {
        "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
        "protocol_version": "veritas-coverage-pilot-v1",
        "completed_scans": 1,
        "selected_market_pair_slots": 1,
        "quality_valid_pairs": 1,
    }
    _write_json(pilot / "summary.json", summary, digest_field="summary_sha256")

    audit = run_audit(pilot, observatory)
    assert audit["analysis"]["fully_supported_scan_count"] == 1
    assert (
        audit["analysis"]["scans"][0]["design_weighted_quality_yield_on_supported_population"]
        == 1.0
    )
    assert audit["safety"]["live_requests"] == 0
