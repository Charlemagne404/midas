"""Gemini public spot metadata and book adapter; data use is held pending review."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator

from midas.frontier.adapters.base import (
    AdapterError,
    BaseReadOnlyAdapter,
    build_capabilities,
)
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
    Capability,
    FeeSchedule,
    FrontierMarket,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    SettlementAssetIdentity,
    SettlementAssetKind,
    TradeObservation,
    Venue,
    stable_market_id,
)

D = Decimal
ADAPTER_VERSION = "frontier-gemini-spot-2"
BASE = "https://api.gemini.com/v1"
SYMBOLS_DOC = "https://developer.gemini.com/trading/rest-api/market-data/list-symbols"
DETAILS_DOC = "https://developer.gemini.com/trading/rest-api/market-data/get-symbol-details"
BOOK_DOC = "https://developer.gemini.com/trading/rest-api/market-data/get-current-order-book"
TRADES_DOC = "https://developer.gemini.com/trading/rest-api/market-data/list-trades"
GEMINI_MARKET_DATA_AGREEMENT_URL = "https://www.gemini.com/legal/market-data-agreement"
GEMINI_API_AGREEMENT_URL = "https://www.gemini.com/legal/api-agreement"
GEMINI_MARKET_DATA_AGREEMENT_DATE = "2025-10-12"
_SYMBOL = re.compile(r"^[A-Z0-9]{4,32}$")
_FIAT_QUOTES = frozenset({"USD", "EUR", "GBP", "SGD", "AUD"})

GEMINI_SOURCE_USE_HOLD_REASON = (
    "Gemini source use remains held: the applicable residency-specific User Agreement and "
    "intended internal research scope have not been reviewed, and the documented API Use Form "
    "has not been completed. The Market Data Agreement dated "
    f"{GEMINI_MARKET_DATA_AGREEMENT_DATE} limits use to permitted internal/informational/market "
    "analysis and prohibits redistribution and specified financial-product or benchmark uses. "
    "No Gemini request will be made while this hold is present."
)


def _quote_identity(code: str) -> SettlementAssetIdentity | None:
    if code in _FIAT_QUOTES:
        return SettlementAssetIdentity(kind=SettlementAssetKind.FIAT, code=code)
    return None


class GeminiSpotConfig(AdapterConfig):
    """Explicit small symbol allowlist, one request/second, and a non-clearable source hold."""

    probe_policy_block_reason: str | None = GEMINI_SOURCE_USE_HOLD_REASON
    pairs: tuple[str, ...] = ("BTCUSD",)
    requests_per_second: Annotated[float, Field(gt=0, le=1)] = 1.0

    @model_validator(mode="after")
    def require_source_use_hold(self) -> GeminiSpotConfig:
        if self.probe_policy_block_reason is None:
            raise ValueError(
                "Gemini source-use hold cannot be cleared by configuration; a reviewed source "
                "permission mechanism is not available"
            )
        return self

    @field_validator("pairs")
    @classmethod
    def validate_pairs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(value) <= 20:
            raise ValueError("Configure between 1 and 20 Gemini spot symbols")
        normalized = tuple(item.strip().upper() for item in value)
        if any(not _SYMBOL.fullmatch(item) for item in normalized):
            raise ValueError("Gemini symbol must be a bounded ASCII native pair identifier")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate Gemini spot symbol")
        return normalized


class GeminiSpotAdapter(BaseReadOnlyAdapter):
    """Configured-pair metadata, bounded books, and one recent-trades page."""

    venue = Venue.GEMINI_SPOT
    allowed_hosts = {"api.gemini.com"}
    capabilities = build_capabilities(
        Venue.GEMINI_SPOT,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Configured symbol details only; the venue-wide symbol list is intentionally not fetched",
                DETAILS_DOC,
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Native spot base/quote identities and source precision are retained",
                DETAILS_DOC,
            ),
            Capability.MARKET_METADATA: (
                "Configured native symbol metadata; non-spot products are rejected",
                DETAILS_DOC,
            ),
            Capability.BOOK_SNAPSHOT: (
                "Bounded aggregated public REST levels; per-level timestamps are documented dummy values and ignored",
                BOOK_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "One bounded recent page after quote currency is established from native symbol details; cursor pagination is not integrated",
                TRADES_DOC,
            ),
            Capability.TICK_CONSTRAINTS: (
                "Gemini quote_increment is preserved as the exact quote-price step",
                DETAILS_DOC,
            ),
            Capability.QUANTITY_CONSTRAINTS: (
                "Gemini base tick_size and minimum base-asset order size are preserved",
                DETAILS_DOC,
            ),
            Capability.MARKET_LIFECYCLE: (
                "Native status is preserved; restricted spot modes carry a quality flag",
                DETAILS_DOC,
            ),
            Capability.HEALTH_DIAGNOSTICS: (
                "Local request/configuration state; health() makes no network request",
                None,
            ),
        },
        {
            Capability.EVENT_MARKET_GROUPS: (
                "Spot pairs are not event groups",
                None,
            ),
            Capability.MULTIVARIATE_EVENT_DISCOVERY: (
                "Spot pairs do not define multivariate event contracts",
                None,
            ),
            Capability.OUTCOME_DEFINITIONS: (
                "Spot pairs define base and quote assets, not event outcomes",
                None,
            ),
            Capability.BOOK_UPDATES: (
                "Incremental WebSocket reconstruction is not implemented",
                None,
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Trade pagination is not implemented",
                None,
            ),
            Capability.HISTORICAL_CANDLES: (
                "Historical candle retrieval is not implemented",
                None,
            ),
            Capability.FEE_METADATA: (
                "Public symbol metadata does not establish account fee applicability",
                DETAILS_DOC,
            ),
            Capability.FEE_SCHEDULE: (
                "Account fee tier and current applicable maker/taker fee are unknown",
                None,
            ),
            Capability.SETTLEMENT_RULES: (
                "Spot inventory is not a prediction-contract resolution payoff",
                None,
            ),
        },
    )

    def __init__(
        self,
        config: GeminiSpotConfig | None = None,
        *,
        transport: PublicReadTransport | None = None,
    ) -> None:
        if config is not None and type(config) is not GeminiSpotConfig:
            raise ValueError("Gemini adapter requires its source-specific configuration")
        self.gemini_config = config or GeminiSpotConfig()
        self._quote_currency_by_pair: dict[str, str] = {}
        super().__init__(self.gemini_config, transport=transport)

    async def discover_markets(self, limit: int = 20) -> tuple[FrontierMarket, ...]:
        self._require(Capability.MARKET_DISCOVERY)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AdapterError("INVALID_LIMIT", "Discovery limit must be between 1 and 100")
        count = min(limit, len(self.gemini_config.pairs), self.config.max_markets_per_call)
        markets = []
        for symbol in self.gemini_config.pairs[:count]:
            response = await self.transport.get_json(f"{BASE}/symbols/details/{symbol}")
            self._capture_response(response, "instrument_metadata")
            raw = self._object(response, "symbol details")
            market = self._normalize_symbol(symbol, raw, response)
            self._quote_currency_by_pair[symbol] = market.quote_asset or ""
            markets.append(market)
        return tuple(markets)

    def _normalize_symbol(
        self, requested_symbol: str, raw: dict[str, Any], response: HTTPObservation
    ) -> FrontierMarket:
        symbol = raw.get("symbol")
        base_asset = raw.get("base_currency")
        quote_asset = raw.get("quote_currency")
        product_type = raw.get("product_type")
        contract_type = raw.get("contract_type")
        if (
            not isinstance(symbol, str)
            or symbol.strip().upper() != requested_symbol
            or not isinstance(base_asset, str)
            or not isinstance(quote_asset, str)
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT", "Gemini symbol identity does not match its allowlisted pair"
            )
        base_asset, quote_asset = base_asset.strip().upper(), quote_asset.strip().upper()
        if (
            not base_asset
            or not quote_asset
            or symbol.strip().upper() != base_asset + quote_asset
            or product_type != "spot"
            or contract_type != "vanilla"
        ):
            raise AdapterError(
                "UNSUPPORTED_INSTRUMENT",
                "Gemini response is not the configured native vanilla spot pair",
            )
        contract_price_currency = raw.get("contract_price_currency")
        if (
            not isinstance(contract_price_currency, str)
            or contract_price_currency.strip().upper() != quote_asset
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT", "Gemini spot price currency differs from its quote asset"
            )
        price_step = _positive_decimal(raw.get("quote_increment"))
        quantity_step = _positive_decimal(raw.get("tick_size"))
        minimum_quantity = _positive_decimal(raw.get("min_order_size"))
        if price_step is None or quantity_step is None or minimum_quantity is None:
            raise AdapterError(
                "INVALID_INSTRUMENT",
                "Gemini symbol precision and minimum must be positive decimals",
            )
        status = raw.get("status")
        if not isinstance(status, str) or status.lower() not in {
            "open",
            "closed",
            "cancel_only",
            "post_only",
            "limit_only",
        }:
            raise AdapterError("INVALID_INSTRUMENT", "Gemini symbol status is missing or unknown")
        flags = ["SPOT_NOT_EVENT_PAYOFF", "ACCOUNT_FEE_TIER_UNKNOWN"]
        if status.lower() in {"cancel_only", "post_only", "limit_only"}:
            flags.append("TRADING_RESTRICTION_PRESENT")
        if raw.get("wrap_enabled") is True:
            flags.append("WRAP_FEATURE_PRESENT_NOT_MODELED")
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, requested_symbol),
            native_market_id=requested_symbol,
            title=f"{base_asset}/{quote_asset} spot",
            description=(
                "Gemini cash spot pair; contextual evidence only. It has no event-contract "
                "payoff or settlement model."
            ),
            market_kind=MarketKind.SPOT_PAIR,
            lifecycle=lifecycle(
                status, active=status.lower() in {"open", "post_only", "limit_only"}
            ),
            instruments=(
                MarketInstrument(
                    native_instrument_id=requested_symbol,
                    label=f"{base_asset}/{quote_asset}",
                    quantity_unit=QuantityUnit.BASE_ASSET,
                    price_currency=quote_asset,
                    price_currency_identity=_quote_identity(quote_asset),
                    tick_size=price_step,
                    quantity_step=quantity_step,
                    minimum_quantity=minimum_quantity,
                ),
            ),
            payoff=PayoffSpec(
                state_ids=(),
                exhaustive=False,
                verified=False,
                verification_basis="Spot inventory has no event settlement payoff model.",
            ),
            fees=FeeSchedule(
                note=(
                    "Unknown: symbol details do not establish account-specific fee tier or "
                    "applicable maker/taker charges"
                )
            ),
            base_asset=base_asset,
            quote_asset=quote_asset,
            settlement_asset=None,
            native_fields=native_json(raw),
            quality_flags=tuple(flags),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "instrument_metadata",
                requested_symbol,
                source_schema_version="Gemini Symbol Details",
            ),
        )

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot:
        self._require(Capability.BOOK_SNAPSHOT)
        if market.venue != self.venue or market.market_kind != MarketKind.SPOT_PAIR:
            raise AdapterError("UNSUPPORTED_MARKET", "Gemini adapter accepts spot pairs only")
        if type(depth) is not int or not 1 <= depth <= 20:
            raise AdapterError("INVALID_DEPTH", "Gemini depth must be between 1 and 20")
        native_id = market.native_market_id
        if instrument_id != native_id or native_id not in self.gemini_config.pairs:
            raise AdapterError("INSTRUMENT_NOT_FOUND", "Pair is outside the configured allowlist")
        if not market.has_valid_structure:
            raise AdapterError("INVALID_INSTRUMENT", "Gemini market fails structural validation")
        raw_symbol = market.native_fields.get("symbol")
        raw_base_asset = market.native_fields.get("base_currency")
        raw_quote_asset = market.native_fields.get("quote_currency")
        raw_price_currency = market.native_fields.get("contract_price_currency")
        if (
            market.canonical_id != stable_market_id(self.venue, native_id)
            or len(market.instruments) != 1
            or market.instruments[0].native_instrument_id != native_id
            or market.instruments[0].quantity_unit != QuantityUnit.BASE_ASSET
            or market.instruments[0].price_currency != market.quote_asset
            or market.instruments[0].price_currency_identity
            != _quote_identity(market.quote_asset or "")
            or not isinstance(raw_symbol, str)
            or raw_symbol.strip().upper() != native_id
            or not isinstance(raw_base_asset, str)
            or raw_base_asset.strip().upper() != market.base_asset
            or not isinstance(raw_quote_asset, str)
            or raw_quote_asset.strip().upper() != market.quote_asset
            or market.native_fields.get("product_type") != "spot"
            or market.native_fields.get("contract_type") != "vanilla"
            or not isinstance(raw_price_currency, str)
            or raw_price_currency.strip().upper() != market.quote_asset
            or market.payoff.verified
            or market.payoff.state_ids
            or any(
                instrument.outcome_id is not None or instrument.payouts
                for instrument in market.instruments
            )
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT",
                "Gemini market does not match its raw spot metadata or has event-payoff semantics",
            )
        response = await self.transport.get_json(
            f"{BASE}/book/{native_id}", {"limit_bids": depth, "limit_asks": depth}
        )
        self._capture_response(response, "book_snapshot")
        raw = self._object(response, "order book")
        asks = _book_side(raw.get("asks"), depth, reverse=False)
        bids = _book_side(raw.get("bids"), depth, reverse=True)
        flags: list[str] = ["SOURCE_BOOK_TIMESTAMP_UNAVAILABLE"]
        if not asks and not bids:
            flags.append("EMPTY_BOOK")
        if (
            asks
            and bids
            and max(level.price for level in bids) >= min(level.price for level in asks)
        ):
            flags.append("CROSSED_OR_LOCKED")
        provenance_value = provenance(
            self.venue,
            ADAPTER_VERSION,
            response,
            "book_snapshot",
            native_id,
            source_schema_version="Gemini REST Order Book",
            exchange_timestamp=None,
            exchange_timestamp_semantics=(
                "Gemini documents per-level timestamp fields as dummy compatibility values; "
                "no exchange book timestamp is established"
            ),
        )
        return BookSnapshot(
            venue=self.venue,
            native_market_id=native_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=bids,
            price_unit=f"{market.quote_asset} per {market.base_asset}",
            price_currency=market.quote_asset,
            price_currency_identity=_quote_identity(market.quote_asset or ""),
            quantity_unit=QuantityUnit.BASE_ASSET,
            received_at_utc=response.response_received_at_utc,
            exchange_timestamp_utc=None,
            exchange_timestamp_semantics=(
                "No exchange book timestamp; per-level timestamp values are documented dummy "
                "fields and ignored. Local HTTP receipt time is retained."
            ),
            quality_flags=tuple(flags),
            provenance=provenance_value,
        )

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        self._validate_trade_request(native_market_id, limit)
        quote_currency = self._quote_currency_by_pair.get(native_market_id)
        if not quote_currency:
            raise AdapterError(
                "QUOTE_CURRENCY_UNRESOLVED",
                "Gemini trade normalization requires source-verified quote-currency metadata from symbol details",
            )
        response = await self.transport.get_json(
            f"{BASE}/trades/{native_market_id}", {"limit_trades": limit}
        )
        self._capture_response(response, "public_trades")
        rows = response.payload
        if not isinstance(rows, list) or len(rows) > limit:
            raise AdapterError(
                "INVALID_TRADE", "Gemini trade response is malformed or exceeds the page limit"
            )

        result: list[TradeObservation] = []
        seen_ids: set[int] = set()
        previous_timestamp: datetime | None = None
        for row in rows:
            if not isinstance(row, dict):
                raise AdapterError("INVALID_TRADE", "Gemini trade row must be an object")
            trade_id = row.get("tid")
            price_raw, amount_raw = row.get("price"), row.get("amount")
            trade_type = row.get("type")
            broken = row.get("broken", False)
            timestamp = _gemini_trade_timestamp(row)
            price = (
                _positive_decimal(price_raw)
                if isinstance(price_raw, str) and len(price_raw) <= 128
                else None
            )
            quantity = (
                _positive_decimal(amount_raw)
                if isinstance(amount_raw, str) and len(amount_raw) <= 128
                else None
            )
            if (
                type(trade_id) is not int
                or not 0 <= trade_id <= 9_223_372_036_854_775_807
                or trade_id in seen_ids
                or not isinstance(price_raw, str)
                or len(price_raw) > 128
                or not isinstance(amount_raw, str)
                or len(amount_raw) > 128
                or price is None
                or quantity is None
            ):
                raise AdapterError(
                    "INVALID_TRADE",
                    "Gemini trade row has invalid trade ID, exact decimal price, or amount",
                )
            if timestamp is None:
                raise AdapterError(
                    "INVALID_TRADE", "Gemini trade timestamp is invalid or inconsistent"
                )
            if not isinstance(trade_type, str) or trade_type not in {"buy", "sell"}:
                raise AdapterError("INVALID_TRADE", "Gemini trade side is not buy or sell")
            if row.get("exchange") != "gemini":
                raise AdapterError("INVALID_TRADE", "Gemini trade exchange identity is invalid")
            if type(broken) is not bool:
                raise AdapterError("INVALID_TRADE", "Gemini trade break flag must be boolean")
            if broken:
                raise AdapterError(
                    "BROKEN_TRADE",
                    "Gemini broken trades are excluded from normal market-data research",
                )
            if previous_timestamp is not None and timestamp > previous_timestamp:
                raise AdapterError(
                    "INVALID_TRADE_ORDER",
                    "Gemini trade page is not in documented newest-first timestamp order",
                )
            seen_ids.add(trade_id)
            previous_timestamp = timestamp
            result.append(
                TradeObservation(
                    schema_version=2,
                    venue=self.venue,
                    native_market_id=native_market_id,
                    native_trade_id=str(trade_id),
                    native_instrument_id=native_market_id,
                    price=price,
                    quantity=quantity,
                    quote_currency=quote_currency,
                    quote_currency_identity=_quote_identity(quote_currency),
                    aggressor_side=trade_type,
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{native_market_id}:{trade_id}",
                        source_schema_version="Gemini REST /v1/trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics=(
                            "Gemini trade execution time; timestampms preferred when both fields exist"
                        ),
                    ),
                )
            )
        return tuple(result)

    def _validate_trade_request(self, native_market_id: str, limit: int) -> None:
        if (
            not isinstance(native_market_id, str)
            or not _SYMBOL.fullmatch(native_market_id)
            or native_market_id != native_market_id.upper()
            or native_market_id not in self.gemini_config.pairs
        ):
            raise AdapterError(
                "INVALID_MARKET", "Gemini trade symbol is outside its pair allowlist"
            )
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AdapterError("INVALID_LIMIT", "Gemini trade page limit must be between 1 and 100")

    @staticmethod
    def _object(response: HTTPObservation, label: str) -> dict[str, Any]:
        if not isinstance(response.payload, dict):
            raise AdapterError("INVALID_SCHEMA", f"Gemini {label} response must be an object")
        return response.payload


def _positive_decimal(value: Any) -> D | None:
    result = parse_decimal(value)
    if result is None or result <= 0:
        return None
    parts = result.as_tuple()
    if not isinstance(parts.exponent, int):
        return None
    if len(parts.digits) > 36 or parts.exponent < -18 or abs(result.adjusted()) > 18:
        return None
    return result


def _gemini_trade_timestamp(row: dict[str, Any]) -> datetime | None:
    values: list[datetime] = []
    for field in ("timestampms", "timestamp"):
        if field not in row:
            continue
        value = row[field]
        if not (
            type(value) is int
            and value >= 0
            or isinstance(value, str)
            and value.isdecimal()
            and len(value) <= 20
        ):
            return None
        timestamp = parse_time(value)
        if timestamp is None:
            return None
        values.append(timestamp)
    if not values or any(value != values[0] for value in values[1:]):
        return None
    return values[0]


def _book_side(value: Any, depth: int, *, reverse: bool) -> tuple[BookLevel, ...]:
    if not isinstance(value, list) or len(value) > depth:
        raise AdapterError(
            "INVALID_BOOK", "Gemini book side is malformed or exceeds the requested depth"
        )
    levels: list[BookLevel] = []
    for row in value:
        if not isinstance(row, dict):
            raise AdapterError("INVALID_BOOK", "Gemini book level must be an object")
        # The official API documents exact decimal strings. Refuse a float or a
        # dummy timestamp in place of the price/quantity evidence.
        if not isinstance(row.get("price"), str) or not isinstance(row.get("amount"), str):
            raise AdapterError(
                "INVALID_BOOK", "Gemini price and amount must be exact decimal strings"
            )
        price, quantity = _positive_decimal(row["price"]), _positive_decimal(row["amount"])
        if price is None or quantity is None:
            raise AdapterError("INVALID_BOOK", "Gemini price and amount must be positive decimals")
        levels.append(BookLevel(price=price, quantity=quantity, exchange_timestamp_utc=None))
    return tuple(sorted(levels, key=lambda item: item.price, reverse=reverse))
