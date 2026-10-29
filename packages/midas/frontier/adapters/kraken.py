"""Kraken spot public-data adapter; spot prices are never event-contract payoffs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from midas.frontier.adapters.base import AdapterError, BaseReadOnlyAdapter, build_capabilities
from midas.frontier.adapters.kraken_book_stream import KrakenBookReconstructor
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
    KrakenBookUpdateFrame,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    Provenance,
    QuantityUnit,
    RawObservation,
    SettlementAssetIdentity,
    SettlementAssetKind,
    TradeObservation,
    Venue,
    stable_market_id,
)

D = Decimal
ADAPTER_VERSION = "frontier-kraken-spot-12"
BASE = "https://api.kraken.com/0/public"
KRAKEN_SPOT_WEBSOCKET_V2_URL = "wss://ws.kraken.com/v2"
ORDERBOOK_DOC = "https://docs.kraken.com/api-reference/market-data/get-order-book"
BOOK_STREAM_DOC = "https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book"
MAX_KRAKEN_STREAM_FRAMES = 32
MAX_KRAKEN_STREAM_SECONDS = 10.0
MAX_KRAKEN_CAPTURE_BYTES = 2 * 1024 * 1024
MAX_KRAKEN_CAPTURE_RECORDS = 32
_KNOWN_FIAT_QUOTES = frozenset({"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "JPY"})
_WS_ASSET_CODES = {"XBT": "BTC", "XDG": "DOGE"}


def _quote_unit_identity(code: str) -> SettlementAssetIdentity | None:
    if code in _KNOWN_FIAT_QUOTES:
        return SettlementAssetIdentity(kind=SettlementAssetKind.FIAT, code=code)
    return None


class KrakenSpotConfig(AdapterConfig):
    """Bounded pair allowlist and public Spot REST rate no higher than 1 request/sec."""

    # Kraken's published public Spot REST guidance is 1 request/sec or less.
    # https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-
    pairs: tuple[str, ...] = ("XBTUSD",)
    requests_per_second: Annotated[float, Field(gt=0, le=1)] = 1.0

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
            Capability.BOOK_UPDATES: (
                "One-symbol bounded WebSocket v2 capture; subscription ack, ordered snapshots and updates, exact CRC32 reconstruction, no reconnect or continuity claim",
                BOOK_STREAM_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "Public spot trade history",
                "https://docs.kraken.com/api-reference/market-data/get-recent-trades",
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
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Kraken public trades expose a last marker but cursor pagination is not integrated into Frontier v1",
                "https://docs.kraken.com/api-reference/market-data/get-recent-trades",
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
        stream_connector: Any = None,
    ) -> None:
        self.kraken_config = config or KrakenSpotConfig()
        self._stream_connector = stream_connector
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
        native_id = self._validate_native_pair_id(native_id)
        wsname_value = raw.get("wsname")
        wsname = wsname_value if isinstance(wsname_value, str) else ""
        assets = _kraken_pair_assets(raw)
        if assets is None:
            raise AdapterError("INVALID_INSTRUMENT", "Kraken pair is missing base/quote identity")
        base_asset, quote_asset = assets
        price_decimals = _bounded_int(raw.get("pair_decimals"), minimum=0, maximum=12)
        quantity_decimals = _bounded_int(raw.get("lot_decimals"), minimum=0, maximum=16)
        if price_decimals is None or quantity_decimals is None:
            raise AdapterError(
                "INVALID_INSTRUMENT",
                "Kraken pair precision must be bounded integer metadata",
            )
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
        quote_identity = _quote_unit_identity(quote_asset)
        instrument = MarketInstrument(
            native_instrument_id=native_id,
            label=wsname or str(raw.get("altname") or native_id),
            quantity_unit=QuantityUnit.BASE_ASSET,
            price_currency=quote_asset,
            price_currency_identity=quote_identity,
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
        if type(depth) is not int or not 1 <= depth <= 20:
            raise AdapterError("INVALID_DEPTH", "Kraken depth must be between 1 and 20")
        if instrument_id != market.native_market_id:
            raise AdapterError(
                "INSTRUMENT_NOT_FOUND", "Pair identifier does not belong to the market"
            )
        native_market_id = self._validate_native_pair_id(market.native_market_id)
        if not market.has_valid_structure:
            raise AdapterError("INVALID_INSTRUMENT", "Kraken market fails structural revalidation")
        native_assets = _kraken_pair_assets(market.native_fields)
        if (
            market.canonical_id != stable_market_id(self.venue, native_market_id)
            or native_assets is None
            or (market.base_asset, market.quote_asset) != native_assets
            or len(market.instruments) != 1
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT", "Kraken market identity does not match native pair metadata"
            )
        instrument = market.instruments[0]
        if (
            instrument.native_instrument_id != native_market_id
            or instrument.quantity_unit != QuantityUnit.BASE_ASSET
            or instrument.price_currency != market.quote_asset
            or instrument.price_currency_identity != _quote_unit_identity(market.quote_asset or "")
        ):
            raise AdapterError(
                "INVALID_INSTRUMENT", "Kraken instrument does not match its native pair identity"
            )
        response = await self.transport.get_json(
            f"{BASE}/Depth", {"pair": native_market_id, "count": depth}
        )
        self._capture_response(response, "book_snapshot")
        raw_map = self._result(response, "Depth")
        raw_book = raw_map.get(native_market_id)
        if any(key != native_market_id for key in raw_map) or not isinstance(raw_book, dict):
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
        base, quote_asset = market.base_asset, market.quote_asset
        return BookSnapshot(
            venue=self.venue,
            native_market_id=market.native_market_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=bids,
            price_unit=f"{quote_asset} per {base}",
            price_currency=instrument.price_currency,
            price_currency_identity=instrument.price_currency_identity,
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

    async def capture_book_updates(
        self,
        market: FrontierMarket,
        *,
        max_frames: int = 16,
        max_updates: int = 16,
        max_duration_seconds: float = 3.0,
        depth: int = 10,
    ) -> tuple[KrakenBookUpdateFrame, ...]:
        """Capture one bounded Kraken v2 public book stream without reconnecting."""
        self._require(Capability.BOOK_UPDATES)
        if self.config.probe_policy_block_reason is not None:
            raise AdapterError("SOURCE_USE_HELD", self.config.probe_policy_block_reason)
        if not self.config.enabled or not self.config.live_public_probe_enabled:
            raise AdapterError(
                "PUBLIC_PROBE_DISABLED",
                "Enable this source and its bounded public-probe flag before opening a stream",
            )
        if type(max_frames) is not int or not 1 <= max_frames <= MAX_KRAKEN_STREAM_FRAMES:
            raise AdapterError(
                "INVALID_STREAM_LIMIT", "Kraken frame limit must be between 1 and 32"
            )
        if type(max_updates) is not int or not 1 <= max_updates <= 100:
            raise AdapterError(
                "INVALID_STREAM_LIMIT", "Kraken update limit must be between 1 and 100"
            )
        if (
            not isinstance(max_duration_seconds, (int, float))
            or isinstance(max_duration_seconds, bool)
            or not 0.1 <= max_duration_seconds <= MAX_KRAKEN_STREAM_SECONDS
        ):
            raise AdapterError(
                "INVALID_STREAM_LIMIT", "Kraken stream duration must be between 0.1 and 10 seconds"
            )
        if type(depth) is not int or depth not in {10, 25, 100}:
            raise AdapterError("INVALID_STREAM_DEPTH", "Kraken book depth must be 10, 25, or 100")
        if self._captures:
            raise AdapterError(
                "UNCLEARED_CAPTURE_BUFFER",
                "Consume earlier adapter captures before starting a stream",
            )
        symbol = self._book_stream_symbol(market)
        reconstructor = KrakenBookReconstructor(symbol, depth=depth)
        if self._stream_connector is None:
            from websockets.asyncio.client import connect

            connector = connect
        else:
            connector = self._stream_connector

        loop = asyncio.get_running_loop()
        deadline = loop.time() + float(max_duration_seconds)
        try:
            await asyncio.wait_for(
                self.transport.pace(),
                timeout=min(self.config.timeout_seconds, float(max_duration_seconds)),
            )
        except TimeoutError as error:
            raise AdapterError(
                "STREAM_RATE_LIMIT_WAIT", "Kraken stream deferred by the bounded pacing wait"
            ) from error
        request_started = datetime.now(UTC)
        request_monotonic_ns = time.monotonic_ns()
        open_timeout = min(self.config.timeout_seconds, deadline - loop.time())
        if open_timeout <= 0:
            raise AdapterError("STREAM_DEADLINE", "Kraken stream capture deadline expired")

        received_frames = 0
        book_state_count = 0
        records: list[KrakenBookUpdateFrame] = []
        try:
            async with connector(
                KRAKEN_SPOT_WEBSOCKET_V2_URL,
                open_timeout=open_timeout,
                close_timeout=min(1.0, self.config.timeout_seconds),
                max_size=self.config.max_response_bytes,
                max_queue=1,
                ping_interval=None,
                compression=None,
                proxy=None,
            ) as websocket:

                async def send_bounded(message: str) -> None:
                    send_timeout = min(self.config.timeout_seconds, deadline - loop.time())
                    if send_timeout <= 0:
                        raise AdapterError(
                            "STREAM_DEADLINE", "Kraken stream capture deadline expired"
                        )
                    try:
                        await asyncio.wait_for(websocket.send(message), timeout=send_timeout)
                    except TimeoutError as error:
                        raise AdapterError(
                            "STREAM_SEND_TIMEOUT", "Kraken stream send exceeded its time bound"
                        ) from error

                await send_bounded(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "params": {
                                "channel": "book",
                                "depth": depth,
                                "symbol": [symbol],
                            },
                            "req_id": 1,
                        },
                        separators=(",", ":"),
                    )
                )
                while received_frames < max_frames and book_state_count < max_updates:
                    receive_timeout = min(deadline - loop.time(), self.config.timeout_seconds)
                    if receive_timeout <= 0:
                        break
                    try:
                        raw_frame = await asyncio.wait_for(
                            websocket.recv(), timeout=receive_timeout
                        )
                    except TimeoutError:
                        if loop.time() >= deadline:
                            break
                        continue
                    received_frames += 1
                    capture = self._capture_book_stream_frame(
                        raw_frame,
                        request_started=request_started,
                        request_monotonic_ns=request_monotonic_ns,
                    )
                    try:
                        state = reconstructor.process_frame(raw_frame)
                    except AdapterError:
                        raise
                    frame_type = reconstructor.last_frame_type
                    if frame_type is None:
                        raise AdapterError(
                            "UNSUPPORTED_STREAM_MESSAGE",
                            "Kraken WebSocket message has no normalized protocol type",
                        )
                    source_timestamp = state.source_timestamp_utc if state is not None else None
                    source_semantics = (
                        "Kraken v2 per-message book timestamp; no reconnect or gap inference"
                        if state is not None
                        else "Control message has no exchange book timestamp"
                    )
                    observation_id = hashlib.sha256(
                        "|".join(
                            (
                                self.venue.value,
                                capture.observation_kind,
                                capture.request_url,
                                capture.raw_sha256,
                                request_started.isoformat(),
                                capture.received_at_utc.isoformat(),
                            )
                        ).encode("utf-8")
                    ).hexdigest()
                    frame_provenance = Provenance(
                        source_url=capture.request_url,
                        adapter_version=ADAPTER_VERSION,
                        source_schema_version="kraken-spot-websocket-v2-book-v1",
                        request_started_at_utc=capture.request_started_at_utc,
                        response_received_at_utc=capture.received_at_utc,
                        request_elapsed_monotonic_ns=capture.request_elapsed_monotonic_ns,
                        processed_at_utc=datetime.now(UTC),
                        exchange_timestamp_utc=source_timestamp,
                        exchange_timestamp_semantics=source_semantics,
                        raw_sha256=capture.raw_sha256,
                        observation_id=observation_id,
                    )
                    frame = KrakenBookUpdateFrame(
                        schema_version=2,
                        frame_type=frame_type,
                        native_market_id=market.native_market_id,
                        symbol=symbol,
                        subscription_depth=depth,
                        stream_message_index=received_frames - 1,
                        book_message_index=state.message_index if state is not None else None,
                        subscription_acknowledged=reconstructor.subscription_acknowledged,
                        bids=state.bids if state is not None else (),
                        asks=state.asks if state is not None else (),
                        source_timestamp_utc=source_timestamp,
                        checksum=state.checksum if state is not None else None,
                        checksum_verified=state.checksum_verified if state is not None else False,
                        received_at_utc=capture.received_at_utc,
                        raw_sha256=capture.raw_sha256,
                        provenance=frame_provenance,
                    )
                    records.append(frame)
                    if state is not None:
                        book_state_count += 1
        except AdapterError as error:
            self.report_failure(error.code, str(error))
            raise
        except Exception as error:
            self.report_failure("STREAM_FAILED", type(error).__name__)
            raise AdapterError(
                "STREAM_FAILED", f"Kraken public stream ended: {type(error).__name__}"
            ) from error
        if records:
            self._last_success = datetime.now(UTC)
            self._last_error_code = None
            self._last_error = None
        return tuple(records)

    def _book_stream_symbol(self, market: FrontierMarket) -> str:
        native_id = self._validate_native_pair_id(market.native_market_id)
        assets = _kraken_pair_assets(market.native_fields)
        instrument = market.instruments[0] if len(market.instruments) == 1 else None
        if (
            not market.has_valid_structure
            or market.venue != self.venue
            or market.market_kind != MarketKind.SPOT_PAIR
            or market.canonical_id != stable_market_id(self.venue, native_id)
            or assets is None
            or (market.base_asset, market.quote_asset) != assets
            or instrument is None
            or instrument.native_instrument_id != native_id
        ):
            raise AdapterError("INVALID_INSTRUMENT", "Kraken stream market fails identity checks")
        native_aliases = {
            native_id,
            str(market.native_fields.get("altname", "")).upper(),
            str(market.native_fields.get("wsname", "")).upper(),
        }
        if not native_aliases.intersection(self.kraken_config.pairs):
            raise AdapterError(
                "PAIR_NOT_CONFIGURED", "Kraken market is outside the configured pair allowlist"
            )
        base = _WS_ASSET_CODES.get(market.base_asset or "", market.base_asset or "")
        quote = _WS_ASSET_CODES.get(market.quote_asset or "", market.quote_asset or "")
        symbol = f"{base}/{quote}"
        if re.fullmatch(r"[A-Z0-9]{2,20}/[A-Z0-9]{2,20}", symbol) is None:
            raise AdapterError("INVALID_INSTRUMENT", "Kraken WebSocket symbol is invalid")
        return symbol

    def _capture_book_stream_frame(
        self,
        raw_frame: str | bytes,
        *,
        request_started: datetime,
        request_monotonic_ns: int,
    ) -> RawObservation:
        if isinstance(raw_frame, bytes):
            raw_bytes = raw_frame
            raw_body = base64.b64encode(raw_bytes).decode("ascii")
            encoding: Literal["base64", "utf8"] = "base64"
        elif isinstance(raw_frame, str):
            raw_bytes = raw_frame.encode("utf-8", errors="strict")
            raw_body = raw_frame
            encoding = "utf8"
        else:
            raise AdapterError("INVALID_STREAM_FRAME", "Kraken frame must be text or bytes")
        if len(raw_bytes) > self.config.max_response_bytes:
            raise AdapterError("STREAM_FRAME_TOO_LARGE", "Kraken frame exceeds its byte bound")
        if (
            self._capture_bytes + len(raw_bytes) > MAX_KRAKEN_CAPTURE_BYTES
            or len(self._captures) >= MAX_KRAKEN_CAPTURE_RECORDS
        ):
            raise AdapterError(
                "CAPTURE_BUDGET_EXCEEDED", "Kraken stream capture budget is exhausted"
            )
        received_at = datetime.now(UTC)
        capture = RawObservation(
            venue=self.venue,
            observation_kind="public_book_update_frame",
            request_url=KRAKEN_SPOT_WEBSOCKET_V2_URL,
            http_status=101,
            request_started_at_utc=request_started,
            received_at_utc=received_at,
            request_elapsed_monotonic_ns=max(0, time.monotonic_ns() - request_monotonic_ns),
            raw_body_encoding=encoding,
            raw_body=raw_body,
            raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            adapter_version=ADAPTER_VERSION,
        )
        self._captures.append(capture)
        self._capture_bytes += len(raw_bytes)
        return capture

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise AdapterError("INVALID_LIMIT", "Kraken trade limit must be between 1 and 1000")
        native_market_id = self._validate_native_pair_id(native_market_id)
        response = await self.transport.get_json(
            f"{BASE}/Trades", {"pair": native_market_id, "count": limit}
        )
        self._capture_response(response, "public_trades")
        raw_map = self._result(response, "Trades")
        if native_market_id not in raw_map:
            raise AdapterError(
                "TRADE_MARKET_MISMATCH", "Kraken trades response omitted the requested pair key"
            )
        if any(key not in {native_market_id, "last"} for key in raw_map):
            raise AdapterError(
                "INVALID_TRADE", "Kraken trades response contains an unexpected pair"
            )
        rows = raw_map[native_market_id]
        if not isinstance(rows, list) or len(rows) > limit:
            raise AdapterError("INVALID_TRADE", "Kraken trades response does not include pair rows")
        result = []
        for index, row in enumerate(rows[:limit]):
            if not isinstance(row, list) or len(row) not in {6, 7}:
                raise AdapterError("INVALID_TRADE", "Kraken trade row is malformed")
            price, quantity = parse_decimal(row[0]), parse_decimal(row[1])
            timestamp = parse_time(row[2])
            if price is None or quantity is None or price <= 0 or quantity <= 0:
                raise AdapterError("INVALID_TRADE", "Kraken trade price or quantity is invalid")
            if timestamp is None:
                raise AdapterError("INVALID_TRADE", "Kraken trade timestamp is invalid")
            native_trade_id: str | None = None
            if len(row) == 7:
                raw_trade_id = row[6]
                if (
                    isinstance(raw_trade_id, bool)
                    or not isinstance(raw_trade_id, (int, str))
                    or (isinstance(raw_trade_id, int) and raw_trade_id < 0)
                    or (isinstance(raw_trade_id, str) and not raw_trade_id.strip())
                    or len(str(raw_trade_id)) > 256
                ):
                    raise AdapterError("INVALID_TRADE", "Kraken trade identifier is invalid")
                native_trade_id = str(raw_trade_id)
            result.append(
                TradeObservation(
                    schema_version=2,
                    venue=self.venue,
                    native_market_id=native_market_id,
                    native_trade_id=native_trade_id,
                    native_instrument_id=native_market_id,
                    price=price,
                    quantity=quantity,
                    # The official REST example shows a native one-letter code but does not
                    # define its maker/taker or aggressor semantics. Keep it in raw evidence.
                    aggressor_side=None,
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{native_market_id}:{native_trade_id or f'{index}:{row[2]}'}",
                        source_schema_version="Spot REST Trades",
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
        if since_epoch_seconds is not None and (
            type(since_epoch_seconds) is not int
            or not 0 <= since_epoch_seconds <= int(datetime.now(UTC).timestamp())
        ):
            raise AdapterError(
                "INVALID_SINCE", "OHLC start time must be a non-future Unix timestamp"
            )
        native_market_id = self._validate_native_pair_id(native_market_id)
        params: dict[str, str | int] = {"pair": native_market_id, "interval": interval_minutes}
        if since_epoch_seconds is not None:
            params["since"] = since_epoch_seconds
        response = await self.transport.get_json(f"{BASE}/OHLC", params)
        self._capture_response(response, "historical_candles")
        raw_map = self._result(response, "OHLC")
        if native_market_id not in raw_map:
            raise AdapterError(
                "CANDLE_PAIR_MISMATCH", "Kraken OHLC response omitted the requested pair"
            )
        if any(key not in {native_market_id, "last"} for key in raw_map):
            raise AdapterError(
                "INVALID_CANDLES", "Kraken OHLC response contains an unexpected pair"
            )
        rows = raw_map[native_market_id]
        if not isinstance(rows, list) or len(rows) > 720:
            raise AdapterError(
                "INVALID_CANDLES", "Kraken OHLC response is malformed or exceeds 720 rows"
            )
        candles = []
        for row in rows:
            if not isinstance(row, list) or len(row) != 8:
                raise AdapterError("INVALID_CANDLES", "Kraken OHLC row is malformed")
            values = [parse_decimal(value) for value in row[1:7]]
            timestamp = parse_time(row[0])
            if timestamp is None or any(value is None for value in values):
                raise AdapterError("INVALID_CANDLES", "Kraken OHLC row contains invalid values")
            open_price, high, low, close, _vwap, volume = values
            assert open_price is not None and high is not None and low is not None
            assert close is not None and volume is not None
            trade_count = row[7]
            if (
                any(value < 0 for value in values if value is not None)
                or low > high
                or not low <= open_price <= high
                or not low <= close <= high
                or type(trade_count) is not int
                or trade_count < 0
            ):
                raise AdapterError(
                    "INVALID_CANDLES", "Kraken OHLC prices, volume, or trade count are invalid"
                )
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
            requested_since_epoch_seconds=since_epoch_seconds,
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

    @staticmethod
    def _validate_native_pair_id(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 64
            or not re.fullmatch(r"[A-Za-z0-9./_-]+", value)
            or value.lower() == "last"
        ):
            raise AdapterError("INVALID_MARKET_ID", "Kraken pair identifier is malformed")
        return value


def _normalize_kraken_asset(native: str) -> str:
    native = native.upper()
    if len(native) == 4 and native.startswith("X"):
        return native[1:]
    if len(native) == 4 and native.startswith("Z"):
        return native[1:]
    if native.startswith("XX") or native.startswith("ZA"):
        return native[1:]
    return native


def _kraken_pair_assets(raw: dict[str, Any]) -> tuple[str, str] | None:
    wsname = raw.get("wsname")
    if isinstance(wsname, str) and "/" in wsname:
        parts = wsname.split("/")
        if len(parts) != 2:
            return None
        base_asset, quote_asset = (part.strip().upper() for part in parts)
    else:
        native_base, native_quote = raw.get("base"), raw.get("quote")
        if not isinstance(native_base, str) or not isinstance(native_quote, str):
            return None
        base_asset = _normalize_kraken_asset(native_base)
        quote_asset = _normalize_kraken_asset(native_quote)
    if not base_asset or not quote_asset:
        return None
    return base_asset, quote_asset


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    if type(value) is not int:
        return None
    if not minimum <= value <= maximum:
        return None
    return value


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
