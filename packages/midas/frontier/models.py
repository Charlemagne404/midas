"""Versioned, venue-aware data contracts; no order-entry concepts are defined here."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

D = Decimal
COINBASE_MARKET_DATA_TERMS_VERSION = "2026-08-07"
Nonnegative = Annotated[Decimal, Field(ge=0, max_digits=36, decimal_places=18, allow_inf_nan=False)]
MonotonicElapsedNs = Annotated[int, Field(strict=True, ge=0, le=9_223_372_036_854_775_807)]
ExactNonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
SettlementScalar = Annotated[
    Decimal, Field(ge=0, le=1, max_digits=36, decimal_places=18, allow_inf_nan=False)
]
Positive = Annotated[Decimal, Field(gt=0, max_digits=36, decimal_places=18, allow_inf_nan=False)]
JointMarketId = Annotated[str, Field(min_length=1, max_length=256)]
JointStateId = Annotated[str, Field(min_length=1, max_length=128)]
JointLocalStateId = Annotated[str, Field(min_length=1, max_length=128)]
JointStateProjection = Annotated[
    dict[JointStateId, JointLocalStateId], Field(min_length=2, max_length=64)
]
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
    COINBASE_EXCHANGE = "coinbase_exchange"


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


class SettlementAssetKind(StrEnum):
    FIAT = "fiat"
    TOKEN = "token"
    OTHER = "other"


class FeeStatus(StrEnum):
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    ESTIMATE = "estimate"


KALSHI_QUADRATIC_TAKER_FORMULA = "kalshi_quadratic_taker_microdollar_v1"


class EconomicAuditDisposition(StrEnum):
    VERIFIED = "verified"
    DISAGREEMENT = "disagreement"
    INCOMPLETE = "incomplete"
    NOT_EVALUATED = "not_evaluated"


class SettlementAuditState(StrEnum):
    INCOMPLETE_EVIDENCE = "INCOMPLETE EVIDENCE"
    SOURCE_VALUES_NOT_FINAL = "SOURCE VALUES NOT FINAL"
    SOURCE_REPORTED_PRODUCT_MATCH = "SOURCE REPORTED PRODUCT MATCH"
    SOURCE_REPORTED_PRODUCT_MISMATCH = "SOURCE REPORTED PRODUCT MISMATCH"
    UNSUPPORTED_SETTLEMENT_STRUCTURE = "UNSUPPORTED SETTLEMENT STRUCTURE"


class SourceState(StrEnum):
    NOT_PROBED = "not_probed"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class Capability(StrEnum):
    MARKET_DISCOVERY = "market_discovery"
    EVENT_MARKET_GROUPS = "event_market_groups"
    MULTIVARIATE_EVENT_DISCOVERY = "multivariate_event_discovery"
    INSTRUMENT_DISCOVERY = "instrument_discovery"
    MARKET_METADATA = "market_metadata"
    OUTCOME_DEFINITIONS = "outcome_definitions"
    BOOK_SNAPSHOT = "book_snapshot"
    BOOK_UPDATES = "book_updates"
    PUBLIC_TRADES = "public_trades"
    PAGINATED_PUBLIC_TRADES = "paginated_public_trades"
    PRICE_HISTORY = "price_history"
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
    probe_policy_block_reason: str | None = Field(default=None, max_length=512)
    timeout_seconds: Annotated[float, Field(ge=0.5, le=15)] = 5.0
    requests_per_second: Annotated[float, Field(gt=0, le=5)] = 1.0
    max_response_bytes: Annotated[int, Field(ge=1024, le=262144)] = 262144
    max_markets_per_call: Annotated[int, Field(ge=1, le=100)] = 20
    retries: Annotated[int, Field(ge=0, le=2)] = 1

    @property
    def has_valid_structure(self) -> bool:
        """Revalidate public-source resource bounds after possible model copies."""
        try:
            validated = type(self).model_validate(self.model_dump(mode="python", warnings=False))
            validated_payload = json.dumps(
                validated.model_dump(mode="json", warnings=False),
                sort_keys=True,
                separators=(",", ":"),
            )
            source_payload = json.dumps(
                self.model_dump(mode="json", warnings=False),
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            return False
        return validated_payload == source_payload


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


class PriceIncrementRange(FrontierModel):
    """Source-native price interval with exact Decimal step metadata."""

    start: Nonnegative
    end: Positive
    step: Positive

    @model_validator(mode="after")
    def interval_is_ordered(self) -> PriceIncrementRange:
        if self.end <= self.start:
            raise ValueError("Price increment range end must exceed its start")
        return self


class MarketInstrument(FrontierModel):
    native_instrument_id: str
    label: str
    outcome_id: str | None = None
    quantity_unit: QuantityUnit = QuantityUnit.UNKNOWN
    price_currency: str | None = None
    price_currency_identity: SettlementAssetIdentity | None = None
    tick_size: Positive | None = None
    price_increment_ranges: tuple[PriceIncrementRange, ...] | None = Field(
        default=None, max_length=32
    )
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

    @model_validator(mode="after")
    def quote_identity_and_constraints_are_valid(self) -> MarketInstrument:
        if self.price_currency_identity is not None and (
            self.price_currency_identity.code != self.price_currency
        ):
            raise ValueError("Instrument quote currency code differs from its canonical identity")
        payout_state_ids = [item.state_id for item in self.payouts]
        if len(payout_state_ids) != len(set(payout_state_ids)):
            raise ValueError("Instrument payout state identifiers must be unique")
        previous_end: Decimal | None = None
        if self.price_increment_ranges is not None:
            for price_range in self.price_increment_ranges:
                if previous_end is not None and price_range.start < previous_end:
                    raise ValueError("Price increment ranges must be ordered and non-overlapping")
                previous_end = price_range.end
        return self


class SelectedMarketComponent(FrontierModel):
    """Native selected contract leg; it does not assert the containing market payoff."""

    venue: Venue
    native_event_id: str | None = Field(default=None, max_length=256)
    native_market_id: str = Field(min_length=1, max_length=256)
    selected_side: Literal["yes", "no"]
    yes_settlement_value_dollars: SettlementScalar | None = None


class SettlementAssetIdentity(FrontierModel):
    """Canonical identity for a denomination unit, distinct from its display ticker."""

    schema_version: Literal[1] = 1
    kind: SettlementAssetKind
    code: str = Field(min_length=2, max_length=16)
    network_id: str | None = Field(default=None, min_length=1, max_length=128)
    asset_reference: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("code")
    @classmethod
    def normalize_asset_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isascii() or not normalized.isalnum():
            raise ValueError("Settlement asset code must be ASCII alphanumeric")
        return normalized

    @field_validator("network_id")
    @classmethod
    def normalize_network_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized or any(character.isspace() for character in normalized):
            raise ValueError("Settlement network identity is invalid")
        return normalized

    @field_validator("asset_reference")
    @classmethod
    def normalize_asset_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.isascii() or any(character.isspace() for character in normalized):
            raise ValueError("Settlement asset reference is invalid")
        if normalized.lower().startswith("0x"):
            if not re.fullmatch(r"0x[0-9a-fA-F]{40}", normalized):
                raise ValueError("EVM settlement asset references must be 20-byte addresses")
            normalized = normalized.lower()
        return normalized

    @model_validator(mode="after")
    def require_namespaced_non_fiat_assets(self) -> SettlementAssetIdentity:
        if self.kind == SettlementAssetKind.FIAT:
            if len(self.code) != 3 or not self.code.isalpha():
                raise ValueError("Fiat settlement assets require a three-letter currency code")
            if self.network_id is not None or self.asset_reference is not None:
                raise ValueError("Fiat settlement identity cannot include a network or reference")
        elif self.network_id is None or self.asset_reference is None:
            raise ValueError("Non-fiat settlement assets require network and asset reference")
        return self

    @property
    def canonical_id(self) -> str:
        """Versioned, collision-free encoding used in deterministic evidence identities."""
        components = json.dumps(
            [
                self.schema_version,
                self.kind.value,
                self.code,
                self.network_id,
                self.asset_reference,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return f"settlement-asset-v2:{components}"


class PayoffSpec(FrontierModel):
    schema_version: int = 2
    state_ids: tuple[str, ...] = ()
    payout_currency: str | None = None
    settlement_asset: str | None = None
    settlement_asset_identity: SettlementAssetIdentity | None = None
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
        if (
            self.settlement_asset_identity is not None
            and self.settlement_asset_identity.code != self.settlement_asset
        ):
            raise ValueError("Payoff settlement asset code differs from its canonical identity")
        return self


class JointStateMapDefinition(FrontierModel):
    """Validated joint-state definition before its content identity is added."""

    schema_version: Literal[1] = 1
    market_ids: tuple[JointMarketId, ...] = Field(min_length=2, max_length=4)
    joint_state_ids: tuple[JointStateId, ...] = Field(min_length=2, max_length=64)
    state_by_market: dict[JointMarketId, JointStateProjection] = Field(min_length=2, max_length=4)
    external_assertion_id: str = Field(min_length=1, max_length=120)
    evidence_observation_ids: tuple[str, ...] = Field(min_length=2, max_length=8)
    asserted_at_utc: datetime
    semantic_status: Literal["externally_asserted_unverified"] = "externally_asserted_unverified"

    @field_validator("asserted_at_utc")
    @classmethod
    def assertion_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Joint-state assertion time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def bounded_mapping(self) -> JointStateMapDefinition:
        if (
            not self.external_assertion_id.strip()
            or any(not item.strip() for item in self.market_ids)
            or any(not item.strip() for item in self.joint_state_ids)
        ):
            raise ValueError("Joint-state assertion and identity labels cannot be blank")
        if tuple(sorted(set(self.market_ids))) != self.market_ids:
            raise ValueError("Joint-state market IDs must be unique and lexically ordered")
        if tuple(sorted(set(self.joint_state_ids))) != self.joint_state_ids:
            raise ValueError("Joint-state IDs must be unique and lexically ordered")
        if set(self.state_by_market) != set(self.market_ids):
            raise ValueError("Joint-state projection markets must exactly match market_ids")
        joint_states = set(self.joint_state_ids)
        for market_id, projection in self.state_by_market.items():
            if set(projection) != joint_states or any(
                not local_state for local_state in projection.values()
            ):
                raise ValueError(
                    f"Joint-state projection for {market_id} must map every state to a bounded local state"
                )
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("Joint-state evidence observation IDs must be unique")
        for observation_id in self.evidence_observation_ids:
            if len(observation_id) != 64 or any(
                character not in "0123456789abcdef" for character in observation_id
            ):
                raise ValueError("Joint-state evidence IDs must be lowercase SHA-256 digests")
        return self


class JointStateMap(JointStateMapDefinition):
    """Bounded, externally asserted map pinned by a canonical content hash.

    The model deliberately has no ``verified`` state. A complete, correctly
    hashed mapping is still a semantic assertion and cannot certify that the
    listed joint states are exhaustive or physically attainable.
    """

    mapping_id: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def content_identity_matches(self) -> bool:
        try:
            definition = JointStateMapDefinition.model_validate(
                {
                    field_name: getattr(self, field_name)
                    for field_name in JointStateMapDefinition.model_fields
                }
            )
            payload = definition.model_dump(mode="json")
            digest = hashlib.sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("utf-8")
            ).hexdigest()
        except (TypeError, ValueError):
            return False
        return self.mapping_id == digest

    @model_validator(mode="after")
    def verify_mapping_identity(self) -> JointStateMap:
        if not self.content_identity_matches:
            raise ValueError("Joint-state mapping identity does not match its evidence payload")
        return self

    @classmethod
    def create(cls, **values: Any) -> JointStateMap:
        """Build a canonical mapping ID, then validate the complete payload."""
        if "mapping_id" in values:
            raise ValueError("mapping_id is derived from the joint-state evidence payload")
        definition = JointStateMapDefinition.model_validate(values)
        payload = definition.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "utf-8"
            )
        ).hexdigest()
        return cls.model_validate(payload | {"mapping_id": digest})


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
    fee_multiplier: Nonnegative | None = None
    formula: str | None = None
    fee_currency: str | None = None
    fee_currency_identity: SettlementAssetIdentity | None = None
    source_url: str | None = None
    evidence_sha256: str | None = None
    evidence_observation_ids: tuple[str, ...] = ()
    evidence_observed_at_utc: datetime | None = None
    effective_at_utc: datetime | None = None
    expires_at_utc: datetime | None = None
    note: str = "No verified instrument-specific schedule"

    @model_validator(mode="after")
    def verified_schedule_has_evidence(self) -> FeeSchedule:
        if self.status == FeeStatus.VERIFIED and not (self.source_url and self.evidence_sha256):
            raise ValueError("Verified fee schedule requires source and evidence hash")
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("Fee evidence observation identities must be unique")
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in self.evidence_observation_ids
        ):
            raise ValueError("Fee evidence observation identities must be SHA-256 digests")
        if self.formula == KALSHI_QUADRATIC_TAKER_FORMULA and (
            self.status != FeeStatus.ESTIMATE
            or self.applies_to != "taker"
            or self.rate != D("0.07")
            or self.fee_multiplier is None
            or self.fee_currency != "USD"
            or self.fee_currency_identity is None
            or self.source_url is None
            or self.evidence_sha256 is None
            or len(self.evidence_observation_ids) != 2
            or self.evidence_observed_at_utc is None
        ):
            raise ValueError("Kalshi fee estimate requires complete public formula provenance")
        if self.fee_currency_identity is not None and (
            self.fee_currency_identity.code != self.fee_currency
        ):
            raise ValueError("Fee currency code differs from its canonical identity")
        return self

    @field_validator("evidence_observed_at_utc", "effective_at_utc", "expires_at_utc")
    @classmethod
    def fee_schedule_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Fee schedule times must include a timezone")
        return value.astimezone(UTC) if value is not None else None


class KalshiFeeMetadata(FrontierModel):
    """Public native Kalshi fee parameters; deliberately not an account fee quote."""

    schema_version: Literal[1, 2] = 2
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
    fee_resolution_state: Literal[
        "event_override", "series_inherited", "partial_override", "override_unreported"
    ] = "override_unreported"
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
        "Fee sensitivity requires both event override fields to be complete or explicitly cleared; missing or partial override metadata is unresolved.",
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

    schema_version: Literal[2] = 2
    model_version: str = "kalshi-event-taker-fee-sensitivity-2026-07-07-v2"
    native_market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str = Field(min_length=1, max_length=256)
    series_ticker: str = Field(min_length=1, max_length=256)
    effective_fee_type: str = Field(min_length=1, max_length=80)
    effective_fee_multiplier: Nonnegative
    fee_resolution_state: Literal["event_override", "series_inherited"]
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

    schema_version: Literal[2] = 2
    model_version: str = "kalshi-event-taker-order-fee-sensitivity-2026-07-07-v2"
    native_market_id: str = Field(min_length=1, max_length=256)
    native_event_id: str = Field(min_length=1, max_length=256)
    series_ticker: str = Field(min_length=1, max_length=256)
    effective_fee_type: str = Field(min_length=1, max_length=80)
    effective_fee_multiplier: Nonnegative
    fee_resolution_state: Literal["event_override", "series_inherited"]
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

    schema_version: int = 3
    model_version: str = "frontier-independent-economic-audit-21"
    disposition: EconomicAuditDisposition
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checked_market_count: int = Field(ge=0, le=4)
    checked_leg_count: int = Field(ge=0, le=16)
    recomputed_gross_cost: SignedDecimal | None = None
    recomputed_modeled_fees: SignedDecimal | None = None
    recomputed_modeled_net_cost: SignedDecimal | None = None
    recomputed_payout_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_gross_pnl_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_net_pnl_by_state: dict[str, SignedDecimal] = Field(default_factory=dict)
    recomputed_worst_case_gross_pnl: SignedDecimal | None = None
    recomputed_worst_case_net_pnl: SignedDecimal | None = None
    recomputed_received_skew_ms: int | None = Field(default=None, ge=0)
    recomputed_exchange_skew_ms: int | None = Field(default=None, ge=0)
    recomputed_timing_verified: bool | None = None
    checks: tuple[str, ...] = Field(default=(), max_length=20)
    message: str = Field(max_length=2000)


class Provenance(FrontierModel):
    source_url: str
    adapter_version: str
    source_schema_version: str | None = None
    request_started_at_utc: datetime
    response_received_at_utc: datetime
    request_elapsed_monotonic_ns: MonotonicElapsedNs | None = None
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
    schema_version: int = 4
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
    settlement_asset_identity: SettlementAssetIdentity | None = None
    reported_settlement_value_dollars: SettlementScalar | None = None
    settlement_is_provisional: StrictBool | None = None
    native_fields: dict[str, Any] = Field(default_factory=dict)
    quality_flags: tuple[str, ...] = ()
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def supported_market_schema_version(cls, value: int) -> int:
        if value not in {1, 2, 3, 4}:
            raise ValueError("Unsupported Frontier market schema version")
        return value

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
        if (
            self.settlement_asset_identity is not None
            and self.settlement_asset_identity.code != self.settlement_asset
        ):
            raise ValueError("Market settlement asset code differs from its canonical identity")
        if (
            self.settlement_asset_identity is not None
            and self.payoff.settlement_asset_identity is not None
            and self.settlement_asset_identity != self.payoff.settlement_asset_identity
        ):
            raise ValueError("Market and payoff settlement asset identities disagree")
        if self.payoff.verified:
            state_ids = set(self.payoff.state_ids)
            for outcome in self.instruments:
                payout_state_ids = [payout.state_id for payout in outcome.payouts]
                if (
                    len(payout_state_ids) != len(set(payout_state_ids))
                    or set(payout_state_ids) != state_ids
                ):
                    raise ValueError(
                        "Verified payoff must define every state exactly once for every outcome"
                    )
        return self

    @property
    def has_valid_structure(self) -> bool:
        """Revalidate nested contract structure after possible unvalidated model copies."""
        try:
            validated = FrontierMarket.model_validate(
                self.model_dump(mode="python", warnings=False)
            )
        except (TypeError, ValueError):
            return False
        return validated == self

    def has_consistent_settlement_asset_identity(self) -> bool:
        """Whether the market and payoff identify the same exact settlement asset."""
        identity = self.settlement_asset_identity
        payoff_identity = self.payoff.settlement_asset_identity
        return (
            identity is not None
            and payoff_identity is not None
            and identity == payoff_identity
            and identity.code == self.settlement_asset
            and identity.code == self.payoff.settlement_asset
        )

    @field_validator("native_fields")
    @classmethod
    def bounded_native_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if len(raw.encode("utf-8")) > 262144:
            raise ValueError("Native metadata exceeds the 256 KiB record bound")
        return value


class MarketMetadataEvidence(FrontierModel):
    """One market-detail capture bound to an existing recorded catalogue row."""

    schema_version: Literal[1] = 1
    venue: Venue
    requested_market_id: str = Field(min_length=1, max_length=256)
    bound_market_observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_observation_kind: Literal["market_metadata"] = "market_metadata"
    market: FrontierMarket

    @model_validator(mode="after")
    def detail_matches_recorded_identity(self) -> MarketMetadataEvidence:
        if self.market.venue != self.venue:
            raise ValueError("Market metadata venue differs from its evidence envelope")
        if self.market.canonical_id != self.requested_market_id:
            raise ValueError("Market metadata does not match the requested recorded market")
        return self


class KalshiMveComponentSettlementValue(FrontierModel):
    native_market_id: str = Field(min_length=1, max_length=256)
    selected_side: Literal["yes", "no"]
    reported_yes_value_dollars: SettlementScalar | None = None
    selected_position_value_dollars: SettlementScalar | None = None


class KalshiMveSettlementAudit(FrontierModel):
    schema_version: int = 2
    audit_algorithm_version: str = Field(min_length=1, max_length=80)
    market_id: str
    native_market_id: str
    source_observation_id: str
    source_raw_sha256: str
    lifecycle: Lifecycle
    settlement_is_provisional: bool | None = None
    state: SettlementAuditState
    component_values: tuple[KalshiMveComponentSettlementValue, ...] = Field(
        default=(), max_length=64
    )
    component_product_dollars: ExactNonnegative | None = None
    reported_settlement_value_dollars: SettlementScalar | None = None
    missing_component_market_ids: tuple[str, ...] = Field(default=(), max_length=64)
    assumptions: tuple[str, ...]
    rule_source_urls: tuple[str, ...] = Field(min_length=2, max_length=3)


class MarketGroup(FrontierModel):
    """Venue-declared event grouping retained separately from payoff equivalence."""

    schema_version: int = 1
    venue: Venue
    group_type: Literal["event", "multivariate_event"]
    native_group_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=512)
    subtitle: str | None = Field(default=None, max_length=512)
    native_series_id: str | None = Field(default=None, max_length=256)
    native_collection_id: str | None = Field(default=None, max_length=256)
    member_native_market_ids: tuple[str, ...] = Field(default=(), max_length=100)
    member_list_state: Literal["included", "empty", "omitted"] = "omitted"
    native_fields: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance

    @model_validator(mode="after")
    def unique_members(self) -> MarketGroup:
        if len(self.member_native_market_ids) != len(set(self.member_native_market_ids)):
            raise ValueError("Market group contains duplicate native market IDs")
        if self.member_list_state == "included" and not self.member_native_market_ids:
            raise ValueError("An included market-member list cannot be empty")
        if self.member_list_state != "included" and self.member_native_market_ids:
            raise ValueError("Markets cannot be listed when the member list is absent or empty")
        return self

    @field_validator("native_fields")
    @classmethod
    def bounded_group_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if len(raw.encode("utf-8")) > 262144:
            raise ValueError("Native market-group metadata exceeds the 256 KiB record bound")
        return value


class MarketBatch(FrontierModel):
    schema_version: int = 2
    venue: Venue
    markets: tuple[FrontierMarket, ...]
    market_groups: tuple[MarketGroup, ...] = Field(default=(), max_length=100)
    cursor: str | None = None
    complete_for_request: bool = False
    note: str = (
        "One bounded discovery response; absence from this page is not proof of venue-wide absence."
    )

    @model_validator(mode="after")
    def group_venues_match_batch(self) -> MarketBatch:
        if any(group.venue != self.venue for group in self.market_groups):
            raise ValueError("Market-group venue must match its batch")
        return self


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
    schema_version: int = 2
    venue: Venue
    native_market_id: str
    native_instrument_id: str
    asks: tuple[BookLevel, ...] = ()
    bids: tuple[BookLevel, ...] = ()
    price_unit: str
    price_currency: str | None = None
    price_currency_identity: SettlementAssetIdentity | None = None
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
    def has_valid_structure(self) -> bool:
        """Revalidate the complete snapshot after possible unvalidated model copies."""
        try:
            validated = BookSnapshot.model_validate(self.model_dump(mode="python", warnings=False))
        except (TypeError, ValueError):
            return False
        return validated == self

    @model_validator(mode="after")
    def quote_identity_matches_code(self) -> BookSnapshot:
        if self.price_currency_identity is not None and (
            self.price_currency_identity.code != self.price_currency
        ):
            raise ValueError("Book quote currency code differs from its canonical identity")
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
    quote_currency_identity: SettlementAssetIdentity | None = None
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
        if self.schema_version not in {1, 2, 3}:
            raise ValueError("Unsupported trade-observation schema version")
        if self.schema_version >= 2 and self.native_instrument_id is None:
            raise ValueError("Trade-observation schemas v2+ require a native instrument identity")
        if self.quote_currency_identity is not None and (
            self.quote_currency_identity.code != self.quote_currency
        ):
            raise ValueError("Trade quote currency differs from its canonical identity")
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
        if self.schema_version == 2 and any(trade.schema_version < 2 for trade in self.trades):
            raise ValueError("Paginated trade-batch entries require trade-observation schema v2+")
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


class HistoricalPricePoint(FrontierModel):
    """A source-reported price sample; it is not a quote or an OHLC candle."""

    timestamp_utc: datetime
    price: SettlementScalar

    @field_validator("timestamp_utc")
    @classmethod
    def price_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Price-history time must include a timezone")
        if value.microsecond:
            raise ValueError("Price-history timestamps must have whole-second precision")
        return value.astimezone(UTC)


class PriceHistorySeries(FrontierModel):
    schema_version: int = 1
    venue: Venue
    native_instrument_id: str = Field(min_length=1, max_length=256)
    interval: Literal["1d", "1w"]
    fidelity_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)]
    requested_start_ts: Annotated[int, Field(strict=True, ge=0)]
    requested_end_ts: Annotated[int, Field(strict=True, ge=1)]
    bound_market_observation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    points: tuple[HistoricalPricePoint, ...] = Field(max_length=1500)
    source_price_semantics: Literal["source_reported_price_sample"] = "source_reported_price_sample"
    source_limit_note: str
    provenance: Provenance

    @field_validator("points", mode="before")
    @classmethod
    def revalidate_point_instances(cls, value: Any) -> Any:
        """Do not trust already-instantiated nested models to have run validators."""
        if isinstance(value, (tuple, list)):
            return tuple(
                point.model_dump(mode="python")
                if isinstance(point, HistoricalPricePoint)
                else point
                for point in value
            )
        return value

    @model_validator(mode="after")
    def price_history_is_bounded_and_ordered(self) -> PriceHistorySeries:
        if self.requested_end_ts <= self.requested_start_ts:
            raise ValueError("Price-history end time must follow its start time")
        if self.requested_end_ts - self.requested_start_ts > 7 * 24 * 60 * 60:
            raise ValueError("Price-history request cannot exceed 7 days")
        timestamps = tuple(int(point.timestamp_utc.timestamp()) for point in self.points)
        if any(
            timestamp < self.requested_start_ts or timestamp > self.requested_end_ts
            for timestamp in timestamps
        ):
            raise ValueError("Price-history points must fall within the requested time range")
        if tuple(sorted(set(timestamps))) != timestamps:
            raise ValueError("Price-history points must be strictly time-ordered and unique")
        return self


class RawObservation(FrontierModel):
    schema_version: int = 2
    venue: Venue
    observation_kind: str
    request_url: str
    http_status: int
    request_started_at_utc: datetime
    received_at_utc: datetime
    request_elapsed_monotonic_ns: MonotonicElapsedNs | None = None
    raw_body: str
    raw_body_encoding: Literal["utf8", "base64"] = "utf8"
    raw_body_state: Literal["complete", "not_captured_after_size_limit"] = "complete"
    raw_sha256: str
    adapter_version: str

    @field_validator("request_started_at_utc", "received_at_utc")
    @classmethod
    def raw_observation_times_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Raw-observation timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_hash_and_size(self) -> RawObservation:
        if self.schema_version not in {1, 2}:
            raise ValueError("Unsupported raw-observation schema version")
        if self.schema_version == 1 and self.raw_body_state != "complete":
            raise ValueError("Raw-observation schema v1 cannot describe omitted response bodies")
        if self.raw_body_encoding == "utf8":
            raw = self.raw_body.encode("utf-8")
        else:
            try:
                raw = base64.b64decode(self.raw_body, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError("Raw observation base64 body is invalid") from error
        if len(raw) > 262144:
            raise ValueError("Raw observation exceeds the 256 KiB record bound")
        if self.raw_body_state == "not_captured_after_size_limit" and raw:
            raise ValueError("Size-rejected response bodies must not be stored")
        digest = hashlib.sha256(raw).hexdigest()
        if digest != self.raw_sha256:
            raise ValueError("Raw observation hash mismatch")
        return self


class ResponseRejectionMetadata(FrontierModel):
    """Observed size metadata for a response rejected by the body-size limit."""

    schema_version: Literal[1] = 1
    rejection_stage: Literal["content_length", "response_stream"]
    response_body_state: Literal["not_captured_after_size_limit"] = "not_captured_after_size_limit"
    response_body_limit_bytes: int = Field(ge=1024, le=262144)
    declared_content_length_bytes: int | None = Field(default=None, ge=0)
    bytes_yielded_at_rejection: int = Field(ge=0, le=524288)

    @model_validator(mode="after")
    def size_metadata_matches_rejection(self) -> ResponseRejectionMetadata:
        if self.rejection_stage == "content_length":
            if (
                self.declared_content_length_bytes is None
                or self.declared_content_length_bytes <= self.response_body_limit_bytes
                or self.bytes_yielded_at_rejection != 0
            ):
                raise ValueError("Content-length rejection metadata is inconsistent")
        elif self.bytes_yielded_at_rejection <= self.response_body_limit_bytes:
            raise ValueError("Stream rejection requires evidence beyond the configured limit")
        return self


class SourceFailureRecord(FrontierModel):
    """Bounded source or normalization failure diagnostic."""

    schema_version: int = 2
    record_kind: Literal["source_failure"] = "source_failure"
    failure_stage: str = Field(min_length=1, max_length=64)
    error_code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=240)
    response_rejection: ResponseRejectionMetadata | None = None

    @field_validator("schema_version")
    @classmethod
    def supported_source_failure_schema(cls, value: int) -> int:
        if value not in {1, 2}:
            raise ValueError("Unsupported source-failure schema version")
        return value

    @model_validator(mode="after")
    def rejection_requires_matching_stage(self) -> SourceFailureRecord:
        if self.response_rejection is not None and self.failure_stage != "transport_rejection":
            raise ValueError("Response-rejection metadata requires the transport_rejection stage")
        return self


def stable_market_id(venue: Venue, native_market_id: str) -> str:
    """Venue-local stable identity; it does not assert cross-venue equivalence."""
    return f"{venue.value}:{native_market_id}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
