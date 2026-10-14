"""Reproduce forward decisions from immutable, finalized Reality source segments."""

from __future__ import annotations

import json
import sqlite3
import time
import zlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from midas.reality.foundry import source_records
from midas.reality.research_measurements import features, pair_quality
from midas.reality.research_schema import digest
from midas.reality.shadow_campaign import verify as verify_campaign
from midas.reality.shadow_source import Context
from midas.reality.shadow_worker import spec_for
from midas.reality.storage import manifest

MAX_DECISIONS = 50_000
MAX_DECISION_EVENT_BYTES = 8 * 1024 * 1024
MAX_DECISION_SAMPLE_COMPRESSED_BYTES = 128 * 1024**2
MAX_DECISION_SAMPLE_DECOMPRESSED_BYTES = 512 * 1024**2
MAX_SOURCE_BYTES = 20 * 1024**3
MAX_LINEAGE_REFERENCES = 1_000_000
_REF_FIELDS = (
    "segment",
    "ordinal",
    "offset",
    "end_offset",
    "compressed_record_sha256",
    "canonical_record_sha256",
    "received_ns",
    "monotonic_ns",
)


def _decode_event(body: bytes) -> tuple[dict[str, Any], int]:
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(body, MAX_DECISION_EVENT_BYTES + 1)
        if len(raw) > MAX_DECISION_EVENT_BYTES or not decoder.eof or decoder.unused_data:
            raise ValueError("Campaign decision event exceeds its size bound")
        value = json.loads(raw)
    except (ValueError, zlib.error, UnicodeDecodeError) as error:
        raise ValueError("Malformed compressed campaign decision event") from error
    if not isinstance(value, dict):
        raise ValueError("Campaign decision event must contain an object")
    return value, len(raw)


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        if all(key in value for key in _REF_FIELDS[:6]):
            return {key: value.get(key) for key in _REF_FIELDS}
        return {key: _stable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _reference_key(value: Any) -> tuple[Any, ...] | None:
    if not isinstance(value, dict) or not all(key in value for key in _REF_FIELDS):
        return None
    segment = value.get("segment")
    ordinal, offset, end_offset = (value.get(key) for key in ("ordinal", "offset", "end_offset"))
    compressed_hash = value.get("compressed_record_sha256")
    canonical_hash = value.get("canonical_record_sha256")
    received_ns, monotonic_ns = value.get("received_ns"), value.get("monotonic_ns")
    if (
        not isinstance(segment, str)
        or Path(segment).name != segment
        or not segment.endswith(".seg")
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or not isinstance(offset, int)
        or isinstance(offset, bool)
        or not isinstance(end_offset, int)
        or isinstance(end_offset, bool)
        or not isinstance(received_ns, int)
        or isinstance(received_ns, bool)
        or not isinstance(monotonic_ns, int)
        or isinstance(monotonic_ns, bool)
        or ordinal < 1
        or offset < 0
        or end_offset <= offset
        or not isinstance(compressed_hash, str)
        or not isinstance(canonical_hash, str)
        or len(compressed_hash) != 64
        or len(canonical_hash) != 64
        or any(char not in "0123456789abcdef" for char in compressed_hash + canonical_hash)
    ):
        return None
    return (
        segment,
        ordinal,
        offset,
        end_offset,
        compressed_hash,
        canonical_hash,
        received_ns,
        monotonic_ns,
    )


def _references(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if any(
            key in value
            for key in (
                "segment",
                "ordinal",
                "offset",
                "end_offset",
                "compressed_record_sha256",
                "canonical_record_sha256",
            )
        ):
            yield value
        else:
            for child in value.values():
                yield from _references(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _references(child)


def _prune_context_refs(context: Context) -> None:
    """Keep only references needed to reproduce current book lineage."""
    needed = {
        book[key][0] for book in context.engine.books.values() for key in ("snapshot", "last")
    }
    context.refs = {ordinal: ref for ordinal, ref in context.refs.items() if ordinal in needed}


def _load_decisions(root: Path, limit: int) -> tuple[list[dict[str, Any]], int | None, int, bool]:
    journal = root / "shadow.sqlite"
    if not journal.is_file() or journal.is_symlink():
        raise ValueError("Campaign journal is missing or unsafe")
    db = sqlite3.connect(journal.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.execute("pragma query_only=on")
    try:
        db.execute("begin")
        tail = db.execute("select seq from events order by seq desc limit 1").fetchone()
        total_count = db.execute("select count(*) from decisions").fetchone()[0]
        compressed_bytes = db.execute(
            "with selected as ("
            "select event_seq from decisions order by ns desc limit ?"
            ") select coalesce(sum(length(e.body)),0) from selected s "
            "join events e on e.seq=s.event_seq",
            (limit,),
        ).fetchone()[0]
        if compressed_bytes > MAX_DECISION_SAMPLE_COMPRESSED_BYTES:
            raise ValueError("Decision sample exceeds its compressed-byte bound")
        rows = db.execute(
            "with selected as ("
            "select source_ordinal,id,ns,condition,market_id,event_seq "
            "from decisions order by ns desc limit ?"
            ") select s.source_ordinal,s.id,s.ns,s.condition,s.market_id,s.event_seq,e.kind,e.body "
            "from selected s join events e on e.seq=s.event_seq",
            (limit,),
        ).fetchall()
        if len(rows) != min(total_count, limit):
            raise ValueError("Campaign decision indexes point to missing journal events")
        truncated = total_count > limit
    finally:
        db.rollback()
        db.close()

    result = []
    seen: set[str] = set()
    decompressed_bytes = 0
    for ordinal, uid, ns, condition, market_id, _event_seq, event_kind, body in rows:
        if event_kind != "decision":
            raise ValueError("Decision index points to a non-decision event")
        event, event_bytes = _decode_event(body)
        decompressed_bytes += event_bytes
        if decompressed_bytes > MAX_DECISION_SAMPLE_DECOMPRESSED_BYTES:
            raise ValueError("Decision sample exceeds its decompressed-byte bound")
        if (
            event.get("id") != uid
            or event.get("decision_ns") != ns
            or event.get("condition") != condition
            or event.get("market_id") != market_id
            or event.get("decision_ordinal") != ordinal
        ):
            raise ValueError("Decision event disagrees with its journal index")
        if uid in seen:
            raise ValueError("Duplicate decision identity in the indexed sample")
        seen.add(uid)
        result.append(event)
    return result, tail[0] if tail else None, len(rows), truncated


def _compare_decision(
    event: dict[str, Any],
    context: Context,
    spec: Any,
    campaign_id: str,
    identity: dict[str, Any],
    source_ref: dict[str, Any],
    difference_paths: Counter[str],
    history_variance: Counter[str],
) -> Counter[str]:
    mismatches: Counter[str] = Counter()
    ordinal = event["decision_ordinal"]
    condition = event["condition"]
    now = event["decision_ns"]
    market = context.cohort.get(condition)
    if event.get("campaign_id") != campaign_id or event.get("id") != digest(
        [campaign_id, condition, ordinal]
    ):
        mismatches["campaign_or_decision_identity"] += 1
    if not identity["start_ns"] <= now < identity["end_ns"]:
        mismatches["campaign_time_window"] += 1
    stored_ref = event.get("source_record_ref")
    if not isinstance(stored_ref, dict) or _stable(stored_ref) != _stable(source_ref):
        mismatches["source_reference"] += 1
    if event.get("producer_implementation_sha256") != context.producer_hash:
        mismatches["producer_identity"] += 1
    if event.get("reconstruction_version") != context.engine.reconstruction_version:
        mismatches["reconstruction_version"] += 1
    if event.get("source_state_sha256") != context.engine.digest():
        mismatches["source_state_sha256"] += 1

    if market is None:
        mismatches["market_cohort"] += 1
        return mismatches
    reason = pair_quality(market, context.engine.books, now, spec)
    if reason is None and any(token in context.bad for token in market["tokens"]):
        reason = "independent_book_divergence"
    if event.get("quality_reason") != reason:
        mismatches["quality_reason"] += 1

    actual_features = actual_baseline = None
    if reason is None:
        actual_features, actual_baseline = features(
            market,
            context.engine.books,
            decision_ns=now,
            spec=spec,
            history={token: list(rows) for token, rows in context.history.items()},
            trades=context.trades,
        )
    stored_features = event.get("features")
    if digest(_stable(stored_features)) != digest(_stable(actual_features)):
        mismatches["features"] += 1
        stored = stored_features if isinstance(stored_features, dict) else {}
        actual = actual_features if isinstance(actual_features, dict) else {}
        for key in set(stored) | set(actual):
            if key != "legs":
                if digest(_stable(stored.get(key))) != digest(_stable(actual.get(key))):
                    difference_paths[f"features.{key}"] += 1
                continue
            stored_legs = stored.get("legs", {})
            actual_legs = actual.get("legs", {})
            if not isinstance(stored_legs, dict) or not isinstance(actual_legs, dict):
                difference_paths["features.legs"] += 1
                continue
            for side in set(stored_legs) | set(actual_legs):
                left, right = stored_legs.get(side), actual_legs.get(side)
                if not isinstance(left, dict) or not isinstance(right, dict):
                    difference_paths[f"features.legs.{side}"] += 1
                    continue
                for field in set(left) | set(right):
                    if digest(_stable(left.get(field))) != digest(_stable(right.get(field))):
                        path = f"features.legs.{side}.{field}"
                        difference_paths[path] += 1
                        if field == "recent_public_trade":
                            stored_trade, actual_trade = left.get(field), right.get(field)
                            if stored_trade is None or actual_trade is None:
                                shape = (
                                    "stored_null_actual_object"
                                    if stored_trade is None
                                    else "stored_object_actual_null"
                                )
                                difference_paths[f"{path}.{shape}"] += 1
                            elif isinstance(stored_trade, dict) and isinstance(actual_trade, dict):
                                for trade_field in set(stored_trade) | set(actual_trade):
                                    if digest(_stable(stored_trade.get(trade_field))) != digest(
                                        _stable(actual_trade.get(trade_field))
                                    ):
                                        difference_paths[f"{path}.{trade_field}"] += 1
    if digest(event.get("baseline")) != digest(actual_baseline):
        mismatches["baseline"] += 1
    stored_sources = event.get("feature_sources")
    actual_sources = context.lineage(market)
    stored_core = (
        {key: value for key, value in stored_sources.items() if key != "history"}
        if isinstance(stored_sources, dict)
        else {}
    )
    actual_core = {key: value for key, value in actual_sources.items() if key != "history"}
    if _stable(stored_core) != _stable(actual_core):
        mismatches["feature_sources"] += 1
        for component in set(stored_core) | set(actual_core):
            if _stable(stored_core.get(component)) != _stable(actual_core.get(component)):
                difference_paths[f"feature_sources.{component}"] += 1
    elif isinstance(stored_sources, dict) and _stable(stored_sources.get("history")) != _stable(
        actual_sources.get("history")
    ):
        history_variance["runtime_history_reference_window_variance_decisions"] += 1
    return mismatches


def reconcile_forward_sources(
    campaign_root: Path,
    *,
    limit: int = 5000,
    max_source_bytes: int = MAX_SOURCE_BYTES,
) -> dict[str, Any]:
    """Compare a bounded SQL decision sample with an immutable finalized source prefix.

    The function reads only cataloged `.seg` files. It never opens `.open` files,
    and the SQLite query runs in a short read-only transaction before source replay.
    Decisions whose raw ordinal is beyond the captured finalized prefix are reported
    as uncovered, since their active segment is intentionally excluded.
    """
    if not 1 <= limit <= MAX_DECISIONS:
        raise ValueError("Decision sample must be bounded to 1..50,000 rows")
    if not 1 <= max_source_bytes <= MAX_SOURCE_BYTES:
        raise ValueError("Finalized source byte bound must be in 1..20 GiB")
    campaign_root = campaign_root.resolve()
    plan_path = campaign_root / "campaign.json"
    if not plan_path.is_file() or plan_path.is_symlink() or plan_path.stat().st_size > 2_000_000:
        raise ValueError("Frozen campaign plan is missing, unsafe, or too large")
    plan = json.loads(plan_path.read_text())
    identity = plan.get("identity")
    campaign_id = plan.get("campaign_id")
    if not isinstance(identity, dict) or not isinstance(campaign_id, str):
        raise ValueError("Invalid frozen campaign identity")
    verify_campaign(plan)
    if identity.get("raw_root") is None:
        raise ValueError("Campaign raw source root is missing")

    decisions, db_tail, decision_count, truncated = _load_decisions(campaign_root, limit)
    targets: dict[int, list[dict[str, Any]]] = {}
    for item in decisions:
        targets.setdefault(item["decision_ordinal"], []).append(item)

    raw_root = Path(identity["raw_root"]).resolve()
    source_manifest = manifest(raw_root)
    segment_infos = source_manifest["segments"]
    if any(
        not isinstance(info.get("file"), str) or not info["file"].endswith(".seg")
        for info in segment_infos
    ):
        raise ValueError("Source manifest contains a non-finalized segment")
    source_bytes = sum(int(info["bytes"]) for info in segment_infos)
    if source_bytes > max_source_bytes:
        raise ValueError("Finalized source snapshot exceeds its byte bound")
    last_ordinal = max((int(info["last"]) for info in segment_infos), default=0)

    context = Context()
    spec = spec_for(plan)
    mismatches: Counter[str] = Counter()
    difference_paths: Counter[str] = Counter()
    history_variance: Counter[str] = Counter()
    expected_refs: set[tuple[Any, ...]] = set()
    for event in decisions:
        if event["decision_ordinal"] > last_ordinal:
            continue
        for ref_value in _references(
            (event.get("source_record_ref"), event.get("feature_sources"))
        ):
            key = _reference_key(ref_value)
            if key is None:
                mismatches["malformed_source_lineage_reference"] += 1
                continue
            if key[1] > event["decision_ordinal"]:
                mismatches["future_ordinal_source_lineage_reference"] += 1
            expected_refs.add(key)
            if len(expected_refs) > MAX_LINEAGE_REFERENCES:
                raise ValueError("Decision sample exceeds the source-lineage reference bound")
    source_records_seen = 0
    target_ids_found: set[str] = set()
    resolved_refs: set[tuple[Any, ...]] = set()
    verified_checkpoints = 0
    for record, ref in source_records(raw_root, source_manifest):
        source_records_seen += 1
        context.consume(record, ref)
        ref_key = _reference_key(ref)
        if ref_key in expected_refs:
            resolved_refs.add(ref_key)
        if record["kind"] == "checkpoint":
            verified_checkpoints += 1
        at_ordinal = targets.get(record["ordinal"], [])
        if at_ordinal:
            target_ids_found.update(target["id"] for target in at_ordinal)
            if record["kind"] != "frame":
                mismatches["source_record_kind"] += len(at_ordinal)
            else:
                for target in at_ordinal:
                    mismatches.update(
                        _compare_decision(
                            target,
                            context,
                            spec,
                            campaign_id,
                            identity,
                            ref,
                            difference_paths,
                            history_variance,
                        )
                    )
        _prune_context_refs(context)

    missing_inside_prefix = [
        item
        for item in decisions
        if item["decision_ordinal"] <= last_ordinal and item["id"] not in target_ids_found
    ]
    uncovered_after_prefix = sum(item["decision_ordinal"] > last_ordinal for item in decisions)
    if missing_inside_prefix:
        mismatches["source_record_missing_inside_finalized_prefix"] += len(missing_inside_prefix)
    unresolved_refs = len(expected_refs - resolved_refs)
    if unresolved_refs:
        mismatches["source_lineage_reference_unresolved"] += unresolved_refs
    compared = len(target_ids_found)
    # Keep only aggregate mismatch categories; no raw market or event payloads are exported.
    return {
        "analysis_version": "veritas-source-replay-v1",
        "captured_ns": time.time_ns(),
        "campaign_id": campaign_id,
        "campaign_root": str(campaign_root),
        "source_root": str(raw_root),
        "source_manifest_sha256": digest(source_manifest),
        "source_segments": len(segment_infos),
        "source_bytes": source_bytes,
        "source_last_finalized_ordinal": last_ordinal,
        "active_segment_read": False,
        "raw_records_replayed": source_records_seen,
        "verified_source_checkpoints": verified_checkpoints,
        "decision_limit": limit,
        "decision_sample_truncated": truncated,
        "decision_sample_rows": decision_count,
        "database_event_tail_sequence": db_tail,
        "decisions_reproduced": compared,
        "decisions_uncovered_after_finalized_prefix": uncovered_after_prefix,
        "decision_rows_missing_inside_finalized_prefix": len(missing_inside_prefix),
        "source_lineage_references_expected": len(expected_refs),
        "source_lineage_references_resolved": len(resolved_refs),
        "source_lineage_references_unresolved": unresolved_refs,
        "mismatches": dict(sorted(mismatches.items())),
        "difference_paths": dict(sorted(difference_paths.items())),
        "history_lineage_variance": dict(sorted(history_variance.items())),
        "passed_for_finalized_prefix": bool(compared and not mismatches),
        "scope": (
            "Reproduces campaign source state, producer/reconstruction identity, quality reason, "
            "features, baseline, and source lineage for the sampled decisions whose source "
            "ordinals are in the captured finalized segment prefix. It does not infer omitted "
            "decisions, fills, or outcomes."
        ),
    }
