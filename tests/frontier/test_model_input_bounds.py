from decimal import Decimal

import pytest
from midas.frontier.models import (
    AdapterCapabilities,
    BookLevel,
    BookSnapshot,
    CandleSeries,
    Capability,
    CapabilityDeclaration,
    FeeSchedule,
    FrontierMarket,
    HistoricalCandle,
    MarketBatch,
    MarketInstrument,
    PayoffSpec,
    Provenance,
    RawObservation,
    ResolutionSpec,
    SourceHealth,
    StatePayout,
    TradeBatch,
    TradeObservation,
    Venue,
)
from pydantic import ValidationError

from tests.frontier.builders import T0, D, book, market


def _valid_trade() -> TradeObservation:
    source_market = market(Venue.KRAKEN, "MODEL-BOUNDS")
    return TradeObservation(
        venue=Venue.KRAKEN,
        native_market_id=source_market.native_market_id,
        native_trade_id="trade-1",
        native_instrument_id=source_market.instruments[0].native_instrument_id,
        price=D("100"),
        quantity=D("0.1"),
        quote_currency="USD",
        received_at_utc=T0,
        provenance=source_market.provenance,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("native_market_id", "m" * 257),
        ("native_event_id", "e" * 257),
        ("title", "t" * 2049),
        ("description", "d" * 65537),
    ),
)
def test_market_rejects_over_limit_identifiers_and_text(field: str, value: str) -> None:
    payload = market(Venue.POLYMARKET, "BOUNDS").model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError):
        FrontierMarket.model_validate(payload)


def test_instrument_and_payoff_cardinality_are_bounded() -> None:
    with pytest.raises(ValidationError):
        MarketInstrument(native_instrument_id="i" * 257, label="Outcome")

    with pytest.raises(ValidationError):
        StatePayout(state_id="s" * 129, amount=Decimal("1"))

    with pytest.raises(ValidationError):
        PayoffSpec(state_ids=tuple(f"state-{index}" for index in range(65)))

    with pytest.raises(ValidationError):
        MarketInstrument(
            native_instrument_id="instrument-1",
            label="Outcome",
            payouts=tuple(
                StatePayout(state_id=f"state-{index}", amount=Decimal("0")) for index in range(65)
            ),
        )


def test_market_and_trade_batches_reject_oversized_pages() -> None:
    source_market = market(Venue.POLYMARKET, "BATCH-BOUNDS")
    with pytest.raises(ValidationError):
        MarketBatch(venue=Venue.POLYMARKET, markets=(source_market,) * 101)

    trade = _valid_trade()
    with pytest.raises(ValidationError):
        TradeBatch(venue=Venue.KRAKEN, trades=(trade,) * 1001)


def test_book_snapshot_rejects_more_than_one_thousand_levels_per_side() -> None:
    source_market = market(Venue.POLYMARKET, "BOOK-BOUNDS")
    snapshot = book(
        source_market,
        source_market.instruments[0].native_instrument_id,
        "0.4",
    )
    payload = snapshot.model_dump(mode="python")
    payload["asks"] = tuple(
        BookLevel(
            price=Decimal(index),
            quantity=Decimal("1"),
            exchange_timestamp_utc=T0,
        )
        for index in range(1, 1002)
    )

    with pytest.raises(ValidationError):
        BookSnapshot.model_validate(payload)


def test_candle_series_rejects_more_than_shared_record_limit() -> None:
    source_market = market(Venue.KRAKEN, "CANDLE-BOUNDS")
    candle = HistoricalCandle(
        open_time_utc=T0,
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        volume=Decimal("3"),
        trade_count=2,
    )

    with pytest.raises(ValidationError):
        CandleSeries(
            venue=Venue.KRAKEN,
            native_market_id=source_market.native_market_id,
            interval_seconds=3600,
            candles=(candle,) * 10_001,
            source_limit_note="bounded fixture",
            provenance=source_market.provenance,
        )


