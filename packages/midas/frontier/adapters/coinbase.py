"""Coinbase Exchange public spot-data adapter; no account or trading access."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

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
    COINBASE_MARKET_DATA_TERMS_VERSION,
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
ADAPTER_VERSION = "frontier-coinbase-exchange-spot-1"
BASE = "https://api.exchange.coinbase.com"
PRODUCTS_DOC = (
    "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-single-product"
)
BOOK_DOC = (
    "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book"
)
TRADES_DOC = (
    "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades"
)
_PRODUCT_ID = re.compile(r"^[A-Z0-9]{1,12}-[A-Z0-9]{1,12}$")
_FIAT_QUOTES = frozenset({"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "JPY", "NZD"})
_DEFAULT_TERMS_HOLD_REASON = (
    "Coinbase Exchange source use remains held until the operator acknowledges "
    f"the reviewed Market Data Terms version {COINBASE_MARKET_DATA_TERMS_VERSION}."
)


def _quote_identity(code: str) -> SettlementAssetIdentity | None:
    if code in _FIAT_QUOTES:
        return SettlementAssetIdentity(kind=SettlementAssetKind.FIAT, code=code)
    return None


class CoinbaseSpotConfig(AdapterConfig):
    """Explicit bounded Coinbase product allowlist; never enumerates the catalog."""

    probe_policy_block_reason: str | None = _DEFAULT_TERMS_HOLD_REASON
    market_data_terms_version_acknowledged: str | None = Field(default=None, max_length=32)
    products: tuple[str, ...] = ("BTC-USD",)

    @model_validator(mode="after")
    def source_use_hold_requires_validated_permission(self) -> CoinbaseSpotConfig:
        if self.probe_policy_block_reason is None:
            raise ValueError(
                "Coinbase source-use hold cannot be cleared by terms acknowledgement alone; "
                "validated permission and intended-scope review are not configured"
            )
        return self

    @field_validator("products")
    @classmethod
    def validate_products(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(value) <= 20:
            raise ValueError("Configure between 1 and 20 Coinbase Exchange products")
        normalized = tuple(item.strip().upper() for item in value)
        if any(len(item) > 25 or not _PRODUCT_ID.fullmatch(item) for item in normalized):
            raise ValueError("Coinbase product must be a bounded BASE-QUOTE native identifier")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate Coinbase product")
        return normalized


class CoinbaseSpotAdapter(BaseReadOnlyAdapter):
    """Public Coinbase Exchange spot metadata, aggregated books, and bounded trades."""

    venue = Venue.COINBASE_EXCHANGE
    allowed_hosts = {"api.exchange.coinbase.com"}
    capabilities = build_capabilities(
        Venue.COINBASE_EXCHANGE,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Configured product lookup only; the venue catalog is not enumerated",
                PRODUCTS_DOC,
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Public product metadata preserves base and quote asset identities",
                PRODUCTS_DOC,
            ),
            Capability.MARKET_METADATA: (
                "Native product metadata and status fields are retained verbatim",
                PRODUCTS_DOC,
            ),
            Capability.BOOK_SNAPSHOT: (
                "Public aggregated level-2 order-book snapshot; response bytes are bounded locally",
                BOOK_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "One bounded public trade page; native maker-side is retained in raw evidence and is not mislabeled as aggressor side",
                TRADES_DOC,
            ),
            Capability.TICK_CONSTRAINTS: (
                "Native quote_increment is normalized as the minimum price tick",
                PRODUCTS_DOC,
            ),
            Capability.QUANTITY_CONSTRAINTS: (
                "Native base increment, base minimum, and minimum market funds are preserved",
                PRODUCTS_DOC,
            ),
            Capability.MARKET_LIFECYCLE: (
                "Product status and trading-disabled state are preserved",
                PRODUCTS_DOC,
            ),
            Capability.HEALTH_DIAGNOSTICS: (
                "Local request/configuration state; health() makes no network request",
                None,
            ),
        },
        {
            Capability.EVENT_MARKET_GROUPS: (
                "Spot products have no event grouping or outcome contracts",
                None,
            ),
            Capability.MULTIVARIATE_EVENT_DISCOVERY: (
                "Spot products have no multivariate event contracts",
                None,
            ),
            Capability.OUTCOME_DEFINITIONS: (
                "A spot pair has base/quote assets, not event outcomes",
                None,
            ),
            Capability.BOOK_UPDATES: (
                "Incremental WebSocket reconstruction is not implemented",
                None,
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Cursor pagination is not followed; one bounded REST page is supported",
                TRADES_DOC,
            ),
            Capability.HISTORICAL_CANDLES: (
                "Historical candle retrieval is not implemented",
                None,
            ),
            Capability.FEE_METADATA: (
                "Public product metadata does not establish the user's applicable account fee",
                PRODUCTS_DOC,
            ),
            Capability.FEE_SCHEDULE: (
                "User fee tier, maker/taker applicability, and current effective fee are unresolved",
                None,
            ),
            Capability.SETTLEMENT_RULES: (
                "Spot asset delivery is not a prediction-contract resolution payoff",
                None,
            ),
        },
    )

    def __init__(
        self,
        config: CoinbaseSpotConfig | None = None,
        *,
        transport: PublicReadTransport | None = None,
    ) -> None:
        if config is not None and type(config) is not CoinbaseSpotConfig:
            raise ValueError("Coinbase adapter requires its source-specific configuration")
        self.coinbase_config = config or CoinbaseSpotConfig()
        super().__init__(self.coinbase_config, transport=transport)

    async def discover_markets(self, limit: int = 20) -> tuple[FrontierMarket, ...]:
        self._require(Capability.MARKET_DISCOVERY)
        if not 1 <= limit <= 100:
            raise AdapterError("INVALID_LIMIT", "Discovery limit must be between 1 and 100")
        product_count = min(
            limit, len(self.coinbase_config.products), self.config.max_markets_per_call
        )
        result = []
        for product_id in self.coinbase_config.products[:product_count]:
            response = await self.transport.get_json(f"{BASE}/products/{product_id}")
            self._capture_response(response, "instrument_metadata")
            raw = self._object(response, "product metadata")
            result.append(self._normalize_product(product_id, raw, response))
        return tuple(result)

    def _normalize_product(
        self, requested_product: str, raw: dict[str, Any], response: HTTPObservation
    ) -> FrontierMarket:
        native_id = raw.get("id")
        base_asset = raw.get("base_currency")
        quote_asset = raw.get("quote_currency")
        if (
            not isinstance(native_id, str)
            or not _PRODUCT_ID.fullmatch(native_id)
            or native_id != requested_product
            or not isinstance(base_asset, str)
            or not isinstance(quote_asset, str)
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT",
                "Coinbase product identity does not match the configured native product",
            )
        base_asset, quote_asset = base_asset.strip().upper(), quote_asset.strip().upper()
        if native_id != f"{base_asset}-{quote_asset}":
            raise AdapterError(
                "INVALID_INSTRUMENT", "Coinbase product base/quote fields do not match its ID"
            )
        tick_size = _optional_positive(raw, "quote_increment", required=True)
        quantity_step = _optional_positive(raw, "base_increment", required=True)
        minimum_quantity = _optional_positive(raw, "base_min_size")
        minimum_notional = _optional_positive(raw, "min_market_funds")
        status = str(raw.get("status") or "").lower()
        trading_disabled = raw.get("trading_disabled") is True
        is_closed = status == "delisted"
        is_open = status == "online" and not trading_disabled
        flags = ["SPOT_NOT_EVENT_PAYOFF", "ACCOUNT_FEE_TIER_UNKNOWN"]
        if raw.get("auction_mode") is True:
            flags.append("AUCTION_MODE_INDICATIVE")
        if (
            status not in {"online", "delisted"}
            or trading_disabled
            or any(raw.get(key) is True for key in ("limit_only", "post_only", "cancel_only"))
        ):
            flags.append("TRADING_RESTRICTION_PRESENT")
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, native_id),
            native_market_id=native_id,
            title=str(raw.get("display_name") or native_id),
            description=(
                "Cash spot pair. Spot prices provide contextual evidence only unless a separately "
                "validated hedge model establishes an equivalent payoff."
            ),
            market_kind=MarketKind.SPOT_PAIR,
            lifecycle=lifecycle(status, active=is_open, closed=is_closed),
            instruments=(
                MarketInstrument(
                    native_instrument_id=native_id,
                    label=str(raw.get("display_name") or native_id),
                    quantity_unit=QuantityUnit.BASE_ASSET,
                    price_currency=quote_asset,
                    price_currency_identity=_quote_identity(quote_asset),
                    tick_size=tick_size,
                    quantity_step=quantity_step,
                    minimum_quantity=minimum_quantity,
                    minimum_notional=minimum_notional,
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
                    "Unknown: public product metadata does not resolve the applicable "
                    "account-specific fee schedule"
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
                native_id,
                source_schema_version="Exchange REST Product",
            ),
        )

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot:
        self._require(Capability.BOOK_SNAPSHOT)
        if market.venue != self.venue or market.market_kind != MarketKind.SPOT_PAIR:
            raise AdapterError("UNSUPPORTED_MARKET", "Coinbase adapter accepts spot pairs only")
        if not 1 <= depth <= 20:
            raise AdapterError("INVALID_DEPTH", "Coinbase depth must be between 1 and 20")
        if (
            instrument_id != market.native_market_id
            or instrument_id not in self.coinbase_config.products
        ):
            raise AdapterError(
                "INSTRUMENT_NOT_FOUND", "Product does not belong to the configured market"
            )
        response = await self.transport.get_json(
            f"{BASE}/products/{instrument_id}/book", {"level": 2}
        )
        self._capture_response(response, "book_snapshot")
        raw = self._object(response, "order book")
        asks = _book_side(raw.get("asks"), depth, reverse=False)
        bids = _book_side(raw.get("bids"), depth, reverse=True)
        if not asks and not bids:
            flags = ["EMPTY_BOOK"]
        else:
            flags = []
        if (
            asks
            and bids
            and max(level.price for level in bids) >= min(level.price for level in asks)
        ):
            flags.append("CROSSED_OR_LOCKED")
        exchange_time = parse_time(raw.get("time"))
        if exchange_time is None:
            flags.append("SOURCE_BOOK_TIME_MISSING")
        sequence = raw.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            flags.append("SOURCE_BOOK_SEQUENCE_MISSING_OR_INVALID")
        if not isinstance(raw.get("auction_mode"), bool):
            flags.append("AUCTION_STATE_MISSING")
        if raw.get("auction_mode") is True:
            flags.append("AUCTION_MODE_INDICATIVE")
        instrument = market.instruments[0]
        base_asset = market.base_asset or "base"
        quote_asset = market.quote_asset or "quote"
        return BookSnapshot(
            venue=self.venue,
            native_market_id=market.native_market_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=bids,
            price_unit=f"{quote_asset} per {base_asset}",
            price_currency=instrument.price_currency,
            price_currency_identity=instrument.price_currency_identity,
            quantity_unit=QuantityUnit.BASE_ASSET,
            received_at_utc=response.response_received_at_utc,
            exchange_timestamp_utc=exchange_time,
            exchange_timestamp_semantics=(
                "Coinbase product-book response time; source sequence and auction state are "
                "retained in raw evidence, not an atomic cross-venue execution timestamp"
            ),
            quality_flags=tuple(flags),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "book_snapshot",
                market.native_market_id,
                source_schema_version="Exchange REST Level 2",
                exchange_timestamp=exchange_time,
                exchange_timestamp_semantics="Coinbase product-book response time",
            ),
        )

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        if not 1 <= limit <= 100:
            raise AdapterError(
                "INVALID_LIMIT", "Coinbase trade page limit must be between 1 and 100"
            )
        if native_market_id not in self.coinbase_config.products:
            raise AdapterError(
                "INSTRUMENT_NOT_FOUND", "Product is outside the configured allowlist"
            )
        response = await self.transport.get_json(
            f"{BASE}/products/{native_market_id}/trades", {"limit": limit}
        )
        self._capture_response(response, "public_trades")
        rows = response.payload
        if not isinstance(rows, list) or len(rows) > 100:
            raise AdapterError(
                "INVALID_TRADE", "Coinbase trade response is malformed or exceeds 100 rows"
            )
        result = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                raise AdapterError("INVALID_TRADE", "Coinbase trade row must be an object")
            price = _positive_decimal(row.get("price"))
            quantity = _positive_decimal(row.get("size"))
            timestamp = parse_time(row.get("time"))
            trade_id = row.get("trade_id")
            if (
                price is None
                or quantity is None
                or timestamp is None
                or isinstance(trade_id, bool)
                or not isinstance(trade_id, (str, int))
                or len(str(trade_id)) > 256
            ):
                raise AdapterError(
                    "INVALID_TRADE", "Coinbase trade row has invalid identity, price, size, or time"
                )
            result.append(
                TradeObservation(
                    venue=self.venue,
                    native_market_id=native_market_id,
                    native_trade_id=str(trade_id),
                    native_instrument_id=native_market_id,
                    price=price,
                    quantity=quantity,
                    quote_currency=native_market_id.split("-", 1)[1],
                    quote_currency_identity=_quote_identity(native_market_id.split("-", 1)[1]),
                    # Coinbase's REST `side` is the maker order side, not the
                    # aggressor side. Keep it in the hash-pinned raw response.
                    aggressor_side=None,
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{native_market_id}:{trade_id}",
                        source_schema_version="Exchange REST Trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics="Coinbase trade execution time",
                    ),
                )
            )
        return tuple(result)

    @staticmethod
    def _object(response: HTTPObservation, label: str) -> dict[str, Any]:
        if not isinstance(response.payload, dict):
            raise AdapterError("INVALID_SCHEMA", f"Coinbase {label} response must be an object")
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


def _optional_positive(source: dict[str, Any], field: str, *, required: bool = False) -> D | None:
    raw = source.get(field)
    if raw is None and not required:
        return None
    result = _positive_decimal(raw)
    if result is None:
        raise AdapterError(
            "INVALID_INSTRUMENT", f"Coinbase product {field} must be a bounded positive decimal"
        )
    return result


def _book_side(value: Any, depth: int, *, reverse: bool) -> tuple[BookLevel, ...]:
    if not isinstance(value, list) or len(value) > 50_000:
        raise AdapterError(
            "INVALID_BOOK", "Coinbase level-2 side is malformed or exceeds its row bound"
        )
    levels = []
    for row in value[:depth]:
        if not isinstance(row, list) or len(row) < 2:
            raise AdapterError("INVALID_BOOK", "Coinbase book level must contain price and size")
        price, quantity = _positive_decimal(row[0]), _positive_decimal(row[1])
        if price is None or quantity is None:
            raise AdapterError(
                "INVALID_BOOK", "Coinbase book price and size must be positive decimals"
            )
        levels.append(BookLevel(price=price, quantity=quantity))
    return tuple(sorted(levels, key=lambda level: level.price, reverse=reverse))
