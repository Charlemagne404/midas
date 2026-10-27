"""Kalshi public REST market-data adapter; no API key or trading route exists."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal
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
    SelectedMarketComponent,
    StatePayout,
    TradeBatch,
    TradeObservation,
    Venue,
    stable_market_id,
)

D = Decimal
ADAPTER_VERSION = "frontier-kalshi-5"
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
            Capability.EVENT_MARKET_GROUPS: (
                "Bounded public event detail with the venue-provided nested market list",
                EVENT_DOC,
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
                "YES/NO identities and MVE selected component market/side identifiers are normalized; combo payoff remains unverified",
                "https://docs.kalshi.com/api-reference/events/get-multivariate-events",
            ),
            Capability.BOOK_SNAPSHOT: (
                "Public REST endpoint returns YES and NO bids; asks are derived using the documented binary complement",
                ORDERBOOK_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "Public market trades endpoint",
                "https://docs.kalshi.com/api-reference/market/get-trades",
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "One explicit ticker-filtered public trade page with an opaque source cursor",
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
            Capability.HISTORICAL_CANDLES: (
                "Historical candles are not normalized by adapter v1",
                None,
            ),
            Capability.FEE_SCHEDULE: (
                "One-fill taker sensitivity exists, but no account-specific fee schedule is promoted into candidate economics; maker applicability, multi-fill rebates, and account precision remain unresolved",
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

    async def discover_event_markets(self, native_event_id: str) -> tuple[FrontierMarket, ...]:
        self._require(Capability.EVENT_MARKET_GROUPS)
        if not isinstance(native_event_id, str) or not _TICKER_PATTERN.fullmatch(native_event_id):
            raise AdapterError("INVALID_EVENT_ID", "Kalshi event ticker is invalid")
        response = await self.transport.get_json(
            f"{BASE}/events/{quote(native_event_id, safe='')}", {"with_nested_markets": "true"}
        )
        self._capture_response(response, "event_market_listing")
        payload = response.payload
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), dict):
            raise AdapterError(
                "INVALID_SCHEMA", "Kalshi event response must contain an event object"
            )
        event = payload["event"]
        if event.get("event_ticker") != native_event_id:
            raise AdapterError("EVENT_ID_MISMATCH", "Kalshi event response does not match request")
        event_title = event.get("title")
        if not isinstance(event_title, str) or not event_title.strip() or len(event_title) > 512:
            raise AdapterError("INVALID_SCHEMA", "Kalshi event title is missing or oversized")
        children = event.get("markets")
        top_level_children = payload.get("markets")
        if isinstance(top_level_children, list) and top_level_children:
            if isinstance(children, list) and children:
                raise AdapterError("INVALID_SCHEMA", "Kalshi event returned two market arrays")
            children = top_level_children
        if not isinstance(children, list) or len(children) > self.config.max_markets_per_call:
            raise AdapterError(
                "INVALID_SCHEMA",
                "Kalshi event markets must be an array within the configured bound",
            )
        records: list[FrontierMarket] = []
        seen: set[str] = set()
        for raw in children:
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_SCHEMA", "Kalshi event market entry must be an object")
            source_event_id = raw.get("event_ticker")
            if source_event_id is not None and source_event_id != native_event_id:
                raise AdapterError("EVENT_ID_MISMATCH", "Kalshi child market names another event")
            record = self._normalize_market(
                raw,
                response,
                parent_event_id=native_event_id,
                parent_event_title=event_title,
            )
            if record.native_market_id in seen:
                raise AdapterError(
                    "DUPLICATE_MARKET", "Kalshi event contains a duplicate market ticker"
                )
            seen.add(record.native_market_id)
            records.append(record)
        return tuple(records)

    def _normalize_market(
        self,
        raw: dict[str, Any],
        response: HTTPObservation,
        *,
        parent_event_id: str | None = None,
        parent_event_title: str | None = None,
    ) -> FrontierMarket:
        ticker = raw.get("ticker")
        if not isinstance(ticker, str) or not ticker or len(ticker) > 256:
            raise AdapterError("INVALID_MARKET", "Kalshi market ticker is missing or oversized")
        native_type = str(raw.get("market_type") or "unknown").lower()
        is_mve = bool(raw.get("mve_collection_ticker") or raw.get("mve_selected_legs"))
        selected_components = self._selected_components(raw, ticker)
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
            native_event_id=parent_event_id or (str(raw.get("event_ticker") or "") or None),
            native_event_title=parent_event_title,
            title=str(raw.get("title") or ticker),
            description=str(raw.get("subtitle") or ""),
            market_kind=kind,
            lifecycle=lifecycle(
                raw.get("status"), closed=raw.get("status") in {"closed", "settled"}
            ),
            instruments=outcomes,
            selected_components=selected_components,
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
                    ("MVE_SELECTED_COMPONENTS_MISSING", is_mve and not selected_components),
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

    def _selected_components(
        self, raw: dict[str, Any], containing_market_id: str
    ) -> tuple[SelectedMarketComponent, ...]:
        if "mve_selected_legs" not in raw:
            return ()
        source_legs = raw["mve_selected_legs"]
        if not isinstance(source_legs, list) or len(source_legs) > 64:
            raise AdapterError(
                "INVALID_MVE_COMPONENTS",
                "Kalshi MVE selected legs must be an array of at most 64 entries",
            )
        components: list[SelectedMarketComponent] = []
        seen: set[str] = set()
        for leg in source_legs:
            if not isinstance(leg, dict):
                raise AdapterError("INVALID_MVE_COMPONENT", "Kalshi MVE leg must be an object")
            market_ticker = leg.get("market_ticker")
            event_ticker = leg.get("event_ticker")
            side = leg.get("side")
            if (
                not isinstance(market_ticker, str)
                or not _TICKER_PATTERN.fullmatch(market_ticker)
                or market_ticker == containing_market_id
                or (
                    event_ticker is not None
                    and (
                        not isinstance(event_ticker, str)
                        or not _TICKER_PATTERN.fullmatch(event_ticker)
                    )
                )
                or not isinstance(side, str)
                or side not in {"yes", "no"}
                or market_ticker in seen
            ):
                raise AdapterError(
                    "INVALID_MVE_COMPONENT",
                    "Kalshi MVE leg identity or selected side is invalid",
                )
            selected_side: Literal["yes", "no"] = "yes" if side == "yes" else "no"
            seen.add(market_ticker)
            components.append(
                SelectedMarketComponent(
                    venue=self.venue,
                    native_event_id=event_ticker,
                    native_market_id=market_ticker,
                    selected_side=selected_side,
                )
            )
        return tuple(components)

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

    async def fetch_trade_page(
        self, native_market_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> TradeBatch:
        """Fetch one public Kalshi trade page for a ticker already recorded by Frontier."""
        self._require(Capability.PAGINATED_PUBLIC_TRADES)
        if (
            not isinstance(native_market_id, str)
            or not _TICKER_PATTERN.fullmatch(native_market_id)
            or len(native_market_id) > 251
        ):
            raise AdapterError("INVALID_MARKET", "Kalshi market ticker is malformed")
        # Keep this UI/API operation substantially below Kalshi's documented 1,000 row ceiling.
        if not 1 <= limit <= 100:
            raise AdapterError("INVALID_LIMIT", "Kalshi trade page size must be between 1 and 100")
        if cursor is not None and (
            not cursor.strip()
            or len(cursor) > 2048
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in cursor)
        ):
            raise AdapterError("INVALID_CURSOR", "Kalshi source cursor is blank or oversized")

        params: dict[str, str | int] = {"ticker": native_market_id, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self.transport.get_json(f"{BASE}/markets/trades", params)
        self._capture_response(response, "public_trades")
        payload = response.payload
        if not isinstance(payload, dict):
            raise AdapterError("INVALID_SCHEMA", "Kalshi trade response must be an object")
        rows = payload.get("trades")
        next_cursor = payload.get("cursor")
        if not isinstance(rows, list) or not isinstance(next_cursor, str):
            raise AdapterError(
                "INVALID_SCHEMA", "Kalshi trade response must contain trades and a cursor"
            )
        if len(rows) > limit:
            raise AdapterError(
                "INVALID_PAGINATION", "Kalshi exceeded the requested trade page size"
            )
        if next_cursor and (
            not next_cursor.strip()
            or len(next_cursor) > 2048
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in next_cursor)
            or next_cursor == cursor
        ):
            raise AdapterError("INVALID_PAGINATION", "Kalshi returned an invalid next cursor")

        trades = []
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_TRADE", "Kalshi trade entry must be an object")
            ticker = raw.get("ticker")
            trade_id = raw.get("trade_id")
            yes_price = parse_decimal(raw.get("yes_price_dollars"))
            quantity = parse_decimal(raw.get("count_fp"))
            timestamp = parse_time(raw.get("created_time"))
            if ticker != native_market_id:
                raise AdapterError(
                    "TRADE_MARKET_MISMATCH", "Kalshi returned a trade for another market ticker"
                )
            if (
                not isinstance(trade_id, str)
                or not trade_id.strip()
                or len(trade_id) > 256
                or yes_price is None
                or not D(0) <= yes_price <= D(1)
                or quantity is None
                or quantity <= 0
                or timestamp is None
            ):
                raise AdapterError("INVALID_TRADE", "Kalshi trade fields failed validation")
            trades.append(
                TradeObservation(
                    schema_version=2,
                    venue=self.venue,
                    native_market_id=native_market_id,
                    native_trade_id=trade_id,
                    native_instrument_id=f"{native_market_id}:YES",
                    outcome_label="YES price reference",
                    outcome_index=0,
                    price=yes_price,
                    quantity=quantity,
                    quote_currency="USD",
                    # Kalshi's taker_outcome_side identifies the outcome side; it is not
                    # documented as a normalized BUY/SELL aggressor direction.
                    aggressor_side=None,
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{native_market_id}:{trade_id}:{index}",
                        source_schema_version="Kalshi public /markets/trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics="Kalshi created_time",
                    ),
                )
            )
        return TradeBatch(
            schema_version=2,
            venue=self.venue,
            trades=tuple(trades),
            requested_market_id=native_market_id,
            page_limit=limit,
            source_cursor=cursor,
            source_next_cursor=next_cursor or None,
            has_more=bool(next_cursor),
        )


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