def test_candle_series_rejects_oversized_source_identity_and_invalid_trade_count() -> None:
    source_market = market(Venue.KRAKEN, "CANDLE-IDENTITY-BOUNDS")
    candle = HistoricalCandle(
        open_time_utc=T0,
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        volume=Decimal("3"),
    )
    payload = {
        "venue": Venue.KRAKEN,
        "native_market_id": "m" * 257,
        "interval_seconds": 3600,
        "candles": (candle,),
        "source_limit_note": "bounded fixture",
        "provenance": source_market.provenance,
    }

    with pytest.raises(ValidationError):
        CandleSeries.model_validate(payload)

    with pytest.raises(ValidationError):
        HistoricalCandle(
            open_time_utc=T0,
            open=Decimal("10"),
            high=Decimal("12"),
            low=Decimal("9"),
            close=Decimal("11"),
            volume=Decimal("3"),
            trade_count=2_147_483_648,
        )


def test_capability_metadata_is_bounded_and_complete() -> None:
    capability = next(iter(Capability))
    with pytest.raises(ValidationError):
        CapabilityDeclaration(
            capability=capability,
            supported=False,
            reason="r" * 513,
        )

    declaration = CapabilityDeclaration(
        capability=capability,
        supported=False,
        reason="Documented as unsupported",
    )
    with pytest.raises(ValidationError):
        AdapterCapabilities(
            venue=Venue.KRAKEN,
            adapter_version="fixture-v1",
            declarations=(declaration,) * (len(Capability) + 1),
        )


def test_source_health_rejects_oversized_error_diagnostics() -> None:
    with pytest.raises(ValidationError):
        SourceHealth(venue=Venue.KRAKEN, last_error="e" * 1025)

    with pytest.raises(ValidationError):
        SourceHealth(venue=Venue.KRAKEN, notes=("n" * 513,))

    with pytest.raises(ValidationError):
        SourceHealth(venue=Venue.KRAKEN, notes=("bounded note",) * 33)

    with pytest.raises(ValidationError):
        SourceHealth(venue=Venue.KRAKEN, requests_in_window=2_147_483_648)


def test_contract_text_and_market_asset_identifiers_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ResolutionSpec(primary_rule="r" * 16_385)

    with pytest.raises(ValidationError):
        FeeSchedule(formula="f" * 8193)

    with pytest.raises(ValidationError):
        MarketInstrument(
            native_instrument_id="instrument-1",
            label="BTC/USD",
            price_currency="U" * 17,
        )

    market_payload = market(Venue.KRAKEN, "ASSET-BOUNDS").model_dump(mode="python")
    market_payload["settlement_asset"] = "s" * 257
    with pytest.raises(ValidationError):
        FrontierMarket.model_validate(market_payload)


def test_raw_and_normalized_provenance_require_bounded_urls_and_sha256() -> None:
    source_market = market(Venue.KRAKEN, "PROVENANCE-BOUNDS")
    provenance = source_market.provenance.model_dump(mode="python")
    raw_observation = {
        "venue": Venue.KRAKEN,
        "observation_kind": "ticker",
        "request_url": "https://api.kraken.com/0/public/Ticker",
        "http_status": 200,
        "request_started_at_utc": T0,
        "received_at_utc": T0,
        "raw_body": "{}",
        "raw_sha256": "a" * 64,
        "adapter_version": "test-v1",
    }

    with pytest.raises(ValidationError):
        Provenance.model_validate(provenance | {"source_url": "u" * 4097})

    with pytest.raises(ValidationError):
        Provenance.model_validate(provenance | {"raw_sha256": "z" * 64})

    with pytest.raises(ValidationError):
        FeeSchedule(evidence_sha256="z" * 64)

    with pytest.raises(ValidationError):
        RawObservation(
            **(raw_observation | {"raw_sha256": "z" * 64}),
        )

    with pytest.raises(ValidationError):
        RawObservation.model_validate(raw_observation | {"request_url": "u" * 4097})
