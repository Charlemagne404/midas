"""Reproduce forward decisions from immutable, finalized Reality source segments."""

from __future__ import annotations

import json
import math
import sqlite3
import time
import zlib
from collections import Counter, defaultdict
from collections.abc import Iterator
from decimal import ROUND_CEILING
from decimal import Decimal as D
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
MAX_COLLECTOR_PROCESS_START_EPOCHS = 1_000
_UPDATE_INTERVAL_BUCKETS = (
    ("0_to_250_ms", 250 * 10**6),
    ("250_to_500_ms", 500 * 10**6),
    ("500_ms_to_1_s", 10**9),
    ("1_to_2_s", 2 * 10**9),
    ("2_to_5_s", 5 * 10**9),
    ("5_to_10_s", 10 * 10**9),
    ("10_to_30_s", 30 * 10**9),
    ("30_to_60_s", 60 * 10**9),
    ("60_s_or_more", None),
)
_CAMPAIGN_ACTIVITY_BLOCK_NS = 300 * 10**9
_KNOWN_GAP_ISSUES = frozenset(
    {
        "top_divergence",
        "malformed_event",
        "unknown_event",
        "timestamp_regression",
        "market_resolved",
        "stale",
        "gap:malformed_constraints",
        "crossed_or_locked",
        "malformed_frame",
        "advertised_top_pending",
    }
)
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
_PROCESS_START_CONFIG_FIELDS = (
    "markets",
    "discovery_limit",
    "refresh_seconds",
    "resync_seconds",
    "stale_seconds",
    "queue_size",
    "segment_seconds",
    "selection_mode",
    "selection_seed",
    "near_expiry_tag_id",
    "comparison_seconds",
    "comparison_timeout_seconds",
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


def _new_timing_bucket() -> dict[str, Any]:
    return {
        "decisions": 0,
        "source_input_lag_ns": [],
        "source_input_lag_bands": Counter(),
        "pair_books_available": Counter(),
        "market_outcomes_updated_in_source_frame": Counter(),
        "max_pair_age_ns": [],
        "cross_outcome_skew_ns": [],
        "freshness_violation_decisions": 0,
    }


def _lag_band(lag_ns: int, limit_ns: int) -> str:
    if lag_ns < 0:
        return "negative"
    if lag_ns > limit_ns:
        return "above_frozen_limit"
    if lag_ns <= 25 * 10**6:
        return "0_to_25_ms"
    if lag_ns <= 50 * 10**6:
        return "25_to_50_ms"
    if lag_ns <= 100 * 10**6:
        return "50_to_100_ms"
    return "100_ms_to_limit"


def _record_timing(bucket: dict[str, Any], sample: dict[str, Any], limit_ns: int) -> None:
    bucket["decisions"] += 1
    lag_ns = sample["source_input_lag_ns"]
    if lag_ns is not None:
        bucket["source_input_lag_ns"].append(lag_ns)
        bucket["source_input_lag_bands"][_lag_band(lag_ns, limit_ns)] += 1
    bucket["pair_books_available"][str(sample["pair_books_available"])] += 1
    bucket["market_outcomes_updated_in_source_frame"][
        str(sample["market_outcomes_updated_in_source_frame"])
    ] += 1
    if sample["freshness_violating_legs"]:
        bucket["freshness_violation_decisions"] += 1
    if sample["max_pair_age_ns"] is not None:
        bucket["max_pair_age_ns"].append(sample["max_pair_age_ns"])
    if sample["cross_outcome_skew_ns"] is not None:
        bucket["cross_outcome_skew_ns"].append(sample["cross_outcome_skew_ns"])


def _timing_distribution(values: list[int]) -> dict[str, Any] | None:
    if not values:
        return None
    ordered = sorted(values)

    def nearest_rank(fraction: D) -> str:
        index = max(
            0,
            int((fraction * len(ordered)).to_integral_value(rounding=ROUND_CEILING)) - 1,
        )
        return str(D(ordered[min(index, len(ordered) - 1)]) / D(1_000_000))

    return {
        "count": len(ordered),
        "minimum_ms": str(D(ordered[0]) / D(1_000_000)),
        "p50_nearest_rank_ms": nearest_rank(D("0.50")),
        "p90_nearest_rank_ms": nearest_rank(D("0.90")),
        "p95_nearest_rank_ms": nearest_rank(D("0.95")),
        "maximum_ms": str(D(ordered[-1]) / D(1_000_000)),
    }


def _interval_band(interval_ns: int) -> str:
    for label, upper_ns in _UPDATE_INTERVAL_BUCKETS:
        if upper_ns is None or interval_ns <= upper_ns:
            return label
    raise AssertionError("An interval did not match a configured bucket")


def _new_interval_state() -> dict[str, Any]:
    return {
        "interval_count": 0,
        "interval_buckets": Counter(),
        "intervals_censored_by_discontinuity": 0,
        "nonmonotonic_intervals": 0,
        "last_update": None,
    }


def _new_source_activity(market: dict[str, Any]) -> dict[str, Any]:
    outcomes = sorted(set(str(outcome) for outcome in market["tokens"].values()))
    return {
        "market_id": str(market["id"]),
        "condition": market["condition"],
        "touched_book_update_frames": 0,
        "one_outcome_update_frames": 0,
        "both_outcome_update_frames": 0,
        "frames_by_updated_outcome_count": Counter(),
        "outcome_update_frames": Counter(),
        "quality_reason_counts": Counter(),
        "pair_touch_interval": _new_interval_state(),
        "outcomes": {outcome: _new_interval_state() for outcome in outcomes},
    }


def _record_interval(state: dict[str, Any], now_ns: int, gap_epoch: int) -> None:
    previous = state["last_update"]
    if previous is not None:
        prior_ns, prior_epoch = previous
        if prior_epoch != gap_epoch:
            state["intervals_censored_by_discontinuity"] += 1
        elif now_ns < prior_ns:
            state["nonmonotonic_intervals"] += 1
        else:
            state["interval_count"] += 1
            state["interval_buckets"][_interval_band(now_ns - prior_ns)] += 1
    state["last_update"] = (now_ns, gap_epoch)


def _interval_distribution(state: dict[str, Any]) -> dict[str, Any] | None:
    count = state["interval_count"]
    if not count:
        return None

    def nearest_rank_bucket(fraction: D) -> str:
        rank = int((fraction * count).to_integral_value(rounding=ROUND_CEILING))
        cumulative = 0
        for label, _ in _UPDATE_INTERVAL_BUCKETS:
            cumulative += state["interval_buckets"][label]
            if cumulative >= rank:
                return label
        raise AssertionError("Interval bucket count is inconsistent")

    return {
        "count": count,
        "nearest_rank_p50_bucket": nearest_rank_bucket(D("0.50")),
        "nearest_rank_p95_bucket": nearest_rank_bucket(D("0.95")),
        "bucket_counts": {
            label: state["interval_buckets"][label] for label, _ in _UPDATE_INTERVAL_BUCKETS
        },
    }


def _finish_source_activity(state: dict[str, Any], family_id: str | None) -> dict[str, Any]:
    return {
        "market_id": state["market_id"],
        "family_id": family_id,
        "touched_book_update_frames": state["touched_book_update_frames"],
        "one_outcome_update_frames": state["one_outcome_update_frames"],
        "both_outcome_update_frames": state["both_outcome_update_frames"],
        "frames_by_updated_outcome_count": dict(
            sorted(state["frames_by_updated_outcome_count"].items())
        ),
        "outcome_update_frames": dict(sorted(state["outcome_update_frames"].items())),
        "quality_reason_counts": dict(sorted(state["quality_reason_counts"].items())),
        "pair_touch_intervals_ms": _interval_distribution(state["pair_touch_interval"]),
        "pair_touch_intervals_censored_by_discontinuity": state["pair_touch_interval"][
            "intervals_censored_by_discontinuity"
        ],
        "outcome_update_intervals_ms": {
            outcome: _interval_distribution(interval)
            for outcome, interval in sorted(state["outcomes"].items())
        },
        "outcome_update_intervals_censored_by_discontinuity": {
            outcome: interval["intervals_censored_by_discontinuity"]
            for outcome, interval in sorted(state["outcomes"].items())
        },
        "nonmonotonic_pair_intervals": state["pair_touch_interval"]["nonmonotonic_intervals"],
    }


def _new_source_activity_block(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_id": str(market["id"]),
        "book_update_frames": 0,
        "frames_by_updated_outcome_count": Counter(),
        "quality_reason_counts": Counter(),
    }


def _new_decision_activity_block(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_id": str(market["id"]),
        "decisions": 0,
        "quality_reason_counts": Counter(),
        "freshness_violation_decisions": 0,
        "market_outcomes_updated_in_source_frame": Counter(),
        "maximum_leg_age_buckets": Counter(),
    }


def _new_family_activity_block() -> dict[str, Any]:
    return {
        "source_market_ids": set(),
        "source_book_update_frames": 0,
        "source_update_frames_by_outcome_count": Counter(),
        "source_quality_reason_counts": Counter(),
        "source_book_update_frames_by_market": Counter(),
        "scheduled_market_ids": set(),
        "scheduled_decisions": 0,
        "freshness_violation_decisions": 0,
        "decision_quality_reason_counts": Counter(),
        "decision_market_outcomes_updated_in_source_frame": Counter(),
        "decision_maximum_leg_age_buckets": Counter(),
        "scheduled_decisions_by_market": Counter(),
        "freshness_violations_by_market": Counter(),
    }


def _gap_issue_label(issue: Any) -> str:
    return issue if isinstance(issue, str) and issue in _KNOWN_GAP_ISSUES else "other"


def _gap_outcome_label(outcome: Any) -> str:
    label = str(outcome).strip().lower()
    return label if label in {"yes", "no"} else "other"


def _safe_process_start_config(payload: dict[str, Any]) -> dict[str, Any] | None:
    config = payload.get("config")
    if not isinstance(config, dict):
        return None
    result: dict[str, Any] = {}
    for field in _PROCESS_START_CONFIG_FIELDS:
        value = config.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            result[field] = value
        elif field == "selection_mode" and isinstance(value, str) and len(value) <= 64:
            result[field] = value
    return result


def _record_gap_issue_market_activity(
    context: Context,
    reason: str,
    block_start_ns: int,
    affected_assets: Any,
    total_by_market: dict[tuple[str, str], dict[str, Any]],
    block_by_market: dict[tuple[int, str, str], dict[str, Any]],
    unmapped_total: defaultdict[str, Counter[str]],
    unmapped_by_block: dict[tuple[int, str], Counter[str]],
) -> None:
    if not isinstance(affected_assets, dict):
        return

    token_to_market_outcome = {
        str(token): (str(market["id"]), _gap_outcome_label(outcome))
        for market in context.cohort.values()
        for token, outcome in market["tokens"].items()
    }
    issues_by_market: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "affected_issue_counts": Counter(),
            "affected_issue_counts_by_outcome": defaultdict(Counter),
            "outcomes": set(),
        }
    )
    unmapped_issues: Counter[str] = Counter()
    for token, issue in affected_assets.items():
        issue_label = _gap_issue_label(issue)
        mapping = token_to_market_outcome.get(token) if isinstance(token, str) else None
        if mapping is None:
            unmapped_issues[issue_label] += 1
        else:
            market_id, outcome = mapping
            entry = issues_by_market[market_id]
            entry["affected_issue_counts"][issue_label] += 1
            entry["affected_issue_counts_by_outcome"][outcome][issue_label] += 1
            entry["outcomes"].add(outcome)

    for market_id, issue_data in issues_by_market.items():
        total_entry = total_by_market.setdefault(
            (reason, market_id),
            {
                "gap_records_with_market_issues": 0,
                "affected_issue_counts": Counter(),
                "affected_issue_counts_by_outcome": defaultdict(Counter),
                "gap_records_by_outcome_count": Counter(),
            },
        )
        block_entry = block_by_market.setdefault(
            (block_start_ns, reason, market_id),
            {
                "gap_records_with_market_issues": 0,
                "affected_issue_counts": Counter(),
                "affected_issue_counts_by_outcome": defaultdict(Counter),
                "gap_records_by_outcome_count": Counter(),
            },
        )
        for entry in (total_entry, block_entry):
            entry["gap_records_with_market_issues"] += 1
            entry["affected_issue_counts"].update(issue_data["affected_issue_counts"])
            entry["gap_records_by_outcome_count"][str(len(issue_data["outcomes"]))] += 1
            for outcome, issue_counts in issue_data["affected_issue_counts_by_outcome"].items():
                entry["affected_issue_counts_by_outcome"][outcome].update(issue_counts)

    if unmapped_issues:
        unmapped_total[reason].update(unmapped_issues)
        unmapped_by_block.setdefault((block_start_ns, reason), Counter()).update(unmapped_issues)


