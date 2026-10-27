from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Literal

import pytest
from midas.frontier.economics import (
    estimate_kalshi_taker_fee_sensitivity,
    estimate_kalshi_taker_order_fee_sensitivity,
)
from midas.frontier.models import KalshiFeeMetadata, KalshiFeeOrderFillInput

from tests.frontier.builders import T0


def fee_metadata(*, fee_type: str = "quadratic", multiplier: str = "1") -> KalshiFeeMetadata:
    return KalshiFeeMetadata(
        adapter_version="frontier-kalshi-fees-test-v1",
        native_market_id="KX-FEE-1",
        native_event_id="KX-FEE-EVENT-1",
        series_ticker="KX-FEE-SERIES",
        event_fee_type_override=None,
        event_fee_multiplier_override=None,
        series_fee_type=fee_type,
        series_fee_multiplier=Decimal(multiplier),
        effective_fee_type=fee_type,
        effective_fee_multiplier=Decimal(multiplier),
        fee_resolution_state="series_inherited",
        event_fee_type_override_field_present=False,
        event_fee_multiplier_override_field_present=False,
        event_raw_sha256="a" * 64,
        series_raw_sha256="b" * 64,
        event_received_at_utc=T0,
        series_received_at_utc=T0 + timedelta(milliseconds=5),
    )


def order_fill(
    *,
    side: Literal["buy", "sell"] = "buy",
    price: str = "0.06",
    quantity: str = "1",
    instrument: str = "KX-FEE-1:YES",
) -> KalshiFeeOrderFillInput:
    return KalshiFeeOrderFillInput(
        native_instrument_id=instrument,
        side=side,
        price_usd=Decimal(price),
        quantity_contracts=Decimal(quantity),
    )


def test_taker_fee_sensitivity_preserves_public_override_and_account_precision_cases():
    metadata = fee_metadata(multiplier="3")
    inputs = {
        "event_observation_id": "c" * 64,
        "series_observation_id": "d" * 64,
        "price_usd": Decimal("0.5"),
        "quantity_contracts": Decimal("1"),
    }
    result = estimate_kalshi_taker_fee_sensitivity(metadata, **inputs)

    assert result.schema_version == 2
    assert result.model_version.endswith("-v2")
    assert result.effective_fee_multiplier == Decimal(3)
    assert result.position_cost_usd == Decimal("0.5")
    assert [item.account_precision_class for item in result.scenarios] == [
        "direct_member",
        "non_direct_member",
    ]
    assert [item.model_fee_before_rounding for item in result.scenarios] == [
        Decimal("0.0525"),
        Decimal("0.0525"),
    ]
    assert [item.total_modeled_fee for item in result.scenarios] == [
        Decimal("0.0525"),
        Decimal("0.06"),
    ]
    assert [item.total_modeled_debit for item in result.scenarios] == [
        Decimal("0.5525"),
        Decimal("0.56"),
    ]
    assert (
        result.calculation_sha256
        == estimate_kalshi_taker_fee_sensitivity(metadata, **inputs).calculation_sha256
    )
    assert any("no order was submitted" in item for item in result.assumptions)


def test_taker_fee_sensitivity_rounds_trade_fee_and_position_debit_separately():
    result = estimate_kalshi_taker_fee_sensitivity(
        fee_metadata(),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        price_usd=Decimal("0.37"),
        quantity_contracts=Decimal("3"),
    )

    assert result.scenarios[0].model_fee_before_rounding == Decimal("0.048951")
    assert result.scenarios[0].trade_fee_rounded_to_microdollar == Decimal("0.048951")
    assert result.scenarios[0].total_modeled_fee == Decimal("0.0490")
    assert result.scenarios[0].balance_rounding_adjustment == Decimal("0.000049")
    assert result.scenarios[1].total_modeled_fee == Decimal("0.05")
    assert result.scenarios[1].balance_rounding_adjustment == Decimal("0.001049")


