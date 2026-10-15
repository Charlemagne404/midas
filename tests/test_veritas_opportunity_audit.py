from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from midas.veritas.opportunity_audit import audit_pair_snapshot, normalize_market

CAPTURED_NS = 1_800_000_000_000_000_000
STAMP_MS = CAPTURED_NS // 1_000_000 - 100
CONDITION = "0x" + "a" * 64


def market(
    *,
    yes_label: str = "Yes",
    no_label: str = "No",
    version: str = "v1",
    fee_enabled: bool = False,
    fee_rate: str = "0.04",
    tick: str = "0.01",
) -> dict[str, Any]:
    outcomes = [yes_label, no_label]
    token_ids = ["11", "12"]
    return {
        "id": "100",
        "conditionId": CONDITION,
        "version": version,
        "outcomes": outcomes,
        "clobTokenIds": token_ids,
        # V1 responses can carry V2 identifiers too; version chooses the CTF IDs.
        "positionIds": ["111", "112"],
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "negRisk": False,
        "negRiskAugmented": False,
        "orderPriceMinTickSize": tick,
        "orderMinSize": "5",
        "feesEnabled": fee_enabled,
        "feeSchedule": {
            "rate": fee_rate,
            "exponent": 1,
            "takerOnly": True,
        }
        if fee_enabled
        else None,
    }


def normalized(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    result, reason = normalize_market(raw or market())
    assert reason is None
    assert result is not None
    return result


def book(
    asset: str,
    *,
    side: str,
    condition: str = CONDITION,
    timestamp: int = STAMP_MS,
    asks: list[dict[str, str]] | None = None,
    bids: list[dict[str, str]] | None = None,
    tick: str = "0.01",
    minimum: str = "5",
    neg_risk: bool = False,
) -> dict[str, Any]:
    if asks is None:
        asks = [{"price": ".4", "size": "100"} if side == "yes" else {"price": ".5", "size": "100"}]
    return {
        "asset_id": asset,
        "market": condition,
        "timestamp": str(timestamp),
        "hash": "h-" + asset,
        "asks": asks,
        "bids": bids or [{"price": ".3", "size": "100"}],
        "tick_size": tick,
        "min_order_size": minimum,
        "neg_risk": neg_risk,
    }


def pair_books(
    *,
    yes_asks: list[dict[str, str]] | None = None,
    no_asks: list[dict[str, str]] | None = None,
    yes_stamp: int = STAMP_MS,
    no_stamp: int = STAMP_MS,
    yes_tick: str = "0.01",
    no_minimum: str = "5",
) -> dict[str, dict[str, Any]]:
    return {
        "11": book("11", side="yes", asks=yes_asks, timestamp=yes_stamp, tick=yes_tick),
        "12": book("12", side="no", asks=no_asks, timestamp=no_stamp, minimum=no_minimum),
    }


def test_v1_uses_same_condition_yes_no_and_ignores_extra_v2_ids():
    result = normalized()
    assert result["protocol"] == "v1"
    assert result["outcomes"] == {"yes": "11", "no": "12"}
    assert result["pair_semantics"] == "same_condition_yes_no_ctf"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"version": "v2"}, "unsupported_protocol"),
        (
            {"outcomes": ["Yes", "No", "Other"], "clobTokenIds": ["11", "12", "13"]},
            "unsupported_outcome_relationship",
        ),
        ({"outcomes": ["Yes", "Maybe"]}, "unsupported_outcome_relationship"),
        ({"negRiskAugmented": True}, "augmented_negative_risk_semantics_unverified"),
        ({"closed": True}, "closed_or_unknown_lifecycle"),
        ({"orderPriceMinTickSize": "0"}, "invalid_market_constraints"),
    ],
)
def test_unsupported_or_invalid_market_semantics_are_excluded(changes, reason):
    raw = market()
    raw.update(changes)
    _, actual = normalize_market(raw)
    assert actual == reason


def test_best_ask_is_lowest_ask_and_depth_walk_sorts_levels_independently():
    yes = [{"price": ".41", "size": "10"}, {"price": ".40", "size": "10"}]
    no = [{"price": ".50", "size": "20"}]
    report = audit_pair_snapshot(
        normalized(),
        pair_books(yes_asks=yes, no_asks=no),
        captured_ns=CAPTURED_NS,
        quantities=("5", "20"),
    )
    assert report["valid"] is True
    assert report["best_ask_by_leg"] == {"yes": "0.40", "no": "0.50"}
    q5, q20 = report["quantity_results"]
    assert q5["positive_full_depth_gross"] is True
    assert q5["minimum_order_notional_satisfied"] is False
    assert q20["displayed_notional_usdc_by_leg"] == {"yes": "8.10", "no": "10.00"}
    assert q20["full_depth_gross_edge_usdc"] == "1.90"
    assert q20["minimum_order_notional_satisfied"] is True
    assert q20["positive_fragmentation_safe_sensitivity"] is True


@pytest.mark.parametrize(
    ("yes_ask", "no_ask", "edge"),
    [(".499", ".500", "0.001"), (".40", ".60", "0.00"), (".55", ".50", "-0.05")],
)
def test_tiny_positive_zero_and_negative_top_edges(yes_ask, no_ask, edge):
    raw = market(tick="0.001", fee_enabled=edge == "0.001")
    normalized_market = normalized(raw)
    books = pair_books(
        yes_asks=[{"price": yes_ask, "size": "100"}],
        no_asks=[{"price": no_ask, "size": "100"}],
    )
    books["11"]["tick_size"] = "0.001"
    books["12"]["tick_size"] = "0.001"
    normalized_market["tick_size"] = "0.001"
    report = audit_pair_snapshot(
        normalized_market,
        books,
        captured_ns=CAPTURED_NS,
        quantities=("20",),
    )
    assert report["valid"] is True
    assert report["top_pair_gross_edge_per_share"] == edge
    quantity = report["quantity_results"][0]
    assert quantity["positive_top_pair_gross"] is (Decimal(edge) > 0)
    if edge == "0.001":
        # q=20 gives $0.02 gross but the declared taker fee curve erases it.
        assert quantity["positive_full_depth_gross"] is True
        assert quantity["positive_single_match_sensitivity"] is False
        assert quantity["positive_fragmentation_safe_sensitivity"] is False


