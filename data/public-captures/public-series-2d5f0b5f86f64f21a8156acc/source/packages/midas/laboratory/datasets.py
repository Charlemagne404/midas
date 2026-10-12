"""Content-addressed recording manifests; receipt time controls observation access."""

import hashlib
from pathlib import Path
from typing import Any

from pydantic import Field

from midas.core.models import Market, MarketEvent, Model, Source
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario, ScenarioEvent
from midas.paper.broker import AccountConfig


class Manifest(Model):
    schema_version: int = 1
    dataset_id: str
    dataset_version: str = "1"
    data_source: str
    provenance: str = "RECORDED"
    content_sha256: str
    event_count: int = Field(ge=1)
    capture_start_ms: int = Field(ge=0)
    capture_end_ms: int = Field(ge=0)
    instrument_ids: tuple[str, ...]
    protocols: tuple[str, ...]
    exchange_timestamp_coverage: float = Field(ge=0, le=1)
    missing_intervals: tuple[tuple[int, int], ...] = ()
    feed_interruptions: tuple[str, ...] = ()
    completeness_limitations: tuple[str, ...]
    market_metadata: tuple[Market, ...]
    economic_assumptions: tuple[str, ...]


def read_events(path: Path) -> list[MarketEvent]:
    events = []
    for index, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            raise ValueError(f"Empty recording line {index}")
        try:
            events.append(MarketEvent.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"Invalid recording line {index}; quarantine dataset") from error
    if not events:
        raise ValueError("Empty dataset")
    return events


def create_manifest(
    path: Path,
    dataset_id: str,
    data_source: str,
    markets: tuple[Market, ...],
    limitations: tuple[str, ...],
) -> Manifest:
    events = read_events(path)
    book_events = [e for e in events if e.book]
    return Manifest(
        dataset_id=dataset_id,
        data_source=data_source,
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        event_count=len(events),
        capture_start_ms=min(e.received_ts_ms for e in events),
        capture_end_ms=max(e.received_ts_ms for e in events),
        instrument_ids=tuple(sorted({i.asset_id for m in markets for i in m.instruments})),
        protocols=tuple(sorted({m.protocol for m in markets})),
        exchange_timestamp_coverage=sum(e.exchange_ts_ms is not None for e in book_events)
        / len(book_events)
        if book_events
        else 0,
        completeness_limitations=limitations,
        market_metadata=markets,
        economic_assumptions=(
            "Hypothetical fills cannot be established from observed depth",
            "Collateral adapter identity/parity and operational costs remain assumptions",
        ),
    )


def validate(path: Path, manifest: Manifest) -> dict[str, Any]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest.content_sha256:
        raise ValueError("Dataset content hash mismatch; quarantine dataset")
    events = read_events(path)
    if len(events) != manifest.event_count:
        raise ValueError("Dataset event count mismatch")
    times = [e.received_ts_ms for e in events]
    if (min(times), max(times)) != (manifest.capture_start_ms, manifest.capture_end_ms):
        raise ValueError("Dataset timestamp coverage mismatch")
    instruments = {i.asset_id for m in manifest.market_metadata for i in m.instruments}
    if set(manifest.instrument_ids) != instruments or set(manifest.protocols) != {
        m.protocol for m in manifest.market_metadata
    }:
        raise ValueError("Dataset manifest metadata mismatch")
    ids: dict[str, str] = {}
    duplicates = late = 0
    latest: dict[str, int] = {}
    book_count = timestamp_count = 0
    for e in events:
        if e.received_ts_ms < 0 or (e.exchange_ts_ms is not None and e.exchange_ts_ms < 0):
            raise ValueError("Dataset negative timestamp")
        fingerprint = digest(e.model_dump(mode="json"))
        if e.event_id in ids:
            if ids[e.event_id] != fingerprint:
                raise ValueError("Conflicting duplicate dataset event")
            duplicates += 1
            continue
        ids[e.event_id] = fingerprint
        if e.source != Source.LIVE or (e.book and e.book.source != Source.LIVE):
            raise ValueError("Historical public dataset contains non-live provenance")
        if e.book:
            b = e.book
            book_count += 1
            timestamp_count += e.exchange_ts_ms is not None
            if b.asset_id not in instruments or e.asset_id != b.asset_id:
                raise ValueError("Unknown or conflicting dataset instrument")
            if b.received_ts_ms != e.received_ts_ms or b.exchange_ts_ms != e.exchange_ts_ms:
                raise ValueError("Event/book clocks disagree")
            market = next(
                m
                for m in manifest.market_metadata
                if b.asset_id in {i.asset_id for i in m.instruments}
            )
            if b.condition_id != market.condition_id:
                raise ValueError("Dataset condition identity mismatch")
            if e.exchange_ts_ms is not None:
                late += e.exchange_ts_ms < latest.get(b.asset_id, -1)
                latest[b.asset_id] = max(e.exchange_ts_ms, latest.get(b.asset_id, -1))
    coverage = timestamp_count / book_count if book_count else 0
    if abs(coverage - manifest.exchange_timestamp_coverage) > 1e-12:
        raise ValueError("Exchange timestamp coverage mismatch")
    return {
        "valid": True,
        "event_count": len(events),
        "duplicates": duplicates,
        "late_exchange_snapshots": late,
        "receipt_out_of_order": times != sorted(times),
        "warnings": list(manifest.completeness_limitations),
        "content_sha256": manifest.content_sha256,
    }


