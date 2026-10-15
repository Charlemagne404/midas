from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from midas.veritas.continuous_analysis import update_finalized_analysis


def _report(scan_id: str, *, valid: bool, candidate: bool = False) -> dict[str, Any]:
    captured_ns = 1_792_044_000_000_000_000
    stamp = str(captured_ns // 1_000_000 - 10_000)
    condition = "condition-1"
    yes = {
        "market": condition,
        "asset_id": "11",
        "timestamp": stamp,
        "hash": "hash-11",
        "bids": [{"price": "0.30", "size": "100"}],
        "asks": [{"price": "0.40" if candidate else "0.50", "size": "100"}],
        "min_order_size": "5",
        "tick_size": "0.01",
        "neg_risk": False,
    }
    no = {
        "market": condition,
        "asset_id": "12",
        "timestamp": stamp,
        "hash": "hash-12",
        "bids": [{"price": "0.30", "size": "100"}],
        "asks": [] if not valid else [{"price": "0.50", "size": "100"}],
        "min_order_size": "5",
        "tick_size": "0.01",
        "neg_risk": False,
    }
    books = {"11": yes, "12": no}
    market = {
        "market_id": "m1",
        "condition": condition,
        "protocol": "v1",
        "pair_semantics": "same_condition_yes_no_ctf",
        "outcomes": {"yes": "11", "no": "12"},
        "negative_risk": False,
        "tick_size": "0.01",
        "minimum_order_notional_usdc": "5",
        "fee_regime": {"status": "verified_disabled"},
        "eligible_for_pair_observation": True,
    }
    return {
        "scan_id": scan_id,
        "snapshot_evidence_sha256": f"evidence-{scan_id}",
        "source_code_sha256": "scanner-source",
        "captured_at_utc": "2026-10-15T06:00:00+00:00",
        "captured_ns": captured_ns,
        "discovery": {
            "query_count": 6,
            "query_candidate_records": 300,
            "unique_market_ids": 280,
            "eligible_pair_markets": 70,
            "excluded_market_ids": 210,
            "exclusion_reasons": {"unsupported_outcome_relationship": 210},
            "universe": [market],
        },
        "quantity_grid": ["5", "10", "20", "50", "100"],
        "selection": {
            "selected_markets": [
                {
                    "market_id": "m1",
                    "categories": ["Politics"],
                    "cohort_role": "stable_random_control",
                }
            ]
        },
        "counts": {
            "valid_quality_pairs": int(valid),
            "positive_top_gross_pairs": int(candidate),
            "invalid_reasons": {} if valid else {"no_empty_ask_side": 1},
            "positive_full_depth_gross_by_quantity": {"20": int(candidate)},
            "positive_minimum_notional_by_quantity": {"20": int(candidate)},
            "positive_single_match_fee_sensitivity_by_quantity": {"20": 0},
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {"20": 0},
            "reported_update_age_bands_by_leg": {
                "yes": {"over_5m": 1},
                "no": {"over_5m": 1},
            },
            "reported_update_age_above_5s_by_leg": {"yes": 1, "no": 1},
            "reported_update_timestamp_skew_bands": {"0_to_250ms": 1},
            "reported_update_timestamp_skew_above_250ms_pairs": 0,
        },
        "market_observations": [
            {
                "market_id": "m1",
                "condition": condition,
                "question": "Fixture market?",
                "outcomes": {"yes": "11", "no": "12"},
                "categories": ["Politics"],
                "cohort_role": "stable_random_control",
                "books": books,
                "book_source_sha256": "book-source",
                "raw_market_metadata_sha256": "market-source",
                "audit": {
                    "valid": False,
                    "reason": "yes_book_stale",
                    "top_pair_gross_edge_per_share": "0.001" if candidate else "-0.01",
                    "quantity_results": [],
                },
                "positive_minimum_notional_quantities": ["20", "50", "100"] if candidate else [],
                "positive_single_match_quantities": [],
                "positive_fragmentation_safe_quantities": [],
            }
        ],
        "source_requests": {
            "gamma_pages": [{"response_sha256": "gamma-hash"}],
            "clob_books": {
                "response_sha256": "clob-hash",
                "requested_at_ns": captured_ns - 100_000_000,
                "received_at_ns": captured_ns,
                "request_asset_count": 2,
                "response_book_count": 2,
                "response_payload": json.dumps([yes, no]),
            },
        },
    }


def _write_snapshot(root: Path, scan_id: str, *, valid: bool, candidate: bool = False) -> None:
    path = root / "snapshots" / f"{scan_id}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        gzip.compress(json.dumps(_report(scan_id, valid=valid, candidate=candidate)).encode())
    )


def test_finalized_analysis_is_incremental_idempotent_and_lineage_preserving(tmp_path):
    _write_snapshot(tmp_path, "scan-001", valid=True, candidate=True)
    prior_summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-snapshot-analysis-v1",
        "cumulative": {},
    }
    (tmp_path / "research-summary.json").write_text(json.dumps(prior_summary))

    first = update_finalized_analysis(tmp_path)
    again = update_finalized_analysis(tmp_path)

    assert first["processed_snapshot_count"] == 1
    assert first["cumulative"]["quality_valid_pairs"] == 1
    assert first["cumulative"]["candidate_event_count"] == 1
    assert first["cumulative"]["reported_update_age_above_5s_by_leg"] == {
        "yes": 1,
        "no": 1,
    }
    assert first["cumulative"]["recent_candidates"][0]["snapshot_file"] == (
        "snapshots/scan-001.json.gz"
    )
    assert json.loads((tmp_path / "research-summary-v1.json").read_text()) == prior_summary
    assert again["processed_snapshot_count"] == 1
    assert again["cumulative"]["quality_valid_pairs"] == 1
    assert len(list((tmp_path / "analysis-events" / "v2").glob("*.json"))) == 1

    _write_snapshot(tmp_path, "scan-002", valid=False)
    updated = update_finalized_analysis(tmp_path)
    assert updated["processed_snapshot_count"] == 2
    assert updated["cumulative"]["quality_valid_pairs"] == 1
    assert updated["cumulative"]["invalid_pairs"] == 1
    assert updated["cumulative"]["invalid_reasons"] == {"no_empty_ask_side": 1}
    assert updated["cumulative"]["maximum_bounded_eligible_markets_seen"] == 70
    assert updated["cumulative"]["candidate_market_ids"] == ["m1"]


def test_finalized_analysis_processes_only_its_bounded_backlog_slice(tmp_path):
    for index in range(3):
        _write_snapshot(tmp_path, f"scan-{index:03d}", valid=True)

    first = update_finalized_analysis(tmp_path, max_pending=1)
    second = update_finalized_analysis(tmp_path, max_pending=1)
    third = update_finalized_analysis(tmp_path, max_pending=1)

    assert first["processed_snapshot_count"] == 1
    assert first["pending_snapshot_count"] == 2
    assert second["processed_snapshot_count"] == 2
    assert second["pending_snapshot_count"] == 1
    assert third["processed_snapshot_count"] == 3
    assert third["pending_snapshot_count"] == 0
    assert third["cumulative"]["quality_valid_pairs"] == 3


def test_finalized_snapshot_and_event_identity_are_checked(tmp_path):
    _write_snapshot(tmp_path, "scan-001", valid=True)
    snapshot = tmp_path / "snapshots" / "scan-001.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(_report("scan-other", valid=True)).encode()))

    try:
        update_finalized_analysis(tmp_path)
    except ValueError as error:
        assert "identity mismatch" in str(error)
    else:
        raise AssertionError("Expected snapshot identity validation to reject the artifact")
