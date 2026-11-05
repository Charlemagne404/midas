from __future__ import annotations

from copy import deepcopy
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from midas.veritas.independent_economics import (
    audit_complementary_pair_economics,
    compare_pair_economics,
)
from midas.veritas.opportunity_audit_v2 import audit_pair_snapshot

CAPTURED_NS = 1_792_044_000_000_000_000


def _fixture(*, candidate: bool = False):
    captured_ns = CAPTURED_NS
    timestamp = str(captured_ns // 1_000_000 - 1_000)
    market = {
        "protocol": "v1",
        "pair_semantics": "same_condition_yes_no_ctf",
        "condition": "0x" + "1" * 64,
        "outcomes": {"yes": "11", "no": "12"},
        "negative_risk": False,
        "tick_size": "0.01",
        "minimum_order_notional_usdc": "5",
        "minimum_order_notional_source": "test.fixture",
        "minimum_order_notional_unit_status": "verified_usdc",
        "active": True,
        "closed": False,
        "accepting_orders": True,
        "orderbook_enabled": True,
        "restricted": False,
        "fee_regime": {
            "enabled": False,
            "status": "verified_disabled",
            "rate": "0",
            "exponent": "1",
        },
    }
    yes_ask = "0.40" if candidate else "0.50"
    books = {
        "11": {
            "market": "0x" + "1" * 64,
            "asset_id": "11",
            "timestamp": timestamp,
            "neg_risk": False,
            "tick_size": "0.01",
            "min_order_size": "5",
            "bids": [{"price": "0.30", "size": "100"}],
            "asks": [{"price": yes_ask, "size": "100"}],
        },
        "12": {
            "market": "0x" + "1" * 64,
            "asset_id": "12",
            "timestamp": timestamp,
            "neg_risk": False,
            "tick_size": "0.01",
            "min_order_size": "5",
            "bids": [{"price": "0.30", "size": "100"}],
            "asks": [{"price": "0.50", "size": "100"}],
        },
    }
    quantities = ("5", "10", "20")
    primary = audit_pair_snapshot(
        market,
        books,
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 10_000_000,
        request_duration_ms=10,
        quantities=quantities,
    )
    reference = audit_complementary_pair_economics(
        market,
        books,
        quantities,
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 10_000_000,
        request_duration_ms=10,
    )
    return market, books, primary, reference


def test_decimal_reference_matches_primary_top_depth_constraints_and_fee_reference():
    _market, _books, primary, reference = _fixture()

    assert primary["valid"] is True
    assert reference["valid"] is True
    assert compare_pair_economics(primary, reference) == []
    assert reference["top_pair_gross_edge_per_share"] == "0.00"
    assert reference["quantity_results"][-1]["full_depth"] is True


def test_decimal_reference_finds_positive_top_edge_without_reusing_primary_result():
    _market, _books, primary, reference = _fixture(candidate=True)

    assert primary["positive_top_pair_gross"] is True
    assert reference["positive_top_pair_gross"] is True
    assert reference["top_pair_gross_edge_per_share"] == "0.10"
    assert compare_pair_economics(primary, reference) == []


def test_restricted_flag_does_not_hide_book_math_or_masquerade_as_source_failure():
    market, books, primary, _reference = _fixture(candidate=True)
    market["restricted"] = True

    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5", "10", "20"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["snapshot_valid"] is True
    assert reference["source_quality"]["status"] == "pass"
    assert reference["execution_scope"]["market_restricted_flag"] is True
    assert reference["execution_scope"]["market_restriction_status"] == "flagged"
    assert reference["execution_scope"]["user_geoblock_status"] == "not_measured"
    assert reference["execution_scope"]["execution_status"] == "not_established"
    assert reference["positive_top_pair_gross"] is True
    assert compare_pair_economics(primary, reference) == []


def test_missing_restricted_flag_stays_unmeasured_instead_of_defaulting_clear():
    market, books, _primary, _reference = _fixture()
    market.pop("restricted")

    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["snapshot_valid"] is True
    assert reference["execution_scope"]["market_restricted_flag"] is None
    assert reference["execution_scope"]["market_restriction_status"] == "unmeasured"
    assert reference["execution_scope"]["execution_status"] == "not_established"


def test_unmeasured_reference_quality_is_not_counted_as_a_quality_disagreement():
    market, books, primary, _reference = _fixture()
    market["active"] = False

    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["source_quality"]["status"] == "unmeasured"
    assert reference["reason"] == "market_lifecycle_ineligible"
    assert compare_pair_economics(primary, reference) == ["validity"]


def test_decimal_reference_preserves_high_precision_price_arithmetic_exactly():
    market, books, _primary, _reference = _fixture()
    market["tick_size"] = "0.00000000000000000000000000001"
    books["11"]["tick_size"] = market["tick_size"]
    books["12"]["tick_size"] = market["tick_size"]
    books["11"]["asks"] = [{"price": "0.40000000000000000000000000001", "size": "100"}]
    books["12"]["asks"] = [{"price": "0.50000000000000000000000000001", "size": "100"}]

    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["valid"] is True
    assert reference["top_pair_gross_edge_per_share"] == "0.09999999999999999999999999998"
    assert reference["quantity_results"][0]["full_depth_gross_edge_usdc"] == (
        "0.49999999999999999999999999990"
    )


def test_decimal_reference_rejects_unbounded_input_and_book_depth():
    market, books, _primary, _reference = _fixture()
    books["11"]["asks"] = [{"price": "0.40", "size": "1"} for _ in range(10_001)]

    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["valid"] is False
    assert reference["reason"] == "invalid_asks_levels"


def test_decimal_reference_recomputes_fee_curve_after_independent_depth_walk():
    market, books, _primary, _reference = _fixture(candidate=True)
    market["fee_regime"] = {
        "status": "verified_taker_curve",
        "enabled": True,
        "rate": "0.1",
        "exponent": "1",
        "settlement_rounding_status": "verified",
    }
    books[market["outcomes"]["yes"]]["asks"] = [
        {"price": "0.40", "size": "5"},
        {"price": "0.40", "size": "5"},
        {"price": "0.50", "size": "100"},
    ]
    captured_ns = CAPTURED_NS
    primary = audit_pair_snapshot(
        market,
        books,
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 10_000_000,
        request_duration_ms=10,
        quantities=("20",),
    )
    reference = audit_complementary_pair_economics(
        market,
        books,
        ("20",),
        captured_ns=captured_ns,
        batch_started_ns=captured_ns - 10_000_000,
        request_duration_ms=10,
    )

    assert primary["valid"] is True
    assert reference["valid"] is True
    assert reference["quantity_results"][0]["independent_fee_reference_by_leg"] is not None
    assert compare_pair_economics(primary, reference) == []


def test_independent_fee_upper_covers_unequal_fragmentation_across_price_levels():
    market, books, _primary, _reference = _fixture(candidate=True)
    market["fee_regime"] = {
        "enabled": True,
        "status": "verified_taker_curve",
        "rate": "0.1",
        "exponent": "1",
        "settlement_rounding_status": "verified",
    }
    books["11"]["asks"] = [
        {"price": "0.40", "size": "4"},
        {"price": "0.41", "size": "7"},
        {"price": "0.45", "size": "9"},
    ]
    books["12"]["asks"] = [
        {"price": "0.50", "size": "3"},
        {"price": "0.51", "size": "8"},
        {"price": "0.52", "size": "9"},
    ]
    reference = audit_complementary_pair_economics(
        market,
        books,
        ("20",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )
    row = reference["quantity_results"][0]
    quantum = Decimal("0.00001")
    rate = Decimal("0.1")

    assert reference["snapshot_valid"] is True
    for side, asset in (("yes", "11"), ("no", "12")):
        realized_floor = Decimal(0)
        realized_half_up = Decimal(0)
        for level in books[asset]["asks"]:
            price = Decimal(level["price"])
            size = Decimal(level["size"])
            fragments = (
                size * Decimal("0.01"),
                size * Decimal("0.09"),
                size * Decimal("0.35"),
                size * Decimal("0.55"),
            )
            assert sum(fragments, Decimal(0)) == size
            for fragment in fragments:
                raw_fee = fragment * rate * price * (1 - price)
                realized_floor += raw_fee.quantize(quantum, rounding=ROUND_DOWN)
                realized_half_up += raw_fee.quantize(quantum, rounding=ROUND_HALF_UP)

        bound = Decimal(
            row["independent_fee_reference_by_leg"][side]["fragmentation_safe_fee_collateral_upper"]
        )
        assert realized_floor <= bound
        assert realized_half_up <= bound


def test_independent_reference_vetoes_a_crossed_book_the_primary_path_accepts():
    market, books, _primary, _reference = _fixture()
    crossed_books = deepcopy(books)
    crossed_books[market["outcomes"]["yes"]]["bids"] = [{"price": "0.60", "size": "10"}]

    primary = audit_pair_snapshot(
        market,
        crossed_books,
        captured_ns=1_792_044_000_000_000_000,
        quantities=("5", "10"),
    )
    reference = audit_complementary_pair_economics(
        market,
        crossed_books,
        ("5", "10"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert primary["valid"] is True
    assert reference["valid"] is False
    assert reference["reason"] == "yes_crossed_book"


def test_independent_reference_rejects_off_tick_prices():
    market, books, _primary, _reference = _fixture()
    off_tick_books = deepcopy(books)
    off_tick_books[market["outcomes"]["yes"]]["asks"][0]["price"] = "0.505"

    reference = audit_complementary_pair_economics(
        market,
        off_tick_books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["valid"] is False
    assert reference["reason"] == "asks_price_off_tick"


def test_independent_reference_rejects_prices_outside_executable_tick_bounds():
    market, books, _primary, _reference = _fixture()
    boundary_books = deepcopy(books)
    boundary_books["11"]["asks"] = [{"price": "0.00", "size": "10"}]

    reference = audit_complementary_pair_economics(
        market,
        boundary_books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["valid"] is False
    assert reference["reason"] == "invalid_asks_level_value"


def test_independent_comparison_exposes_depth_disagreement():
    _market, _books, primary, reference = _fixture()
    altered = deepcopy(reference)
    altered["quantity_results"][0]["full_depth"] = not altered["quantity_results"][0]["full_depth"]

    assert "depth:5" in compare_pair_economics(primary, altered)


def test_independent_reference_rejects_stale_source_and_reports_validity_disagreement():
    market, books, primary, _reference = _fixture()
    stale_books = deepcopy(books)
    stale_timestamp = str(CAPTURED_NS // 1_000_000 - 5_001)
    stale_books["11"]["timestamp"] = stale_timestamp
    stale_books["12"]["timestamp"] = stale_timestamp
    reference = audit_complementary_pair_economics(
        market,
        stale_books,
        ("5", "10"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert primary["valid"] is True
    assert reference["valid"] is False
    assert reference["source_quality"]["status"] == "fail"
    assert reference["reason"] == "yes_source_timestamp_stale"
    assert {"validity", "source_quality"} <= set(compare_pair_economics(primary, reference))


def test_unsupported_fee_schedule_is_not_economic_support():
    market, books, primary, _reference = _fixture(candidate=True)
    market["fee_regime"] = {
        "enabled": True,
        "status": "unsupported_or_invalid_schedule",
    }
    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5", "10", "20"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert primary["valid"] is True
    assert reference["valid"] is True
    assert reference["economic_supported"] is False
    assert reference["economically_eligible"] is False
    assert compare_pair_economics(primary, reference) == []


def test_reference_calculates_complete_position_net_and_minimum_constraints():
    market, books, _primary, _reference = _fixture(candidate=True)
    market["fee_regime"] = {
        "enabled": True,
        "status": "verified_taker_curve",
        "rate": "0.1",
        "exponent": "1",
        "settlement_rounding_status": "verified",
    }
    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5", "20"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )
    small, large = reference["quantity_results"]

    assert small["entry_collateral_usdc"] == "4.50"
    assert small["minimum_order_constraints_satisfied"] is False
    assert large["entry_collateral_usdc"] == "18.00"
    assert (
        large["complete_position_net_sensitivities_usdc"]["fragmentation_safe_upper_net_usdc"]
        == "0.04000"
    )
    assert large["economically_eligible"] is True


def test_unverified_minimum_unit_and_fee_rounding_block_economic_eligibility():
    market, books, _primary, _reference = _fixture(candidate=True)
    market.pop("minimum_order_notional_unit_status")
    market["fee_regime"] = {
        "enabled": True,
        "status": "verified_taker_curve",
        "rate": "0.1",
        "exponent": "1",
    }
    # Keep both implementations on the same changed source assumptions. The
    # earlier fixture result used verified USDC minimum units and disabled fees.
    primary = audit_pair_snapshot(
        market,
        books,
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
        quantities=("5", "10", "20"),
    )
    reference = audit_complementary_pair_economics(
        market,
        books,
        ("5", "10", "20"),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
        request_duration_ms=10,
    )

    assert reference["snapshot_valid"] is True
    assert reference["economic_supported"] is False
    assert reference["economic_status"] == "fee_settlement_rounding_unverified"
    assert reference["constraint_support"]["market_minimum_notional"]["unit_status"] == "unverified"
    quantity_20 = next(
        row for row in reference["quantity_results"] if row["quantity_shares_per_leg"] == "20"
    )
    assert quantity_20["minimum_order_notional_satisfied"] is None
    assert quantity_20["independent_fee_reference_by_leg"] is not None
    assert reference["economically_eligible"] is False
    assert compare_pair_economics(primary, reference) == []


def test_reference_rejects_future_source_timestamps_and_unmeasured_request_timing():
    market, books, _primary, _reference = _fixture()
    future_books = deepcopy(books)
    future_books["11"]["timestamp"] = str(CAPTURED_NS // 1_000_000 + 1)
    reference = audit_complementary_pair_economics(
        market,
        future_books,
        ("5",),
        captured_ns=CAPTURED_NS,
        batch_started_ns=CAPTURED_NS - 10_000_000,
    )
    unmeasured = audit_complementary_pair_economics(market, books, ("5",), captured_ns=CAPTURED_NS)

    assert reference["reason"] == "yes_source_timestamp_in_future"
    assert unmeasured["reason"] == "request_timing_unavailable"
