"""Versioned public-observation research contract, separate from execution truth."""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .storage import canonical

FEATURE_VERSION = "reality-decision-features-v1"
LABEL_VERSION = "reality-observable-labels-v1"
BUILDER_VERSION = "reality-foundry-v1"
TARGETS = (
    "quote_persistence",
    "depth_at_original_quotes",
    "adverse_ask_movement",
    "opportunity_persistence",
    "displayed_acquisition_cost",
    "market_disruption",
    "quoted_exit_value_change",
)
LIMITATIONS = [
    "Public quotes/depth do not identify hypothetical fills, private queue position or own market impact.",
    "Receipt-order reconstruction is unsequenced and may not contain every venue event.",
    "Labels use the first sufficiently synchronized later depth observations within declared tolerance, not sub-event interpolation.",
    "Aggregate depth at a price does not identify survival of the same constituent orders.",
    "Prices/costs use collateral units before fees, conversion and settlement assumptions.",
    "Correlated snapshots are grouped; row count is not independent sample coverage.",
]


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class DatasetSpec:
    horizons_ms: tuple[int, ...] = (100, 300, 1000, 5000)
    quantity: str = "5"
    hypothetical_capital: str = "100"
    stride_ms: int = 1000
    future_tolerance_ms: int = 500
    max_freshness_ms: int = 5000
    max_skew_ms: int = 250
    lookback_ms: int = 10000
    embargo_ms: int = 10000
    group_window_ms: int = 30000
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    start_ns: int | None = None
    end_ns: int | None = None
    max_examples: int = 200000
    derivative_budget_bytes: int = 512 * 1024**2
    reserve_bytes: int = 20 * 1024**3
    source_kind: str = "genuine_public_recording"

    def __post_init__(self) -> None:
        if (
            not self.horizons_ms
            or len(self.horizons_ms) > 8
            or len(set(self.horizons_ms)) != len(self.horizons_ms)
            or any(type(h) is not int or not 1 <= h <= 60000 for h in self.horizons_ms)
        ):
            raise ValueError("Horizons must be distinct positive integer milliseconds <=60000")
        for name in (
            "stride_ms",
            "future_tolerance_ms",
            "max_freshness_ms",
            "max_skew_ms",
            "lookback_ms",
            "embargo_ms",
            "group_window_ms",
            "max_examples",
            "derivative_budget_bytes",
            "reserve_bytes",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.embargo_ms < max(self.horizons_ms) + self.future_tolerance_ms:
            raise ValueError("Embargo must cover every label horizon plus observation tolerance")
        for value in (self.quantity, self.hypothetical_capital):
            if not isinstance(value, str) or len(value) > 80:
                raise ValueError("Hypothetical quantities must be bounded decimal strings")
            number = Decimal(value)
            if not number.is_finite() or not 0 < number <= 1000000:
                raise ValueError("Hypothetical quantities out of range")
        if not all(
            math.isfinite(x) for x in (self.train_fraction, self.validation_fraction)
        ) or not (
            0 < self.train_fraction < 1
            and 0 < self.validation_fraction < 1
            and self.train_fraction + self.validation_fraction < 1
        ):
            raise ValueError("Invalid chronological fractions")
        if self.start_ns is not None and self.end_ns is not None and self.start_ns >= self.end_ns:
            raise ValueError("Dataset time window is empty")
        if self.source_kind not in {"genuine_public_recording", "labeled_fixture"}:
            raise ValueError("Unsupported evidence source kind")

    def tolerance_ms(self, horizon_ms: int) -> int:
        return min(self.future_tolerance_ms, max(1, horizon_ms // 4))

    def dump(self) -> dict[str, Any]:
        value = asdict(self)
        value["horizons_ms"] = list(self.horizons_ms)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DatasetSpec:
        data = dict(value)
        if "horizons_ms" in data:
            data["horizons_ms"] = tuple(data["horizons_ms"])
        return cls(**data)