def replay_scenario(
    path: Path,
    manifest: Manifest,
    account: AccountConfig | None = None,
    latency_ms: int = 0,
    start_ms: int | None = None,
    end_ms: int | None = None,
    market_id: str | None = None,
) -> Scenario:
    validation = validate(path, manifest)
    market = next(
        (m for m in manifest.market_metadata if market_id is None or m.id == market_id), None
    )
    if market is None:
        raise ValueError("Dataset market not found")
    # Stable receipt order preserves equal-time capture order; exchange time never grants access.
    events = sorted(
        enumerate(read_events(path)), key=lambda item: (item[1].received_ts_ms, item[0])
    )
    start = start_ms if start_ms is not None else manifest.capture_start_ms
    end = end_ms if end_ms is not None else manifest.capture_end_ms
    if not manifest.capture_start_ms <= start <= end <= manifest.capture_end_ms:
        raise ValueError("Replay window outside dataset coverage")
    assets = {i.asset_id for i in market.instruments}
    snapshots = {
        e.book.asset_id: e.book for _, e in reversed(events) if e.book and e.book.asset_id in assets
    }
    if set(snapshots) != assets:
        raise ValueError("Dataset lacks both instrument snapshots")
    # Initial venue placeholders are invalid; strategy receives nothing before receipt events.
    initial_books = {
        a: b.model_copy(
            update={
                "asks": (),
                "bids": (),
                "valid": False,
                "received_ts_ms": manifest.capture_start_ms,
                "exchange_ts_ms": None,
            }
        )
        for a, b in snapshots.items()
    }
    selected = []
    seen = set()
    for _, e in events:
        if not start <= e.received_ts_ms <= end or e.event_id in seen:
            continue
        seen.add(e.event_id)
        offset = e.received_ts_ms - manifest.capture_start_ms
        if e.book and e.book.asset_id in assets:
            selected.append(
                ScenarioEvent(
                    id=e.event_id,
                    time_ms=offset,
                    kind="market",
                    payload={"books": {e.book.asset_id: e.book.model_dump(mode="json")}},
                )
            )
        elif e.asset_id in assets:
            selected.append(
                ScenarioEvent(
                    id=e.event_id,
                    time_ms=offset,
                    kind="market",
                    payload={
                        "books": {e.asset_id: initial_books[e.asset_id].model_dump(mode="json")}
                    },
                )
            )
        elif e.kind == "price_change":
            invalid = {
                a: initial_books[a]
                .model_copy(
                    update={"received_ts_ms": e.received_ts_ms, "exchange_ts_ms": e.exchange_ts_ms}
                )
                .model_dump(mode="json")
                for a in {d.get("asset_id") for d in e.raw.get("price_changes", [])}
                if a in assets
            }
            if invalid:
                selected.append(
                    ScenarioEvent(
                        id=e.event_id, time_ms=offset, kind="market", payload={"books": invalid}
                    )
                )
        elif e.kind == "attested_metadata" and e.raw["market"]["id"] == market.id:
            selected.append(
                ScenarioEvent(
                    id=e.event_id,
                    time_ms=offset,
                    kind="market",
                    payload={"market": e.raw["market"]},
                )
            )
    return Scenario(
        id=f"replay:{manifest.dataset_id}:{market.id}",
        family="historical",
        provenance="RECORDED",
        seed=(account or AccountConfig()).execution.seed,
        market=market.model_copy(update={"active": False}),
        books=initial_books,
        account=(account or AccountConfig()).model_copy(update={"mode": "historical"}),
        events=tuple(selected),
        observation_latency_ms=latency_ms,
        epoch_ms=manifest.capture_start_ms,
        horizon_ms=end - manifest.capture_start_ms + latency_ms,
        dataset_id=manifest.dataset_id,
        dataset_hash=manifest.content_sha256,
        warnings=tuple(validation["warnings"]),
    )


def load_dataset(root: Path, id: str) -> tuple[Path, Manifest]:
    # Callers choose IDs from a catalog, never arbitrary filesystem paths.
    if not id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid dataset identifier")
    manifest = Manifest.model_validate_json((root / f"{id}.manifest.json").read_text())
    if manifest.dataset_id != id:
        raise ValueError("Dataset identifier mismatch")
    return root / f"{id}.jsonl", manifest
