from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from midas.veritas.observatory import _enrich_candidate
from midas.veritas.opportunity_audit import normalize_market
from midas.veritas.universe_coverage import analyze_market_universe_coverage


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _market(index: int, *, category: str = "Politics", spread: str = "0.01") -> dict[str, Any]:
    number = index + 1
    return {
        "id": str(800_000 + number),
        "conditionId": "0x" + f"{number:064x}",
        "version": "v1",
        "question": f"Fixture market {number}?",
        "slug": f"fixture-market-{number}",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": json.dumps([str(900_000 + number * 2), str(900_001 + number * 2)]),
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "negRisk": False,
        "negRiskAugmented": False,
        "restricted": False,
        "orderPriceMinTickSize": "0.01",
        "orderMinSize": 5,
        "feesEnabled": False,
        "liquidityNum": 1_500 + number * 100,
        "volume24hr": 100 + number,
        "endDate": "2027-06-01T00:00:00Z",
        "bestBid": "0.39",
        "bestAsk": "0.40",
        "spread": spread,
        "category": category,
        "events": [{"id": str(910_000 + number), "category": "Fixture"}],
    }


def _write_snapshot(
    snapshots_dir: Path,
    *,
    sequence: int,
    captured_ns: int,
    markets: list[dict[str, Any]],
    ask_shift: str,
) -> Path:
    pages: list[dict[str, Any]] = []
    for frame_index in range(6):
        rows = markets if frame_index == 0 else []
        payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False)
        payload_bytes = payload.encode()
        pages.append(
            {
                "query_id": f"frame_{frame_index}",
                "candidate_count": len(rows),
                "response_payload": payload,
                "response_bytes": len(payload_bytes),
                "response_sha256": _digest(payload_bytes),
            }
        )

    universe = []
    selected = []
    observations = []
    books_by_asset = []
    for raw in markets:
        normalized, reason = normalize_market(raw)
        assert normalized is not None and reason is None
        enriched = _enrich_candidate(raw, normalized, ["frame_0"])
        universe.append(
            {
                **enriched,
                "eligible_for_pair_observation": True,
                "exclusion_reason": None,
            }
        )
        selected.append(
            {
                **enriched,
                "cohort_role": "rotating_stratified",
                "selection_stratum": "fixture",
                "selection_probability": "1",
                "selection_probability_basis": "fixture_conditional_sample",
            }
        )
        yes_asset = normalized["outcomes"]["yes"]
        no_asset = normalized["outcomes"]["no"]
        timestamp_ms = captured_ns // 1_000_000 - 100
        yes_book = {
            "asset_id": yes_asset,
            "market": normalized["condition"],
            "timestamp": str(timestamp_ms),
            "hash": f"yes-{yes_asset}-{ask_shift}",
            "asks": [{"price": "0.40", "size": "100"}],
            "bids": [{"price": "0.39", "size": "100"}],
            "tick_size": "0.01",
            "min_order_size": "5",
            "neg_risk": False,
        }
        no_book = {
            "asset_id": no_asset,
            "market": normalized["condition"],
            "timestamp": str(timestamp_ms),
            "hash": f"no-{no_asset}",
            "asks": [{"price": "0.61", "size": "100"}],
            "bids": [{"price": "0.60", "size": "100"}],
            "tick_size": "0.01",
            "min_order_size": "5",
            "neg_risk": False,
        }
        books_by_asset.extend([yes_book, no_book])
        observations.append(
            {
                "market_id": normalized["market_id"],
                "condition": normalized["condition"],
                "outcomes": {"yes": yes_asset, "no": no_asset},
                "books": {yes_asset: yes_book, no_asset: no_book},
                "audit": {
                    "best_bid_by_leg": {"yes": "0.39", "no": "0.59"},
                    "best_ask_by_leg": {"yes": ask_shift, "no": "0.61"},
                    "quality": {
                        "reported_update_age_ms_by_leg": {"yes": 400, "no": 800},
                        "reported_update_timestamp_skew_ms": 100,
                    },
                    "payoff_identity": {
                        "yes_asset_id": yes_asset,
                        "no_asset_id": no_asset,
                    },
                },
            }
        )

    clob_payload = json.dumps(books_by_asset, separators=(",", ":"), ensure_ascii=False)
    clob_bytes = clob_payload.encode()
    clob_digest = _digest(clob_bytes)
    source_code_sha256 = "a" * 64
    sequence_seed = 101 + sequence
    evidence_material = {
        "gamma_response_hashes": [page["response_sha256"] for page in pages],
        "clob_response_sha256": clob_digest,
        "source_code_sha256": source_code_sha256,
        "captured_ns": captured_ns,
        "selection_seed": sequence_seed,
        "sequence": sequence,
    }
    evidence_sha256 = _digest(_canonical(evidence_material))
    captured = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC)
    scan_id = f"scan-{captured.strftime('%Y%m%dT%H%M%SZ')}-{evidence_sha256[:12]}"
    snapshot = {
        "scan_id": scan_id,
        "captured_ns": captured_ns,
        "captured_at_utc": captured.isoformat(),
        "source_code_sha256": source_code_sha256,
        "snapshot_evidence_sha256": evidence_sha256,
        "authenticated_requests": False,
        "orders_submitted": False,
        "discovery": {
            "query_count": 6,
            "query_candidate_records": len(markets),
            "unique_market_ids": len(markets),
            "duplicate_records_across_queries": 0,
            "identity_conflicts": 0,
            "eligible_pair_markets": len(markets),
            "excluded_market_ids": 0,
            "exclusion_reasons": {},
            "queries": pages,
            "universe": universe,
        },
        "selection": {
            "plan": {"seed": sequence_seed, "sequence": sequence, "phase": "liquidity"},
            "selected_markets": selected,
        },
        "source_requests": {
            "public_http_attempts": 7,
            "gamma_pages": pages,
            "clob_books": {
                "response_payload": clob_payload,
                "response_bytes": len(clob_bytes),
                "response_sha256": clob_digest,
                "requested_at_ns": captured_ns - 200_000_000,
                "received_at_ns": captured_ns,
                "request_asset_count": len(books_by_asset),
                "response_book_count": len(books_by_asset),
            },
        },
        "collection_bounds": {"gamma_queries_per_scan": 6, "target_markets": 40},
        "quantity_grid": ["5", "10", "20", "50", "100"],
        "market_observations": observations,
        "counts": {
            "selected_markets": len(markets),
            "valid_quality_pairs": len(markets),
            "positive_top_gross_pairs": 0,
            "invalid_reasons": {},
        },
    }
    path = snapshots_dir / f"{scan_id}.json.gz"
    path.write_bytes(gzip.compress(_canonical(snapshot)))
    return path