def _finish_family_activity_blocks(
    source_blocks: dict[tuple[str, int], dict[str, Any]],
    decision_blocks: dict[tuple[str, int], dict[str, Any]],
    family_by_condition: dict[str, str],
) -> list[dict[str, Any]]:
    blocks: defaultdict[tuple[str, int], dict[str, Any]] = defaultdict(_new_family_activity_block)
    for (condition, block_start_ns), data in source_blocks.items():
        family_id = family_by_condition.get(condition, "unassigned")
        aggregate = blocks[(family_id, block_start_ns)]
        market_id = data["market_id"]
        aggregate["source_market_ids"].add(market_id)
        aggregate["source_book_update_frames"] += data["book_update_frames"]
        aggregate["source_update_frames_by_outcome_count"].update(
            data["frames_by_updated_outcome_count"]
        )
        aggregate["source_quality_reason_counts"].update(data["quality_reason_counts"])
        aggregate["source_book_update_frames_by_market"][market_id] += data["book_update_frames"]
    for (condition, block_start_ns), data in decision_blocks.items():
        family_id = family_by_condition.get(condition, "unassigned")
        aggregate = blocks[(family_id, block_start_ns)]
        market_id = data["market_id"]
        aggregate["scheduled_market_ids"].add(market_id)
        aggregate["scheduled_decisions"] += data["decisions"]
        aggregate["freshness_violation_decisions"] += data["freshness_violation_decisions"]
        aggregate["decision_quality_reason_counts"].update(data["quality_reason_counts"])
        aggregate["decision_market_outcomes_updated_in_source_frame"].update(
            data["market_outcomes_updated_in_source_frame"]
        )
        aggregate["decision_maximum_leg_age_buckets"].update(data["maximum_leg_age_buckets"])
        aggregate["scheduled_decisions_by_market"][market_id] += data["decisions"]
        aggregate["freshness_violations_by_market"][market_id] += data[
            "freshness_violation_decisions"
        ]

    result = []
    for (family_id, block_start_ns), data in sorted(blocks.items()):
        result.append(
            {
                "family_id": family_id,
                "block_start_ns": block_start_ns,
                "source_markets_with_updates": len(data["source_market_ids"]),
                "source_book_update_frames": data["source_book_update_frames"],
                "source_update_frames_by_outcome_count": dict(
                    sorted(data["source_update_frames_by_outcome_count"].items())
                ),
                "source_quality_reason_counts": dict(
                    sorted(data["source_quality_reason_counts"].items())
                ),
                "source_book_update_frames_by_market": dict(
                    sorted(data["source_book_update_frames_by_market"].items())
                ),
                "scheduled_markets": len(data["scheduled_market_ids"]),
                "scheduled_decisions": data["scheduled_decisions"],
                "freshness_violation_decisions": data["freshness_violation_decisions"],
                "decision_quality_reason_counts": dict(
                    sorted(data["decision_quality_reason_counts"].items())
                ),
                "decision_market_outcomes_updated_in_source_frame": dict(
                    sorted(data["decision_market_outcomes_updated_in_source_frame"].items())
                ),
                "decision_maximum_leg_age_buckets": dict(
                    sorted(data["decision_maximum_leg_age_buckets"].items())
                ),
                "scheduled_decisions_by_market": dict(
                    sorted(data["scheduled_decisions_by_market"].items())
                ),
                "freshness_violations_by_market": dict(
                    sorted(data["freshness_violations_by_market"].items())
                ),
            }
        )
    return result


