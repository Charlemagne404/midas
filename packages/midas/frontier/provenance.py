"""Exact links between normalized records and the raw responses they describe."""

from __future__ import annotations

from typing import Any

from midas.frontier.models import MarketBatch, Provenance, RawObservation, TradeBatch


def capture_matches_provenance(raw: RawObservation, provenance: Provenance) -> bool:
    """Require all response identity and timing fields to match the raw capture."""
    return (
        provenance.raw_sha256 == raw.raw_sha256
        and provenance.source_url == raw.request_url
        and provenance.adapter_version == raw.adapter_version
        and provenance.request_started_at_utc == raw.request_started_at_utc
        and provenance.response_received_at_utc == raw.received_at_utc
        and provenance.request_elapsed_monotonic_ns == raw.request_elapsed_monotonic_ns
    )


def normalized_capture_matches(raw: RawObservation, normalized: Any) -> bool:
    """Check each provenance-bearing record nested in one normalized observation.

    Discovery batches and trade batches carry provenance on their members. Empty
    batches and source-failure diagnostics carry no normalized source record and
    are valid capture companions.
    """
    if isinstance(normalized, MarketBatch):
        records = (*normalized.markets, *normalized.market_groups)
    elif isinstance(normalized, TradeBatch):
        records = normalized.trades
    else:
        records = (normalized,)

    provenances = tuple(
        provenance
        for record in records
        if isinstance((provenance := getattr(record, "provenance", None)), Provenance)
    )
    return all(capture_matches_provenance(raw, provenance) for provenance in provenances)