def test_positive_gross_with_insufficient_displayed_depth_is_not_a_candidate():
    books = pair_books(
        yes_asks=[{"price": ".4", "size": "4"}],
        no_asks=[{"price": ".5", "size": "100"}],
    )
    report = audit_pair_snapshot(normalized(), books, captured_ns=CAPTURED_NS, quantities=("5",))
    result = report["quantity_results"][0]
    assert result["top_pair_positive_gross"] is True
    assert result["full_depth"] is False
    assert result["positive_full_depth_gross"] is False


@pytest.mark.parametrize(
    ("books", "reason"),
    [
        (pair_books(yes_tick="0.02"), "yes_constraint_mismatch"),
        (pair_books(no_minimum="4"), "no_constraint_mismatch"),
        (pair_books(yes_asks=[{"price": ".405", "size": "100"}]), "yes_price_off_tick"),
    ],
)
def test_inconsistent_public_books_are_rejected(books, reason):
    report = audit_pair_snapshot(normalized(), books, captured_ns=CAPTURED_NS, quantities=("5",))
    assert report["valid"] is False
    assert report["reason"] == reason


def test_old_reported_book_timestamp_is_retained_as_a_diagnostic():
    old = pair_books(yes_stamp=STAMP_MS - 5_001)
    report = audit_pair_snapshot(normalized(), old, captured_ns=CAPTURED_NS, quantities=("5",))
    assert report["valid"] is True
    assert report["quality"]["reported_update_age_ms_by_leg"]["yes"] == 5_101
    assert report["quality"]["reported_update_age_above_diagnostic_threshold_by_leg"] == {
        "yes": True,
        "no": False,
    }
    assert report["quality"]["returned_in_same_batch_response"] is True
    assert report["quality"]["batch_atomicity_verified"] is False
    assert report["quality"]["sequence_verified"] is False


def test_reported_timestamp_skew_is_diagnostic_not_a_batch_capture_rejection():
    skewed = pair_books(yes_stamp=STAMP_MS - 251, no_stamp=STAMP_MS)
    report = audit_pair_snapshot(normalized(), skewed, captured_ns=CAPTURED_NS, quantities=("5",))
    assert report["valid"] is True
    assert report["quality"]["reported_update_timestamp_skew_ms"] == 251
    assert report["quality"]["reported_update_timestamp_skew_above_diagnostic_threshold"] is True


def test_slow_batch_and_far_future_reported_timestamp_are_rejected():
    report = audit_pair_snapshot(
        normalized(),
        pair_books(),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 5_001_000_000,
        quantities=("5",),
    )
    assert report["valid"] is False
    assert report["reason"] == "batch_request_too_slow_or_clock_regressed"

    future = pair_books(yes_stamp=CAPTURED_NS // 1_000_000 + 1_001)
    report = audit_pair_snapshot(normalized(), future, captured_ns=CAPTURED_NS, quantities=("5",))
    assert report["valid"] is False
    assert report["reason"] == "yes_timestamp_in_future"


def test_wrong_condition_is_rejected():
    wrong = pair_books()
    wrong["12"]["market"] = "0x" + "b" * 64
    report = audit_pair_snapshot(normalized(), wrong, captured_ns=CAPTURED_NS, quantities=("5",))
    assert report["reason"] == "no_book_identity_mismatch"


def test_fee_unavailable_does_not_hide_valid_positive_gross_evidence():
    raw = market(fee_enabled=True)
    raw["feeSchedule"] = {"rate": "0.02", "exponent": 2, "takerOnly": True}
    candidate = normalized(raw)
    report = audit_pair_snapshot(
        candidate, pair_books(), captured_ns=CAPTURED_NS, quantities=("20",)
    )
    quantity = report["quantity_results"][0]
    assert report["valid"] is True
    assert quantity["positive_full_depth_gross"] is True
    assert quantity["fee_status"] == "unsupported_or_invalid_schedule"
    assert quantity["hypothetical_fee_evaluation"] is None


def test_enabled_taker_fee_math_matches_independent_decimal_calculation():
    candidate = normalized(market(fee_enabled=True, fee_rate="0.04", tick="0.001"))
    books = pair_books(
        yes_asks=[{"price": ".499", "size": "20"}],
        no_asks=[{"price": ".500", "size": "20"}],
    )
    books["11"]["tick_size"] = "0.001"
    books["12"]["tick_size"] = "0.001"
    report = audit_pair_snapshot(candidate, books, captured_ns=CAPTURED_NS, quantities=("20",))
    result = report["quantity_results"][0]["hypothetical_fee_evaluation"]
    assert result is not None
    assert result["acquisition_cost_by_leg"] == {"yes": "9.980", "no": "10.000"}
    assert result["single_match_fee_total_usdc_by_rounding_mode"]["half_up"] == "0.40000"
    assert Decimal(result["net_hypothetical_single_match_worst_resolution"]) == Decimal(
        "-0.38080160320641282565130261"
    )
