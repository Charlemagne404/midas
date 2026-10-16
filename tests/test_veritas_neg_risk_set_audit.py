from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from midas.veritas.neg_risk_set_audit import (
    EVENT_ID,
    EVENT_SLUG,
    EXPECTED_MARKET_IDS,
    GROUP_ID,
    audit_books,
    verify_event,
)


def _event() -> dict[str, Any]:
    labels = [
        "less than $2B",
        "between $2B and $3B",
        "between $3B and $4B",
        "between $4B and $5B",
        "between $5B and $7B",
        "between $7B and $10B",
        "between $10B and $15B",
        "at least $15B",
        "not IPO by December 31, 2027",
    ]
    markets = []
    for index, (market_id, label) in enumerate(zip(EXPECTED_MARKET_IDS, labels, strict=True)):
        token_base = 10_000 + index * 2
        markets.append(
            {
                "id": market_id,
                "question": f"Will Strava’s market cap be {label} at market close on IPO day?",
                "negRisk": True,
                "negRiskAugmented": None,
                "negRiskMarketID": GROUP_ID,
                "version": "v1",
                "active": True,
                "closed": False,
                "acceptingOrders": True,
                "enableOrderBook": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps([str(token_base), str(token_base + 1)]),
                "conditionId": f"0x{index + 1:064x}",
                "feesEnabled": True,
                "feeSchedule": {"rate": 0.04, "exponent": 1, "takerOnly": True},
                "orderPriceMinTickSize": 0.001 if index % 2 == 0 else 0.01,
                "orderMinSize": 5,
            }
        )
    return {
        "id": EVENT_ID,
        "slug": EVENT_SLUG,
        "description": (
            "If no Strava IPO occurs by December 31, 2027, this market resolves to No IPO. "
            "If the relevant value falls exactly between two brackets, it resolves to the "
            "higher range bracket."
        ),
        "negRisk": True,
        "negRiskAugmented": False,
        "negRiskMarketID": GROUP_ID,
        "active": True,
        "closed": False,
        "markets": markets,
    }


def _books(
    markets: list[dict[str, Any]],
    *,
    timestamp_ms: int = 1_700_000_000_000,
    side: str = "yes",
) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": market[f"{side}_token_id"],
            "market": market["condition_id"],
            "neg_risk": True,
            "timestamp": str(timestamp_ms),
            "tick_size": market["tick_size"],
            "min_order_size": market["minimum_order_shares"],
            "asks": [{"price": "0.100", "size": "200"}],
        }
        for market in markets
    ]


def test_verify_event_requires_complete_nonoverlapping_event_ranges() -> None:
    markets = verify_event(_event())

    assert len(markets) == 9
    assert [row["market_id"] for row in markets] == list(EXPECTED_MARKET_IDS)
    assert [row["outcome_interval_billions"] for row in markets[:8]] == [
        {"lower_inclusive": "0", "upper_exclusive": "2"},
        {"lower_inclusive": "2", "upper_exclusive": "3"},
        {"lower_inclusive": "3", "upper_exclusive": "4"},
        {"lower_inclusive": "4", "upper_exclusive": "5"},
        {"lower_inclusive": "5", "upper_exclusive": "7"},
        {"lower_inclusive": "7", "upper_exclusive": "10"},
        {"lower_inclusive": "10", "upper_exclusive": "15"},
        {"lower_inclusive": "15", "upper_exclusive": None},
    ]
    assert markets[-1]["outcome_interval_billions"] is None


@pytest.mark.parametrize("mutation", ["missing_member", "gap", "wrong_group", "augmented"])
def test_verify_event_fails_closed_on_incomplete_or_changed_structure(mutation: str) -> None:
    event = _event()
    if mutation == "missing_member":
        event["markets"].pop()
    elif mutation == "gap":
        event["markets"][1]["question"] = "Will Strava’s market cap be between $2.1B and $3B?"
    elif mutation == "wrong_group":
        event["markets"][0]["negRiskMarketID"] = "0x" + "0" * 64
    else:
        event["negRiskAugmented"] = True

    with pytest.raises(ValueError):
        verify_event(event)


