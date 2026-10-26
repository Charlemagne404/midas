from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from midas.frontier.economics import estimate_kalshi_taker_fee_sensitivity
from midas.frontier.models import KalshiFeeMetadata

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
        event_fee_type_override_field_present=False,
        event_fee_multiplier_override_field_present=False,
        event_raw_sha256="a" * 64,
        series_raw_sha256="b" * 64,
        event_received_at_utc=T0,
        series_received_at_utc=T0 + timedelta(milliseconds=5),
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
