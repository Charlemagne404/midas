"""Polymarket adapter over the existing version-aware public normalization path."""

from __future__ import annotations

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
    StatePayout,
    TradeObservation,
    Venue,
    stable_market_id,
)
from midas.market_data.polymarket import normalize_market

D = Decimal
ADAPTER_VERSION = "frontier-polymarket-1"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"
POLY_FEES_DOC = "https://docs.polymarket.com/trading/fees"
POLY_DATA_DOC = "https://docs.polymarket.com/developers/CLOB/introduction"


class PolymarketAdapter(BaseReadOnlyAdapter):
    venue = Venue.POLYMARKET
    allowed_hosts = {"gamma-api.polymarket.com", "clob.polymarket.com", "data-api.polymarket.com"}
    capabilities = build_capabilities(
        Venue.POLYMARKET,
        ADAPTER_VERSION,
        {
            Capability.MARKET_DISCOVERY: (
                "Active markets via public Gamma REST API",
                "https://docs.polymarket.com/developers/gamma-markets-api/overview",
            ),
            Capability.INSTRUMENT_DISCOVERY: (
                "Outcome token identifiers via Gamma v1/v2 fields",
                "https://docs.polymarket.com/developers/CLOB/introduction",
            ),
            Capability.MARKET_METADATA: (
                "Native market and condition metadata are retained",
                "https://docs.polymarket.com/developers/gamma-markets-api/overview",
            ),
            Capability.OUTCOME_DEFINITIONS: (
                "Outcome labels and token IDs are exposed; payout attestation remains separate",
                "https://docs.polymarket.com/developers/CLOB/introduction",
            ),
            Capability.BOOK_SNAPSHOT: (
                "Public CLOB REST book snapshots",
                "https://docs.polymarket.com/developers/CLOB/market-data",
            ),
            Capability.PUBLIC_TRADES: (
                "Public Data API trades",
                "https://institute.polymarket.com/data",
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

    def _normalize_market(self, raw: dict[str, Any], response: HTTPObservation) -> FrontierMarket:
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
                    price_currency="USDC",
                    tick_size=tick if tick is not None and tick > 0 else None,
                    minimum_quantity=minimum if minimum is not None and minimum > 0 else None,
                    payouts=payouts,
                )
            )
        fee = self._fee(legacy.fee, raw, response)
        end_time = parse_time(raw.get("endDateIso") or raw.get("endDate"))
        rules_hash = None
        if legacy.resolution_source or legacy.description:
            from midas.frontier.models import sha256_text

            rules_hash = sha256_text(f"{legacy.resolution_source}\n{legacy.description}")
        return FrontierMarket(
            venue=self.venue,
            canonical_id=stable_market_id(self.venue, legacy.id),
            native_market_id=legacy.id,
            native_event_id=legacy.event_id,
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
                payout_currency="USD",
                settlement_asset=None,
                exhaustive=False,
                verified=False,
                verification_basis="Outcome labels/token IDs are source metadata; CTF payout and collateral attestation is not performed here.",
            ),
            resolution=ResolutionSpec(
                primary_rule=legacy.description or None,
                authority=legacy.resolution_source or None,
                closes_at_utc=end_time,
                evidence_sha256=rules_hash,
                verified=False,
            ),
            fees=fee,
            quote_asset="USDC",
            native_fields=native_json(raw),
            quality_flags=tuple(
                flag
                for flag, condition in (
                    ("PAYOUT_NOT_ATTESTED", not legacy.payout_verified),
                    ("SETTLEMENT_ASSET_NOT_ATTESTED", True),
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
    def _fee(fee: LegacyFee, raw: dict[str, Any], response: HTTPObservation) -> FeeSchedule:
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
            fee_currency="USDC",
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
        response = await self.transport.get_json(f"{CLOB}/book", {"token_id": instrument_id})
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
            price_unit="USDC per outcome share",
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


def json_stable(*values: Any) -> str:
    import json

    return json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
