"""Chronological public quote windows, deliberately separate from execution labels."""

import json
import time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.core.models import Book, MarketEvent, Model
from midas.economics.attestation import digest
from midas.laboratory.datasets import Manifest, load_dataset, read_events, validate


class ObservationSpec(Model):
    version: Literal["public-poll-windows-1"] = "public-poll-windows-1"
    source_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    train_percent: int = Field(default=70, ge=1, le=98)
    validation_percent: int = Field(default=15, ge=1, le=98)
    embargo_ms: int = Field(default=10000, ge=0, le=3600000)
    max_pair_skew_ms: int = Field(default=1000, ge=0, le=60000)
    max_book_age_ms: int = Field(default=10000, ge=0, le=3600000)

    @model_validator(mode="after")
    def partitions(self) -> "ObservationSpec":
        if self.train_percent + self.validation_percent >= 100:
            raise ValueError("Leave a nonempty chronological test fraction")
        return self


def numeric(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def windows(
    events: list[MarketEvent], assets: tuple[str, ...], spec: ObservationSpec, progress: Any = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(assets) != 2 or len(set(assets)) != 2:
        raise ValueError("Observation windows require exactly two declared instruments")
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("Duplicate source events cannot form unique observation windows")
    if [e.received_ts_ms for e in events] != sorted(e.received_ts_ms for e in events):
        raise ValueError("Receipt order is not chronological; quarantine source")
    metadata = [e for e in events if e.kind == "public_metadata"]
    if len(metadata) != 1:
        raise ValueError("Require one initial public metadata event")
    groups: dict[int, list[MarketEvent]] = defaultdict(list)
    prefix = spec.source_id + ":poll:"
    for event in events:
        if event.kind not in {"public_metadata", "book"}:
            raise ValueError("Poll windows require metadata and book observations only")
        if event.book is None:
            continue
        if not event.event_id.startswith(prefix):
            raise ValueError("Require bounded REST poll-pair event identities")
        number, separator, asset = event.event_id[len(prefix) :].partition(":")
        if not separator or not number.isdecimal() or asset != event.asset_id:
            raise ValueError("Invalid poll or instrument identity")
        groups[int(number)].append(event)
    if list(groups) != sorted(groups):
        raise ValueError("Poll identities are out of chronological order")
    rows: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for processed, (poll_index, snapshots) in enumerate(sorted(groups.items())):
        if progress:
            progress(processed, len(groups))
        reasons = []
        if len(snapshots) != 2 or {e.asset_id for e in snapshots} != set(assets):
            rejected["missing_or_duplicate_instrument"] += 1
            continue
        first, available = (
            min(e.received_ts_ms for e in snapshots),
            max(e.received_ts_ms for e in snapshots),
        )
        if metadata[0].received_ts_ms > first:
            reasons.append("metadata_not_yet_available")
        if available - first > spec.max_pair_skew_ms:
            reasons.append("non_atomic_pair_exceeds_skew_limit")
        books: dict[str, Book] = {}
        for snapshot in snapshots:
            assert snapshot.asset_id is not None and snapshot.book is not None
            books[snapshot.asset_id] = snapshot.book
        ages = []
        for event in snapshots:
            assert event.book is not None
            if not event.book.valid:
                reasons.append("invalid_book")
            if event.exchange_ts_ms is None:
                reasons.append("missing_exchange_timestamp")
            elif event.exchange_ts_ms > event.received_ts_ms:
                reasons.append("future_exchange_timestamp")
            else:
                ages.append(available - event.exchange_ts_ms)
        if ages and max(ages) > spec.max_book_age_ms:
            reasons.append("stale_book_at_pair_availability")
        if reasons:
            rejected.update(set(reasons))
            continue
        ordered = [books[a] for a in sorted(assets)]
        features = {
            "ask_sum": float(sum(b.asks[0].price for b in ordered))
            if all(b.asks for b in ordered)
            else None,
            "bid_sum": float(sum(b.bids[0].price for b in ordered))
            if all(b.bids for b in ordered)
            else None,
            "min_best_ask_depth": float(min(b.asks[0].size for b in ordered))
            if all(b.asks for b in ordered)
            else None,
            "pair_receipt_skew_ms": available - first,
            "max_book_age_ms": max(ages),
        }
        shape = [
            {
                "asset_id": b.asset_id,
                "asks": [{"price": numeric(x.price), "size": numeric(x.size)} for x in b.asks],
                "bids": [{"price": numeric(x.price), "size": numeric(x.size)} for x in b.bids],
                "tick_size": numeric(b.tick_size),
                "min_order_size": numeric(b.min_order_size),
                "minimum_unit": b.minimum_unit,
            }
            for b in ordered
        ]
        rows.append(
            {
                "base_episode_id": f"{spec.source_id}:poll:{poll_index}",
                "poll": poll_index,
                "event_ids": [e.event_id for e in snapshots],
                "metadata_event_id": metadata[0].event_id,
                "first_received_ms": first,
                "available_at_ms": available,
                "features": features,
                "quote_shape_hash": digest(shape),
            }
        )
    if progress:
        progress(len(groups), len(groups))
    if len(rows) < 6:
        raise ValueError("Need at least six valid paired polls for chronological partitions")
    n_train = len(rows) * spec.train_percent // 100
    n_validation = len(rows) * spec.validation_percent // 100
    if min(n_train, n_validation, len(rows) - n_train - n_validation) < 1:
        raise ValueError("Insufficient windows for requested fractions")
    train_end = rows[n_train - 1]["available_at_ms"]
    validation_end = rows[n_train + n_validation - 1]["available_at_ms"]
    for index, row in enumerate(rows):
        partition = (
            "train"
            if index < n_train
            else "validation"
            if index < n_train + n_validation
            else "test"
        )
        prior_end = train_end if partition == "validation" else validation_end
        if partition != "train" and row["first_received_ms"] <= prior_end + spec.embargo_ms:
            partition = "embargo"
        row["partition"] = partition
    counts = Counter(r["partition"] for r in rows)
    if any(not counts[p] for p in ("train", "validation", "test")):
        raise ValueError(
            "Recording too short for partition embargo; collect longer data or declare a smaller embargo"
        )
    hashes = defaultdict(set)
    for row in rows:
        if row["partition"] != "embargo":
            hashes[row["quote_shape_hash"]].add(row["partition"])
    missing = Counter(k for r in rows for k, value in r["features"].items() if value is None)
    return rows, {
        "source_polls": len(groups),
        "missing_poll_numbers": max(groups) + 1 - len(groups),
        "valid_paired_polls": len(rows),
        "quarantine_reasons": dict(rejected),
        "partition_windows": dict(counts),
        "unique_quote_shapes": len({r["quote_shape_hash"] for r in rows}),
        "cross_partition_repeated_quote_shapes": sum(len(v) > 1 for v in hashes.values()),
        "missing_feature_values": dict(missing),
        "partition_bounds": {
            p: {
                "first_received_ms": min(
                    r["first_received_ms"] for r in rows if r["partition"] == p
                ),
                "last_available_ms": max(r["available_at_ms"] for r in rows if r["partition"] == p),
            }
            for p in ("train", "validation", "test")
        },
    }


def load(root: Path, identity: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    directory = artifact_path(root, "observations", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if (
        record["eligible_for_execution_training"] is not False
        or record["label_definition"] is not None
    ):
        raise ValueError("Observation windows cannot assert execution labels")
    if sha256(directory / "rows.json") != record["rows_sha256"]:
        raise ValueError("Frozen observation rows changed")
    if sha256(directory / "source-manifest.json") != record["source_manifest_sha256"]:
        raise ValueError("Frozen observation source metadata changed")
    source = directory / "source.jsonl"
    if source.stat().st_size > 16 * 1024**2 or sha256(source) != record["source_content_sha256"]:
        raise ValueError("Frozen observation source changed")
    manifest = Manifest.model_validate_json((directory / "source-manifest.json").read_text())
    validate(source, manifest)
    return record, json.loads((directory / "rows.json").read_text())


def build(root: Path, spec: ObservationSpec, progress: Any = None) -> dict[str, Any]:
    source, manifest = load_dataset(root.parent / "datasets", spec.source_id)
    if source.stat().st_size > 16 * 1024**2 or manifest.event_count > 20000:
        raise ValueError("Observation input exceeds bounded ingestion limits")
    evidence = validate(source, manifest)
    if not evidence["valid"]:
        raise ValueError("Source recording did not validate")
    source_hash = research_hash()
    identity = (
        "observations-"
        + digest([spec.model_dump(mode="json"), manifest.content_sha256, source_hash])[:24]
    )
    directory = artifact_path(root, "observations", identity)
    if (directory / "manifest.json").exists():
        return load(root, identity)[0]
    if progress:
        progress.register("observations", identity)
    rows, quality = windows(read_events(source), manifest.instrument_ids, spec, progress)
    atomic_bytes(directory / "source.jsonl", source.read_bytes())
    atomic_bytes(
        directory / "source-manifest.json",
        (root.parent / "datasets" / (spec.source_id + ".manifest.json")).read_bytes(),
    )
    atomic_json(directory / "rows.json", rows)
    record = {
        "observation_id": identity,
        "state": "COMPLETED",
        "created_at": time.time(),
        "configuration": spec.model_dump(mode="json"),
        "source_hash": source_hash,
        "source_dataset_id": spec.source_id,
        "source_content_sha256": manifest.content_sha256,
        "source_manifest_sha256": sha256(directory / "source-manifest.json"),
        "rows_sha256": sha256(directory / "rows.json"),
        "provenance": "RECORDED_PUBLIC",
        "feature_version": "public-quote-summary-1",
        "feature_schema": list(rows[0]["features"]),
        "feature_units": {
            "ask_sum": "Sum of sequential observed best ask quotes; collateral route unverified",
            "bid_sum": "Sum of sequential observed best bid quotes; collateral route unverified",
            "min_best_ask_depth": "Observed shares at the smaller best ask; not fillable quantity",
            "pair_receipt_skew_ms": "Milliseconds between the two snapshot receipts",
            "max_book_age_ms": "Maximum exchange timestamp age when both snapshots are available",
        },
        "label_definition": None,
        "eligible_for_execution_training": False,
        "quality": quality,
        "source_validation": evidence,
        "limitations": [
            *manifest.completeness_limitations,
            "Windows become available only after both sequential snapshots arrive.",
            "Chronological partitions with embargo are observational research partitions; no empirical execution labels.",
            "Repeated quote shapes across partitions are reported, not independent market samples.",
            "Quote sums and depth are observations, not verified economic profit or fill probability.",
        ],
    }
    atomic_json(directory / "manifest.json", record)
    return record
