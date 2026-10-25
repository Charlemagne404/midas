from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.veritas.continuous_analysis import update_finalized_analysis


def _report(
    scan_id_hint: str,
    *,
    valid: bool,
    candidate: bool = False,
    minutes_after: int = 0,
    state_version: str = "same",
    reported_age_ms: int = 1_000,
) -> dict[str, Any]:
    captured_ns = 1_792_044_000_000_000_000 + minutes_after * 60_000_000_000
    captured_at_utc = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC).isoformat()
    stamp = str(captured_ns // 1_000_000 - reported_age_ms)
    condition = "0x" + "1" * 64
    yes = {
        "market": condition,
        "asset_id": "11",
        "timestamp": stamp,
        "hash": f"hash-11-{state_version}",
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
        "hash": f"hash-12-{state_version}",
        "bids": [{"price": "0.30", "size": "100"}],
        "asks": [] if not valid else [{"price": "0.50", "size": "100"}],
        "min_order_size": "5",
        "tick_size": "0.01",
        "neg_risk": False,
    }
    books = {"11": yes, "12": no}
    clob_payload = json.dumps([yes, no], separators=(",", ":"))
    clob_digest = hashlib.sha256(clob_payload.encode("utf-8")).hexdigest()
    gamma_payload = "[]"
    gamma_digest = hashlib.sha256(gamma_payload.encode("utf-8")).hexdigest()
    requested_at_ns = captured_ns - 100_000_000
    request_assets = ["11", "12"]
    request_body = [{"token_id": asset} for asset in request_assets]
    request_digest = hashlib.sha256(
        json.dumps(
            request_body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    market = {
        "market_id": "m1",
        "condition": condition,
        "protocol": "v1",
        "pair_semantics": "same_condition_yes_no_ctf",
        "outcomes": {"yes": "11", "no": "12"},
        "negative_risk": False,
        "tick_size": "0.01",
        "minimum_order_notional_usdc": "5",
        "active": True,
        "closed": False,
        "accepting_orders": True,
        "orderbook_enabled": True,
        "restricted": False,
        "fee_regime": {"enabled": False, "status": "verified_disabled"},
        "eligible_for_pair_observation": True,
    }
    source_code_sha256 = "scanner-source"
    sequence = minutes_after // 30 + 1
    seed = 12345
    evidence_material = {
        "gamma_response_hashes": [gamma_digest],
        "clob_response_sha256": [clob_digest],
        "source_code_sha256": source_code_sha256,
        "captured_ns": captured_ns,
        "selection_seed": seed,
        "sequence": sequence,
    }
    evidence_digest = hashlib.sha256(
        json.dumps(
            evidence_material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    timestamp_id = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    scan_id = f"{scan_id_hint}-{timestamp_id}-{evidence_digest[:12]}"
    return {
        "scan_id": scan_id,
        "snapshot_evidence_sha256": evidence_digest,
        "source_code_sha256": source_code_sha256,
        "captured_at_utc": captured_at_utc,
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
            "plan": {
                "phase": "fixture",
                "seed": seed,
                "sequence": sequence,
                "bounded_eligible_population": 70,
                "selected_count": 1,
            },
            "selected_markets": [
                {
                    "market_id": "m1",
                    "outcomes": {"yes": "11", "no": "12"},
                    "categories": ["Politics"],
                    "cohort_role": "stable_random_control",
                    "selection_probability": "1/70",
                    "selection_stratum": "Politics|medium|long",
                }
            ],
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
                "selection_probability": "1/70",
                "selection_stratum": "Politics|medium|long",
                "books": books,
                "book_source_sha256": clob_digest,
                "book_integrity": {
                    "status": "complete",
                    "request_duration_ms": 100.0,
                    "requested_at_ns": requested_at_ns,
                    "received_at_ns": captured_ns,
                },
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
            "gamma_pages": [{"response_sha256": gamma_digest, "response_payload": gamma_payload}],
            "clob_book_batches": [
                {
                    "response_sha256": clob_digest,
                    "request_sha256": request_digest,
                    "requested_at_ns": requested_at_ns,
                    "received_at_ns": captured_ns,
                    "request_asset_count": 2,
                    "request_asset_ids": request_assets,
                    "response_book_count": 2,
                    "response_payload": clob_payload,
                }
            ],
        },
    }


def _write_snapshot(
    root: Path,
    scan_id: str,
    *,
    valid: bool,
    candidate: bool = False,
    minutes_after: int = 0,
    state_version: str = "same",
    reported_age_ms: int = 1_000,
) -> str:
    report = _report(
        scan_id,
        valid=valid,
        candidate=candidate,
        minutes_after=minutes_after,
        state_version=state_version,
        reported_age_ms=reported_age_ms,
    )
    actual_scan_id = str(report["scan_id"])
    report["snapshot_file"] = f"snapshots/{actual_scan_id}.json.gz"
    path = root / "snapshots" / f"{actual_scan_id}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(report).encode()))
    return actual_scan_id


def test_finalized_analysis_is_incremental_idempotent_and_lineage_preserving(tmp_path):
    first_scan_id = _write_snapshot(
        tmp_path, "scan-001", valid=True, candidate=True, reported_age_ms=1_000
    )
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
    assert first["cumulative"]["legacy_freshness_valid_pairs"] == 1
    assert first["cumulative"]["candidate_event_count"] == 1
    assert first["cumulative"]["reported_update_age_above_5s_by_leg"] == {
        "yes": 0,
        "no": 0,
    }
    assert first["cumulative"]["recent_candidates"][0]["snapshot_file"] == (
        f"snapshots/{first_scan_id}.json.gz"
    )
    assert (
        json.loads(
            (tmp_path / "research-summary-veritas-finalized-snapshot-analysis-v1.json").read_text()
        )
        == prior_summary
    )
    assert again["processed_snapshot_count"] == 1
    assert again["cumulative"]["quality_valid_pairs"] == 1
    assert len(list((tmp_path / "analysis-events" / "v6-independent-v2").glob("*.json"))) == 1

    _write_snapshot(tmp_path, "scan-002", valid=False, minutes_after=30, state_version="changed")
    updated = update_finalized_analysis(tmp_path)
    assert updated["processed_snapshot_count"] == 2
    assert updated["cumulative"]["quality_valid_pairs"] == 1
    assert updated["cumulative"]["invalid_pairs"] == 1
    assert updated["cumulative"]["invalid_reasons"] == {"no_empty_ask_side": 1}
    assert updated["cumulative"]["maximum_bounded_eligible_markets_seen"] == 70
    assert updated["cumulative"]["candidate_market_ids"] == ["m1"]
    market = updated["cumulative"]["observed_market_ids"]["m1"]
    assert market["selected_observations"] == 2
    assert market["quality_valid_pairs"] == 1
    assert market["legacy_freshness_valid_pairs"] == 1
    assert market["first_observed_at_utc"] == "2026-10-15T06:00:00+00:00"
    assert market["last_observed_at_utc"] == "2026-10-15T06:30:00+00:00"
    assert market["sampled_state_fingerprint_count"] == 2
    assert market["sampled_state_comparisons"] == 1
    assert market["sampled_state_changes"] == 1
    assert updated["cumulative"]["legacy_freshness_invalid_reasons"] == {"no_empty_ask_side": 1}


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


def test_independent_source_freshness_disagreement_is_retained(tmp_path):
    _write_snapshot(
        tmp_path,
        "scan-stale-source",
        valid=True,
        candidate=True,
        reported_age_ms=5_001,
    )

    result = update_finalized_analysis(tmp_path)

    assert result["cumulative"]["primary_quality_valid_pairs"] == 1
    assert result["cumulative"]["independent_economic_snapshot_valid_pairs"] == 0
    assert result["cumulative"]["independent_economic_valid_pairs"] == 0
    assert result["cumulative"]["quality_valid_pairs"] == 0
    assert result["cumulative"]["independent_economic_disagreements"] == {
        "source_quality": 1,
        "validity": 1,
    }


def test_finalized_snapshot_and_event_identity_are_checked(tmp_path):
    actual_scan_id = _write_snapshot(tmp_path, "scan-001", valid=True)
    snapshot = tmp_path / "snapshots" / f"{actual_scan_id}.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(_report("scan-other", valid=True)).encode()))

    result = update_finalized_analysis(tmp_path)
    assert result["processed_snapshot_count"] == 0
    assert result["quarantined_snapshot_count"] == 1
    assert result["quarantined_this_run"] == 1


def test_analysis_rolls_over_a_summary_larger_than_the_old_reader_limit(tmp_path):
    _write_snapshot(tmp_path, "scan-large-summary", valid=True)
    old_summary = (
        b'{"schema_version":1,"analysis_version":"veritas-finalized-snapshot-analysis-v1",'
        b'"legacy_payload":"' + b"x" * (2 * 1024 * 1024 + 128) + b'"}'
    )
    (tmp_path / "research-summary.json").write_bytes(old_summary)

    result = update_finalized_analysis(tmp_path)

    assert result["processed_snapshot_count"] == 1
    assert (
        tmp_path / "research-summary-veritas-finalized-snapshot-analysis-v1.json"
    ).read_bytes() == old_summary
    assert json.loads((tmp_path / "research-summary.json").read_text())["analysis_version"] == (
        "veritas-finalized-snapshot-analysis-v6"
    )


def test_corrupt_snapshot_is_quarantined_without_blocking_later_valid_snapshots(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "scan-000-corrupt.json.gz").write_bytes(b"broken-gzip-evidence")
    _write_snapshot(tmp_path, "scan-001-valid", valid=True)

    first = update_finalized_analysis(tmp_path, max_pending=2)
    second = update_finalized_analysis(tmp_path, max_pending=2)

    assert first["processed_snapshot_count"] == 1
    assert first["processed_this_run"] == 1
    assert first["quarantined_snapshot_count"] == 1
    assert first["quarantined_this_run"] == 1
    assert first["pending_snapshot_count"] == 0
    assert second["processed_snapshot_count"] == 1
    assert second["quarantined_snapshot_count"] == 1
    assert second["quarantined_this_run"] == 0
    assert len(list((tmp_path / "analysis-events" / "v6-independent-v2").glob("*.json"))) == 1


def test_analysis_catalog_compacts_only_the_published_detail_projection():
    from midas.veritas.analysis_catalog import (
        MAX_RETAINED_MARKET_DETAILS,
        _compact_cumulative,
    )

    details = {
        f"market-{index:04d}": {
            "selected_observations": index + 1,
            "last_observed_at_utc": f"2026-10-{1 + index // 24:02d}T{index % 24:02d}:00:00+00:00",
        }
        for index in range(MAX_RETAINED_MARKET_DETAILS + 10)
    }
    cumulative = {"observed_market_ids": details, "candidate_market_ids": []}

    _compact_cumulative(cumulative)

    assert len(cumulative["observed_market_ids"]) == MAX_RETAINED_MARKET_DETAILS
    assert cumulative["observed_market_details_truncated"] is True
    assert cumulative["observed_market_details_limit"] == MAX_RETAINED_MARKET_DETAILS
    assert "market-1009" in cumulative["observed_market_ids"]
    assert "market-0000" not in cumulative["observed_market_ids"]


def test_analysis_recovers_a_durable_event_written_before_catalog_commit(tmp_path):
    from midas.veritas.analysis_catalog import ANALYSIS_EVENTS_DIRECTORY
    from midas.veritas.continuous_analysis import (
        _event_from_snapshot,
        _read_snapshot,
        _sha256_file,
        _write_event_exclusive,
    )

    scan_id = _write_snapshot(tmp_path, "scan-event-before-db", valid=True)
    snapshot_path = tmp_path / "snapshots" / f"{scan_id}.json.gz"
    report = _read_snapshot(snapshot_path)
    event = _event_from_snapshot(report, snapshot_path, snapshot_sha256=_sha256_file(snapshot_path))
    event_dir = tmp_path / "analysis-events" / ANALYSIS_EVENTS_DIRECTORY
    event_dir.mkdir(parents=True)
    event_path = event_dir / f"{scan_id}.json"
    assert _write_event_exclusive(event_path, event) is True

    recovered = update_finalized_analysis(tmp_path)

    assert recovered["processed_snapshot_count"] == 1
    assert recovered["processed_this_run"] == 1
    assert recovered["quarantined_snapshot_count"] == 0
    assert recovered["cumulative"]["quality_valid_pairs"] == 1


def test_analysis_catalog_v2_migration_adds_explicit_economic_status_columns(tmp_path):
    import sqlite3

    from midas.veritas.analysis_catalog import ANALYSIS_CATALOG_NAME, current_state

    _write_snapshot(tmp_path, "scan-catalog-migration", valid=True, reported_age_ms=1_000)
    update_finalized_analysis(tmp_path)
    catalog = tmp_path / ANALYSIS_CATALOG_NAME
    with sqlite3.connect(catalog) as connection:
        connection.execute("UPDATE catalog_meta SET value='2' WHERE key='catalog_version'")
        for name in (
            "snapshot_valid",
            "economic_supported",
            "net_economic_eligible",
            "source_quality_status",
            "fee_support_status",
            "independent_reference_version",
        ):
            connection.execute(f"ALTER TABLE analysis_observations DROP COLUMN {name}")
        connection.execute("ALTER TABLE analysis_events DROP COLUMN independent_reference_version")

    state = current_state(tmp_path)

    assert state["processed_snapshot_count"] == 1
    with sqlite3.connect(catalog) as connection:
        version = connection.execute(
            "SELECT value FROM catalog_meta WHERE key='catalog_version'"
        ).fetchone()[0]
        columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_observations)")}
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert version == "6"
    assert {
        "snapshot_valid",
        "economic_supported",
        "net_economic_eligible",
        "source_quality_status",
        "fee_support_status",
        "independent_reference_version",
    } <= columns
    assert integrity == "ok"


def test_corrupt_analysis_catalog_is_preserved_and_rebuilt_in_bounded_slices(tmp_path):
    import sqlite3

    from midas.veritas.analysis_catalog import ANALYSIS_CATALOG_NAME
    from midas.veritas.continuous_analysis import rebuild_analysis_catalog

    _write_snapshot(tmp_path, "scan-rebuild-001", valid=True, reported_age_ms=1_000)
    _write_snapshot(
        tmp_path,
        "scan-rebuild-002",
        valid=True,
        minutes_after=30,
        reported_age_ms=1_000,
    )
    update_finalized_analysis(tmp_path)
    catalog = tmp_path / ANALYSIS_CATALOG_NAME
    catalog.write_bytes(b"not a sqlite database")

    first = rebuild_analysis_catalog(tmp_path, max_pending=1)
    backup = tmp_path / str(first["preserved_corrupt_catalog"])
    second = rebuild_analysis_catalog(tmp_path, max_pending=1)

    assert first["status"] == "REBUILDING"
    assert backup.read_bytes() == b"not a sqlite database"
    assert first["analysis"]["processed_snapshot_count"] == 1
    assert first["analysis"]["pending_snapshot_count"] == 1
    assert second["status"] == "CURRENT"
    assert second["analysis"]["processed_snapshot_count"] == 2
    assert second["analysis"]["pending_snapshot_count"] == 0
    with sqlite3.connect(catalog) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert backup.exists()


def test_analysis_republishes_summary_from_committed_catalog_state(tmp_path):
    _write_snapshot(tmp_path, "scan-summary-after-db", valid=True)
    first = update_finalized_analysis(tmp_path)
    summary_path = tmp_path / "research-summary.json"
    summary_path.unlink()

    recovered = update_finalized_analysis(tmp_path)

    published = json.loads(summary_path.read_text())
    assert first["processed_snapshot_count"] == recovered["processed_snapshot_count"] == 1
    assert recovered["processed_this_run"] == 0
    assert published["measurement_status"] == "MEASURED"
    assert published["cumulative"]["quality_valid_pairs"] == 1


def test_snapshot_and_analysis_catalogs_join_for_independent_reaudit(tmp_path):
    from midas.veritas.scan_catalog import reconcile
    from midas.veritas.scan_catalog import summary as catalog_summary

    _write_snapshot(
        tmp_path,
        "scan-independent-join",
        valid=True,
        reported_age_ms=1_000,
    )
    reconcile(tmp_path)
    analysis = update_finalized_analysis(tmp_path)

    independent = catalog_summary(tmp_path)["independent_reaudit"]
    event_path = (
        tmp_path
        / "analysis-events"
        / "v6-independent-v2"
        / f"{Path(analysis['last_processed_snapshot_file']).name.removesuffix('.json.gz')}.json"
    )
    event = json.loads(event_path.read_text())
    economics = event["market_rows"][0]["independent_economic_reference"]

    assert independent["status"] == "MEASURED"
    assert independent["processed_scan_count"] == 1
    assert independent["matched_indexed_scan_count"] == 1
    assert independent["unprocessed_indexed_scan_count"] == 0
    assert independent["selected_market_observations"] == 1
    assert independent["quality_valid_pairs"] == 1
    assert independent["independent_economic_audit"]["agreement_on_all_measured_pairs"] is True
    assert independent["independent_economic_audit"]["reference_version"] == (
        "veritas-independent-economic-reference-v2"
    )
    assert economics["reference_version"] == "veritas-independent-economic-reference-v2"
    assert "levels_used" not in economics["quantity_results"][0]


def test_analysis_summary_publishes_bounded_details_with_exact_unique_counts(tmp_path):
    from midas.veritas.continuous_analysis import MAX_ANALYSIS_SUMMARY_BYTES

    _write_snapshot(tmp_path, "scan-bounded-summary", valid=True, candidate=True)

    result = update_finalized_analysis(tmp_path)
    summary_path = tmp_path / "research-summary.json"
    published = json.loads(summary_path.read_text())

    assert summary_path.stat().st_size <= MAX_ANALYSIS_SUMMARY_BYTES
    assert result["cumulative"]["unique_market_id_count"] == 1
    assert result["cumulative"]["unique_candidate_market_id_count"] == 1
    assert published["cumulative"]["unique_market_id_count"] == 1


def test_oversized_prior_summary_is_stream_preserved_before_bounded_republication(tmp_path):
    from midas.veritas.continuous_analysis import MAX_ANALYSIS_SUMMARY_BYTES

    _write_snapshot(tmp_path, "scan-summary-migration", valid=True)
    prior_summary = (
        b'{"schema_version":1,"analysis_version":"veritas-finalized-snapshot-analysis-v5",'
        b'"cumulative":{"padding":"' + b"x" * (3 * 1024 * 1024) + b'"}}'
    )
    summary_path = tmp_path / "research-summary.json"
    summary_path.write_bytes(prior_summary)

    result = update_finalized_analysis(tmp_path)

    preserved_path = tmp_path / "research-summary-veritas-finalized-snapshot-analysis-v5.json"
    published = json.loads(summary_path.read_text())
    assert preserved_path.read_bytes() == prior_summary
    assert summary_path.stat().st_size <= MAX_ANALYSIS_SUMMARY_BYTES
    assert published["analysis_version"] == "veritas-finalized-snapshot-analysis-v6"
    assert result["processed_snapshot_count"] == 1
