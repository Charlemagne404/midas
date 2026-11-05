from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

import pytest
from midas.veritas.scan_catalog import (
    CATALOG_NAME,
    rebuild_catalog,
    reconcile,
    record_snapshot,
    summary,
)


def _report(scan_id: str, edge: str = "-0.025") -> dict:
    captured_ns = 1_792_044_000_000_000_000
    return {
        "scan_id": scan_id,
        "captured_ns": captured_ns,
        "captured_at_utc": "2026-10-15T06:00:00+00:00",
        "snapshot_evidence_sha256": "a" * 64,
        "source_code_sha256": "b" * 64,
        "discovery": {
            "query_candidate_records": 81,
            "unique_market_ids": 64,
            "eligible_pair_markets": 32,
        },
        "selection": {
            "plan": {
                "phase": "expiry",
                "bounded_eligible_population": 32,
                "reference_population_excluding_available_frozen_controls": 4,
                "reference_selected": 1,
                "selected_count": 1,
            },
            "selected_markets": [
                {
                    "market_id": "market-1",
                    "primary_category": "Politics",
                    "liquidity_band": "medium",
                    "expiry_band": "long",
                    "spread_band": "tight_le_0.01",
                    "volume_24h_usdc": "1250.5",
                    "end_ns": captured_ns + 1_000,
                }
            ],
        },
        "counts": {
            "valid_quality_pairs": 1,
            "positive_top_gross_pairs": 0,
            "invalid_reasons": {},
        },
        "source_requests": {
            "public_http_attempts": 7,
            "clob_book_batches": [
                {
                    "requested_at_ns": captured_ns - 10_000_000,
                    "received_at_ns": captured_ns,
                }
            ],
        },
        "market_observations": [
            {
                "market_id": "market-1",
                "categories": ["Politics", "Current Events"],
                "cohort_role": "reference_random",
                "selection_probability": "0.25",
                "selection_stratum": "Politics|medium|long",
                "book_integrity": {"status": "complete"},
                "audit": {
                    "valid": True,
                    "positive_top_pair_gross": False,
                    "top_pair_gross_edge_per_share": edge,
                    "quality": {
                        "reported_update_age_ms_by_leg": {"yes": 700, "no": 800},
                        "reported_update_timestamp_skew_ms": 100,
                        "batch_duration_ms": 10,
                    },
                    "quantity_results": [
                        {
                            "quantity_shares_per_leg": "20",
                            "full_depth": True,
                            "full_depth_gross_edge_usdc": "-0.50",
                            "positive_full_depth_gross": False,
                            "fee_status": "verified_disabled",
                            "positive_single_match_sensitivity": False,
                            "positive_fragmentation_safe_sensitivity": False,
                        }
                    ],
                },
            }
        ],
    }


def _write(root: Path, scan_id: str, edge: str = "-0.025") -> tuple[dict, Path]:
    report = _report(scan_id, edge=edge)
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    path = snapshots / f"{scan_id}.json.gz"
    path.write_bytes(gzip.compress(json.dumps(report, sort_keys=True).encode(), mtime=0))
    return report, path


def test_catalog_reconciles_saved_observations_without_a_summary_index(tmp_path):
    scan_id = "scan-20261015T060000Z-catalog01"
    _write(tmp_path, scan_id)
    # An invalid neighboring file is quarantined without blocking valid evidence.
    corrupt = tmp_path / "snapshots" / "scan-20261015T060001Z-corrupt.json.gz"
    corrupt.write_bytes(b"not-gzip")

    result = reconcile(tmp_path)

    assert result["indexed_this_run"] == 1
    assert result["quarantined_this_run"] == 1
    assert result["indexed_snapshot_count"] == 1
    assert result["quarantined_snapshot_count"] == 1
    indexed = summary(tmp_path)
    assert indexed["scan_count"] == 1
    assert indexed["selected_market_observation_count"] == 1
    assert indexed["unique_market_count"] == 1
    assert indexed["quality_valid_pair_count"] == 1
    assert indexed["strict_fresh_pair_count"] == 1
    assert indexed["cohort_observation_counts"] == {"reference_random": 1}
    assert indexed["reference_cohort_summary"]["indexed_observations"] == 1
    assert indexed["reference_cohort_summary"]["quality_valid_observations"] == 1
    assert (
        indexed["reference_cohort_summary"]["positive_share_among_quality_valid_observations"] == 0
    )
    assert indexed["top_markets_by_observation_count"][0]["minimum_edge_per_share"] == "-0.025"
    assert Path(tmp_path / CATALOG_NAME).is_file()