def test_non_direct_rounding_matches_kalshi_documented_fill_example():
    result = estimate_kalshi_taker_fee_sensitivity(
        fee_metadata(),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        price_usd=Decimal("0.055"),
        quantity_contracts=Decimal("1"),
    )

    assert result.scenarios[1].model_fee_before_rounding == Decimal("0.00363825")
    assert result.scenarios[1].trade_fee_rounded_to_microdollar == Decimal("0.003639")
    assert result.scenarios[1].balance_rounding_adjustment == Decimal("0.001361")
    assert result.scenarios[1].total_modeled_fee == Decimal("0.005")
    assert result.scenarios[1].total_modeled_debit == Decimal("0.06")


def test_order_fee_sensitivity_accumulates_rounding_and_caps_rebates_per_fill():
    fills = (order_fill(), order_fill())
    result = estimate_kalshi_taker_order_fee_sensitivity(
        fee_metadata(),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        order_fills=fills,
    )

    assert result.schema_version == 2
    assert result.model_version.endswith("-v2")
    direct, non_direct = result.scenarios
    assert [fill.rounding_fee_usd for fill in non_direct.fills] == [
        Decimal("0.006052"),
        Decimal("0.006052"),
    ]
    assert [fill.rebate_usd for fill in non_direct.fills] == [Decimal(0), Decimal("0.01")]
    assert non_direct.fills[1].accumulated_rounding_before_rebate_usd == Decimal("0.012104")
    assert non_direct.fills[1].accumulated_rounding_after_rebate_usd == Decimal("0.002104")
    assert non_direct.total_trade_fee_usd == Decimal("0.007896")
    assert non_direct.total_rounding_fee_usd == Decimal("0.012104")
    assert non_direct.total_rebate_usd == Decimal("0.01")
    assert non_direct.total_net_fee_usd == Decimal("0.01")
    assert non_direct.total_balance_change_usd == Decimal("-0.13")

    assert [fill.rebate_usd for fill in direct.fills] == [Decimal(0), Decimal("0.0001")]
    assert direct.fills[1].accumulated_rounding_after_rebate_usd == Decimal("0.000004")
    assert direct.total_net_fee_usd == Decimal("0.0079")
    assert direct.total_balance_change_usd == Decimal("-0.1279")
    for scenario in result.scenarios:
        assert scenario.total_balance_change_usd == (
            scenario.total_signed_revenue_usd - scenario.total_net_fee_usd
        )
        assert all(fill.net_fee_usd >= 0 for fill in scenario.fills)
    assert (
        result.calculation_sha256
        == estimate_kalshi_taker_order_fee_sensitivity(
            fee_metadata(),
            event_observation_id="c" * 64,
            series_observation_id="d" * 64,
            order_fills=fills,
        ).calculation_sha256
    )
    assert any("order-level rounding accumulator" in item for item in result.assumptions)


def test_order_fee_sensitivity_handles_sell_revenue_and_order_sequence_identity():
    first = order_fill(side="sell", price="0.055")
    second = order_fill(side="sell")
    args = {
        "event_observation_id": "c" * 64,
        "series_observation_id": "d" * 64,
    }
    forward = estimate_kalshi_taker_order_fee_sensitivity(
        fee_metadata(), order_fills=(first, second), **args
    )
    reverse = estimate_kalshi_taker_order_fee_sensitivity(
        fee_metadata(), order_fills=(second, first), **args
    )

    non_direct = forward.scenarios[1]
    assert [fill.signed_revenue_usd for fill in non_direct.fills] == [
        Decimal("0.055"),
        Decimal("0.06"),
    ]
    assert all(fill.balance_change_after_rebate_usd >= 0 for fill in non_direct.fills)
    assert forward.calculation_sha256 != reverse.calculation_sha256
    assert len(forward.input_observation_ids) == len(forward.input_raw_sha256) == 2


def test_fee_sensitivities_preserve_the_full_supported_decimal_input_precision():
    price = Decimal("0.123456789012")
    quantity = Decimal("0.987654321098")
    single = estimate_kalshi_taker_fee_sensitivity(
        fee_metadata(),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        price_usd=price,
        quantity_contracts=quantity,
    )
    order = estimate_kalshi_taker_order_fee_sensitivity(
        fee_metadata(),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        order_fills=(order_fill(price=str(price), quantity=str(quantity)),),
    )

    assert single.position_cost_usd == price * quantity
    assert order.order_fills[0].price_usd == price
    assert order.order_fills[0].quantity_contracts == quantity
    with localcontext() as context:
        context.prec = 128
        exact_model_fee = Decimal("0.07") * quantity * price * (Decimal(1) - price)
    assert order.scenarios[0].fills[0].model_fee_before_rounding == exact_model_fee


