"""Polymarket adapter over the existing version-aware public normalization path."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from midas.core.models import Fee as LegacyFee
from midas.core.models import Market as LegacyMarket
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
from midas.frontier.adapters.transport import HTTPObservation
from midas.frontier.models import (
    AdapterConfig,
    BookLevel,
    BookSnapshot,
    Capability,
    FeeSchedule,
    FeeStatus,
    FrontierMarket,
    MarketInstrument,
    MarketKind,
    PayoffSpec,
    QuantityUnit,
    ResolutionSpec,
    SettlementAssetIdentity,
    SettlementAssetKind,
    StatePayout,
    TradeBatch,
    TradeObservation,
    Venue,
    stable_market_id,
)
from midas.market_data.polymarket import normalize_market

D = Decimal
ADAPTER_VERSION = "frontier-polymarket-6"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
CLOB_V2 = "https://clob-v2.polymarket.com"
DATA = "https://data-api.polymarket.com"
POLY_FEES_DOC = "https://docs.polymarket.com/trading/fees"
POLY_DATA_DOC = "https://docs.polymarket.com/developers/CLOB/introduction"
POLY_PROTOCOL_DOC = "https://github.com/Polymarket/rs-clob-client-v2/blob/main/README.md"
POLY_V2_ASSETS_DOC = "https://github.com/Polymarket/polymarket-v2-external/blob/main/README.md"
POLY_V2_PUSD_ADDRESS = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"


def _payout_asset_identity(protocol: str) -> SettlementAssetIdentity | None:
    if protocol != "v2":
        return None
    return SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="pUSD",
        network_id="eip155:137",
        asset_reference=POLY_V2_PUSD_ADDRESS,
    )


class PolymarketAdapter(BaseReadOnlyAdapter):
    venue = Venue.POLYMARKET
    allowed_hosts = {
        "gamma-api.polymarket.com",
        "clob.polymarket.com",
        "clob-v2.polymarket.com",
        "data-api.polymarket.com",
    }
    capabilities = build_capabilities(
        Venue.POLYMARKET,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Active markets via public Gamma REST API",
                "https://docs.polymarket.com/developers/gamma-markets-api/overview",
            ),
            Capability.EVENT_MARKET_GROUPS: (
                "Bounded public Gamma event detail with its child markets and parent title",
                "https://docs.polymarket.com/market-data/discover-markets",
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Outcome token identifiers via Gamma v1/v2 fields",
                "https://docs.polymarket.com/developers/CLOB/introduction",
            ),
            Capability.MARKET_METADATA: (
                "Native market and condition metadata plus exact known-ID Gamma detail lookup are retained",
                "https://docs.polymarket.com/market-data/discover-markets",
            ),
            Capability.OUTCOME_DEFINITIONS: (
                "Outcome labels and token IDs are exposed; payout attestation remains separate",
                "https://docs.polymarket.com/developers/CLOB/introduction",
            ),
            Capability.BOOK_SNAPSHOT: (
                "Public CLOB REST snapshots use the host for the source market's v1 or v2 asset schema",
                POLY_PROTOCOL_DOC,
            ),
            Capability.PUBLIC_TRADES: (
                "Public Data API trades",
                "https://institute.polymarket.com/data",
            ),
            Capability.PAGINATED_PUBLIC_TRADES: (
                "Public condition-filtered Data API v2 trades with opaque keyset cursors; each page is one bounded GET",
                "https://data-api.polymarket.com/v2/docs",
            ),
            Capability.FEE_SCHEDULE: (
                "Market fee metadata is accepted only through the existing strict exponent-one validator",
                POLY_FEES_DOC,
            ),
            Capability.TICK_CONSTRAINTS: (
                "CLOB book tick size and Gamma minimums are retained when present",
                "https://docs.polymarket.com/developers/CLOB/market-data",
            ),
            Capability.QUANTITY_CONSTRAINTS: (
                "Gamma minimum order quantity is retained when present",
                "https://docs.polymarket.com/developers/Gamma-markets-api/overview",
            ),
            Capability.SETTLEMENT_RULES: (
                "Resolution source/description are exposed as source text; no semantic equivalence is certified",
                "https://docs.polymarket.com/developers/Gamma-markets-api/overview",
            ),
            Capability.MARKET_LIFECYCLE: (
                "Active/closed/order-acceptance metadata is preserved",
                "https://docs.polymarket.com/developers/Gamma-markets-api/overview",
            ),
            Capability.HEALTH_DIAGNOSTICS: (
                "Local request/configuration state; no network request is made by health()",
                None,
            ),
        },
        {
            Capability.BOOK_UPDATES: (
                "No incremental book stream is consumed by this bounded adapter",
                None,
            ),
            Capability.HISTORICAL_CANDLES: (
                "Historical price series are not normalized in adapter v1",
                POLY_DATA_DOC,
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
            f"{GAMMA}/markets",
            {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": "liquidity",
                "ascending": "false",
            },
        )
        self._capture_response(response, "market_listing")
        if not isinstance(response.payload, list):
            raise AdapterError("INVALID_SCHEMA", "Gamma markets response must be a JSON array")
        records: list[FrontierMarket] = []
        for raw in response.payload:
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_SCHEMA", "Gamma market entry must be an object")
            records.append(self._normalize_market(raw, response))
        return tuple(records)

    def market_metadata_request_url(self, native_market_id: str) -> str:
        """Return the exact public single-market URL for a validated Gamma ID."""
        if not isinstance(native_market_id, str) or not re.fullmatch(
            r"[0-9]{1,20}", native_market_id
        ):
            raise AdapterError("INVALID_MARKET_ID", "Polymarket market ID must be numeric")
        return f"{GAMMA}/markets/{native_market_id}"

    async def fetch_market_metadata(self, native_market_id: str) -> FrontierMarket:
        """Fetch one known Gamma market by its native ID without expanding its event."""
        self._require(Capability.MARKET_METADATA)
        request_url = self.market_metadata_request_url(native_market_id)
        response = await self.transport.get_json(request_url)
        self._capture_response(response, "market_metadata")
        payload = response.payload
        if not isinstance(payload, dict):
            raise AdapterError("INVALID_SCHEMA", "Gamma market detail response must be an object")
        if str(payload.get("id")) != native_market_id:
            raise AdapterError("MARKET_ID_MISMATCH", "Gamma market detail does not match request")
        return self._normalize_market(payload, response)

    async def discover_event_markets(self, native_event_id: str) -> tuple[FrontierMarket, ...]:
        self._require(Capability.EVENT_MARKET_GROUPS)
        if not re.fullmatch(r"[0-9]{1,20}", native_event_id):
            raise AdapterError("INVALID_EVENT_ID", "Polymarket event ID must be numeric")
        response = await self.transport.get_json(f"{GAMMA}/events/{native_event_id}")
        self._capture_response(response, "event_market_listing")
        payload = response.payload
        if not isinstance(payload, dict):
            raise AdapterError("INVALID_SCHEMA", "Gamma event response must be an object")
        event_id = payload.get("id")
        event_title = payload.get("title")
        children = payload.get("markets")
        if str(event_id) != native_event_id:
            raise AdapterError("EVENT_ID_MISMATCH", "Gamma event response does not match request")
        if not isinstance(event_title, str) or not event_title.strip() or len(event_title) > 512:
            raise AdapterError("INVALID_SCHEMA", "Gamma event title is missing or oversized")
        if not isinstance(children, list) or len(children) > self.config.max_markets_per_call:
            raise AdapterError(
                "INVALID_SCHEMA", "Gamma event markets must be an array within the configured bound"
            )
        records: list[FrontierMarket] = []
        seen: set[str] = set()
        for raw in children:
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_SCHEMA", "Gamma event market entry must be an object")
            record = self._normalize_market(
                raw,
                response,
                parent_event_id=native_event_id,
                parent_event_title=event_title,
            )
            if record.native_market_id in seen:
                raise AdapterError("DUPLICATE_MARKET", "Gamma event contains a duplicate market ID")
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
        try:
            legacy: LegacyMarket = normalize_market(raw)
        except (KeyError, TypeError, ValueError) as error:
            raise AdapterError(
                "INVALID_MARKET", f"Polymarket market failed legacy validation: {error}"
            ) from error
        if legacy.fee.verified:
            fee_verified_at = int(response.response_received_at_utc.timestamp() * 1000)
            legacy = legacy.model_copy(
                update={
                    "fee": legacy.fee.model_copy(
                        update={
                            "verified_ts_ms": fee_verified_at,
                            "expires_ts_ms": fee_verified_at + 300_000,
                        }
                    )
                }
            )
        if legacy.protocol not in {"v1", "v2"} or not legacy.instruments:
            raise AdapterError(
                "UNSUPPORTED_MARKET_SCHEMA", "Unknown Polymarket outcome-token schema"
            )
        payout_asset_identity = _payout_asset_identity(legacy.protocol)
        quote_currency = payout_asset_identity.code if payout_asset_identity else "USDC"
        settlement_asset = quote_currency if payout_asset_identity else None
        state_ids: tuple[str, ...]
        if len(legacy.instruments) == 2 and [item.label for item in legacy.instruments] == [
            "Yes",
            "No",
        ]:
            state_ids = ("yes", "no")
            kind = MarketKind.BINARY_EVENT
        else:
            state_ids = tuple(f"outcome:{index}" for index in range(len(legacy.instruments)))
            kind = MarketKind.MULTI_OUTCOME_EVENT
        outcomes: list[MarketInstrument] = []
        for index, instrument in enumerate(legacy.instruments):
            payouts = tuple(
                StatePayout(state_id=state, amount=D(1) if index == state_index else D(0))
                for state_index, state in enumerate(state_ids)
            )
            tick = parse_decimal(raw.get("orderPriceMinTickSize"))
            minimum = parse_decimal(raw.get("orderMinSize"))
            outcomes.append(
                MarketInstrument(
                    native_instrument_id=instrument.asset_id,
                    label=instrument.label,
                    outcome_id=state_ids[index],
                    quantity_unit=QuantityUnit.SHARE,
                    price_currency=quote_currency,
                    price_currency_identity=payout_asset_identity,
                    tick_size=tick if tick is not None and tick > 0 else None,
                    minimum_quantity=minimum if minimum is not None and minimum > 0 else None,
                    payouts=payouts,
                )
            )
        fee = self._fee(
            legacy.fee,
            raw,
            response,
            fee_currency=quote_currency,
            fee_currency_identity=payout_asset_identity,
        )
        end_time = parse_time(raw.get("endDateIso") or raw.get("endDate"))
        rules_hash = None
        if legacy.resolution_source or legacy.description:
            from midas.frontier.models import sha256_text

            rules_hash = sha256_text(f"{legacy.resolution_source}\n{legacy.description}")
        event_rows = raw.get("events")
        nested_event = (
            event_rows[0]
            if isinstance(event_rows, list)
            and len(event_rows) == 1
            and isinstance(event_rows[0], dict)
            else {}
        )
        event_id = parent_event_id or legacy.event_id
        event_title = parent_event_title or (
            nested_event.get("title") if isinstance(nested_event.get("title"), str) else None
        )
        outcome_label = raw.get("groupItemTitle")
        if not isinstance(outcome_label, str) or len(outcome_label) > 512:
            outcome_label = None
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, legacy.id),
            native_market_id=legacy.id,
            native_event_id=event_id,
            native_event_title=event_title,
            outcome_label=outcome_label,
            title=legacy.question,
            description=legacy.description,
            market_kind=kind,
            lifecycle=lifecycle(
                "closed" if legacy.closed else None,
                active=legacy.active and legacy.accepting_orders,
                closed=legacy.closed,
            ),
            instruments=tuple(outcomes),
            payoff=PayoffSpec(
                state_ids=state_ids,
                payout_currency=settlement_asset or "USD",
                settlement_asset=settlement_asset,
                settlement_asset_identity=payout_asset_identity,
                exhaustive=False,
                verified=False,
                verification_basis=(
                    "Position-backed v2 settlement asset is mapped from documented Polymarket protocol "
                    f"metadata ({POLY_PROTOCOL_DOC}; {POLY_V2_ASSETS_DOC}); market-specific payoff remains unverified."
                    if payout_asset_identity
                    else "Outcome labels/token IDs are source metadata; CTF payout and collateral attestation is not performed here."
                ),
            ),
            resolution=ResolutionSpec(
                primary_rule=legacy.description or None,
                authority=legacy.resolution_source or None,
                closes_at_utc=end_time,
                evidence_sha256=rules_hash,
                verified=False,
            ),
            fees=fee,
            quote_asset=quote_currency,
            settlement_asset=settlement_asset,
            settlement_asset_identity=payout_asset_identity,
            native_fields=native_json(raw),
            quality_flags=tuple(
                flag
                for flag, condition in (
                    ("PAYOUT_NOT_ATTESTED", not legacy.payout_verified),
                    (
                        "SETTLEMENT_ASSET_PROTOCOL_MAPPED"
                        if payout_asset_identity
                        else "SETTLEMENT_ASSET_NOT_ATTESTED",
                        True,
                    ),
                    ("RESOLUTION_SEMANTICS_NOT_VERIFIED", not bool(legacy.resolution_source)),
                    ("CROSS_VENUE_EQUIVALENCE_NOT_ASSERTED", True),
                )
                if condition
            ),
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "market_metadata",
                legacy.id,
                source_schema_version=legacy.protocol,
            ),
        )

    @staticmethod
    def _fee(
        fee: LegacyFee,
        raw: dict[str, Any],
        response: HTTPObservation,
        *,
        fee_currency: str,
        fee_currency_identity: SettlementAssetIdentity | None,
    ) -> FeeSchedule:
        from midas.frontier.models import sha256_text

        if not fee.verified:
            return FeeSchedule(
                note="Gamma did not provide a supported, verified market fee schedule"
            )
        if fee.expires_ts_ms is not None and fee.expires_ts_ms <= int(
            response.response_received_at_utc.timestamp() * 1000
        ):
            return FeeSchedule(
                note="Polymarket fee evidence expired before this response was received"
            )
        evidence = json_stable(raw.get("feeSchedule"), raw.get("feesEnabled"))
        return FeeSchedule(
            status=FeeStatus.VERIFIED,
            version=fee.rule_version,
            applies_to="taker",
            rate=fee.rate,
            formula="quantity * rate * price * (1 - price); exponent 1",
            fee_currency=fee_currency,
            fee_currency_identity=fee_currency_identity,
            source_url=POLY_FEES_DOC,
            evidence_sha256=sha256_text(evidence),
            effective_at_utc=response.response_received_at_utc,
            expires_at_utc=datetime.fromtimestamp(fee.expires_ts_ms / 1000, tz=UTC)
            if fee.expires_ts_ms is not None
            else None,
            note="Source-specific fee is retained; settlement/collateral equivalence remains unverified.",
        )

    async def fetch_book(
        self, market: FrontierMarket, instrument_id: str, depth: int = 20
    ) -> BookSnapshot:
        self._require(Capability.BOOK_SNAPSHOT)
        if market.venue != self.venue:
            raise AdapterError("VENUE_MISMATCH", "Market does not belong to Polymarket")
        if not 1 <= depth <= 100:
            raise AdapterError("INVALID_DEPTH", "Book depth must be between 1 and 100")
        instrument = next(
            (item for item in market.instruments if item.native_instrument_id == instrument_id),
            None,
        )
        if instrument is None:
            raise AdapterError("INSTRUMENT_NOT_FOUND", "Instrument does not belong to this market")
        protocol = market.provenance.source_schema_version
        if protocol not in {"v1", "v2"} or market.native_fields.get("version") != protocol:
            raise AdapterError(
                "UNSUPPORTED_MARKET_SCHEMA",
                "Market protocol does not match its source provenance",
            )
        payout_asset_identity = _payout_asset_identity(protocol)
        if market.settlement_asset_identity != payout_asset_identity:
            raise AdapterError(
                "UNSUPPORTED_SETTLEMENT_ASSET",
                "Market settlement asset does not match its documented protocol mapping",
            )
        clob_base = CLOB_V2 if protocol == "v2" else CLOB
        response = await self.transport.get_json(f"{clob_base}/book", {"token_id": instrument_id})
        self._capture_response(response, "book_snapshot")
        raw = response.payload
        if not isinstance(raw, dict) or str(raw.get("asset_id")) != instrument_id:
            raise AdapterError("INVALID_BOOK", "Polymarket book response asset identity mismatch")
        if str(raw.get("market") or "") != str(market.native_fields.get("conditionId") or ""):
            raise AdapterError("INVALID_BOOK", "Polymarket book condition identity mismatch")
        try:
            asks = tuple(
                BookLevel(price=D(str(item["price"])), quantity=D(str(item["size"])))
                for item in raw.get("asks", [])[:depth]
            )
            bids = tuple(
                BookLevel(price=D(str(item["price"])), quantity=D(str(item["size"])))
                for item in raw.get("bids", [])[:depth]
            )
            timestamp = parse_time(raw.get("timestamp"))
        except (KeyError, TypeError, ValueError) as error:
            raise AdapterError(
                "INVALID_BOOK", "Polymarket book contained malformed levels"
            ) from error
        flags = (
            ("CROSSED_OR_LOCKED",)
            if asks and bids and max(x.price for x in bids) >= min(x.price for x in asks)
            else ()
        )
        return BookSnapshot(
            venue=self.venue,
            native_market_id=market.native_market_id,
            native_instrument_id=instrument_id,
            asks=asks,
            bids=bids,
            price_unit=f"{market.quote_asset or 'USDC'} per outcome share",
            price_currency=market.quote_asset,
            price_currency_identity=market.settlement_asset_identity,
            quantity_unit=instrument.quantity_unit,
            received_at_utc=response.response_received_at_utc,
            exchange_timestamp_utc=timestamp,
            exchange_timestamp_semantics="CLOB book timestamp; source precision and matching-engine simultaneity are not established",
            quality_flags=flags,
            provenance=provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "book_snapshot",
                f"{market.native_market_id}:{instrument_id}",
                source_schema_version=market.native_fields.get("version"),
                exchange_timestamp=timestamp,
                exchange_timestamp_semantics="CLOB response timestamp",
            ),
        )

    async def fetch_trades(
        self, native_market_id: str, limit: int = 100
    ) -> tuple[TradeObservation, ...]:
        self._require(Capability.PUBLIC_TRADES)
        if not 1 <= limit <= 1000:
            raise AdapterError("INVALID_LIMIT", "Trade limit must be between 1 and 1000")
        response = await self.transport.get_json(
            f"{DATA}/trades", {"market": native_market_id, "limit": limit}
        )
        self._capture_response(response, "public_trades")
        if not isinstance(response.payload, list):
            raise AdapterError("INVALID_SCHEMA", "Polymarket trade response must be an array")
        result = []
        for raw in response.payload[:limit]:
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_SCHEMA", "Polymarket trade entry must be an object")
            price = parse_decimal(raw.get("price"))
            quantity = parse_decimal(raw.get("size"))
            timestamp = parse_time(raw.get("timestamp"))
            if price is None or quantity is None or quantity <= 0:
                raise AdapterError(
                    "INVALID_TRADE", "Polymarket trade has invalid price or quantity"
                )
            identity = str(raw.get("transactionHash") or raw.get("asset") or "unknown")
            response_provenance = provenance(
                self.venue,
                ADAPTER_VERSION,
                response,
                "public_trade",
                identity,
                exchange_timestamp=timestamp,
                exchange_timestamp_semantics="Data API trade timestamp",
            )
            result.append(
                TradeObservation(
                    venue=self.venue,
                    native_market_id=str(raw.get("conditionId") or native_market_id),
                    native_trade_id=str(raw.get("transactionHash") or "") or None,
                    price=price,
                    quantity=quantity,
                    quote_currency="USDC",
                    aggressor_side=str(raw.get("side") or "unknown"),
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=response_provenance,
                )
            )
        return tuple(result)

    async def fetch_trade_page(
        self, condition_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> TradeBatch:
        """Fetch one public v2 keyset page for a recorded Polymarket condition."""
        self._require(Capability.PAGINATED_PUBLIC_TRADES)
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", condition_id):
            raise AdapterError("INVALID_MARKET", "Condition ID must be a 32-byte 0x hex value")
        if not 1 <= limit <= 100:
            raise AdapterError("INVALID_LIMIT", "Trade page size must be between 1 and 100")
        if cursor is not None and (
            not cursor.strip()
            or len(cursor) > 2048
            or any(ord(character) < 0x21 or ord(character) > 0x7E for character in cursor)
        ):
            raise AdapterError("INVALID_CURSOR", "Source trade cursor is blank or oversized")

        params: dict[str, str | int] = {
            "condition": condition_id,
            "limit": limit,
            "taker_only": "true",
            "filter_type": "TOKENS",
            "filter_amount": "0.01",
        }
        if cursor is not None:
            params["cursor"] = cursor
        response = await self.transport.get_json(f"{DATA}/v2/trades", params)
        self._capture_response(response, "public_trades")
        payload = response.payload
        if not isinstance(payload, dict):
            raise AdapterError("INVALID_SCHEMA", "Data API v2 trade response must be an object")
        rows = payload.get("data")
        pagination = payload.get("pagination")
        if not isinstance(rows, list) or not isinstance(pagination, dict):
            raise AdapterError(
                "INVALID_SCHEMA", "Data API v2 trade response must contain data and pagination"
            )
        if len(rows) > limit:
            raise AdapterError("INVALID_PAGINATION", "Data API v2 exceeded the requested page size")
        page_limit = pagination.get("limit")
        has_more = pagination.get("has_more")
        next_cursor = pagination.get("next_cursor")
        if (
            type(page_limit) is not int
            or page_limit != limit
            or not isinstance(has_more, bool)
            or (next_cursor is not None and not isinstance(next_cursor, str))
            or has_more != (next_cursor is not None)
        ):
            raise AdapterError("INVALID_PAGINATION", "Data API v2 returned inconsistent pagination")
        if next_cursor is not None and (
            not next_cursor.strip()
            or len(next_cursor) > 2048
            or any(ord(character) < 0x21 or ord(character) > 0x7E for character in next_cursor)
            or next_cursor == cursor
        ):
            raise AdapterError("INVALID_PAGINATION", "Data API v2 returned an invalid next cursor")

        trades: list[TradeObservation] = []
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                raise AdapterError("INVALID_TRADE", "Data API v2 trade entry must be an object")
            row_condition = raw.get("condition_id")
            token_id = raw.get("token_id")
            side = raw.get("side")
            outcome_label = raw.get("outcome")
            outcome_index = raw.get("outcome_index")
            price = parse_decimal(raw.get("price"))
            quantity = parse_decimal(raw.get("size"))
            timestamp = parse_time(raw.get("timestamp"))
            if row_condition != condition_id:
                raise AdapterError(
                    "TRADE_MARKET_MISMATCH", "Data API v2 returned a trade for another condition"
                )
            if (
                not isinstance(token_id, str)
                or not token_id
                or len(token_id) > 128
                or not isinstance(side, str)
                or side not in {"BUY", "SELL"}
                or not isinstance(outcome_label, str)
                or len(outcome_label) > 160
                or type(outcome_index) is not int
                or not 0 <= outcome_index <= 2_147_483_647
                or price is None
                or not D(0) <= price <= D(1)
                or quantity is None
                or quantity <= 0
                or timestamp is None
            ):
                raise AdapterError("INVALID_TRADE", "Data API v2 trade fields failed validation")
            transaction_hash = raw.get("transaction_hash")
            if transaction_hash is not None and (
                not isinstance(transaction_hash, str) or len(transaction_hash) > 128
            ):
                raise AdapterError(
                    "INVALID_TRADE", "Data API v2 transaction hash is malformed or oversized"
                )
            native_trade_id = (
                transaction_hash if isinstance(transaction_hash, str) and transaction_hash else None
            )
            trades.append(
                TradeObservation(
                    schema_version=2,
                    venue=self.venue,
                    native_market_id=condition_id,
                    native_trade_id=native_trade_id,
                    native_instrument_id=token_id,
                    outcome_label=outcome_label or None,
                    outcome_index=outcome_index,
                    price=price,
                    quantity=quantity,
                    quote_currency="USDC",
                    aggressor_side=side,
                    exchange_timestamp_utc=timestamp,
                    received_at_utc=response.response_received_at_utc,
                    provenance=provenance(
                        self.venue,
                        ADAPTER_VERSION,
                        response,
                        "public_trade",
                        f"{condition_id}:{token_id}:{native_trade_id or 'no-hash'}:{index}",
                        source_schema_version="Data API v2 /trades",
                        exchange_timestamp=timestamp,
                        exchange_timestamp_semantics="Polymarket Data API block timestamp in epoch seconds",
                    ),
                )
            )
        return TradeBatch(
            schema_version=2,
            venue=self.venue,
            trades=tuple(trades),
            requested_market_id=condition_id,
            page_limit=limit,
            source_cursor=cursor,
            source_next_cursor=next_cursor,
            has_more=has_more,
        )


def json_stable(*values: Any) -> str:
    import json

    return json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
