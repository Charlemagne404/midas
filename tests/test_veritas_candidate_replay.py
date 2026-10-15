from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.veritas.continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from midas.veritas.economic_experiment import compare_qualification_rules
from midas.veritas.opportunity_audit import audit_pair_snapshot, normalize_market


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sanitized(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": str(book.get("market") or "").casefold(),
        "asset_id": str(book.get("asset_id") or book.get("assetId") or ""),
        "timestamp": book.get("timestamp"),
        "hash": str(book.get("hash") or ""),
        "bids": book.get("bids") if isinstance(book.get("bids"), list) else [],
        "asks": book.get("asks") if isinstance(book.get("asks"), list) else [],
        "min_order_size": str(book.get("min_order_size") or ""),
        "tick_size": str(book.get("tick_size") or ""),
        "neg_risk": book.get("neg_risk"),
    }


def _write_source_fixture(root: Path) -> dict[str, Any]:
    captured_ns = int(datetime(2026, 10, 15, 6, 0, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    condition = "0x" + "11" * 32
    raw_market = {
        "id": "market-777",
        "conditionId": condition,
        "version": "v1",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "outcomes": ["YES", "NO"],
        "clobTokenIds": ["101", "102"],
        "negRisk": False,
        "orderPriceMinTickSize": "0.01",
        "orderMinSize": "5",
        "feesEnabled": False,
    }
    normalized, exclusion = normalize_market(raw_market)
    assert normalized is not None and exclusion is None
    market_metadata_sha256 = _sha256(_canonical(raw_market))
    raw_books = [
        {
            "asset_id": "101",
            "market": condition,
            "timestamp": str(captured_ns // 1_000_000 - 1_000),
            "hash": "yes-book-hash",
            "bids": [{"price": "0.48", "size": "100"}],
            "asks": [{"price": "0.49", "size": "100"}],
            "min_order_size": "5",
            "tick_size": "0.01",
            "neg_risk": False,
        },
        {
            "asset_id": "102",
            "market": condition,
            "timestamp": str(captured_ns // 1_000_000 - 1_000),
            "hash": "no-book-hash",
            "bids": [{"price": "0.49", "size": "100"}],
            "asks": [{"price": "0.50", "size": "100"}],
            "min_order_size": "5",
            "tick_size": "0.01",
            "neg_risk": False,
        },
    ]
    gamma_payload = json.dumps([raw_market], separators=(",", ":"))
    gamma_response = {
        "query_id": "fixture",
        "parameters": {"active": "true", "closed": "false", "limit": 50, "offset": 0},
        "candidate_count": 1,
        "requested_at_ns": captured_ns - 3_000_000,
        "received_at_ns": captured_ns - 2_000_000,
        "response_payload": gamma_payload,
        "response_sha256": _sha256(gamma_payload.encode()),
        "response_bytes": len(gamma_payload.encode()),
    }
    clob_payload = json.dumps(raw_books, separators=(",", ":"))
    requested_assets = [normalized["outcomes"]["yes"], normalized["outcomes"]["no"]]
    clob = {
        "requested_at_ns": captured_ns - 2_000_000,
        "received_at_ns": captured_ns,
        "request_attempts": 1,
        "request_asset_count": 2,
        "response_book_count": 2,
        "request_sha256": _sha256(_canonical([{"token_id": asset} for asset in requested_assets])),
        "response_payload": clob_payload,
        "response_sha256": _sha256(clob_payload.encode()),
        "response_bytes": len(clob_payload.encode()),
    }
    books = {book["asset_id"]: _sanitized(book) for book in raw_books}
    audit = audit_pair_snapshot(
        normalized,
        books,
        captured_ns=captured_ns,
        batch_started_ns=clob["requested_at_ns"],
        quantities=("5", "10", "20", "50", "100"),
    )
    assert audit["valid"] is True
    assert audit["positive_top_pair_gross"] is True
    selected = {
        **normalized,
        "raw_market_metadata_sha256": market_metadata_sha256,
        "cohort_role": "rotating_stratified",
        "categories": ["Fixture"],
        "selection_probability": "1",
        "selection_probability_basis": "synthetic fixture",
        "selection_stratum": "fixture",
    }
    gamma_pages = [gamma_response]
    source_code_sha256 = "a" * 64
    sequence = 1
    selection_seed = 20261015
    evidence_material = {
        "gamma_response_hashes": [gamma_response["response_sha256"]],
        "clob_response_sha256": clob["response_sha256"],
        "source_code_sha256": source_code_sha256,
        "captured_ns": captured_ns,
        "selection_seed": selection_seed,
        "sequence": sequence,
    }
    evidence_sha256 = _sha256(_canonical(evidence_material))
    scan_id = f"scan-20261015T060000Z-{evidence_sha256[:12]}"
    snapshot_file = f"snapshots/{scan_id}.json.gz"
    sampled_book_hash = _sha256(b"yes-book-hash|no-book-hash")
    observation = {
        "market_id": normalized["market_id"],
        "condition": normalized["condition"],
        "outcomes": normalized["outcomes"],
        "question": "Synthetic complement fixture",
        "categories": ["Fixture"],
        "cohort_role": "rotating_stratified",
        "selection_probability": "1",
        "selection_probability_basis": "synthetic fixture",
        "selection_stratum": "fixture",
        "raw_market_metadata_sha256": market_metadata_sha256,
        "audit": audit,
        "gross_positive_quantities": [
            row["quantity_shares_per_leg"]
            for row in audit["quantity_results"]
            if row["positive_full_depth_gross"]
        ],
        "positive_minimum_notional_quantities": [
            row["quantity_shares_per_leg"]
            for row in audit["quantity_results"]
            if row["positive_full_depth_gross"] and row["minimum_order_notional_satisfied"]
        ],
        "positive_single_match_quantities": [
            row["quantity_shares_per_leg"]
            for row in audit["quantity_results"]
            if row["positive_single_match_sensitivity"]
        ],
        "positive_fragmentation_safe_quantities": [
            row["quantity_shares_per_leg"]
            for row in audit["quantity_results"]
            if row["positive_fragmentation_safe_sensitivity"]
        ],
        "books": books,
        "book_source_sha256": clob["response_sha256"],
    }
    snapshot = {
        "analysis_version": "veritas-public-observatory-v2",
        "captured_at_utc": datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC).isoformat(
            timespec="microseconds"
        ),
        "captured_ns": captured_ns,
        "quantity_grid": ["5", "10", "20", "50", "100"],
        "scan_id": scan_id,
        "snapshot_file": snapshot_file,
        "snapshot_evidence_sha256": evidence_sha256,
        "source_code_sha256": source_code_sha256,
        "orders_submitted": False,
        "authenticated_requests": False,
        "selection": {
            "plan": {"sequence": sequence, "seed": selection_seed},
            "selected_markets": [selected],
        },
        "discovery": {
            "queries": gamma_pages,
            "universe": [{**selected, "eligible_for_pair_observation": True}],
        },
        "source_requests": {"gamma_pages": gamma_pages, "clob_books": clob},
        "market_observations": [observation],
    }
    event = {
        "analysis_version": SNAPSHOT_ANALYSIS_VERSION,
        "scan_id": scan_id,
        "snapshot_file": snapshot_file,
        "snapshot_evidence_sha256": evidence_sha256,
        "snapshot_source_code_sha256": source_code_sha256,
        "analysis_source_code_sha256": "b" * 64,
        "captured_at_utc": snapshot["captured_at_utc"],
        "captured_ns": captured_ns,
        "attempted_market_pairs": 1,
        "valid_quality_pairs": 1,
        "positive_top_gross_pairs": 1,
        "counts": {
            "positive_full_depth_gross_by_quantity": {"20": 1},
            "positive_minimum_notional_by_quantity": {"20": 1},
            "positive_single_match_fee_sensitivity_by_quantity": {"20": 1},
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": {"20": 1},
        },
        "market_rows": [
            {
                "market_id": normalized["market_id"],
                "categories": ["Fixture"],
                "cohort_role": "rotating_stratified",
                "valid": True,
                "legacy_freshness_valid": True,
                "legacy_freshness_invalid_reason": None,
                "top_pair_gross_edge_per_share": audit["top_pair_gross_edge_per_share"],
                "sampled_book_state_hash": sampled_book_hash,
            }
        ],
    }
    event["analysis_event_sha256"] = _sha256(_canonical(event))
    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / f"{scan_id}.json.gz").write_bytes(gzip.compress(_canonical(snapshot), mtime=0))
    event_dir = root / "analysis-events" / "v4"
    event_dir.mkdir(parents=True)
    (event_dir / f"{scan_id}.json").write_bytes(_canonical(event))
    return {"scan_id": scan_id, "snapshot": snapshot, "event": event}


def test_positive_candidate_replays_hashed_source_and_recomputes_economic_checks(tmp_path):
    _write_source_fixture(tmp_path)
    event_path = next((tmp_path / "analysis-events" / "v4").glob("scan-*.json"))
    event = json.loads(event_path.read_text())

    result = compare_qualification_rules([event], source_root=tmp_path)

    assert result["analysis_version"] == "veritas-economic-qualification-comparison-v3"
    assert result["gross_candidate_evidence_count"] == 1
    assert result["gross_candidate_replay"]["status"] == "ALL_GROSS_CANDIDATES_REPLAYED"
    assert result["gross_candidate_replay"]["complete"] is True
    replay = result["gross_candidate_replay"]["candidates"][0]
    assert replay["status"] == "GROSS_POSITIVE_REPLAYED_ECONOMIC_SENSITIVITIES_POSITIVE"
    assert replay["top_pair_gross_edge_per_share"] == "0.01"
    assert replay["independent_arithmetic"]["method"] == (
        "decimal_best_ask_and_sorted_depth_replay-v1"
    )
    assert replay["independent_arithmetic"]["full_depth_gross_edge_usdc"] == "0.20"
    assert replay["source_integrity"]["gamma_response_payloads_verified"] is True
    assert replay["source_integrity"]["clob_response_payload_verified"] is True
    assert replay["freshness"]["request_to_receipt_gate_passed"] is True
    assert replay["freshness"]["sequence_verified"] is False
    assert replay["quantity_qualification"]["full_displayed_depth"] is True
    assert replay["quantity_qualification"]["minimum_order_notional_satisfied_both_legs"] is True
    assert replay["quantity_qualification"]["fragmentation_safe_fee_sensitivity_positive"] is True
    assert replay["promotion_status"] == "BLOCKED_NO_SEQUENCE_OR_ORDER_ARRIVAL_EVIDENCE"
    assert result["gross_candidate_evidence"][0]["verification_status"] == (
        "GROSS_EDGE_SOURCE_REPLAYED"
    )


def test_candidate_replay_rejects_snapshot_book_payload_that_differs_from_hashed_response(
    tmp_path,
):
    fixture = _write_source_fixture(tmp_path)
    snapshot = fixture["snapshot"]
    snapshot["market_observations"][0]["books"]["101"]["asks"][0]["price"] = "0.30"
    snapshot_path = tmp_path / "snapshots" / f"{fixture['scan_id']}.json.gz"
    snapshot_path.write_bytes(gzip.compress(_canonical(snapshot), mtime=0))
    result = compare_qualification_rules([fixture["event"]], source_root=tmp_path)

    replay = result["gross_candidate_replay"]
    assert replay["complete"] is False
    assert replay["status"] == "SOURCE_REPLAY_FAILED"
    assert replay["candidates"][0]["reason"] == (
        "snapshot_book_payload_differs_from_hashed_clob_response"
    )
    assert result["gross_candidate_evidence_count"] == 1
