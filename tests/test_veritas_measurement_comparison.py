from __future__ import annotations

from midas.veritas.measurement_comparison import compare_timestamp_gate

CONDITION = "0x" + "a" * 64
CAPTURED_NS = 1_800_000_000_000_000_000
REPORTED_TIMESTAMP_MS = CAPTURED_NS // 1_000_000 - 10_000


def test_same_snapshot_comparison_repairs_age_censoring_without_changing_prices():
    market = {
        "market_id": "100",
        "condition": CONDITION,
        "protocol": "v1",
        "pair_semantics": "same_condition_yes_no_ctf",
        "outcomes": {"yes": "11", "no": "12"},
        "negative_risk": False,
        "tick_size": "0.01",
        "minimum_order_notional_usdc": "5",
        "fee_regime": {"status": "verified_disabled"},
        "eligible_for_pair_observation": True,
    }

    def book(asset_id: str, price: str) -> dict:
        return {
            "market": CONDITION,
            "asset_id": asset_id,
            "timestamp": str(REPORTED_TIMESTAMP_MS),
            "hash": f"hash-{asset_id}",
            "bids": [{"price": "0.30", "size": "100"}],
            "asks": [{"price": price, "size": "100"}],
            "min_order_size": "5",
            "tick_size": "0.01",
            "neg_risk": False,
        }

    report = {
        "scan_id": "scan-20261015T060201Z-517641164ed1",
        "snapshot_file": "snapshots/scan-20261015T060201Z-517641164ed1.json.gz",
        "snapshot_evidence_sha256": "evidence-hash",
        "source_code_sha256": "old-observer-hash",
        "captured_ns": CAPTURED_NS,
        "discovery": {"universe": [market]},
        "counts": {
            "valid_quality_pairs": 0,
            "invalid_reasons": {"yes_book_stale": 1},
        },
        "source_requests": {
            "clob_books": {
                "requested_at_ns": CAPTURED_NS - 100_000_000,
                "received_at_ns": CAPTURED_NS,
                "response_sha256": "clob-response-hash",
            },
            "gamma_pages": [{"response_sha256": "gamma-response-hash"}],
        },
        "market_observations": [
            {
                "market_id": "100",
                "books": {"11": book("11", "0.40"), "12": book("12", "0.50")},
                "audit": {"valid": False, "reason": "yes_book_stale"},
            }
        ],
    }

    comparison = compare_timestamp_gate(report, quantities=("5",))

    assert comparison["original_gate"]["quality_valid_pairs"] == 0
    assert comparison["original_gate"]["invalid_reasons"] == {"yes_book_stale": 1}
    assert comparison["corrected_gate"]["quality_valid_pairs"] == 1
    assert comparison["corrected_gate"]["invalid_reasons"] == {}
    assert comparison["corrected_gate"]["positive_top_gross_pairs"] == 1
    assert comparison["corrected_gate"]["positive_full_depth_gross_by_quantity"] == {"5": 1}
    assert comparison["corrected_gate"]["reported_update_age_above_5s_by_leg"] == {
        "yes": 1,
        "no": 1,
    }
    assert comparison["corrected_gate"]["batch_atomicity_verified"] is False
    assert comparison["source_lineage"]["clob_response_sha256"] == "clob-response-hash"
    assert comparison["orders_submitted"] is False
