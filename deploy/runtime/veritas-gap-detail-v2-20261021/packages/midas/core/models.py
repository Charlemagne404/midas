"""Framework-independent domain contracts. All money is exact Decimal collateral units."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

D = Decimal
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Source(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    LIVE = "LIVE"
    RECORDED = "RECORDED"


class Status(StrEnum):
    VERIFIED = "VERIFIED_MATHEMATICAL"
    CANDIDATE = "CANDIDATE"
    LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    PAYOUT = "UNVERIFIED_PAYOUT"
    FEES = "UNKNOWN_FEES"
    STALE = "STALE_DATA"
    INVALID = "INVALID_MARKET"
    NEGATIVE = "NEGATIVE_EDGE"
    UNSUPPORTED = "UNSUPPORTED_STRUCTURE"
    CAPITAL = "INSUFFICIENT_CAPITAL"


class Instrument(Model):
    asset_id: str
    label: str


class Fee(Model):
    rate: Nonnegative = D("0")
    exponent: int = 1
    verified: bool = False
    evidence: str = "No verified market-specific schedule"
    verified_ts_ms: int | None = None
    expires_ts_ms: int | None = None
    rule_version: str = "polymarket-fees-2026-10-11"


class Market(Model):
    id: str
    event_id: str
    question: str
    condition_id: str
    protocol: str
    instruments: tuple[Instrument, ...]
    source: Source
    active: bool = True
    closed: bool = False
    accepting_orders: bool = True
    negative_risk: bool = False
    augmented_negative_risk: bool = False
    complementary_verified: bool = False
    payout_verified: bool = False
    payout_per_set: Positive = D("1")
    payout_evidence: str = "Not established"
    fee: Fee = Fee()
    description: str = ""
    resolution_source: str = ""
    resolution_metadata: dict[str, Any] = Field(default_factory=dict)
    execution_delay_ms: int | None = None
    attestation: dict[str, Any] | None = None


class Level(Model):
    price: Annotated[Decimal, Field(gt=0, lt=1, allow_inf_nan=False)]
    size: Positive


class Book(Model):
    asset_id: str
    condition_id: str
    asks: tuple[Level, ...] = ()
    bids: tuple[Level, ...] = ()
    tick_size: Positive = D("0.01")
    min_order_size: Positive = D("5")
    minimum_unit: Literal["shares", "notional"] = "shares"
    exchange_ts_ms: int | None = None
    received_ts_ms: int
    source: Source
    valid: bool = True
    integrity: str = "snapshot"
    hash: str | None = None
    invalid_reason: str | None = None

    @model_validator(mode="after")
    def levels_valid(self) -> "Book":
        for levels in (self.asks, self.bids):
            if len({x.price for x in levels}) != len(levels):
                raise ValueError("Duplicate price level")
            if any(x.price % self.tick_size != 0 for x in levels):
                raise ValueError("Price violates tick size")
        if (
            self.asks
            and self.bids
            and max(x.price for x in self.bids) >= min(x.price for x in self.asks)
        ):
            raise ValueError("Crossed or locked snapshot")
        return self

    @field_validator("exchange_ts_ms", "received_ts_ms")
    @classmethod
    def nonnegative_ts(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Negative timestamp")
        return value


class Slice(Model):
    asset_id: str
    price: Decimal
    quantity: Decimal
    notional: Decimal
    fee: Decimal


class Evaluation(Model):
    market_id: str
    question: str
    source: Source
    observed_ts_ms: int
    status: Status
    reasons: tuple[str, ...]
    quantity: Decimal = D("0")
    available_quantity: Decimal = D("0")
    gross_cost: Decimal = D("0")
    fees: Decimal = D("0")
    required_capital: Decimal = D("0")
    minimum_payout: Decimal = D("0")
    gross_profit: Decimal = D("0")
    net_profit: Decimal = D("0")
    gross_edge: Decimal = D("0")
    net_edge: Decimal = D("0")
    capital_utilization: Decimal = D("0")
    slippage: Decimal = D("0")
    payouts: dict[str, Decimal] = Field(default_factory=dict)
    slices: tuple[Slice, ...] = ()
    assumptions: tuple[str, ...] = ()
    books: tuple[Book, ...] = ()
    market: Market | None = None
    economic_proof: dict[str, Any] = Field(default_factory=dict)


class MarketEvent(Model):
    schema_version: int = 1
    event_id: str
    kind: str
    source: Source
    received_ts_ms: int
    exchange_ts_ms: int | None = None
    asset_id: str | None = None
    raw: dict[str, Any]
    raw_wire_json: str | None = None
    book: Book | None = None
    interpretation_version: str = "midas-adapter-1"