def test_catalog_record_is_idempotent_and_rejects_evidence_replacement(tmp_path):
    scan_id = "scan-20261015T060000Z-catalog02"
    report, path = _write(tmp_path, scan_id)

    first = record_snapshot(tmp_path, report, path)
    repeated = record_snapshot(tmp_path, report, path)

    assert first["status"] == "indexed"
    assert repeated["status"] == "already_indexed"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="conflicts"):
        record_snapshot(tmp_path, report, path)
    assert summary(tmp_path)["scan_count"] == 1


def test_catalog_reconcile_is_bounded_and_quarantines_by_content_identity(tmp_path):
    with pytest.raises(ValueError, match="between 1 and 50"):
        reconcile(tmp_path, limit=51)
    corrupt = tmp_path / "snapshots" / "scan-20261015T060001Z-bad.json.gz"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"first-invalid-content")

    first = reconcile(tmp_path, limit=1)
    corrupt.write_bytes(b"different-invalid-content")
    second = reconcile(tmp_path, limit=1)

    assert first["quarantined_this_run"] == 1
    assert second["quarantined_this_run"] == 1
    assert second["quarantined_snapshot_count"] == 2
    with sqlite3.connect(tmp_path / CATALOG_NAME) as connection:
        rows = connection.execute(
            "SELECT DISTINCT snapshot_file_sha256 FROM quarantines"
        ).fetchall()
    assert len(rows) == 2


def test_catalog_reports_unmeasured_metrics_as_unavailable_not_zero(tmp_path):
    scan_id = "scan-20261015T060000Z-partial01"
    report, path = _write(tmp_path, scan_id)
    report["counts"].pop("valid_quality_pairs")
    report["counts"].pop("positive_top_gross_pairs")
    report["market_observations"][0].pop("audit")
    path.write_bytes(gzip.compress(json.dumps(report, sort_keys=True).encode(), mtime=0))

    record_snapshot(tmp_path, report, path)
    result = summary(tmp_path)

    assert result["measurement_status"] == "PARTIALLY_MEASURED"
    assert result["selected_market_observation_count"] == 1
    assert result["quality_valid_pair_count"] is None
    assert result["strict_fresh_pair_count"] is None
    assert result["positive_top_gross_pair_count"] is None
    assert result["metrics"]["quality_valid_pairs"]["partial_observed_total"] == 0
    assert result["metrics"]["quality_valid_pairs"]["unmeasured_scan_count"] == 1


def test_empty_catalog_marks_outcomes_not_measured(tmp_path):
    result = summary(tmp_path)

    assert result["measurement_status"] == "NOT_MEASURED"
    assert result["scan_count"] == 0
    assert result["quality_valid_pair_count"] is None
    assert result["positive_top_gross_pair_count"] is None


def test_scan_catalog_snapshot_insert_is_atomic_on_duplicate_observations(tmp_path):
    scan_id = "scan-20261015T060000Z-atomic01"
    report, path = _write(tmp_path, scan_id)
    report["market_observations"].append(dict(report["market_observations"][0]))

    with pytest.raises(sqlite3.IntegrityError):
        record_snapshot(tmp_path, report, path)

    assert summary(tmp_path)["scan_count"] == 0
    report["market_observations"].pop()
    assert record_snapshot(tmp_path, report, path)["status"] == "indexed"
    assert summary(tmp_path)["scan_count"] == 1


def test_scan_catalog_rotates_snapshot_hash_verification_without_rewriting_index(tmp_path):
    scan_id = "scan-20261015T060000Z-integrity01"
    _write(tmp_path, scan_id)
    first = reconcile(tmp_path)
    assert first["integrity_check_this_run"]["status"] == "CURRENT"

    path = tmp_path / "snapshots" / f"{scan_id}.json.gz"
    path.write_bytes(path.read_bytes() + b"tampered")
    second = reconcile(tmp_path)

    assert second["integrity_check_this_run"]["status"] == "HASH_MISMATCH"
    assert second["integrity_issue_count"] == 1
    assert summary(tmp_path)["scan_count"] == 1


def test_corrupt_scan_catalog_is_preserved_and_rebuilt_in_bounded_passes(tmp_path):
    _write(tmp_path, "scan-20261015T060000Z-rebuild01")
    _write(tmp_path, "scan-20261015T060100Z-rebuild02")
    corrupt_path = tmp_path / CATALOG_NAME
    corrupt_path.write_bytes(b"partial sqlite page")

    first = rebuild_catalog(tmp_path, limit=1)
    preserved = tmp_path / str(first["preserved_corrupt_catalog"])
    second = rebuild_catalog(tmp_path, limit=1)

    assert first["status"] == "REBUILDING"
    assert preserved.read_bytes() == b"partial sqlite page"
    assert first["result"]["indexed_this_run"] == 1
    assert second["status"] == "CURRENT"
    assert second["result"]["indexed_this_run"] == 1
    assert second["handled_snapshot_identity_count"] == 2
    assert summary(tmp_path)["scan_count"] == 2