def test_coverage_report_counts_market_contract_and_asset_identity_separately(tmp_path: Path):
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()
    first_ns = 1_800_000_000_000_000_000
    first = _market(0, category="Politics", spread="0.01")
    second = _market(1, category="Sports", spread="0.06")
    first_path = _write_snapshot(
        snapshots_dir,
        sequence=1,
        captured_ns=first_ns,
        markets=[first],
        ask_shift="0.40",
    )
    first_snapshot = json.loads(gzip.decompress(first_path.read_bytes()))
    first_snapshot["counts"]["valid_quality_pairs"] = 0
    first_path.write_bytes(gzip.compress(_canonical(first_snapshot)))
    latest_path = _write_snapshot(
        snapshots_dir,
        sequence=2,
        captured_ns=first_ns + 1_800_000_000_000,
        markets=[first, second],
        ask_shift="0.41",
    )
    latest = json.loads(gzip.decompress(latest_path.read_bytes()))
    latest["market_observations"][0]["audit"]["payoff_identity"] = None
    latest_path.write_bytes(gzip.compress(_canonical(latest)))

    report = analyze_market_universe_coverage(snapshots_dir)

    assert report["source"]["snapshot_count"] == 2
    assert report["source"]["gamma_response_count"] == 12
    assert report["source"]["gamma_response_hashes_verified"] is True
    assert report["collection_protocol"]["total_quality_valid_market_pairs"] == 3
    assert report["collection_protocol"]["capture_recorded_quality_valid_market_pairs"] == 2
    assert report["collection_protocol"]["capture_vs_current_replay_valid_pair_delta"] == 1
    assert report["collection_protocol"]["scans_with_capture_vs_replay_count_mismatch"] == 1
    assert report["identity_coverage"]["distinct_gamma_market_ids_over_window"] == 2
    assert report["identity_coverage"]["distinct_condition_ids_over_window"] == 2
    assert report["identity_coverage"]["distinct_outcome_asset_ids_over_window"] == 4
    assert report["identity_coverage"]["latest_scan"]["distinct_selected_outcome_asset_ids"] == 4
    assert (
        report["identity_coverage"]["latest_scan"]["distinct_payoff_verified_outcome_asset_ids"]
        == 2
    )
    assert report["identity_coverage"]["selected_market_ids_over_window"] == 2
    assert report["freshness_and_sampled_activity"]["sampled_top_of_book_comparisons"] == 1
    assert report["freshness_and_sampled_activity"]["sampled_top_of_book_changed_comparisons"] == 1
    assert report["metadata_coverage"]["latest_scan_v1_eligible_population"][
        "liquidity_band_counts"
    ] == {"medium": 2}


def test_coverage_report_rejects_tampered_gamma_payload(tmp_path: Path):
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()
    path = _write_snapshot(
        snapshots_dir,
        sequence=1,
        captured_ns=1_800_000_000_000_000_000,
        markets=[_market(0)],
        ask_shift="0.40",
    )
    snapshot = json.loads(gzip.decompress(path.read_bytes()))
    snapshot["source_requests"]["gamma_pages"][0]["response_payload"] = "[]"
    snapshot["discovery"]["queries"][0]["response_payload"] = "[]"
    path.write_bytes(gzip.compress(_canonical(snapshot)))

    with pytest.raises(ValueError, match="digest mismatch"):
        analyze_market_universe_coverage(snapshots_dir)
