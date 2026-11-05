"""Provider-neutral observation provenance with explicit clock/sequence uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TimestampUnit = Literal[
    "seconds",
    "milliseconds",
    "microseconds",
    "nanoseconds",
    "opaque",
    "unknown",
    "not_provided",
]
TimestampSemantics = Literal[
    "event_time", "publish_time", "snapshot_time", "receipt_time", "unknown", "not_provided"
]
SequenceSemantics = Literal[
    "global_monotonic",
    "connection_monotonic",
    "market_monotonic",
    "opaque",
    "unknown",
    "not_provided",
]


@dataclass(frozen=True)
class SourceProvenance:
    """Source identity plus the provider's actual timestamp and ordering contract.

    Missing timestamps or sequences remain explicit. The model never derives a
    provider sequence from MIDAS's local ordinal or receipt clock.
    """

    source_id: str
    market_id: str | None = None
    market_structure: str | None = None
    timestamp_value: int | str | None = None
    timestamp_unit: TimestampUnit = "not_provided"
    timestamp_semantics: TimestampSemantics = "not_provided"
    clock_domain: str = "unknown"
    timestamp_uncertainty_ns: int | None = None
    sequence_value: int | str | None = None
    sequence_semantics: SequenceSemantics = "not_provided"
    sequence_scope: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, str)
            or not self.source_id.strip()
            or len(self.source_id) > 128
        ):
            raise ValueError("Source identity must contain 1..128 characters")
        if (
            not isinstance(self.clock_domain, str)
            or not self.clock_domain.strip()
            or len(self.clock_domain) > 128
        ):
            raise ValueError("Clock domain must contain 1..128 characters")
        if (self.market_id is None) != (self.market_structure is None):
            raise ValueError("Market identity and structure must be recorded together")
        for name, value in (
            ("Market identity", self.market_id),
            ("Market structure", self.market_structure),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 256
            ):
                raise ValueError(f"{name} must contain 1..256 characters")
        if not isinstance(self.timestamp_unit, str) or self.timestamp_unit not in {
            "seconds",
            "milliseconds",
            "microseconds",
            "nanoseconds",
            "opaque",
            "unknown",
            "not_provided",
        }:
            raise ValueError("Unsupported provider timestamp unit")
        if not isinstance(self.timestamp_semantics, str) or self.timestamp_semantics not in {
            "event_time",
            "publish_time",
            "snapshot_time",
            "receipt_time",
            "unknown",
            "not_provided",
        }:
            raise ValueError("Unsupported provider timestamp semantics")
        if not isinstance(self.sequence_semantics, str) or self.sequence_semantics not in {
            "global_monotonic",
            "connection_monotonic",
            "market_monotonic",
            "opaque",
            "unknown",
            "not_provided",
        }:
            raise ValueError("Unsupported provider sequence semantics")
        if self.timestamp_value is not None and type(self.timestamp_value) not in (int, str):
            raise ValueError("Provider timestamp must be an integer, string, or None")
        if self.timestamp_value is None:
            if self.timestamp_unit not in {
                "not_provided",
                "unknown",
            } or self.timestamp_semantics not in {
                "not_provided",
                "unknown",
            }:
                raise ValueError("Missing provider timestamp must be represented explicitly")
        elif self.timestamp_unit in {"not_provided", "unknown"} or self.timestamp_semantics in {
            "not_provided",
            "unknown",
        }:
            raise ValueError("Present provider timestamp needs declared semantics")
        elif isinstance(self.timestamp_value, int) and self.timestamp_value < 0:
            raise ValueError("Provider timestamp cannot be negative")
        elif isinstance(self.timestamp_value, str) and not self.timestamp_value:
            raise ValueError("Opaque provider timestamp cannot be empty")
        if self.timestamp_uncertainty_ns is not None:
            if type(self.timestamp_uncertainty_ns) is not int or self.timestamp_uncertainty_ns < 0:
                raise ValueError("Timestamp uncertainty must be a nonnegative integer")
            if self.timestamp_value is None:
                raise ValueError("Timestamp uncertainty requires a present timestamp")
        if self.sequence_value is not None and type(self.sequence_value) not in (int, str):
            raise ValueError("Provider sequence must be an integer, string, or None")
        if self.sequence_value is None:
            if self.sequence_semantics not in {"not_provided", "unknown"} or self.sequence_scope:
                raise ValueError("Missing provider sequence must remain explicitly unsequenced")
        else:
            if self.sequence_semantics in {"not_provided", "unknown"}:
                raise ValueError("Present provider sequence needs declared semantics")
            if isinstance(self.sequence_value, int) and self.sequence_value < 0:
                raise ValueError("Provider sequence cannot be negative")
            if isinstance(self.sequence_value, str) and not self.sequence_value:
                raise ValueError("Opaque provider sequence cannot be empty")
            if (
                not isinstance(self.sequence_scope, str)
                or not self.sequence_scope.strip()
                or len(self.sequence_scope) > 256
            ):
                raise ValueError("Provider sequence needs an explicit scope")

    def record_metadata(self) -> dict[str, dict[str, int | str | None]]:
        """Return one nested metadata object suitable for ``Store.append``."""
        return {
            "source_provenance": {
                "source_id": self.source_id,
                "market_id": self.market_id,
                "market_structure": self.market_structure,
                "timestamp_value": self.timestamp_value,
                "timestamp_unit": self.timestamp_unit,
                "timestamp_semantics": self.timestamp_semantics,
                "clock_domain": self.clock_domain,
                "timestamp_uncertainty_ns": self.timestamp_uncertainty_ns,
                "sequence_value": self.sequence_value,
                "sequence_semantics": self.sequence_semantics,
                "sequence_scope": self.sequence_scope,
            }
        }
