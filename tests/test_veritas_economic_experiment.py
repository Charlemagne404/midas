from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from midas.veritas.continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from midas.veritas.economic_experiment import compare_qualification_rules, run_finalized_experiment


def _event(
    scan_id: str,
    *,
    attempted: int,
    valid: int,
    top: int,
    full_depth: int,
    minimum: int,
    single_match: int,
    fragmentation_safe: int,
) -> dict[str, Any]:
    event = {
        "analysis_version": SNAPSHOT_ANALYSIS_VERSION,
        "scan_id": scan_id,
        "snapshot_file": f"snapshots/{scan_id}.json.gz",
        "snapshot_evidence_sha256": hashlib.sha256(f"evidence-{scan_id}".encode()).hexdigest(),
        "snapshot_source_code_sha256": f"scanner-{scan_id}",
        "analysis_event_sha256": None,
        "captured_ns": 1_800_000_000_000_000_000,
        "captured_at_utc": "2026-10-15T06:00:00+00:00",
        "attempted_market_pairs": attempted,
        "valid_quality_pairs": valid,
        "positive_top_gross_pairs": top,
        "counts": {
            "positive_full_depth_gross_by_quantity": {"20": full_depth},
            "positive_minimum_notional_by_quantity": {"20": minimum},
            "positive_single_match_fee_sensitivity_by_quantity": {"20": single_match},
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {"20": fragmentation_safe},
        },
        "market_rows": [
            {
                "market_id": f"market-{scan_id}-{index}",
                "cohort_role": "rotating_stratified",
                "categories": ["Fixture"],
                "valid": True,
                "top_pair_gross_edge_per_share": "0.01" if index < top else "-0.01",
                "sampled_book_state_hash": hashlib.sha256(
                    f"book-{scan_id}-{index}".encode()
                ).hexdigest(),
                "legacy_freshness_valid": False,
                "legacy_freshness_invalid_reason": "reported_update_age_above_5s",
            }
            for index in range(valid)
        ],
    }
    payload = dict(event)
    payload.pop("analysis_event_sha256")
    event["analysis_event_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return event


def test_economic_qualification_compares_baseline_with_depth_and_fee_gates():
    events = [
        _event(
            "scan-001",
            attempted=3,
            valid=2,
            top=1,
            full_depth=1,
            minimum=0,
            single_match=0,
            fragmentation_safe=0,
        ),
        _event(
            "scan-002",
            attempted=2,
            valid=1,
            top=0,
            full_depth=0,
            minimum=0,
            single_match=0,
            fragmentation_safe=0,
        ),
    ]

    result = compare_qualification_rules(events, quantity="20")

    assert result["experiment_id"] == "VERITAS-M2-ECO-QUAL-001"
    assert result["analysis_version"] == "veritas-economic-qualification-comparison-v4"
    assert result["experiment_run_id"].startswith("VERITAS-M2-ECO-QUAL-001-V4-RUN-")
    assert len(result["dataset_sha256"]) == 64
    assert result["baseline"]["positive_states"] == 1
    assert result["research_improvement"]["positive_states"] == 0
    assert result["sample"]["attempted_market_pairs"] == 5
    assert result["sample"]["quality_valid_pairs"] == 3
    assert result["sample"]["top_pair_edge_per_share"]["positive_count"] == 1
    assert result["gross_candidate_evidence_count"] == 1
    assert result["gross_candidate_evidence_complete"] is True
    assert result["research_improvement"]["count_stage"] == (
        "finalized_event_usdc_notional_prefilter"
    )
    assert result["independent_candidate_replay_qualification"]["complete"] is False
    assert (
        result["independent_candidate_replay_qualification"][
            "positive_full_depth_and_both_minimums"
        ]
        is None
    )
    candidate = result["gross_candidate_evidence"][0]
    assert candidate["candidate_type"] == "quality_valid_positive_top_ask_gross"
    assert candidate["market_id"] == "market-scan-001-0"
    assert candidate["top_pair_gross_edge_per_share"] == "0.01"
    assert candidate["verification_status"] == "NOT_YET_INDEPENDENTLY_REPLAYED"
    source_interval = candidate["source_interval"]
    assert source_interval["scan_id"] == "scan-001"
    assert source_interval["snapshot_file"] == "snapshots/scan-001.json.gz"
    assert source_interval["snapshot_evidence_sha256"] == events[0]["snapshot_evidence_sha256"]
    assert source_interval["analysis_event_sha256"] == events[0]["analysis_event_sha256"]
    assert (
        source_interval["sampled_book_state_hash"]
        == events[0]["market_rows"][0]["sampled_book_state_hash"]
    )
    assert candidate["market_context"]["legacy_freshness_valid"] is False
    assert result["status"] == "preliminary_gross_edge_failed_economic_qualification"
    assert result["orders_submitted"] is False
    assert (
        compare_qualification_rules(events[:1])["experiment_run_id"] != result["experiment_run_id"]
    )


def test_economic_qualification_rejects_missing_positive_candidate_provenance():
    event = _event(
        "scan-003",
        attempted=1,
        valid=1,
        top=1,
        full_depth=0,
        minimum=0,
        single_match=0,
        fragmentation_safe=0,
    )
    event["market_rows"][0]["top_pair_gross_edge_per_share"] = "-0.01"
    payload = dict(event)
    payload.pop("analysis_event_sha256")
    event["analysis_event_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()

    with pytest.raises(ValueError, match="does not match its quality-valid market rows"):
        compare_qualification_rules([event])


def test_economic_qualification_rejects_tampered_or_wrong_version_events():
    event = _event(
        "scan-001",
        attempted=1,
        valid=1,
        top=0,
        full_depth=0,
        minimum=0,
        single_match=0,
        fragmentation_safe=0,
    )
    event["counts"]["positive_minimum_notional_by_quantity"]["20"] = 1
    with pytest.raises(ValueError, match="digest mismatch"):
        compare_qualification_rules([event])

    event = _event(
        "scan-002",
        attempted=1,
        valid=1,
        top=0,
        full_depth=0,
        minimum=0,
        single_match=0,
        fragmentation_safe=0,
    )
    event["analysis_version"] = "unknown-version"
    with pytest.raises(ValueError, match="current analysis version"):
        compare_qualification_rules([event])


def test_finalized_experiment_uses_current_analysis_event_version(tmp_path):
    from midas.veritas.continuous_analysis import VERSION

    event = _event(
        "scan-001",
        attempted=2,
        valid=1,
        top=0,
        full_depth=0,
        minimum=0,
        single_match=0,
        fragmentation_safe=0,
    )
    event_dir = tmp_path / "analysis-events" / VERSION.rsplit("-", 1)[-1]
    event_dir.mkdir(parents=True)
    (event_dir / "scan-001.json").write_text(json.dumps(event))

    result = run_finalized_experiment(tmp_path)

    assert result["input_analysis_version"] == SNAPSHOT_ANALYSIS_VERSION
    assert result["sample"]["attempted_market_pairs"] == 2
    assert result["sample"]["quality_valid_pairs"] == 1
