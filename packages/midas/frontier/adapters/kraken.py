"""Kraken spot public-data adapter; spot prices are never event-contract payoffs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import field_validator

from midas.frontier.adapters.base import AdapterError, BaseReadOnlyAdapter, build_capabilities
from midas.frontier.adapters.normalization import (
    lifecycle,
    native_json,
    parse_decimal,
    parse_time,
    provenance,
)
from midas.frontier.adapters.transport import HTTPObservation, PublicReadTransport
from midas.frontier.models import (
    AdapterConfig,
    BookLevel,
    BookSnapshot,
    CandleSeries,
    Capability,
    FeeSchedule,
    FrontierMarket,
    HistoricalCandle,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    TradeObservation,
    Venue,
    stable_market_id,
)

D = Decimal
ADAPTER_VERSION = "frontier-kraken-spot-1"
BASE = "https://api.kraken.com/0/public"
ORDERBOOK_DOC = "https://docs.kraken.com/api-reference/market-data/get-order-book"


class KrakenSpotConfig(AdapterConfig):
    """Bounded explicit pair allowlist; does not enumerate the full Kraken catalog."""

    pairs: tuple[str, ...] = ("XBTUSD",)

    @field_validator("pairs")
    @classmethod
    def validate_pairs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(value) <= 20:
            raise ValueError("Configure between 1 and 20 Kraken spot pairs")
        normalized = tuple(cls._validate_pair_name(item) for item in value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate Kraken pair")
        return normalized

    @classmethod
    def _validate_pair_name(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 32 or not re.fullmatch(r"[A-Z0-9/._-]+", value):
            raise ValueError("Kraken pair must be a bounded native symbol")
        return value


class KrakenSpotAdapter(BaseReadOnlyAdapter):
    venue = Venue.KRAKEN
    allowed_hosts = {"api.kraken.com"}
    capabilities = build_capabilities(
        Venue.KRAKEN,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Configured-pair lookup via public AssetPairs; full catalog enumeration is intentionally disabled",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Spot pair metadata and native asset names",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.MARKET_METADATA: (
                "Public pair constraints, status, and fee fields are retained verbatim",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.BOOK_SNAPSHOT: ("Public REST aggregated order-book depth", ORDERBOOK_DOC),
            Capability.PUBLIC_TRADES: (
                "Public spot trade history",
                "https://docs.kraken.com/api/docs/rest-api/get-post-trade",
            ),
            Capability.HISTORICAL_CANDLES: (
                "Public OHLC candles with source limit stated in each result",
                "https://docs.kraken.com/api/docs/rest-api/get-ohlc-data",
            ),
            Capability.TICK_CONSTRAINTS: (
                "Pair price decimals and explicit tick_size are retained",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.QUANTITY_CONSTRAINTS: (
                "Pair lot decimals and order minimums are retained",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.MARKET_LIFECYCLE: (
                "Pair status is retained",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.HEALTH_DIAGNOSTICS: (
                "Local request/configuration state; no network request is made by health()",
                None,
            ),
        },
        {
            Capability.OUTCOME_DEFINITIONS: (
                "Spot pairs have base/quote assets, not event outcomes",
                None,
            ),
            Capability.BOOK_UPDATES: (
                "No incremental WebSocket reconstruction is implemented",
                None,
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Kraken public trades expose a last marker but cursor pagination is not integrated into Frontier v1",
                "https://docs.kraken.com/api/docs/rest-api/get-recent-trades",
            ),
            Capability.FEE_SCHEDULE: (
                "Fee fields are retained when supplied, but account tier and current applicable fee are not resolved",
                "https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs",
            ),
            Capability.SETTLEMENT_RULES: (
                "A spot pair is not a prediction-market resolution contract",
                None,
            ),
        },
    )

    def __init__(
        self,
        config: KrakenSpotConfig | None = None,
        *,
        transport: PublicReadTransport | None = None,
    ) -> None:
        self.kraken_config = config or KrakenSpotConfig()
        super().__init__(self.kraken_config, transport=transport)

    async def discover_markets(self, limit: int = 20) -> tuple[FrontierMarket, ...]:
        self._require(Capability.MARKET_DISCOVERY)
        pair_count = min(limit, len(self.kraken_config.pairs), self.config.max_markets_per_call)
        if pair_count < 1:
            raise AdapterError("INVALID_LIMIT", "Discovery limit must be positive")
        result = []
        for symbol in self.kraken_config.pairs[:pair_count]:
            response = await self.transport.get_json(f"{BASE}/AssetPairs", {"pair": symbol})
            self._capture_response(response, "instrument_metadata")
            raw_map = self._result(response, "AssetPairs")
            if not raw_map:
                raise AdapterError(
                    "INSTRUMENT_NOT_FOUND", f"Kraken did not return configured pair {symbol}"
                )
            if len(raw_map) != 1:
                raise AdapterError(
                    "AMBIGUOUS_INSTRUMENT", f"Kraken pair query {symbol} returned multiple pairs"
                )
            native_id, raw_pair = next(iter(raw_map.items()))
            result.append(self._normalize_pair(str(native_id), raw_pair, response))
        return tuple(result)

    def _normalize_pair(
        self, native_id: str, raw: dict[str, Any], response: HTTPObservation
    ) -> FrontierMarket:
        wsname = str(raw.get("wsname") or "")
        if "/" in wsname:
            base_asset, quote_asset = (part.strip().upper() for part in wsname.split("/", 1))
        else:
            base_asset = _normalize_kraken_asset(str(raw.get("base") or ""))
            quote_asset = _normalize_kraken_asset(str(raw.get("quote") or ""))
        if not base_asset or not quote_asset:
            raise AdapterError("INVALID_INSTRUMENT", "Kraken pair is missing base/quote identity")
        price_decimals = _bounded_int(raw.get("pair_decimals"), minimum=0, maximum=12)
        quantity_decimals = _bounded_int(raw.get("lot_decimals"), minimum=0, maximum=16)
        tick_size = parse_decimal(raw.get("tick_size"))
        minimum_quantity = parse_decimal(raw.get("ordermin"))
        minimum_notional = parse_decimal(raw.get("costmin"))
        if tick_size is None and price_decimals is not None:
            tick_size = D(1).scaleb(-price_decimals)
        lot_step = D(1).scaleb(-quantity_decimals) if quantity_decimals is not None else None
        provenance_record = provenance(
            self.venue,
            ADAPTER_VERSION,
            response,
            "instrument_metadata",
            native_id,
            source_schema_version="AssetPairs",
        )
        instrument = MarketInstrument(
            native_instrument_id=native_id,
            label=wsname or str(raw.get("altname") or native_id),
            quantity_unit=QuantityUnit.BASE_ASSET,
            price_currency=quote_asset,
            tick_size=tick_size if tick_size is not None and tick_size > 0 else None,
            quantity_step=lot_step if lot_step is not None and lot_step > 0 else None,
            minimum_quantity=minimum_quantity
            if minimum_quantity is not None and minimum_quantity > 0
            else None,
            minimum_notional=minimum_notional
            if minimum_notional is not None and minimum_notional > 0
            else None,
        )
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, native_id),
            native_market_id=native_id,
            title=f"{wsname or raw.get('altname') or native_id} spot",
            description="Cash spot pair; contextual evidence only unless a separate hedge model proves equivalence.",
            market_kind=MarketKind.SPOT_PAIR,
            lifecycle=lifecycle(raw.get("status")),
            instruments=(instrument,),
            payoff=PayoffSpec(
                state_ids=(),
                exhaustive=False,
                verified=False,
                verification_basis="Spot inventory has no event settlement payoff model.",
            ),
            fees=FeeSchedule(
                note="Unknown: public pair fee fields do not establish the account's current applicable fee tier"
            ),
            base_asset=base_asset,
            quote_asset=quote_asset,
            settlement_asset=None,
            native_fields=native_json(raw),
            quality_flags=(
                "SPOT_NOT_EVENT_PAYOFF",
                "ACCOUNT_FEE_TIER_UNKNOWN",
                "ACCOUNT_ACCESS_AND_CUSTODY_UNVERIFIED",
            ),
            provenance=provenance_record,
        )

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot:
        self._require(Capability.BOOK_SNAPSHOT)
        if market.venue != self.venue or market.market_kind != MarketKind.SPOT_PAIR:
            raise AdapterError("UNSUPPORTED_MARKET", "Kraken adapter accepts spot pairs only")
        if not 1 <= depth <= 20:
            raise AdapterError("INVALID_DEPTH", "Kraken depth must be between 1 and 20")
        if instrument_id != market.native_market_id:
            raise AdapterError(
                "INSTRUMENT_NOT_FOUND", "Pair identifier does not belong to the market"
            )
        altname = str(market.native_fields.get("altname") or market.native_market_id)
        response = await self.transport.get_json(f"{BASE}/Depth", {"pair": altname, "count": depth})
        self._capture_response(response, "book_snapshot")
        raw_map = self._result(response, "Depth")
        raw_book = raw_map.get(market.native_market_id)
        if raw_book is None and len(raw_map) == 1:
            raw_book = next(iter(raw_map.values()))
        if not isinstance(raw_book, dict):
            raise AdapterError(
                "INVALID_BOOK", "Kraken book response does not match the requested pair"
            )
        asks = _kraken_book_side(raw_book.get("asks"), depth, reverse=False)
        bids = _kraken_book_side(raw_book.get("bids"), depth, reverse=True)
        flags = []
        if not asks and not bids:
            flags.append("EMPTY_BOOK")
        if asks and bids and max(x.price for x in bids) >= min(x.price for x in asks):
            flags.append("CROSSED_OR_LOCKED")
        if any(level.exchange_timestamp_utc is None for level in asks + bids):
            flags.append("LEVEL_TIMESTAMP_MISSING")
        base = market.base_asset or "base"
        quote_asset = market.quote_asset or "quote"
        return BookSnapshot(
            venue=self.venue,
            native_market_id=market.native_market_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=bids,
            price_unit=f"{quote_asset} per {base}",
            quantity_unit=QuantityUnit.BASE_ASSET,
            received_at_utc=response.response_received_at_utc,
            exchange_timestamp_semantics="Each level has an independent last-update time; no unified book snapshot time is asserted",
            quality_flags=tuple(flags),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "book_snapshot",
                market.native_market_id,
                source_schema_version="REST Depth",
                exchange_timestamp_semantics="Per-level timestamps, not a single snapshot timestamp",
            ),
        )

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        if not 1 <= limit <= 1000:
            raise AdapterError("INVALID_LIMIT", "Kraken trade limit must be between 1 and 1000")
        response = await self.transport.get_json(f"{BASE}/Trades", {"pair": native_market_id})
        self._capture_response(response, "public_trades")
        raw_map = self._result(response, "Trades")
        rows = raw_map.get(native_market_id)
        if rows is None and len(raw_map) >= 1:
            rows = next((value for key, value in raw_map.items() if key != "last"), None)
        if not isinstance(rows, list):
            raise AdapterError("INVALID_TRADE", "Kraken trades response does not include pair rows")
        result = []
        for index, row in enumerate(rows[:limit]):
            if not isinstance(row, list) or len(row) < 6:
                raise AdapterError("INVALID_TRADE", "Kraken trade row is malformed")
            price, quantity = parse_decimal(row[0]), parse_decimal(row[1])
            timestamp = parse_time(row[2])
            if price is None or quantity is None or price <= 0 or quantity <= 0:
                raise AdapterError("INVALID_TRADE", "Kraken trade price or quantity is invalid")
            result.append(
                TradeObservation(
                    venue=self.venue,
                    native_market_id=native_market_id,
                    price=price,
                    quantity=quantity,
                    aggressor_side=str(row[3]),
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{native_market_id}:{index}:{row[2]}",
                        source_schema_version="REST Trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics="Kraken per-trade epoch timestamp",
                    ),
                )
            )
        return tuple(result)

    async def fetch_candles(
        self,
        native_market_id: str,
        interval_minutes: int = 60,
        since_epoch_seconds: int | None = None,
    ) -> CandleSeries:
        self._require(Capability.HISTORICAL_CANDLES)
        intervals = {1, 5, 15, 30, 60, 240, 1440, 10080, 21600}
        if interval_minutes not in intervals:
            raise AdapterError("INVALID_INTERVAL", "Unsupported Kraken OHLC interval")
        if since_epoch_seconds is not None and not 0 <= since_epoch_seconds <= int(
            datetime.now(UTC).timestamp()
        ):
            raise AdapterError(
                "INVALID_SINCE", "OHLC start time must be a non-future Unix timestamp"
            )
        params: dict[str, str | int] = {"pair": native_market_id, "interval": interval_minutes}
        if since_epoch_seconds is not None:
            params["since"] = since_epoch_seconds
        response = await self.transport.get_json(f"{BASE}/OHLC", params)
        self._capture_response(response, "historical_candles")
        raw_map = self._result(response, "OHLC")
        rows = raw_map.get(native_market_id)
        if rows is None:
            rows = next((value for key, value in raw_map.items() if key != "last"), None)
        if not isinstance(rows, list) or len(rows) > 720:
            raise AdapterError(
                "INVALID_CANDLES", "Kraken OHLC response is malformed or exceeds 720 rows"
            )
        candles = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 8:
                raise AdapterError("INVALID_CANDLES", "Kraken OHLC row is malformed")
            values = [parse_decimal(value) for value in row[1:7]]
            timestamp = parse_time(row[0])
            if timestamp is None or any(value is None for value in values):
                raise AdapterError("INVALID_CANDLES", "Kraken OHLC row contains invalid values")
            open_price, high, low, close, _vwap, volume = values
            assert open_price is not None and high is not None and low is not None
            assert close is not None and volume is not None
            try:
                trade_count = int(row[7])
            except (TypeError, ValueError) as error:
                raise AdapterError(
                    "INVALID_CANDLES", "Kraken OHLC trade count is invalid"
                ) from error
            candles.append(
                HistoricalCandle(
                    open_time_utc=timestamp,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    trade_count=trade_count,
                )
            )
        return CandleSeries(
            venue=self.venue,
            native_market_id=native_market_id,
            interval_seconds=interval_minutes * 60,
            candles=tuple(candles),
            source_limit_note="Kraken OHLC is capped at 720 rows; the newest returned candle may be incomplete.",
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "historical_candles",
                native_market_id,
                source_schema_version=f"OHLC:{interval_minutes}m",
            ),
        )

    @staticmethod
    def _result(response: HTTPObservation, endpoint: str) -> dict[str, Any]:
        payload = response.payload
        if not isinstance(payload, dict) or not isinstance(payload.get("error"), list):
            raise AdapterError("INVALID_SCHEMA", f"Kraken {endpoint} response has no error array")
        if payload["error"]:
            message = ", ".join(str(item)[:100] for item in payload["error"][:3])
            raise AdapterError("SOURCE_REPORTED_ERROR", f"Kraken {endpoint}: {message}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise AdapterError("INVALID_SCHEMA", f"Kraken {endpoint} response has no result object")
        return result


def _normalize_kraken_asset(native: str) -> str:
    native = native.upper()
    if len(native) == 4 and native.startswith("X"):
        return native[1:]
    if len(native) == 4 and native.startswith("Z"):
        return native[1:]
    if native.startswith("XX") or native.startswith("ZA"):
        return native[1:]
    return native


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if not minimum <= result <= maximum:
        return None
    return result


def _kraken_book_side(value: Any, depth: int, *, reverse: bool) -> tuple[BookLevel, ...]:
    if not isinstance(value, list):
        raise AdapterError("INVALID_BOOK", "Kraken book side must be an array")
    levels = []
    for row in value[:depth]:
        if not isinstance(row, list) or len(row) < 2:
            raise AdapterError("INVALID_BOOK", "Kraken book level is malformed")
        price, quantity = parse_decimal(row[0]), parse_decimal(row[1])
        timestamp = parse_time(row[2]) if len(row) > 2 else None
        if price is None or quantity is None or price <= 0 or quantity <= 0:
            raise AdapterError("INVALID_BOOK", "Kraken price or quantity is invalid")
        levels.append(BookLevel(price=price, quantity=quantity, exchange_timestamp_utc=timestamp))
    return tuple(sorted(levels, key=lambda level: level.price, reverse=reverse))