@pytest.mark.parametrize(
    "fills",
    [
        (),
        tuple(order_fill(price="0.5") for _ in range(33)),
        (order_fill(price="0.5"), order_fill(side="sell", price="0.5")),
        (order_fill(instrument="KX-FEE-1:YES"), order_fill(instrument="KX-FEE-1:NO")),
    ],
)
def test_order_fee_sensitivity_rejects_empty_oversized_or_mixed_side_orders(fills):
    with pytest.raises(ValueError):
        estimate_kalshi_taker_order_fee_sensitivity(
            fee_metadata(),
            event_observation_id="c" * 64,
            series_observation_id="d" * 64,
            order_fills=fills,
        )


@pytest.mark.parametrize(
    "fee_type",
    (
        "quadratic",
        "quadratic_with_combo_maker_fees",
    ),
)
def test_supported_quadratic_maker_variants_keep_taker_formula(fee_type: str):
    result = estimate_kalshi_taker_fee_sensitivity(
        fee_metadata(fee_type=fee_type),
        event_observation_id="c" * 64,
        series_observation_id="d" * 64,
        price_usd=Decimal("0.5"),
        quantity_contracts=Decimal("1"),
    )

    assert result.effective_fee_type == fee_type
    assert result.scenarios[0].trade_fee_rounded_to_microdollar == Decimal("0.0175")


@pytest.mark.parametrize(
    "fee_resolution_state",
    ("partial_override", "override_unreported"),
)
def test_taker_sensitivities_reject_incomplete_event_fee_resolution(fee_resolution_state: str):
    metadata = fee_metadata().model_copy(update={"fee_resolution_state": fee_resolution_state})
    evidence = {"event_observation_id": "c" * 64, "series_observation_id": "d" * 64}
    with pytest.raises(ValueError, match="override is partial or unreported"):
        estimate_kalshi_taker_fee_sensitivity(
            metadata,
            **evidence,
            price_usd=Decimal("0.5"),
            quantity_contracts=Decimal("1"),
        )
    with pytest.raises(ValueError, match="override is partial or unreported"):
        estimate_kalshi_taker_order_fee_sensitivity(
            metadata,
            **evidence,
            order_fills=(order_fill(),),
        )


def test_legacy_fee_metadata_defaults_to_unreported_and_cannot_be_estimated():
    stored = fee_metadata().model_dump(mode="json")
    stored["schema_version"] = 1
    stored.pop("fee_resolution_state")
    legacy = KalshiFeeMetadata.model_validate(stored)

    assert legacy.schema_version == 1
    assert legacy.fee_resolution_state == "override_unreported"
    with pytest.raises(ValueError, match="override is partial or unreported"):
        estimate_kalshi_taker_fee_sensitivity(
            legacy,
            event_observation_id="c" * 64,
            series_observation_id="d" * 64,
            price_usd=Decimal("0.5"),
            quantity_contracts=Decimal("1"),
        )


@pytest.mark.parametrize(
    ("price", "quantity", "fee_type", "message"),
    [
        ("0", "1", "quadratic", "price"),
        ("1", "1", "quadratic", "price"),
        ("0.5", "1000001", "quadratic", "quantity"),
        ("0.5", "1", "linear", "quadratic"),
    ],
)
def test_taker_fee_sensitivity_rejects_unsupported_or_unbounded_inputs(
    price: str, quantity: str, fee_type: str, message: str
):
    with pytest.raises(ValueError, match=message):
        estimate_kalshi_taker_fee_sensitivity(
            fee_metadata(fee_type=fee_type),
            event_observation_id="c" * 64,
            series_observation_id="d" * 64,
            price_usd=Decimal(price),
            quantity_contracts=Decimal(quantity),
        )
