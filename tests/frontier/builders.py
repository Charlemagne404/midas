from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from midas.frontier.models import (
    BookLevel,
    BookSnapshot,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    Lifecycle,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    Provenance,
    QuantityUnit,
    ResolutionSpec,
    SettlementAssetIdentity,
    SettlementAssetKind,
    StatePayout,
    Venue,
)

D = Decimal
T0 = datetime(2026, 10, 26, 20, 0, tzinfo=UTC)
USD_SETTLEMENT_IDENTITY = SettlementAssetIdentity(kind=SettlementAssetKind.FIAT, code="USD")


def market(
    venue: Venue, native_id: str, *, title: str = "Who wins the local election?"
) -> FrontierMarket:
    prefix = venue.value.upper()
    units = QuantityUnit.SHARE if venue == Venue.POLYMARKET else QuantityUnit.CONTRACT
    return FrontierMarket(
        venue=venue,
        canonical_id=f"{venue.value}:{native_id}",
        native_market_id=native_id,
        native_event_id=f"{native_id}-event",
        title=title,
        market_kind=MarketKind.BINARY_EVENT,
        lifecycle=Lifecycle.OPEN,
        instruments=(
            MarketInstrument(
                native_instrument_id=f"{prefix}:{native_id}:YES",
                label="Yes",
                outcome_id="yes",
                quantity_unit=units,
                price_currency="USD",
                payouts=(
                    StatePayout(state_id="yes", amount=D(1)),
                    StatePayout(state_id="no", amount=D(0)),
                ),
            ),
            MarketInstrument(
                native_instrument_id=f"{prefix}:{native_id}:NO",
                label="No",
                outcome_id="no",
                quantity_unit=units,
                price_currency="USD",
                payouts=(
                    StatePayout(state_id="yes", amount=D(0)),
                    StatePayout(state_id="no", amount=D(1)),
                ),
            ),
        ),
        payoff=PayoffSpec(
            state_ids=("yes", "no"),
            payout_currency="USD",
            settlement_asset="USD",
            settlement_asset_identity=USD_SETTLEMENT_IDENTITY,
            exhaustive=True,
            verified=True,
            verification_basis="controlled-test-fixture",
        ),
        resolution=ResolutionSpec(
            primary_rule="The named candidate receives the most votes.",
            authority="Official election authority",
            closes_at_utc=T0 + timedelta(hours=1),
            settles_at_utc=T0 + timedelta(hours=2),
            evidence_sha256="a" * 64,
            resolution_fingerprint="election:test:2026-11-01:most-votes",
            verified=True,
        ),
        fees=FeeSchedule(
            status=FeeStatus.VERIFIED,
            version="controlled-zero-fee-v1",
            applies_to="taker",
            rate=D(0),
            formula="quantity * rate * price * (1 - price); exponent 1",
            fee_currency="USD",
            source_url="https://example.test/fee-evidence",
            evidence_sha256="b" * 64,
        ),
        settlement_asset="USD",
        settlement_asset_identity=USD_SETTLEMENT_IDENTITY,
        native_fields={"fixture": "explicit controlled test data"},
        provenance=Provenance(
            source_url="https://example.test/market",
            adapter_version="test-adapter-1",
            request_started_at_utc=T0,
            response_received_at_utc=T0,
            processed_at_utc=T0,
            raw_sha256=("c" if venue == Venue.POLYMARKET else "d") * 64,
            observation_id=f"{venue.value}-{native_id}-metadata",
        ),
    )


def book(market_value: FrontierMarket, instrument_id: str, ask: str) -> BookSnapshot:
    return BookSnapshot(
        venue=market_value.venue,
        native_market_id=market_value.native_market_id,
        native_instrument_id=instrument_id,
        asks=(BookLevel(price=D(ask), quantity=D(10), exchange_timestamp_utc=T0),),
        bids=(
            BookLevel(
                price=max(D(0), D(ask) - D("0.01")), quantity=D(10), exchange_timestamp_utc=T0
            ),
        ),
        price_unit="USD per contract",
        quantity_unit=market_value.instruments[0].quantity_unit,
        received_at_utc=T0,
        exchange_timestamp_utc=T0,
        exchange_timestamp_semantics="controlled test fixture",
        provenance=Provenance(
            source_url="https://example.test/book",
            adapter_version="test-adapter-1",
            request_started_at_utc=T0,
            response_received_at_utc=T0,
            processed_at_utc=T0,
            exchange_timestamp_utc=T0,
            exchange_timestamp_semantics="controlled test fixture",
            raw_sha256=("e" if market_value.venue == Venue.POLYMARKET else "f") * 64,
            observation_id=f"{market_value.venue.value}-{market_value.native_market_id}-{instrument_id}-book",
        ),
    )