def _finish_timing_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "decisions": bucket["decisions"],
        "source_input_lag_ms": _timing_distribution(bucket["source_input_lag_ns"]),
        "source_input_lag_bands": dict(sorted(bucket["source_input_lag_bands"].items())),
        "pair_books_available": dict(sorted(bucket["pair_books_available"].items())),
        "market_outcomes_updated_in_source_frame": dict(
            sorted(bucket["market_outcomes_updated_in_source_frame"].items())
        ),
        "maximum_leg_age_ms": _timing_distribution(bucket["max_pair_age_ns"]),
        "cross_outcome_skew_ms": _timing_distribution(bucket["cross_outcome_skew_ns"]),
        "freshness_violation_decisions": bucket["freshness_violation_decisions"],
    }


def _decision_timing(
    event: dict[str, Any],
    context: Context,
    source_ref: dict[str, Any],
    max_freshness_ns: int,
) -> dict[str, Any]:
    now = event["decision_ns"]
    market = context.cohort.get(event["condition"])
    books = []
    if market is not None:
        books = [
            context.engine.books[token]
            for token in market["tokens"]
            if token in context.engine.books
        ]
    market_updates_in_frame = sum(
        book["last"][0] == source_ref["ordinal"]
        and book["received_ns"] == source_ref["received_ns"]
        for book in books
    )
    ages = [now - book["received_ns"] for book in books]
    times = [book["received_ns"] for book in books]
    lag_ns = now - source_ref["received_ns"]
    return {
        "source_input_lag_ns": lag_ns,
        "quality_reason": event.get("quality_reason") or "eligible",
        "market_id": str(event.get("market_id", "unknown")),
        "family_id": event.get("family_id"),
        "pair_books_available": len(books),
        "market_outcomes_updated_in_source_frame": market_updates_in_frame,
        "max_pair_age_ns": max(ages) if len(books) == 2 else None,
        "cross_outcome_skew_ns": max(times) - min(times) if len(times) == 2 else None,
        "freshness_violating_legs": sum(age > max_freshness_ns for age in ages),
    }


