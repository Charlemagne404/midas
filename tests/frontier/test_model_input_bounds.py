from decimal import Decimal

import pytest
from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    FrontierMarket,
    MarketBatch,
    MarketInstrument,
    PayoffSpec,
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