def test_audit_books_reports_positive_full_depth_after_fee_sensitivity() -> None:
    markets = verify_event(_event())
    captured_ns = 1_700_000_000_000_000_000
    result = audit_books(
        markets,
        _books(markets),
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 100_000_000,
    )

    assert result["quality"]["valid"] is True
    assert result["top_of_book"]["complete_yes_set_best_ask_sum_usdc"] == "0.900"
    assert result["top_of_book"]["gross_edge_per_set_usdc"] == "0.100"
    first = result["quantity_scenarios"][0]
    assert first["quantity_per_outcome_shares"] == "5"
    assert first["complete_depth"] is True
    assert first["all_minimum_share_sizes_satisfied"] is True
    assert first["displayed_gross_edge_usdc"] == "0.500"
    assert first["fragmentation_safe_upper_fee_usdc"] == "0.32400"
    assert first["positive_fragmentation_safe_after_fee"] is True
    assert result["actual_fills"] == "unknown_counterfactual"
    assert result["orders_submitted"] is False


def test_audit_books_rejects_missing_stale_and_skewed_book_batches() -> None:
    markets = verify_event(_event())
    captured_ns = 1_700_000_000_000_000_000
    books = _books(markets)
    books.pop()
    books[0]["timestamp"] = "1699999990000"
    books[1]["timestamp"] = "1699999999500"
    result = audit_books(
        markets,
        books,
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 100_000_000,
    )

    assert result["quality"]["valid"] is False
    assert "book_asset_set_does_not_match_complete_yes_set" in result["quality"]["issues"]
    assert "market_1185108_book_fields_invalid" in result["quality"]["issues"]
    assert "book_timestamp_skew_outside_bound" in result["quality"]["issues"]
    assert result["quantity_scenarios"][0]["positive_fragmentation_safe_after_fee"] is False


def test_stale_books_keep_descriptive_economics_but_never_qualify() -> None:
    markets = verify_event(_event())
    captured_ns = 1_700_000_000_000_000_000
    books = _books(markets)
    books[0]["timestamp"] = "1699999994000"
    result = audit_books(
        markets,
        books,
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 100_000_000,
        include_stale_quotes_for_descriptive_math=True,
    )

    assert result["quality"]["valid"] is False
    assert result["quality"]["max_source_timestamp_age_ms"] == 6_000
    assert "market_1185108_source_timestamp_age_outside_bound" in result["quality"]["issues"]
    assert result["top_of_book"]["gross_edge_per_set_usdc"] == "0.100"
    assert result["top_of_book"]["positive_gross"] is False
    first = result["quantity_scenarios"][0]
    assert first["complete_depth"] is True
    assert first["displayed_gross_edge_usdc"] == "0.500"
    assert first["positive_full_depth_gross"] is False
    assert first["positive_fragmentation_safe_after_fee"] is False


def test_complete_no_basket_uses_protocol_minimum_payout_floor() -> None:
    markets = verify_event(_event())
    captured_ns = 1_700_000_000_000_000_000
    result = audit_books(
        markets,
        _books(markets, side="no"),
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 100_000_000,
        side="no",
        payout_shares_per_set=Decimal(8),
        payoff_description="At least eight payout shares under the at-most-one-Yes rule",
    )

    assert result["quality"]["valid"] is True
    assert result["payoff_basket"] == "no"
    assert result["minimum_payout_shares_per_set"] == "8"
    assert result["top_of_book"]["complete_no_set_best_ask_sum_usdc"] == "0.900"
    assert result["top_of_book"]["gross_edge_per_set_usdc"] == "7.100"
    first = result["quantity_scenarios"][0]
    assert first["displayed_gross_edge_usdc"] == "35.500"
    assert first["positive_fragmentation_safe_after_fee"] is True
