from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from midas.veritas.continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from midas.veritas.economic_experiment import compare_qualification_rules


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
        "snapshot_evidence_sha256": f"evidence-{scan_id}",
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
                "valid": True,
                "top_pair_gross_edge_per_share": "0.01" if index < top else "-0.01",
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
    assert result["experiment_run_id"].startswith("VERITAS-M2-ECO-QUAL-001-RUN-")
    assert len(result["dataset_sha256"]) == 64
    assert result["baseline"]["positive_states"] == 1
    assert result["research_improvement"]["positive_states"] == 0
    assert result["sample"]["attempted_market_pairs"] == 5
    assert result["sample"]["quality_valid_pairs"] == 3
    assert result["sample"]["top_pair_edge_per_share"]["positive_count"] == 1
    assert result["status"] == "preliminary_gross_edge_failed_economic_qualification"
    assert result["orders_submitted"] is False
    assert (
        compare_qualification_rules(events[:1])["experiment_run_id"] != result["experiment_run_id"]
    )


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
