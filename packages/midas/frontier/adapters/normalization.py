"""Shared timestamp, identity, and evidence helpers for venue adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from midas.frontier.adapters.transport import HTTPObservation
from midas.frontier.models import Lifecycle, Provenance, Venue

D = Decimal


def parse_decimal(value: Any) -> D | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = D(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def parse_time(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and value.isdecimal()):
        try:
            timestamp = D(str(value))
            if timestamp > D("10000000000"):
                timestamp /= D(1000)
            seconds = int(timestamp)
            micros = int((timestamp - D(seconds)) * D(1_000_000))
            return datetime.fromtimestamp(seconds, tz=UTC) + timedelta(microseconds=micros)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def lifecycle(value: Any, *, active: bool | None = None, closed: bool | None = None) -> Lifecycle:
    status = str(value or "").lower()
    if status in {"settled", "resolved"}:
        return Lifecycle.SETTLED
    if status in {"closed", "finalized", "inactive"} or closed is True:
        return Lifecycle.CLOSED
    if status in {"paused", "suspended"}:
        return Lifecycle.PAUSED
    if status in {"unopened", "initialized"}:
        return Lifecycle.UNOPENED
    if status in {"active", "open", "trading", "online"} or active is True:
        return Lifecycle.OPEN
    if active is False:
        return Lifecycle.PAUSED
    return Lifecycle.UNKNOWN


def provenance(
    venue: Venue,
    adapter_version: str,
    response: HTTPObservation,
    observation_kind: str,
    native_identity: str,
    *,
    source_schema_version: str | None = None,
    exchange_timestamp: datetime | None = None,
    exchange_timestamp_semantics: str = "unknown",
) -> Provenance:
    raw_hash = hashlib.sha256(response.raw_body.encode("utf-8")).hexdigest()
    observation_id = hashlib.sha256(
        "|".join(
            (
                venue.value,
                observation_kind,
                native_identity,
                raw_hash,
                response.request_started_at_utc.isoformat(),
                response.response_received_at_utc.isoformat(),
            )
        ).encode()
    ).hexdigest()
    return Provenance(
        source_url=response.url,
        adapter_version=adapter_version,
        source_schema_version=source_schema_version,
        request_started_at_utc=response.request_started_at_utc,
        response_received_at_utc=response.response_received_at_utc,
        processed_at_utc=datetime.now(UTC),
        exchange_timestamp_utc=exchange_timestamp,
        exchange_timestamp_semantics=exchange_timestamp_semantics,
        raw_sha256=raw_hash,
        observation_id=observation_id,
    )


def native_json(raw: dict[str, Any]) -> dict[str, Any]:
    """Copy source fields through a JSON round trip to exclude executable objects."""
    try:
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
        decoded = json.loads(encoded, parse_float=D)
    except (TypeError, ValueError) as error:
        raise ValueError("Source metadata is not safely JSON serializable") from error
    if not isinstance(decoded, dict):
        raise ValueError("Expected a source object")
    return decoded
