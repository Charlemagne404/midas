"""Kalshi public REST market-data adapter; no API key or trading route exists."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from midas.frontier.adapters.base import AdapterError, BaseReadOnlyAdapter, build_capabilities
from midas.frontier.adapters.normalization import (
    lifecycle,
    native_json,
    parse_decimal,
    parse_time,
    provenance,
)
from midas.frontier.adapters.transport import HTTPObservation
from midas.frontier.models import (
    AdapterConfig,
    BookLevel,
    BookSnapshot,
    Capability,
    FeeSchedule,
    FrontierMarket,
    KalshiFeeMetadata,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    ResolutionSpec,
    StatePayout,
    TradeObservation,
    Venue,
    stable_market_id,
)

D = Decimal
ADAPTER_VERSION = "frontier-kalshi-2"
_TICKER_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
BASE = "https://external-api.kalshi.com/trade-api/v2"
MARKET_DATA_DOC = "https://docs.kalshi.com/getting_started/quick_start_market_data"
MARKETS_DOC = "https://docs.kalshi.com/api-reference/market/get-markets"
ORDERBOOK_DOC = "https://docs.kalshi.com/api-reference/market/get-market-orderbook"
EVENT_DOC = "https://docs.kalshi.com/api-reference/events/get-event"
SERIES_DOC = "https://docs.kalshi.com/api-reference/market/get-series"


class KalshiAdapter(BaseReadOnlyAdapter):
    venue = Venue.KALSHI
    allowed_hosts = {"external-api.kalshi.com"}
    capabilities = build_capabilities(
        Venue.KALSHI,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Public cursor-based market listing; this adapter reads one bounded page",
                MARKETS_DOC,
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Binary YES/NO contract identifiers are derived from the native market ticker",
                MARKETS_DOC,
            ),
            Capability.MARKET_METADATA: (
                "Native market fields and raw settlement rules are retained",
                MARKETS_DOC,
            ),
            Capability.OUTCOME_DEFINITIONS: (
                "YES/NO titles and source payout metadata are retained; MVE legs remain opaque",
                MARKET_DATA_DOC,
            ),
            Capability.BOOK_SNAPSHOT: (
                "Public REST endpoint returns YES and NO bids; asks are derived using the documented binary complement",
                ORDERBOOK_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "Public market trades endpoint",
                "https://docs.kalshi.com/api-reference/market/get-trades",
            ),
            Capability.TICK_CONSTRAINTS: (
                "Native piecewise price ranges and price-level structure are retained; a single tick may not apply",
                MARKETS_DOC,
            ),
            Capability.QUANTITY_CONSTRAINTS: (
                "Fixed-point quantities and native size fields are retained when present",
                MARKETS_DOC,
            ),
            Capability.SETTLEMENT_RULES: (
                "Primary/secondary rules are exposed as raw text; semantic equivalence is not certified",
                MARKETS_DOC,
            ),
            Capability.MARKET_LIFECYCLE: (
                "Native status, close, expiration and result fields are retained",
                MARKETS_DOC,
            ),
            Capability.HEALTH_DIAGNOSTICS: (
                "Local request/configuration state; no network request is made by health()",
                None,
            ),
            Capability.FEE_METADATA: (
                "Public event overrides and series fee type/multiplier are normalized and captured; exact account fees remain unresolved",
                EVENT_DOC,
            ),
        },
        {
            Capability.BOOK_UPDATES: (
                "WebSocket updates are not implemented; this adapter only captures REST snapshots",
                None,
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Cursor-based Kalshi trade pagination is not normalized by adapter v1",
                "https://docs.kalshi.com/api-reference/market/get-trades",
            ),
            Capability.HISTORICAL_CANDLES: (
                "Historical candles are not normalized by adapter v1",
                None,
            ),
            Capability.FEE_SCHEDULE: (
                "Public fee documentation is market-specific; no validated market-specific fee resolver is implemented",
                "https://help.kalshi.com/en/articles/13823805-fees",
            ),
        },
    )

    def __init__(self, config: AdapterConfig | None = None, *, transport: Any = None) -> None:
        super().__init__(config, transport=transport)

    async def discover_markets(self, limit: int = 20) -> tuple[FrontierMarket, ...]:
        self._require(Capability.MARKET_DISCOVERY)
        if not 1 <= limit <= min(self.config.max_markets_per_call, 100):
            raise AdapterError(
                "INVALID_LIMIT", "Market discovery limit must be within source bounds"
            )
        response = await self.transport.get_json(
            f"{BASE}/markets", {"limit": limit, "status": "open"}
        )
        self._capture_response(response, "market_listing")
        if not isinstance(response.payload, dict) or not isinstance(
            response.payload.get("markets"), list
        ):
            raise AdapterError("INVALID_SCHEMA", "Kalshi response must contain a markets array")
        result = []
        for raw in response.payload["markets"]:
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_SCHEMA", "Kalshi market entry must be an object")
            result.append(self._normalize_market(raw, response))
        return tuple(result)

    def _normalize_market(self, raw: dict[str, Any], response: HTTPObservation) -> FrontierMarket:
        ticker = raw.get("ticker")
        if not isinstance(ticker, str) or not ticker or len(ticker) > 256:
            raise AdapterError("INVALID_MARKET", "Kalshi market ticker is missing or oversized")
        native_type = str(raw.get("market_type") or "unknown").lower()
        is_mve = bool(raw.get("mve_collection_ticker") or raw.get("mve_selected_legs"))
        kind = (
            MarketKind.CONDITIONAL_EVENT
            if is_mve
            else MarketKind.BINARY_EVENT
            if native_type == "binary"
            else MarketKind.UNKNOWN
        )

        notional = parse_decimal(raw.get("notional_value_dollars"))
        payout_value = notional if notional is not None and notional > 0 else D(1)
        states = (
            ("yes", "no") if kind in {MarketKind.BINARY_EVENT, MarketKind.CONDITIONAL_EVENT} else ()
        )
        outcomes: tuple[MarketInstrument, ...] = ()
        if states:
            yes_label = str(raw.get("yes_sub_title") or "YES")
            no_label = str(raw.get("no_sub_title") or "NO")
            outcomes = (
                MarketInstrument(
                    native_instrument_id=f"{ticker}:YES",
                    label=yes_label,
                    outcome_id="yes",
                    quantity_unit=QuantityUnit.CONTRACT,
                    price_currency="USD",
                    payouts=(
                        StatePayout(state_id="yes", amount=payout_value),
                        StatePayout(state_id="no", amount=D(0)),
                    ),
                ),
                MarketInstrument(
                    native_instrument_id=f"{ticker}:NO",
                    label=no_label,
                    outcome_id="no",
                    quantity_unit=QuantityUnit.CONTRACT,
                    price_currency="USD",
                    payouts=(
                        StatePayout(state_id="yes", amount=D(0)),
                        StatePayout(state_id="no", amount=payout_value),
                    ),
                ),
            )
        primary_rule = raw.get("rules_primary")
        secondary_rule = raw.get("rules_secondary")
        rule_hash = None
        if primary_rule or secondary_rule:
            from midas.frontier.models import sha256_text

            rule_hash = sha256_text(f"{primary_rule or ''}\n{secondary_rule or ''}")
        exchange_ts = parse_time(raw.get("updated_time"))
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, ticker),
            native_market_id=ticker,
            native_event_id=str(raw.get("event_ticker") or "") or None,
            title=str(raw.get("title") or ticker),
            description=str(raw.get("subtitle") or ""),
            market_kind=kind,
            lifecycle=lifecycle(
                raw.get("status"), closed=raw.get("status") in {"closed", "settled"}
            ),
            instruments=outcomes,
            payoff=PayoffSpec(
                state_ids=states,
                payout_currency="USD" if states else None,
                settlement_asset="USD" if states else None,
                exhaustive=False,
                verified=False,
                verification_basis=(
                    "Native YES/NO and notional metadata only; resolution and settlement conditions require independent validation."
                ),
            ),
            resolution=ResolutionSpec(
                primary_rule=str(primary_rule) if primary_rule else None,
                secondary_rule=str(secondary_rule) if secondary_rule else None,
                closes_at_utc=parse_time(raw.get("close_time")),
                settles_at_utc=parse_time(
                    raw.get("expected_expiration_time") or raw.get("expiration_time")
                ),
                source_timestamp_semantics="Kalshi updated_time is market metadata update time, not a book timestamp",
                evidence_sha256=rule_hash,
                verified=False,
            ),
            fees=FeeSchedule(
                note=(
                    "Unknown: native event/series fee parameters are available separately, but "
                    "maker/taker applicability and account-specific fee rounding are not modeled."
                )
            ),
            settlement_asset="USD" if states else None,
            native_fields=native_json(raw),
            quality_flags=tuple(
                flag
                for flag, condition in (
                    ("MVE_PAYOFF_NOT_MODELED", is_mve),
                    ("RULES_PRIMARY_MISSING", not bool(primary_rule)),
                    ("FEE_SCHEDULE_UNKNOWN", True),
                    ("PAYOFF_NOT_VERIFIED", True),
                    ("BOOK_TIMESTAMP_NOT_PROVIDED", True),
                )
                if condition
            ),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "market_metadata",
                ticker,
                source_schema_version=f"market_type:{native_type}",
                exchange_timestamp=exchange_ts,
                exchange_timestamp_semantics="updated_time is metadata update time",
            ),
        )

    async def fetch_fee_metadata(self, market: FrontierMarket) -> KalshiFeeMetadata:
        """Capture public event/series fee parameters without asserting account-level fees."""
        self._require(Capability.FEE_METADATA)
        if market.venue != self.venue:
            raise AdapterError("VENUE_MISMATCH", "Market does not belong to Kalshi")
        event_ticker = market.native_event_id
        if not isinstance(event_ticker, str) or not _TICKER_PATTERN.fullmatch(event_ticker):
            raise AdapterError("FEE_EVENT_MISSING", "Recorded market lacks a usable event ticker")

        # Omitting child markets keeps this metadata-only response small and bounded.
        event_response = await self.transport.get_json(
            f"{BASE}/events/{quote(event_ticker, safe='')}", {"exclude_markets": "true"}
        )
        event_capture = self._capture_response(event_response, "event_fee_metadata")
        payload = event_response.payload
        event = payload.get("event") if isinstance(payload, dict) else None
        if not isinstance(event, dict) or event.get("event_ticker") != event_ticker:
            raise AdapterError("INVALID_FEE_EVENT", "Kalshi event fee response identity is invalid")
        series_ticker = event.get("series_ticker")
        if not isinstance(series_ticker, str) or not _TICKER_PATTERN.fullmatch(series_ticker):
            raise AdapterError(
                "INVALID_FEE_EVENT", "Kalshi event response lacks a valid series ticker"
            )

        event_fee_type = _optional_bounded_text(event, "fee_type_override", max_length=80)
        event_multiplier = _optional_multiplier(event, "fee_multiplier_override")
        series_response = await self.transport.get_json(
            f"{BASE}/series/{quote(series_ticker, safe='')}"
        )
        series_capture = self._capture_response(series_response, "series_fee_metadata")
        series_payload = series_response.payload
        series = series_payload.get("series") if isinstance(series_payload, dict) else None
        if not isinstance(series, dict) or series.get("ticker") != series_ticker:
            raise AdapterError(
                "INVALID_FEE_SERIES", "Kalshi series fee response identity is invalid"
            )
        series_fee_type = _required_bounded_text(series, "fee_type", max_length=80)
        series_multiplier = _required_multiplier(series, "fee_multiplier")

        return KalshiFeeMetadata(
            adapter_version=ADAPTER_VERSION,
            native_market_id=market.native_market_id,
            native_event_id=event_ticker,
            series_ticker=series_ticker,
            event_fee_type_override=event_fee_type,
            event_fee_multiplier_override=event_multiplier,
            series_fee_type=series_fee_type,
            series_fee_multiplier=series_multiplier,
            effective_fee_type=event_fee_type or series_fee_type,
            effective_fee_multiplier=(
                event_multiplier if event_multiplier is not None else series_multiplier
            ),
            event_fee_type_override_field_present="fee_type_override" in event,
            event_fee_multiplier_override_field_present="fee_multiplier_override" in event,
            event_raw_sha256=event_capture.raw_sha256,
            series_raw_sha256=series_capture.raw_sha256,
            event_received_at_utc=event_capture.received_at_utc,
            series_received_at_utc=series_capture.received_at_utc,
        )

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot:
        self._require(Capability.BOOK_SNAPSHOT)
        if market.venue != self.venue:
            raise AdapterError("VENUE_MISMATCH", "Market does not belong to Kalshi")
        if market.market_kind not in {MarketKind.BINARY_EVENT, MarketKind.CONDITIONAL_EVENT}:
            raise AdapterError(
                "UNSUPPORTED_MARKET", "Only source-declared binary markets are supported"
            )
        if not 1 <= depth <= 100:
            raise AdapterError("INVALID_DEPTH", "Book depth must be between 1 and 100")
        if instrument_id not in {item.native_instrument_id for item in market.instruments}:
            raise AdapterError(
                "INSTRUMENT_NOT_FOUND", "Instrument does not belong to this Kalshi market"
            )
        ticker = quote(market.native_market_id, safe="")
        response = await self.transport.get_json(
            f"{BASE}/markets/{ticker}/orderbook", {"depth": depth}
        )
        self._capture_response(response, "book_snapshot")
        payload = response.payload
        if not isinstance(payload, dict) or not isinstance(payload.get("orderbook_fp"), dict):
            raise AdapterError("INVALID_BOOK", "Kalshi response is missing orderbook_fp")
        raw_book = payload["orderbook_fp"]
        yes = self._levels(raw_book.get("yes_dollars"), depth, "YES")
        no = self._levels(raw_book.get("no_dollars"), depth, "NO")
        is_yes = instrument_id.endswith(":YES")
        bids = yes if is_yes else no
        opposite = no if is_yes else yes
        # A NO bid at p is a YES ask at 1-p. The public docs explicitly describe this.
        asks = tuple(
            sorted(
                (
                    BookLevel(price=D(1) - level.price, quantity=level.quantity)
                    for level in opposite
                ),
                key=lambda level: level.price,
            )
        )
        flags = []
        if not asks and not bids:
            flags.append("EMPTY_BOOK")
        if (
            asks
            and bids
            and max(level.price for level in bids) >= min(level.price for level in asks)
        ):
            flags.append("CROSSED_OR_LOCKED")
        flags.append("NO_EXCHANGE_SNAPSHOT_TIMESTAMP")
        return BookSnapshot(
            venue=self.venue,
            native_market_id=market.native_market_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=tuple(sorted(bids, key=lambda level: level.price, reverse=True)),
            price_unit="USD per binary contract",
            quantity_unit=QuantityUnit.CONTRACT,
            received_at_utc=response.response_received_at_utc,
            exchange_timestamp_semantics="REST response has no unified exchange book timestamp",
            quality_flags=tuple(flags),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "book_snapshot",
                f"{market.native_market_id}:{instrument_id}",
                source_schema_version="orderbook_fp",
                exchange_timestamp_semantics="No exchange snapshot timestamp in endpoint response",
            ),
        )

    @staticmethod
    def _levels(value: Any, depth: int, side: str) -> tuple[BookLevel, ...]:
        if not isinstance(value, list):
            raise AdapterError("INVALID_BOOK", f"Kalshi {side} book must be an array")
        levels = []
        for row in value[:depth]:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise AdapterError("INVALID_BOOK", f"Malformed Kalshi {side} book row")
            price = parse_decimal(row[0])
            quantity = parse_decimal(row[1])
            if price is None or quantity is None or not D(0) <= price <= D(1) or quantity <= 0:
                raise AdapterError("INVALID_BOOK", f"Invalid Kalshi {side} price or quantity")
            levels.append(BookLevel(price=price, quantity=quantity))
        return tuple(levels)

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        if not 1 <= limit <= 1000:
            raise AdapterError("INVALID_LIMIT", "Trade limit must be between 1 and 1000")
        response = await self.transport.get_json(
            f"{BASE}/markets/trades", {"ticker": native_market_id, "limit": limit}
        )
        self._capture_response(response, "public_trades")
        payload = response.payload
        if not isinstance(payload, dict) or not isinstance(payload.get("trades"), list):
            raise AdapterError(
                "INVALID_SCHEMA", "Kalshi trades response must contain a trades array"
            )
        result = []
        for raw in payload["trades"][:limit]:
            price = parse_decimal(raw.get("yes_price_dollars"))
            quantity = parse_decimal(raw.get("count_fp"))
            timestamp = parse_time(raw.get("created_time"))
            if price is None or quantity is None or quantity <= 0:
                raise AdapterError("INVALID_TRADE", "Kalshi trade has invalid price or quantity")
            result.append(
                TradeObservation(
                    venue=self.venue,
                    native_market_id=native_market_id,
                    native_trade_id=str(raw.get("trade_id") or "") or None,
                    price=price,
                    quantity=quantity,
                    quote_currency="USD",
                    aggressor_side=str(raw.get("taker_outcome_side") or "unknown"),
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        str(raw.get("trade_id") or raw.get("created_time") or native_market_id),
                        source_schema_version="public-trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics="Kalshi created_time",
                    ),
                )
            )
        return tuple(result)


def _required_bounded_text(raw: dict[str, Any], key: str, *, max_length: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise AdapterError("INVALID_FEE_METADATA", f"Kalshi {key} is missing or malformed")
    return value


def _optional_bounded_text(raw: dict[str, Any], key: str, *, max_length: int) -> str | None:
    if key not in raw or raw[key] is None:
        return None
    return _required_bounded_text(raw, key, max_length=max_length)


def _required_multiplier(raw: dict[str, Any], key: str) -> Decimal:
    value = parse_decimal(raw.get(key))
    if value is None or value < 0:
        raise AdapterError("INVALID_FEE_METADATA", f"Kalshi {key} is missing or malformed")
    return value


def _optional_multiplier(raw: dict[str, Any], key: str) -> Decimal | None:
    if key not in raw or raw[key] is None:
        return None
    return _required_multiplier(raw, key)
