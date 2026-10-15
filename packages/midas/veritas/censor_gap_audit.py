"""Read-only verification of gap-censored outcomes against finalized source records."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import struct
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from midas.reality.research_schema import digest
from midas.reality.storage import MAGIC, MAX_RECORD, file_hash

VERSION = "veritas-censor-gap-reference-audit-v1"
MAX_OUTCOMES = 50_000
MAX_CAMPAIGN_BYTES = 2_000_000
MAX_CATALOG_BYTES = 128 * 1024
MAX_OUTCOME_EVENT_BYTES = 64 * 1024**2
MAX_SOURCE_BYTES = 512 * 1024**2
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SEGMENT = re.compile(r"(?P<first>[0-9]{20})-(?P<uuid>[0-9a-f]{32})\.seg\Z")


def _campaign(campaign_root: Path) -> tuple[dict[str, Any], Path, Path, str]:
    if campaign_root.is_symlink() or not campaign_root.is_dir():
        raise ValueError("Campaign root is missing or unsafe")
    plan_path = campaign_root / "campaign.json"
    journal_path = campaign_root / "shadow.sqlite"
    if (
        plan_path.is_symlink()
        or not plan_path.is_file()
        or plan_path.stat().st_size > MAX_CAMPAIGN_BYTES
    ):
        raise ValueError("Campaign plan is missing, unsafe, or too large")
    if journal_path.is_symlink() or not journal_path.is_file():
        raise ValueError("Campaign journal is missing or unsafe")
    plan_bytes = plan_path.read_bytes()
    try:
        plan = json.loads(plan_bytes)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("Campaign plan is malformed") from error
    if not isinstance(plan, dict):
        raise ValueError("Campaign plan must be an object")
    identity = plan.get("identity")
    campaign_id = plan.get("campaign_id")
    if not isinstance(identity, dict) or not isinstance(campaign_id, str):
        raise ValueError("Campaign identity is missing")
    if digest(identity) != campaign_id:
        raise ValueError("Campaign identity hash mismatch")
    raw_value = identity.get("raw_root")
    start_ns = identity.get("start_ns")
    end_ns = identity.get("end_ns")
    if (
        not isinstance(raw_value, str)
        or not isinstance(start_ns, int)
        or isinstance(start_ns, bool)
        or not isinstance(end_ns, int)
        or isinstance(end_ns, bool)
        or start_ns >= end_ns
    ):
        raise ValueError("Campaign source root or window is invalid")
    raw_root = Path(raw_value)
    if raw_root.is_symlink() or not raw_root.is_dir():
        raise ValueError("Campaign source root is missing or unsafe")
    return plan, journal_path, raw_root, hashlib.sha256(plan_bytes).hexdigest()


def _decode_followup(body: bytes) -> dict[str, Any]:
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(body, MAX_RECORD + 1)
        if len(raw) > MAX_RECORD or not decoder.eof or decoder.unused_data:
            raise ValueError("Follow-up event compression is invalid")
        event = json.loads(raw)
    except (UnicodeDecodeError, ValueError, zlib.error) as error:
        raise ValueError("Follow-up event is malformed") from error
    if not isinstance(event, dict):
        raise ValueError("Follow-up event must contain an object")
    return event


def _validated_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Gap-censored outcome has no source termination reference")
    reference: dict[str, Any] = {
        key: value.get(key)
        for key in (
            "segment",
            "offset",
            "end_offset",
            "ordinal",
            "received_ns",
            "compressed_record_sha256",
            "canonical_record_sha256",
        )
    }
    segment = reference["segment"]
    if not isinstance(segment, str) or _SEGMENT.fullmatch(segment) is None:
        raise ValueError("Gap-censored outcome references an unsafe or unfinalized segment")
    for key in ("offset", "end_offset", "ordinal", "received_ns"):
        number = reference[key]
        if not isinstance(number, int) or isinstance(number, bool):
            raise ValueError("Gap-censored outcome source reference has an invalid integer")
    offset = cast(int, reference["offset"])
    end_offset = cast(int, reference["end_offset"])
    ordinal = cast(int, reference["ordinal"])
    if offset < len(MAGIC) or end_offset <= offset or ordinal < 1:
        raise ValueError("Gap-censored outcome source reference has an invalid range")
    for key in ("compressed_record_sha256", "canonical_record_sha256"):
        value = reference[key]
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise ValueError("Gap-censored outcome source reference has an invalid digest")
    return reference


def _read_catalog(segment_path: Path) -> dict[str, Any]:
    catalog_path = segment_path.with_suffix(".json")
    if catalog_path.is_symlink() or not catalog_path.is_file():
        raise ValueError("Referenced source segment has no finalized catalog")
    if catalog_path.stat().st_size > MAX_CATALOG_BYTES:
        raise ValueError("Referenced source catalog exceeds its bound")
    try:
        catalog = json.loads(catalog_path.read_text())
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError("Referenced source catalog is malformed") from error
    if not isinstance(catalog, dict):
        raise ValueError("Referenced source catalog must be an object")
    if (
        set(catalog)
        != {"schema_version", "file", "sha256", "bytes", "first", "last", "count", "kinds"}
        or catalog.get("schema_version") != 1
        or catalog.get("file") != segment_path.name
        or not isinstance(catalog.get("sha256"), str)
        or _SHA256.fullmatch(catalog["sha256"]) is None
        or not isinstance(catalog.get("bytes"), int)
        or isinstance(catalog.get("bytes"), bool)
        or not isinstance(catalog.get("first"), int)
        or isinstance(catalog.get("first"), bool)
        or not isinstance(catalog.get("last"), int)
        or isinstance(catalog.get("last"), bool)
        or not isinstance(catalog.get("count"), int)
        or isinstance(catalog.get("count"), bool)
        or catalog.get("count", 0) < 1
        or not isinstance(catalog.get("kinds"), dict)
    ):
        raise ValueError("Referenced source catalog identity is invalid")
    size = segment_path.stat().st_size
    if catalog["bytes"] != size:
        raise ValueError("Referenced source segment size differs from its catalog")
    if _SEGMENT.fullmatch(segment_path.name) is None:
        raise ValueError("Referenced source segment name is invalid")
    if segment_path.name[:20] != f"{catalog['first']:020d}":
        raise ValueError("Referenced source segment first ordinal differs from its catalog")
    if catalog["first"] > catalog["last"]:
        raise ValueError("Referenced source catalog ordinal range is invalid")
    return catalog


def _read_record(segment_path: Path, reference: dict[str, Any]) -> dict[str, Any]:
    if segment_path.is_symlink() or not segment_path.is_file():
        raise ValueError("Referenced finalized source segment is missing or unsafe")
    with segment_path.open("rb") as handle:
        if handle.read(len(MAGIC)) != MAGIC:
            raise ValueError("Referenced source segment header is invalid")
        handle.seek(reference["offset"])
        header = handle.read(36)
        if len(header) != 36:
            raise ValueError("Referenced source record header is truncated")
        length, expected_compressed_sha = struct.unpack(">I32s", header)
        if not 0 < length <= MAX_RECORD:
            raise ValueError("Referenced source record length is invalid")
        compressed = handle.read(length)
        if len(compressed) != length or handle.tell() != reference["end_offset"]:
            raise ValueError("Referenced source record end offset is invalid")
        if hashlib.sha256(compressed).digest() != expected_compressed_sha:
            raise ValueError("Referenced source record frame checksum mismatch")
        if hashlib.sha256(compressed).hexdigest() != reference["compressed_record_sha256"]:
            raise ValueError("Campaign/source compressed record digest mismatch")
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, MAX_RECORD + 1)
            if len(raw) > MAX_RECORD or not decoder.eof or decoder.unused_data:
                raise ValueError("Referenced source record compression is invalid")
            record = json.loads(raw)
        except (UnicodeDecodeError, ValueError, zlib.error) as error:
            raise ValueError("Referenced source record payload is malformed") from error
        if hashlib.sha256(raw).hexdigest() != reference["canonical_record_sha256"]:
            raise ValueError("Campaign/source canonical record digest mismatch")
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != 1
        or record.get("ordinal") != reference["ordinal"]
        or record.get("received_ns") != reference["received_ns"]
        or not isinstance(record.get("kind"), str)
    ):
        raise ValueError("Campaign/source record identity mismatch")
    return record


def audit_censored_gap_records(
    campaign_root: Path,
    *,
    limit: int = MAX_OUTCOMES,
    max_source_bytes: int = 128 * 1024**2,
) -> dict[str, Any]:
    """Verify gap-related censor references using bounded read-only source access."""
    if not 1 <= limit <= MAX_OUTCOMES:
        raise ValueError("Censored outcome query exceeds its explicit bound")
    if (
        not isinstance(max_source_bytes, int)
        or isinstance(max_source_bytes, bool)
        or not 1 <= max_source_bytes <= MAX_SOURCE_BYTES
    ):
        raise ValueError("Source segment byte bound is invalid")
    plan, journal_path, raw_root, plan_sha256 = _campaign(campaign_root)
    campaign_id = plan["campaign_id"]
    db = sqlite3.connect(journal_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    db.execute("pragma query_only=on")
    references: dict[int, dict[str, Any]] = {}
    by_reason: Counter[str] = Counter()
    by_horizon: dict[str, Counter[str]] = {}
    scanned = event_bytes = 0
    try:
        db.execute("begin")
        tail = db.execute("select seq,sha from events order by seq desc limit 1").fetchone()
        rows = db.execute(
            "select o.decision_id,o.horizon,o.status,e.kind,e.body "
            "from outcomes o join events e on e.seq=o.event_seq "
            "where o.status='censored' order by e.seq limit ?",
            (limit + 1,),
        )
        while batch := rows.fetchmany(256):
            for decision_id, horizon, status, kind, body in batch:
                if scanned >= limit:
                    raise ValueError("Censored outcome query was truncated")
                scanned += 1
                event_bytes += len(body)
                if event_bytes > MAX_OUTCOME_EVENT_BYTES:
                    raise ValueError("Censored outcome event bytes exceed their explicit bound")
                if kind != "followup":
                    raise ValueError("Outcome index points to a non-follow-up event")
                event = _decode_followup(body)
                if (
                    event.get("campaign_id") != campaign_id
                    or event.get("decision_id") != decision_id
                    or event.get("horizon_ms") != horizon
                ):
                    raise ValueError("Follow-up event differs from its indexed identity")
                labels = event.get("labels")
                if not isinstance(labels, dict) or labels.get("status") != status:
                    raise ValueError("Follow-up event status differs from its outcome index")
                reason = labels.get("reason")
                if not isinstance(reason, str) or not reason.startswith(
                    ("recorded_gap:", "book_issue:gap:")
                ):
                    continue
                suffix = reason.partition("gap:")[2]
                if not suffix:
                    raise ValueError("Gap censor reason is empty")
                reference = _validated_reference(event.get("termination_ref"))
                ordinal = reference["ordinal"]
                prior = references.get(ordinal)
                if prior is not None and prior["reference"] != reference:
                    raise ValueError("One source ordinal has inconsistent campaign references")
                bucket = references.setdefault(ordinal, {"reference": reference, "labels": set()})
                bucket["labels"].add(reason)
                by_reason[reason] += 1
                by_horizon.setdefault(str(horizon), Counter())[reason] += 1
    finally:
        db.rollback()
        db.close()

    segments = {entry["reference"]["segment"] for entry in references.values()}
    segment_bytes = 0
    segment_hashes: dict[str, str] = {}
    for name in sorted(segments):
        path = raw_root / name
        if path.parent != raw_root or path.is_symlink() or not path.is_file():
            raise ValueError("Referenced finalized source segment is missing or unsafe")
        catalog = _read_catalog(path)
        segment_bytes += int(catalog["bytes"])
        if segment_bytes > max_source_bytes:
            raise ValueError("Referenced source segments exceed the explicit byte bound")
        actual_sha = file_hash(path)
        if actual_sha != catalog["sha256"]:
            raise ValueError("Referenced finalized source segment digest mismatch")
        for entry in references.values():
            reference = entry["reference"]
            if (
                reference["segment"] == name
                and not catalog["first"] <= reference["ordinal"] <= catalog["last"]
            ):
                raise ValueError("Referenced source ordinal is outside its finalized catalog range")
        segment_hashes[name] = actual_sha

    kinds: Counter[str] = Counter()
    direct_gap_records: Counter[str] = Counter()
    indirect_issue_kinds: Counter[str] = Counter()
    explicit_gap_ordinals: set[int] = set()
    record_bytes = 0
    for ordinal, entry in references.items():
        reference = entry["reference"]
        record = _read_record(raw_root / reference["segment"], reference)
        kinds[record["kind"]] += 1
        record_bytes += reference["end_offset"] - reference["offset"]
        for reason in entry["labels"]:
            if reason.startswith("recorded_gap:"):
                expected_reason = reason.removeprefix("recorded_gap:")
                payload = record.get("payload")
                if record["kind"] != "gap" or not isinstance(payload, dict):
                    raise ValueError("Explicit recorded-gap censor does not reference a gap record")
                if payload.get("reason") != expected_reason:
                    raise ValueError("Explicit gap censor reason differs from its source record")
                direct_gap_records[expected_reason] += 1
                explicit_gap_ordinals.add(ordinal)
        if any(reason.startswith("book_issue:gap:") for reason in entry["labels"]):
            indirect_issue_kinds[record["kind"]] += 1

    return {
        "schema_version": 1,
        "analysis_version": VERSION,
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "verified",
        "campaign": {
            "campaign_id": campaign_id,
            "campaign_plan_sha256": plan_sha256,
        },
        "query": {
            "censored_outcome_limit": limit,
            "censored_outcomes_scanned": scanned,
            "censored_outcome_event_bytes_read": event_bytes,
            "event_byte_limit": MAX_OUTCOME_EVENT_BYTES,
            "truncated": False,
        },
        "journal_snapshot": {
            "read_only": True,
            "tail_event_seq": tail[0] if tail else None,
            "tail_event_sha256": tail[1] if tail else None,
            "hash_chain_reverified": False,
            "sqlite_integrity_check_performed": False,
        },
        "gap_censors": {
            "outcome_rows": sum(by_reason.values()),
            "outcome_rows_by_reason": dict(sorted(by_reason.items())),
            "outcome_rows_by_horizon_ms": {
                horizon: dict(sorted(reasons.items()))
                for horizon, reasons in sorted(by_horizon.items(), key=lambda item: int(item[0]))
            },
            "unique_termination_records": len(references),
            "unique_termination_record_kinds": dict(sorted(kinds.items())),
            "explicit_recorded_gap_outcomes": sum(
                count for reason, count in by_reason.items() if reason.startswith("recorded_gap:")
            ),
            "unique_explicit_gap_records_verified": len(explicit_gap_ordinals),
            "unique_explicit_gap_records_by_reason": dict(sorted(direct_gap_records.items())),
            "book_issue_gap_outcomes": sum(
                count for reason, count in by_reason.items() if reason.startswith("book_issue:gap:")
            ),
            "unique_book_issue_termination_records_by_source_kind": dict(
                sorted(indirect_issue_kinds.items())
            ),
            "book_issue_direct_gap_causality_verified": False,
        },
        "source_verification": {
            "active_open_segments_read": False,
            "finalized_segment_byte_limit": max_source_bytes,
            "unique_finalized_segments_verified": len(segment_hashes),
            "finalized_segment_bytes_hashed": segment_bytes,
            "unique_source_records_verified": sum(kinds.values()),
            "source_record_frame_bytes_read": record_bytes,
            "record_offsets_and_hashes_verified": True,
        },
        "limitations": [
            "The read-only SQLite event hash chain and full database integrity were not reverified.",
            "Explicit recorded_gap labels are matched to their exact finalized gap record.",
            "book_issue:gap references are verified as source records but are not attributed to a specific prior gap.",
            "future_observation_unavailable remains a mixed absence, inactivity, and coverage category.",
            "Source record identity does not establish exchange sequence, fills, or profitability.",
        ],
    }
