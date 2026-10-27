"""Versioned, venue-aware data contracts; no order-entry concepts are defined here."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

D = Decimal
Nonnegative = Annotated[Decimal, Field(ge=0, max_digits=36, decimal_places=18, allow_inf_nan=False)]
ExactNonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, max_digits=36, decimal_places=18, allow_inf_nan=False)]
FeeRate = Annotated[
    Decimal, Field(ge=0, le=1, max_digits=18, decimal_places=12, allow_inf_nan=False)
]
SignedDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]


class FrontierModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Venue(StrEnum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    KRAKEN = "kraken"


class MarketKind(StrEnum):
    BINARY_EVENT = "binary_event"
    MULTI_OUTCOME_EVENT = "multi_outcome_event"
    CONDITIONAL_EVENT = "conditional_event"
    SPOT_PAIR = "spot_pair"
    DERIVATIVE = "derivative"
    UNKNOWN = "unknown"


class Lifecycle(StrEnum):
    UNKNOWN = "unknown"
    UNOPENED = "unopened"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    SETTLED = "settled"
    EXPIRED = "expired"


class QuantityUnit(StrEnum):
    CONTRACT = "contract"
    SHARE = "share"
    BASE_ASSET = "base_asset"
    LOT = "lot"
    UNKNOWN = "unknown"


class FeeStatus(StrEnum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    ESTIMATE = "estimate"


class EconomicAuditDisposition(StrEnum):
    VERIFIED = "verified"
    DISAGREEMENT = "disagreement"
    INCOMPLETE = "incomplete"
    NOT_EVALUATED = "not_evaluated"


class SourceState(StrEnum):
    NOT_PROBED = "not_probed"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class Capability(StrEnum):
    MARKET_DISCOVERY = "market_discovery"
    EVENT_MARKET_GROUPS = "event_market_groups"
    INSTRUMENT_DISCOVERY = "instrument_discovery"
    MARKET_METADATA = "market_metadata"
    OUTCOME_DEFINITIONS = "outcome_definitions"
    BOOK_SNAPSHOT = "book_snapshot"
    BOOK_UPDATES = "book_updates"
    PUBLIC_TRADES = "public_trades"
    PAGINATED_PUBLIC_TRADES = "paginated_public_trades"
    HISTORICAL_CANDLES = "historical_candles"
    FEE_METADATA = "fee_metadata"
    FEE_SCHEDULE = "fee_schedule"
    TICK_CONSTRAINTS = "tick_constraints"
    QUANTITY_CONSTRAINTS = "quantity_constraints"
    SETTLEMENT_RULES = "settlement_rules"
    MARKET_LIFECYCLE = "market_lifecycle"
    HEALTH_DIAGNOSTICS = "health_diagnostics"


class CapabilityDeclaration(FrontierModel):
    capability: Capability
    supported: bool
    state: str = "documented"
    reason: str
    documentation_url: str | None = None


class AdapterCapabilities(FrontierModel):
    schema_version: int = 1
    venue: Venue
    adapter_version: str
    declarations: tuple[CapabilityDeclaration, ...]

    @model_validator(mode="after")
    def declares_all_capabilities_once(self) -> AdapterCapabilities:
        declared = [item.capability for item in self.declarations]
        if len(set(declared)) != len(Capability) or set(declared) != set(Capability):
            raise ValueError("Every capability must be declared exactly once")
        return self

    def supports(self, capability: Capability) -> bool:
        return next(item.supported for item in self.declarations if item.capability == capability)


class AdapterConfig(FrontierModel):
    """Local public-read limits. Credentials and arbitrary base URLs are not accepted."""

    enabled: bool = False
    live_public_probe_enabled: bool = False
    timeout_seconds: Annotated[float, Field(ge=0.5, le=15)] = 5.0
    requests_per_second: Annotated[float, Field(gt=0, le=5)] = 1.0
    max_response_bytes: Annotated[int, Field(ge=1024, le=262144)] = 262144
    max_markets_per_call: Annotated[int, Field(ge=1, le=100)] = 20
    retries: Annotated[int, Field(ge=0, le=2)] = 1


class SourceHealth(FrontierModel):
    venue: Venue
    state: SourceState = SourceState.NOT_PROBED
    checked_at_utc: datetime | None = None
    last_success_at_utc: datetime | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    requests_in_window: int = 0
    supported_capabilities: tuple[Capability, ...] = ()
    unsupported_capabilities: tuple[Capability, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator("checked_at_utc", "last_success_at_utc")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamps must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None


class StatePayout(FrontierModel):
    state_id: str
    amount: Nonnegative


class MarketInstrument(FrontierModel):
    native_instrument_id: str
    label: str
    outcome_id: str | None = None
    quantity_unit: QuantityUnit = QuantityUnit.UNKNOWN
    price_currency: str | None = None
    tick_size: Positive | None = None
    quantity_step: Positive | None = None
    minimum_quantity: Positive | None = None
    minimum_notional: Positive | None = None
    payouts: tuple[StatePayout, ...] = ()

    @field_validator("price_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.upper()
        if not value.isascii() or not value.isalnum() or not 2 <= len(value) <= 16:
            raise ValueError("Invalid currency or settlement asset identifier")
        return value


class SelectedMarketComponent(FrontierModel):
    """Native selected contract leg; it does not assert the containing market payoff."""

    venue: Venue
    native_event_id: str | None = Field(default=None, max_length=256)
    native_market_id: str = Field(min_length=1, max_length=256)
    selected_side: Literal["yes", "no"]


class PayoffSpec(FrontierModel):
    schema_version: int = 1
    state_ids: tuple[str, ...] = ()
    payout_currency: str | None = None
    settlement_asset: str | None = None
    exhaustive: bool = False
    verified: bool = False
    verification_basis: str = "Not established"

    @model_validator(mode="after")
    def verified_payoff_has_states_and_settlement(self) -> PayoffSpec:
        if self.verified and (
            not self.state_ids or not self.payout_currency or not self.settlement_asset
        ):
            raise ValueError("A verified payoff requires states, currency, and settlement asset")
        if len(set(self.state_ids)) != len(self.state_ids):
            raise ValueError("Duplicate payoff state")
        return self


class ResolutionSpec(FrontierModel):
    primary_rule: str | None = None
    secondary_rule: str | None = None
    authority: str | None = None
    closes_at_utc: datetime | None = None
    settles_at_utc: datetime | None = None
    source_timestamp_semantics: str | None = None
    evidence_sha256: str | None = None
    resolution_fingerprint: str | None = None
    verified: bool = False

    @field_validator("closes_at_utc", "settles_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Resolution times must include a timezone")
        return value.astimezone(UTC) if value is not None else None


class FeeSchedule(FrontierModel):
    status: FeeStatus = FeeStatus.UNKNOWN
    version: str | None = None
    applies_to: str | None = None
    fixed_fee: Nonnegative | None = None
    rate: FeeRate | None = None
    formula: str | None = None
    fee_currency: str | None = None
    source_url: str | None = None
    evidence_sha256: str | None = None
    effective_at_utc: datetime | None = None
    expires_at_utc: datetime | None = None
    note: str = "No verified instrument-specific schedule"

    @model_validator(mode="after")
    def verified_schedule_has_evidence(self) -> FeeSchedule:
        if self.status == FeeStatus.VERIFIED and not (self.source_url and self.evidence_sha256):
            raise ValueError("Verified fee schedule requires source and evidence hash")
        return self


class KalshiFeeMetadata(FrontierModel):
    """Public native Kalshi fee parameters; deliberately not an account fee quote."""

    schema_version: Literal[1] = 1
    adapter_version: str
    native_market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str = Field(min_length=1, max_length=256)
    series_ticker: str = Field(min_length=1, max_length=256)
    event_fee_type_override: str | None = Field(default=None, max_length=80)
    event_fee_multiplier_override: Nonnegative | None = None
    series_fee_type: str = Field(min_length=1, max_length=80)
    series_fee_multiplier: Nonnegative
    effective_fee_type: str = Field(min_length=1, max_length=80)
    effective_fee_multiplier: Nonnegative
    event_fee_type_override_field_present: bool
    event_fee_multiplier_override_field_present: bool
    event_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    series_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_received_at_utc: datetime
    series_received_at_utc: datetime
    schedule_source_url: str = "https://kalshi.com/fee-schedule"
    fee_rounding_documentation_url: str = "https://docs.kalshi.com/getting_started/fee_rounding"
    economics_state: Literal["unresolved"] = "unresolved"
    limitations: tuple[str, ...] = (
        "A bounded manual one-order quadratic taker-fee sensitivity is implemented; unsupported fee types fail closed and candidate costs remain unresolved.",
        "Maker fees and schedule changes outside the dated public formula are not modeled.",
        "Account balance precision is not identified; both documented balance precision cases are shown.",
        "Maker/taker mixed orders, account-specific adjustments, and FCM-specific charges remain unresolved.",
    )

    @field_validator("event_received_at_utc", "series_received_at_utc")
    @classmethod
    def fee_metadata_times_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Fee metadata times must include a timezone")
        return value.astimezone(UTC)


class KalshiFeeRoundingScenario(FrontierModel):
    account_precision_class: Literal["direct_member", "non_direct_member"]
    balance_quantum: Positive
    model_fee_before_rounding: ExactNonnegative
    trade_fee_rounded_to_microdollar: ExactNonnegative
    balance_rounding_adjustment: ExactNonnegative
    total_modeled_fee: ExactNonnegative
    total_modeled_debit: ExactNonnegative


class KalshiTakerFeeSensitivity(FrontierModel):
    """One-fill public-schedule sensitivity; not a user-account fee quotation."""

    schema_version: Literal[1] = 1
    model_version: str = "kalshi-event-taker-fee-sensitivity-2026-07-07-v1"
    native_market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str = Field(min_length=1, max_length=256)
    series_ticker: str = Field(min_length=1, max_length=256)
    effective_fee_type: str = Field(min_length=1, max_length=80)
    effective_fee_multiplier: Nonnegative
    input_observation_ids: tuple[str, str]
    input_raw_sha256: tuple[str, str]
    input_received_at_utc: tuple[datetime, datetime]
    price_usd: Decimal = Field(gt=0, lt=1, max_digits=18, decimal_places=12, allow_inf_nan=False)
    quantity_contracts: Decimal = Field(
        gt=0, le=1_000_000, max_digits=24, decimal_places=12, allow_inf_nan=False
    )
    position_cost_usd: ExactNonnegative
    scenarios: tuple[KalshiFeeRoundingScenario, ...]
    formula_source_url: str = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
    rounding_source_url: str = "https://docs.kalshi.com/getting_started/fee_rounding"
    calculation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assumptions: tuple[str, ...]

    @field_validator("input_received_at_utc")
    @classmethod
    def sensitivity_times_are_utc(
        cls, value: tuple[datetime, datetime]
    ) -> tuple[datetime, datetime]:
        normalized = []
        for item in value:
            if item.tzinfo is None or item.utcoffset() is None:
                raise ValueError("Fee sensitivity timestamps must include a timezone")
            normalized.append(item.astimezone(UTC))
        return normalized[0], normalized[1]

    @field_validator("input_observation_ids", "input_raw_sha256")
    @classmethod
    def sensitivity_hashes_are_sha256(cls, value: tuple[str, str]) -> tuple[str, str]:
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in value
        ):
            raise ValueError(
                "Fee sensitivity evidence identities must be lowercase SHA-256 digests"
            )
        return value


class KalshiFeeOrderFillInput(FrontierModel):
    """One manually supplied fill in a single hypothetical Kalshi order."""

    native_instrument_id: str = Field(min_length=1, max_length=256)
    side: Literal["buy", "sell"]
    price_usd: Decimal = Field(gt=0, lt=1, max_digits=18, decimal_places=12, allow_inf_nan=False)
    quantity_contracts: Decimal = Field(
        gt=0, le=1_000_000, max_digits=24, decimal_places=12, allow_inf_nan=False
    )


class KalshiFeeOrderFillResult(FrontierModel):
    fill_index: int = Field(ge=0, le=31)
    native_instrument_id: str = Field(min_length=1, max_length=256)
    side: Literal["buy", "sell"]
    price_usd: Positive
    quantity_contracts: Positive
    signed_revenue_usd: SignedDecimal
    model_fee_before_rounding: ExactNonnegative
    trade_fee_rounded_to_microdollar: ExactNonnegative
    aligned_balance_change_before_rebate_usd: SignedDecimal
    rounding_fee_usd: ExactNonnegative
    accumulated_rounding_before_rebate_usd: ExactNonnegative
    rebate_usd: ExactNonnegative
    accumulated_rounding_after_rebate_usd: ExactNonnegative
    net_fee_usd: ExactNonnegative
    balance_change_after_rebate_usd: SignedDecimal


class KalshiFeeOrderPrecisionScenario(FrontierModel):
    account_precision_class: Literal["direct_member", "non_direct_member"]
    balance_quantum: Positive
    fills: tuple[KalshiFeeOrderFillResult, ...] = Field(min_length=1, max_length=32)
    total_signed_revenue_usd: SignedDecimal
    total_trade_fee_usd: ExactNonnegative
    total_rounding_fee_usd: ExactNonnegative
    total_rebate_usd: ExactNonnegative
    total_net_fee_usd: ExactNonnegative
    total_balance_change_usd: SignedDecimal


class KalshiFeeOrderSensitivity(FrontierModel):
    """One-order, multi-fill taker sensitivity; not an account fee quotation."""

    schema_version: Literal[1] = 1
    model_version: str = "kalshi-event-taker-order-fee-sensitivity-2026-07-07-v1"
    native_market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str = Field(min_length=1, max_length=256)
    series_ticker: str = Field(min_length=1, max_length=256)
    effective_fee_type: str = Field(min_length=1, max_length=80)
    effective_fee_multiplier: Nonnegative
    input_observation_ids: tuple[str, str]
    input_raw_sha256: tuple[str, str]
    input_received_at_utc: tuple[datetime, datetime]
    order_fills: tuple[KalshiFeeOrderFillInput, ...] = Field(min_length=1, max_length=32)
    scenarios: tuple[KalshiFeeOrderPrecisionScenario, KalshiFeeOrderPrecisionScenario]
    formula_source_url: str = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
    rounding_source_url: str = "https://docs.kalshi.com/getting_started/fee_rounding"
    calculation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assumptions: tuple[str, ...]

    @field_validator("input_received_at_utc")
    @classmethod
    def order_sensitivity_times_are_utc(
        cls, value: tuple[datetime, datetime]
    ) -> tuple[datetime, datetime]:
        normalized = []
        for item in value:
            if item.tzinfo is None or item.utcoffset() is None:
                raise ValueError("Fee sensitivity timestamps must include a timezone")
            normalized.append(item.astimezone(UTC))
        return normalized[0], normalized[1]

    @field_validator("input_observation_ids", "input_raw_sha256")
    @classmethod
    def order_sensitivity_hashes_are_sha256(cls, value: tuple[str, str]) -> tuple[str, str]:
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in value
        ):
            raise ValueError(
                "Fee sensitivity evidence identities must be lowercase SHA-256 digests"
            )
        return value


class IndependentEconomicAudit(FrontierModel):
    """Recomputed candidate economics from normalized contracts and source books."""

    schema_version: int = 1
    model_version: str = "frontier-independent-economic-audit-2"
    disposition: EconomicAuditDisposition
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checked_market_count: int = Field(ge=0, le=2)
    checked_leg_count: int = Field(ge=0, le=16)
    recomputed_gross_cost: SignedDecimal | None = None
    recomputed_modeled_fees: SignedDecimal | None = None
    recomputed_modeled_net_cost: SignedDecimal | None = None
    recomputed_payout_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_gross_pnl_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_net_pnl_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_worst_case_gross_pnl: SignedDecimal | None = None
    recomputed_worst_case_net_pnl: SignedDecimal | None = None
    checks: tuple[str, ...] = Field(default=(), max_length=20)
    message: str = Field(max_length=2000)


class Provenance(FrontierModel):
    source_url: str
    adapter_version: str
    source_schema_version: str | None = None
    request_started_at_utc: datetime
    response_received_at_utc: datetime
    processed_at_utc: datetime
    persisted_at_utc: datetime | None = None
    exchange_timestamp_utc: datetime | None = None
    exchange_timestamp_semantics: str = "unknown"
    clock_uncertainty_ms: Nonnegative | None = None
    raw_sha256: str
    observation_id: str

    @field_validator(
        "request_started_at_utc",
        "response_received_at_utc",
        "processed_at_utc",
        "persisted_at_utc",
        "exchange_timestamp_utc",
    )
    @classmethod
    def all_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Provenance timestamps must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None


class FrontierMarket(FrontierModel):
    schema_version: int = 1
    venue: Venue
    canonical_id: str
    native_market_id: str
    native_event_id: str | None = None
    native_event_title: str | None = Field(default=None, max_length=512)
    outcome_label: str | None = Field(default=None, max_length=512)
    title: str
    description: str = ""
    market_kind: MarketKind
    lifecycle: Lifecycle = Lifecycle.UNKNOWN
    instruments: tuple[MarketInstrument, ...] = ()
    selected_components: tuple[SelectedMarketComponent, ...] = Field(default=(), max_length=64)
    payoff: PayoffSpec = PayoffSpec()
    resolution: ResolutionSpec = ResolutionSpec()
    fees: FeeSchedule = FeeSchedule()
    base_asset: str | None = None
    quote_asset: str | None = None
    settlement_asset: str | None = None
    native_fields: dict[str, Any] = Field(default_factory=dict)
    quality_flags: tuple[str, ...] = ()
    provenance: Provenance

    @model_validator(mode="after")
    def consistent_structure(self) -> FrontierMarket:
        if not self.canonical_id or not self.native_market_id:
            raise ValueError("Market identities cannot be empty")
        ids = [item.native_instrument_id for item in self.instruments]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate native instrument identifier")
        component_ids = [(item.venue, item.native_market_id) for item in self.selected_components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Duplicate selected native market component")
        if any(
            item.venue == self.venue and item.native_market_id == self.native_market_id
            for item in self.selected_components
        ):
            raise ValueError("A market cannot list itself as a selected component")
        if self.market_kind == MarketKind.SPOT_PAIR:
            if not self.base_asset or not self.quote_asset or self.payoff.state_ids:
                raise ValueError(
                    "Spot pairs require base/quote assets and cannot claim event payoffs"
                )
        if self.payoff.verified:
            state_ids = set(self.payoff.state_ids)
            for outcome in self.instruments:
                if {payout.state_id for payout in outcome.payouts} != state_ids:
                    raise ValueError("Verified payoff must define every state for every outcome")
        return self

    @field_validator("native_fields")
    @classmethod
    def bounded_native_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if len(raw.encode("utf-8")) > 262144:
            raise ValueError("Native metadata exceeds the 256 KiB record bound")
        return value


class MarketBatch(FrontierModel):
    schema_version: int = 1
    venue: Venue
    markets: tuple[FrontierMarket, ...]
    cursor: str | None = None
    complete_for_request: bool = False
    note: str = (
        "One bounded discovery response; absence from this page is not proof of venue-wide absence."
    )


class BookLevel(FrontierModel):
    price: Nonnegative
    quantity: Positive
    exchange_timestamp_utc: datetime | None = None

    @field_validator("exchange_timestamp_utc")
    @classmethod
    def level_time_is_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Level timestamp must include a timezone")
        return value.astimezone(UTC) if value is not None else None


class BookSnapshot(FrontierModel):
    schema_version: int = 1
    venue: Venue
    native_market_id: str
    native_instrument_id: str
    asks: tuple[BookLevel, ...] = ()
    bids: tuple[BookLevel, ...] = ()
    price_unit: str
    quantity_unit: QuantityUnit
    received_at_utc: datetime
    exchange_timestamp_utc: datetime | None = None
    exchange_timestamp_semantics: str = "unknown"
    freshness_limit_ms: int | None = None
    quality_flags: tuple[str, ...] = ()
    provenance: Provenance

    @field_validator("received_at_utc", "exchange_timestamp_utc")
    @classmethod
    def book_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Book timestamps must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def unique_price_levels(self) -> BookSnapshot:
        for side in (self.asks, self.bids):
            prices = [level.price for level in side]
            if len(prices) != len(set(prices)):
                raise ValueError("Duplicate book price level")
        return self

    @property
    def crossed(self) -> bool:
        return bool(
            self.asks
            and self.bids
            and max(x.price for x in self.bids) >= min(x.price for x in self.asks)
        )


class TradeObservation(FrontierModel):
    schema_version: int = 1
    venue: Venue
    native_market_id: str
    native_trade_id: str | None = Field(default=None, max_length=256)
    native_instrument_id: str | None = Field(default=None, max_length=256)
    outcome_label: str | None = Field(default=None, max_length=160)
    outcome_index: int | None = Field(default=None, ge=0, le=2_147_483_647)
    price: Nonnegative
    quantity: Positive
    quote_currency: str | None = None
    aggressor_side: str | None = None
    exchange_timestamp_utc: datetime | None = None
    received_at_utc: datetime
    provenance: Provenance

    @field_validator("exchange_timestamp_utc", "received_at_utc")
    @classmethod
    def trade_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Trade timestamps must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def trade_schema_is_supported(self) -> TradeObservation:
        if self.schema_version not in {1, 2}:
            raise ValueError("Unsupported trade-observation schema version")
        if self.schema_version == 2 and self.native_instrument_id is None:
            raise ValueError("Trade-observation schema v2 requires a native instrument identity")
        return self


class TradeBatch(FrontierModel):
    """One source response and its bounded normalized public trades."""

    schema_version: int = 1
    venue: Venue
    trades: tuple[TradeObservation, ...]
    requested_market_id: str | None = Field(default=None, max_length=256)
    page_limit: int | None = Field(default=None, ge=1, le=1000)
    source_cursor: str | None = Field(default=None, max_length=2048)
    source_next_cursor: str | None = Field(default=None, max_length=2048)
    has_more: bool | None = None

    @model_validator(mode="after")
    def trade_venues_match_batch(self) -> TradeBatch:
        if self.schema_version not in {1, 2}:
            raise ValueError("Unsupported trade-batch schema version")
        if any(trade.venue != self.venue for trade in self.trades):
            raise ValueError("Trade batch entries must belong to the declared venue")
        if self.schema_version == 2 and any(trade.schema_version != 2 for trade in self.trades):
            raise ValueError("Paginated trade-batch entries must use trade-observation schema v2")
        if self.requested_market_id is not None and any(
            trade.native_market_id != self.requested_market_id for trade in self.trades
        ):
            raise ValueError("Trade batch entries must match the requested market")
        if self.has_more is not None:
            if self.has_more != (self.source_next_cursor is not None):
                raise ValueError("Trade pagination flag must match its source continuation cursor")
            if self.page_limit is None:
                raise ValueError("Paginated trade batches require their source page limit")
        if self.schema_version == 2 and (
            self.requested_market_id is None or self.page_limit is None or self.has_more is None
        ):
            raise ValueError("Trade-batch schema v2 requires complete page metadata")
        if self.source_cursor is not None and not self.source_cursor.strip():
            raise ValueError("Source trade cursor cannot be blank")
        if self.source_next_cursor is not None and not self.source_next_cursor.strip():
            raise ValueError("Next source trade cursor cannot be blank")
        return self


class HistoricalCandle(FrontierModel):
    open_time_utc: datetime
    open: Nonnegative
    high: Nonnegative
    low: Nonnegative
    close: Nonnegative
    volume: Nonnegative
    trade_count: int | None = None

    @field_validator("open_time_utc")
    @classmethod
    def candle_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Candle time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def candle_prices_are_consistent(self) -> HistoricalCandle:
        if (
            self.low > self.high
            or not self.low <= self.open <= self.high
            or not self.low <= self.close <= self.high
        ):
            raise ValueError("Candle OHLC values are inconsistent")
        if self.trade_count is not None and self.trade_count < 0:
            raise ValueError("Candle trade count cannot be negative")
        return self


class CandleSeries(FrontierModel):
    schema_version: int = 1
    venue: Venue
    native_market_id: str
    interval_seconds: int
    candles: tuple[HistoricalCandle, ...]
    source_limit_note: str
    provenance: Provenance


class RawObservation(FrontierModel):
    schema_version: int = 1
    venue: Venue
    observation_kind: str
    request_url: str
    http_status: int
    request_started_at_utc: datetime
    received_at_utc: datetime
    raw_body: str
    raw_body_encoding: Literal["utf8", "base64"] = "utf8"
    raw_sha256: str
    adapter_version: str

    @model_validator(mode="after")
    def valid_hash_and_size(self) -> RawObservation:
        if self.raw_body_encoding == "utf8":
            raw = self.raw_body.encode("utf-8")
        else:
            try:
                raw = base64.b64decode(self.raw_body, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError("Raw observation base64 body is invalid") from error
        if len(raw) > 262144:
            raise ValueError("Raw observation exceeds the 256 KiB record bound")
        digest = hashlib.sha256(raw).hexdigest()
        if digest != self.raw_sha256:
            raise ValueError("Raw observation hash mismatch")
        return self


class SourceFailureRecord(FrontierModel):
    """Bounded normalization failure attached to a captured successful response."""

    schema_version: int = 1
    record_kind: Literal["source_failure"] = "source_failure"
    failure_stage: str = Field(min_length=1, max_length=64)
    error_code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=240)


def stable_market_id(venue: Venue, native_market_id: str) -> str:
    """Venue-local stable identity; it does not assert cross-venue equivalence."""
    return f"{venue.value}:{native_market_id}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