def _observe_source_activity_frame(
    context: Context,
    record: dict[str, Any],
    activity_by_condition: dict[str, dict[str, Any]],
    activity_blocks: dict[tuple[str, int], dict[str, Any]],
    gap_epoch: int,
    spec: Any,
) -> None:
    now_ns = record["received_ns"]
    ordinal = record["ordinal"]
    for condition, market in context.cohort.items():
        updated_outcomes = []
        for token, outcome in market["tokens"].items():
            book = context.engine.books.get(token)
            if book is not None and book["last"][0] == ordinal and book["received_ns"] == now_ns:
                updated_outcomes.append(str(outcome))
        if not updated_outcomes:
            continue

        activity = activity_by_condition.get(condition)
        if activity is None:
            activity = _new_source_activity(market)
            activity_by_condition[condition] = activity
        activity["touched_book_update_frames"] += 1
        distinct_outcomes = sorted(set(updated_outcomes))
        if len(distinct_outcomes) > 1:
            activity["both_outcome_update_frames"] += 1
        else:
            activity["one_outcome_update_frames"] += 1
        activity["frames_by_updated_outcome_count"][str(len(distinct_outcomes))] += 1
        reason = pair_quality(market, context.engine.books, now_ns, spec)
        if reason is None and any(token in context.bad for token in market["tokens"]):
            reason = "independent_book_divergence"
        quality_reason = reason or "eligible"
        activity["quality_reason_counts"][quality_reason] += 1

        block_start_ns = (now_ns // _CAMPAIGN_ACTIVITY_BLOCK_NS) * _CAMPAIGN_ACTIVITY_BLOCK_NS
        block_key = (condition, block_start_ns)
        block = activity_blocks.get(block_key)
        if block is None:
            block = _new_source_activity_block(market)
            activity_blocks[block_key] = block
        block["book_update_frames"] += 1
        block["frames_by_updated_outcome_count"][str(len(distinct_outcomes))] += 1
        block["quality_reason_counts"][quality_reason] += 1

        _record_interval(activity["pair_touch_interval"], now_ns, gap_epoch)
        for outcome in distinct_outcomes:
            interval = activity["outcomes"].setdefault(outcome, _new_interval_state())
            _record_interval(interval, now_ns, gap_epoch)
            activity["outcome_update_frames"][outcome] += 1


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
    if event.get("source_input_lag_ns") != now - source_ref["received_ns"]:
        mismatches["source_input_lag_ns"] += 1
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
    lag_limit_ms = identity["max_decision_input_lag_ms"]
    lag_limit_ns = int(lag_limit_ms) * 10**6
    max_freshness_ns = int(identity["max_freshness_ms"]) * 10**6
    mismatches: Counter[str] = Counter()
    difference_paths: Counter[str] = Counter()
    history_variance: Counter[str] = Counter()
    timing_all = _new_timing_bucket()
    timing_by_reason: defaultdict[str, dict[str, Any]] = defaultdict(_new_timing_bucket)
    timing_by_market: defaultdict[str, dict[str, Any]] = defaultdict(_new_timing_bucket)
    timing_market_families: dict[str, str | None] = {}
    activity_by_condition: dict[str, dict[str, Any]] = {}
    source_activity_blocks: dict[tuple[str, int], dict[str, Any]] = {}
    decision_activity_blocks: dict[tuple[str, int], dict[str, Any]] = {}
    source_gap_blocks: dict[int, dict[str, Any]] = {}
    source_gap_issue_by_market: dict[tuple[str, str], dict[str, Any]] = {}
    source_gap_issue_by_market_block: dict[tuple[int, str, str], dict[str, Any]] = {}
    source_gap_unmapped_issue_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    source_gap_unmapped_issue_blocks: dict[tuple[int, str], Counter[str]] = {}
    source_gap_reasons: Counter[str] = Counter()
    source_gap_affected_asset_counts: Counter[str] = Counter()
    source_gap_affected_issue_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    activity_discontinuities: Counter[str] = Counter()
    collector_process_start_epochs: list[dict[str, Any]] = []
    activity_gap_epoch = 0
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
        now_ns = record["received_ns"]
        in_campaign_window = identity["start_ns"] <= now_ns < identity["end_ns"]
        if record["kind"] == "gap":
            activity_gap_epoch += 1
            payload = record["payload"]
            if payload.get("reason") == "process_start":
                if len(collector_process_start_epochs) >= MAX_COLLECTOR_PROCESS_START_EPOCHS:
                    raise ValueError("Finalized source exceeds the process-start epoch bound")
                implementation_hash = payload.get("implementation_sha256")
                if (
                    not isinstance(implementation_hash, str)
                    or len(implementation_hash) != 64
                    or any(char not in "0123456789abcdef" for char in implementation_hash)
                ):
                    implementation_hash = None
                reconstruction_version = payload.get("reconstruction_version")
                if not isinstance(reconstruction_version, int) or isinstance(
                    reconstruction_version, bool
                ):
                    reconstruction_version = None
                collector_process_start_epochs.append(
                    {
                        "ordinal": record["ordinal"],
                        "received_ns": now_ns,
                        "in_campaign_window": in_campaign_window,
                        "implementation_sha256": implementation_hash,
                        "reconstruction_version": reconstruction_version,
                        "collector_config": _safe_process_start_config(payload),
                    }
                )
            if in_campaign_window:
                reason = payload.get("reason", "unknown")
                source_gap_reasons[reason] += 1
                activity_discontinuities[reason] += 1
                block_start_ns = (
                    now_ns // _CAMPAIGN_ACTIVITY_BLOCK_NS
                ) * _CAMPAIGN_ACTIVITY_BLOCK_NS
                gap_block = source_gap_blocks.setdefault(
                    block_start_ns,
                    {
                        "gap_reasons": Counter(),
                        "affected_asset_counts_by_reason": Counter(),
                        "affected_issue_counts_by_reason": defaultdict(Counter),
                    },
                )
                gap_block["gap_reasons"][reason] += 1
                affected = payload.get("affected_assets")
                if isinstance(affected, dict):
                    count = len(affected)
                    gap_block["affected_asset_counts_by_reason"][reason] += count
                    source_gap_affected_asset_counts[reason] += count
                    for issue in affected.values():
                        label = _gap_issue_label(issue)
                        gap_block["affected_issue_counts_by_reason"][reason][label] += 1
                        source_gap_affected_issue_counts[reason][label] += 1
                _record_gap_issue_market_activity(
                    context,
                    reason,
                    block_start_ns,
                    affected,
                    source_gap_issue_by_market,
                    source_gap_issue_by_market_block,
                    source_gap_unmapped_issue_counts,
                    source_gap_unmapped_issue_blocks,
                )
        barrier = context.consume(record, ref)
        ref_key = _reference_key(ref)
        if ref_key in expected_refs:
            resolved_refs.add(ref_key)
        if record["kind"] == "checkpoint":
            verified_checkpoints += 1
        if record["kind"] == "frame" and in_campaign_window:
            producer_supported = context.producer_hash in identity["allowed_producer_hashes"]
            reconstruction_supported = (
                context.engine.reconstruction_version in identity["allowed_reconstruction_versions"]
            )
            if not producer_supported or not reconstruction_supported:
                activity_gap_epoch += 1
                if in_campaign_window:
                    reason = (
                        "unsupported_producer_frame"
                        if not producer_supported
                        else "unsupported_reconstruction_frame"
                    )
                    activity_discontinuities[reason] += 1
            elif barrier == "receiver_clock_regression":
                activity_gap_epoch += 1
                activity_discontinuities["receiver_clock_regression"] += 1
            else:
                _observe_source_activity_frame(
                    context,
                    record,
                    activity_by_condition,
                    source_activity_blocks,
                    activity_gap_epoch,
                    spec,
                )
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
                    timing = _decision_timing(target, context, ref, max_freshness_ns)
                    _record_timing(timing_all, timing, lag_limit_ns)
                    _record_timing(timing_by_reason[timing["quality_reason"]], timing, lag_limit_ns)
                    _record_timing(timing_by_market[timing["market_id"]], timing, lag_limit_ns)
                    timing_market_families[timing["market_id"]] = timing["family_id"]
                    market = context.cohort.get(target["condition"])
                    if market is not None:
                        block_start_ns = (
                            target["decision_ns"] // _CAMPAIGN_ACTIVITY_BLOCK_NS
                        ) * _CAMPAIGN_ACTIVITY_BLOCK_NS
                        block_key = (target["condition"], block_start_ns)
                        block = decision_activity_blocks.get(block_key)
                        if block is None:
                            block = _new_decision_activity_block(market)
                            decision_activity_blocks[block_key] = block
                        block["decisions"] += 1
                        block["quality_reason_counts"][timing["quality_reason"]] += 1
                        if timing["freshness_violating_legs"]:
                            block["freshness_violation_decisions"] += 1
                        block["market_outcomes_updated_in_source_frame"][
                            str(timing["market_outcomes_updated_in_source_frame"])
                        ] += 1
                        if timing["max_pair_age_ns"] is not None:
                            age_bucket = _interval_band(timing["max_pair_age_ns"])
                            block["maximum_leg_age_buckets"][age_bucket] += 1
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
    timing_report = {
        "covered_decisions": timing_all["decisions"],
        "frozen_input_lag_limit_ms": lag_limit_ms,
        "all": _finish_timing_bucket(timing_all),
        "by_quality_reason": {
            name: _finish_timing_bucket(bucket) for name, bucket in sorted(timing_by_reason.items())
        },
        "by_market": {
            market_id: {
                "family_id": timing_market_families[market_id],
                **_finish_timing_bucket(bucket),
            }
            for market_id, bucket in sorted(timing_by_market.items())
        },
    }
    final_families = context.families.identities()
    family_by_condition = {
        condition_key.removeprefix("condition:"): family_id
        for condition_key, family_id in final_families.items()
        if condition_key.startswith("condition:")
    }
    source_activity = [
        _finish_source_activity(
            activity,
            final_families.get("condition:" + condition),
        )
        for condition, activity in sorted(
            activity_by_condition.items(), key=lambda item: (item[1]["market_id"], item[0])
        )
    ]
    source_activity_by_family_block = _finish_family_activity_blocks(
        source_activity_blocks, decision_activity_blocks, family_by_condition
    )
    source_gaps_by_block = [
        {
            "block_start_ns": block_start_ns,
            "gap_reasons": dict(sorted(block["gap_reasons"].items())),
            "affected_asset_counts_by_reason": dict(
                sorted(block["affected_asset_counts_by_reason"].items())
            ),
            "affected_issue_counts_by_reason": {
                reason: dict(sorted(issues.items()))
                for reason, issues in sorted(block["affected_issue_counts_by_reason"].items())
            },
        }
        for block_start_ns, block in sorted(source_gap_blocks.items())
    ]
    source_gap_issue_activity_by_market = [
        {
            "gap_reason": reason,
            "market_id": market_id,
            "gap_records_with_market_issues": data["gap_records_with_market_issues"],
            "affected_issue_counts": dict(sorted(data["affected_issue_counts"].items())),
            "affected_issue_counts_by_outcome": {
                outcome: dict(sorted(issues.items()))
                for outcome, issues in sorted(data["affected_issue_counts_by_outcome"].items())
            },
            "gap_records_by_outcome_count": dict(
                sorted(data["gap_records_by_outcome_count"].items())
            ),
        }
        for (reason, market_id), data in sorted(source_gap_issue_by_market.items())
    ]
    source_gap_issue_activity_by_market_block = [
        {
            "block_start_ns": block_start_ns,
            "gap_reason": reason,
            "market_id": market_id,
            "gap_records_with_market_issues": data["gap_records_with_market_issues"],
            "affected_issue_counts": dict(sorted(data["affected_issue_counts"].items())),
            "affected_issue_counts_by_outcome": {
                outcome: dict(sorted(issues.items()))
                for outcome, issues in sorted(data["affected_issue_counts_by_outcome"].items())
            },
            "gap_records_by_outcome_count": dict(
                sorted(data["gap_records_by_outcome_count"].items())
            ),
        }
        for (block_start_ns, reason, market_id), data in sorted(
            source_gap_issue_by_market_block.items()
        )
    ]
    source_gap_unmapped_issue_activity_by_block = [
        {
            "block_start_ns": block_start_ns,
            "gap_reason": reason,
            "affected_issue_counts": dict(sorted(counts.items())),
        }
        for (block_start_ns, reason), counts in sorted(source_gap_unmapped_issue_blocks.items())
    ]
    # Keep only aggregate mismatch categories; no raw market or event payloads are exported.
    return {
        "analysis_version": "veritas-source-replay-v6",
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
        "decision_timing": timing_report,
        "source_gap_reasons_in_campaign_window": dict(sorted(source_gap_reasons.items())),
        "source_activity_discontinuities_in_campaign_window": dict(
            sorted(activity_discontinuities.items())
        ),
        "source_gap_affected_asset_counts_by_reason": dict(
            sorted(source_gap_affected_asset_counts.items())
        ),
        "source_gap_affected_issue_counts_by_reason": {
            reason: dict(sorted(issues.items()))
            for reason, issues in sorted(source_gap_affected_issue_counts.items())
        },
        "source_gap_issue_activity_by_market": source_gap_issue_activity_by_market,
        "source_gap_issue_activity_by_market_5min_block": (
            source_gap_issue_activity_by_market_block
        ),
        "collector_process_start_configuration": {
            "epochs_scanned": len(collector_process_start_epochs),
            "epochs_in_campaign_window": sum(
                bool(epoch["in_campaign_window"]) for epoch in collector_process_start_epochs
            ),
            "epochs_with_captured_allowlisted_config": sum(
                bool(epoch["collector_config"]) for epoch in collector_process_start_epochs
            ),
            "epochs_without_captured_allowlisted_config": sum(
                not bool(epoch["collector_config"]) for epoch in collector_process_start_epochs
            ),
            "allowlisted_config_fields": list(_PROCESS_START_CONFIG_FIELDS),
            "epochs": collector_process_start_epochs,
        },
        "source_gap_unmapped_issue_counts_by_reason": {
            reason: dict(sorted(issues.items()))
            for reason, issues in sorted(source_gap_unmapped_issue_counts.items())
        },
        "source_gap_unmapped_issue_activity_by_5min_block": (
            source_gap_unmapped_issue_activity_by_block
        ),
        "source_gaps_by_5min_block": source_gaps_by_block,
        "source_activity_by_family_5min_block": source_activity_by_family_block,
        "source_activity_by_market": source_activity,
        "passed_for_finalized_prefix": bool(compared and not mismatches),
        "scope": (
            "Reproduces campaign source state, producer/reconstruction identity, quality reason, "
            "features, baseline, and source lineage for the sampled decisions whose source "
            "ordinals are in the captured finalized segment prefix. It also summarizes campaign "
            "window book-update intervals by market, excluding intervals that span a recorded "
            "gap or unsupported source frame; aligns market updates, scheduled decisions, and "
            "aggregated gap issue labels by five-minute family block, mapping issue entries to "
            "campaign market IDs and YES/NO outcomes without exporting asset identifiers. It also "
            "reports allowlisted configuration fields from finalized collector process-start "
            "records, excluding storage paths. It does not infer omitted decisions, fills, or "
            "outcomes."
        ),
    }
