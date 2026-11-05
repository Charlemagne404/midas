"""Join frozen gap-censored outcomes to the verified finalized gap prefix.

The join is descriptive: a same-market gap preceding a book-issue reference is
reported as a candidate temporal link, not as proof that the gap caused the
censor or that a quote was unavailable at the venue.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.reality.research_schema import digest
from midas.reality.storage import file_hash
from midas.veritas import censor_gap_audit as source_audit
from midas.veritas.gap_detail_analysis import (
    MAX_EVENT_BYTES,
    MAX_STATE_BYTES,
    _canonical,
    _code_identity,
    _read_sealed,
    read_finalized_gap_detail_summary,
)
from midas.veritas.gap_detail_analysis import (
    VERSION as GAP_DETAIL_VERSION,
)

VERSION = "veritas-censor-gap-attribution-v1"
MAX_OUTCOMES = source_audit.MAX_OUTCOMES
MAX_OUTCOME_EVENT_BYTES = source_audit.MAX_OUTCOME_EVENT_BYTES
MAX_SOURCE_BYTES = source_audit.MAX_SOURCE_BYTES
MAX_GAP_INDEX_SEGMENTS = 100_000
MAX_GAP_INDEX_BYTES = 256 * 1024**2
_SEGMENT = re.compile(r"[0-9]{20}\.json\Z")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_gap_index(
    root: Path,
    *,
    campaign_id: str,
    campaign_sha256: str,
    campaign_start_ns: int,
    campaign_end_ns: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read and verify the sealed summary, state, segment events, and chains."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Gap-detail root is missing or unsafe")
    summary = read_finalized_gap_detail_summary(root)
    if summary is None:
        raise ValueError("Gap-detail summary is missing")
    state_path = root / "gap-detail-state-v1.json"
    state = _read_sealed(
        state_path,
        maximum=MAX_STATE_BYTES,
        key="state_sha256",
        label="gap-detail state",
    )
    for value in (summary, state):
        if (
            value.get("analysis_version") != GAP_DETAIL_VERSION
            or value.get("campaign_id") != campaign_id
            or value.get("campaign_sha256") != campaign_sha256
        ):
            raise ValueError("Gap-detail campaign or version does not match the frozen plan")
    if (
        summary.get("processed_segment_count") != state.get("processed_segment_count")
        or summary.get("processed_source_bytes") != state.get("processed_source_bytes")
        or summary.get("prefix_catalog_sha256") != state.get("prefix_catalog_sha256")
        or summary.get("last_event_chain_sha256") != state.get("last_event_chain_sha256")
        or summary.get("last_processed_ordinal") != state.get("last_ordinal")
        or summary.get("last_processed_segment_file") != state.get("last_segment_file")
    ):
        raise ValueError("Gap-detail summary and state disagree")
    code_files = _code_identity()
    if (
        summary.get("analysis_code_files") != code_files
        or summary.get("analysis_code_sha256") != digest(code_files)
        or summary.get("campaign_window_ns")
        != {"start": campaign_start_ns, "end_exclusive": campaign_end_ns}
    ):
        raise ValueError("Gap-detail code or campaign-window identity differs from current pins")

    count = state.get("processed_segment_count")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or count > MAX_GAP_INDEX_SEGMENTS
    ):
        raise ValueError("Gap-detail processed segment count is invalid")
    event_dir = root / "gap-detail-events" / "v1"
    if (
        (root / "gap-detail-events").is_symlink()
        or event_dir.is_symlink()
        or not event_dir.is_dir()
    ):
        raise ValueError("Gap-detail event directory is missing or unsafe")

    prior_prefix = "0" * 64
    prior_event_chain = "0" * 64
    total_bytes = 0
    indexed_gaps: list[dict[str, Any]] = []
    gap_ordinals: set[int] = set()
    window_reasons: Counter[str] = Counter()
    window_markets: Counter[str] = Counter()
    window_unmapped_assets = 0
    window_gaps_without_reported_assets = 0
    for index in range(1, count + 1):
        event_path = event_dir / f"{index:020d}.json"
        if _SEGMENT.fullmatch(event_path.name) is None:
            raise ValueError("Gap-detail event filename is invalid")
        total_bytes += event_path.stat().st_size if event_path.exists() else 0
        if total_bytes > MAX_GAP_INDEX_BYTES:
            raise ValueError("Gap-detail event prefix exceeds the audit byte bound")
        event = _read_sealed(
            event_path,
            maximum=MAX_EVENT_BYTES,
            key="gap_event_sha256",
            label="gap-detail event",
        )
        catalog = event.get("source_catalog")
        if not isinstance(catalog, dict):
            raise ValueError("Gap-detail source catalog is missing")
        segment = event.get("source_segment")
        segment_sha256 = event.get("source_segment_sha256")
        if (
            event.get("schema_version") != 1
            or event.get("analysis_version") != GAP_DETAIL_VERSION
            or event.get("analysis_code_sha256") != summary.get("analysis_code_sha256")
            or event.get("campaign_id") != campaign_id
            or event.get("campaign_sha256") != campaign_sha256
            or event.get("segment_index") != index
            or event.get("prior_prefix_catalog_sha256") != prior_prefix
            or not isinstance(segment, str)
            or catalog.get("file") != segment
            or catalog.get("sha256") != segment_sha256
            or event.get("source_catalog_sha256") != _canonical_sha(catalog)
            or event.get("record_count") != catalog.get("count")
            or event.get("source_ordinal_start") != catalog.get("first")
            or event.get("source_ordinal_end") != catalog.get("last")
            or event.get("record_kinds") != catalog.get("kinds")
        ):
            raise ValueError("Gap-detail event source identity or catalog chain is invalid")
        prior_prefix = hashlib.sha256(bytes.fromhex(prior_prefix) + _canonical(catalog)).hexdigest()
        if event.get("prefix_catalog_sha256") != prior_prefix:
            raise ValueError("Gap-detail prefix catalog digest mismatch")

        gaps = event.get("gap_events")
        if (
            not isinstance(gaps, list)
            or event.get("gap_event_count") != len(gaps)
            or len(gaps) != catalog.get("kinds", {}).get("gap", 0)
        ):
            raise ValueError("Gap-detail segment gap count differs from its source catalog")
        in_window_count = 0
        for gap in gaps:
            if not isinstance(gap, dict):
                raise ValueError("Gap-detail event contains a malformed gap row")
            ordinal = gap.get("ordinal")
            received_ns = gap.get("received_ns")
            affected = gap.get("affected_market_ids")
            if (
                not isinstance(ordinal, int)
                or isinstance(ordinal, bool)
                or not isinstance(received_ns, int)
                or isinstance(received_ns, bool)
                or not isinstance(gap.get("in_campaign_window"), bool)
                or not isinstance(affected, list)
                or any(not isinstance(market, str) or not market for market in affected)
                or gap.get("affected_asset_scope") not in ("reported_assets", "not_reported")
                or not isinstance(gap.get("affected_asset_count"), int)
                or isinstance(gap.get("affected_asset_count"), bool)
                or gap.get("affected_asset_count", -1) < 0
                or ordinal < catalog["first"]
                or ordinal > catalog["last"]
                or gap.get("segment_index") != index
                or gap.get("segment_file") != segment
                or ordinal in gap_ordinals
            ):
                raise ValueError("Gap-detail gap row has invalid or duplicate identity")
            if gap["in_campaign_window"] != (campaign_start_ns <= received_ns < campaign_end_ns):
                raise ValueError("Gap-detail campaign-window label differs from frozen plan")
            gap_ordinals.add(ordinal)
            if gap["in_campaign_window"]:
                reason = gap.get("reason")
                if not isinstance(reason, str) or not reason:
                    raise ValueError("Gap-detail gap reason is invalid")
                unmapped = gap.get("unmapped_affected_asset_count")
                if not isinstance(unmapped, int) or isinstance(unmapped, bool) or unmapped < 0:
                    raise ValueError("Gap-detail unmapped asset count is invalid")
                in_window_count += 1
                window_reasons[reason] += 1
                window_unmapped_assets += unmapped
                if gap.get("affected_asset_scope") == "not_reported":
                    window_gaps_without_reported_assets += 1
                for market_id in affected:
                    window_markets[market_id] += 1
                indexed_gaps.append(
                    {
                        "ordinal": ordinal,
                        "received_ns": received_ns,
                        "reason": reason,
                        "affected_market_ids": affected,
                        "segment_index": index,
                        "segment_file": segment,
                        "segment_sha256": segment_sha256,
                        "unmapped_affected_asset_count": gap.get("unmapped_affected_asset_count"),
                    }
                )
        if event.get("campaign_window_gap_event_count") != in_window_count:
            raise ValueError("Gap-detail campaign-window count differs from its event rows")
        event_digest = event.get("gap_event_sha256")
        if not isinstance(event_digest, str) or len(event_digest) != 64:
            raise ValueError("Gap-detail event chain digest is invalid")
        prior_event_chain = hashlib.sha256(
            bytes.fromhex(prior_event_chain) + bytes.fromhex(event_digest)
        ).hexdigest()

    if (
        prior_prefix != state.get("prefix_catalog_sha256")
        or prior_event_chain != state.get("last_event_chain_sha256")
        or len(indexed_gaps) != summary.get("campaign_window_gap_event_count")
        or dict(window_reasons) != summary.get("campaign_window_gap_counts_by_reason")
        or dict(window_markets) != summary.get("campaign_window_affected_market_counts")
        or window_unmapped_assets != summary.get("campaign_window_unmapped_affected_asset_count")
        or window_gaps_without_reported_assets
        != summary.get("campaign_window_gap_events_without_reported_assets")
    ):
        raise ValueError("Gap-detail indexed prefix does not reconcile to its sealed state")
    return {
        "summary": summary,
        "state": state,
        "indexed_campaign_gaps": indexed_gaps,
        "indexed_event_bytes": total_bytes,
    }, indexed_gaps


def audit_censored_gap_attribution(
    campaign_root: Path,
    gap_detail_root: Path,
    *,
    limit: int = MAX_OUTCOMES,
    max_source_bytes: int = 128 * 1024**2,
) -> dict[str, Any]:
    """Verify frozen gap-censor source records and link prior same-market gaps."""
    if not 1 <= limit <= MAX_OUTCOMES:
        raise ValueError("Censored outcome query exceeds its explicit bound")
    if (
        not isinstance(max_source_bytes, int)
        or isinstance(max_source_bytes, bool)
        or not 1 <= max_source_bytes <= MAX_SOURCE_BYTES
    ):
        raise ValueError("Source segment byte bound is invalid")
    plan, journal_path, raw_root, plan_sha256 = source_audit._campaign(campaign_root)
    campaign_id = plan["campaign_id"]
    identity = plan["identity"]
    start_ns = identity["start_ns"]
    end_ns = identity["end_ns"]

    gap_snapshot, indexed_gaps = _read_gap_index(
        gap_detail_root,
        campaign_id=campaign_id,
        campaign_sha256=plan_sha256,
        campaign_start_ns=start_ns,
        campaign_end_ns=end_ns,
    )
    gap_by_ordinal = {gap["ordinal"]: gap for gap in indexed_gaps}
    gaps_by_market_reason: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    gaps_by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for gap in indexed_gaps:
        if not isinstance(gap["reason"], str) or not gap["reason"]:
            raise ValueError("Gap-detail reason is invalid")
        for market_id in gap["affected_market_ids"]:
            gaps_by_market_reason[(market_id, gap["reason"])].append(gap)
            gaps_by_market[market_id].append(gap)
    for values in (*gaps_by_market_reason.values(), *gaps_by_market.values()):
        values.sort(key=lambda gap: (gap["ordinal"], gap["received_ns"]))

    db = sqlite3.connect(journal_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    db.execute("pragma query_only=on")
    references: dict[tuple[str, int, str], dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []
    by_reason: Counter[str] = Counter()
    by_horizon: dict[str, Counter[str]] = {}
    scanned = event_bytes = 0
    try:
        db.execute("begin")
        tail = db.execute("select seq,sha from events order by seq desc limit 1").fetchone()
        rows = db.execute(
            "select o.decision_id,o.horizon,o.status,e.kind,e.seq,e.occurred_ns,e.body,"
            "d.condition,d.market_id,d.ns,d.source_ordinal "
            "from outcomes o join events e on e.seq=o.event_seq "
            "left join decisions d on d.id=o.decision_id "
            "where o.status='censored' order by e.seq limit ?",
            (limit + 1,),
        )
        while batch := rows.fetchmany(256):
            for (
                decision_id,
                horizon,
                status,
                kind,
                event_seq,
                occurred_ns,
                body,
                condition,
                market_id,
                decision_ns,
                decision_ordinal,
            ) in batch:
                if scanned >= limit:
                    raise ValueError("Censored outcome query was truncated")
                scanned += 1
                event_bytes += len(body)
                if event_bytes > MAX_OUTCOME_EVENT_BYTES:
                    raise ValueError("Censored outcome event bytes exceed their explicit bound")
                if kind != "followup":
                    raise ValueError("Outcome index points to a non-follow-up event")
                event = source_audit._decode_followup(body)
                if (
                    event.get("campaign_id") != campaign_id
                    or event.get("decision_id") != decision_id
                    or event.get("horizon_ms") != horizon
                    or not isinstance(labels := event.get("labels"), dict)
                    or labels.get("status") != status
                ):
                    raise ValueError("Follow-up event differs from its indexed identity")
                reason = labels.get("reason")
                if not isinstance(reason, str) or not reason.startswith(
                    ("recorded_gap:", "book_issue:gap:")
                ):
                    continue
                if (
                    condition is None
                    or market_id is None
                    or decision_ns is None
                    or decision_ordinal is None
                ):
                    raise ValueError("Gap-censored outcome has no durable market decision row")
                market_id_text = str(market_id)
                if isinstance(market_id, bool) or not market_id_text:
                    raise ValueError("Gap-censored outcome decision market id is invalid")
                if not isinstance(condition, str) or not condition:
                    raise ValueError("Gap-censored outcome decision condition is invalid")
                if (
                    not isinstance(decision_ns, int)
                    or isinstance(decision_ns, bool)
                    or not isinstance(decision_ordinal, int)
                    or isinstance(decision_ordinal, bool)
                    or not isinstance(occurred_ns, int)
                    or isinstance(occurred_ns, bool)
                    or not start_ns <= decision_ns < end_ns
                ):
                    raise ValueError("Gap-censored outcome decision time is invalid")
                reference = source_audit._validated_reference(event.get("termination_ref"))
                key = (
                    reference["segment"],
                    reference["offset"],
                    reference["compressed_record_sha256"],
                )
                previous = references.get(key)
                if previous is not None and previous["reference"] != reference:
                    raise ValueError("One source record has inconsistent campaign references")
                bucket = references.setdefault(
                    key, {"reference": reference, "labels": set(), "record": None}
                )
                bucket["labels"].add(reason)
                suffix = reason.partition("gap:")[2]
                if not suffix:
                    raise ValueError("Gap censor reason is empty")
                outcomes.append(
                    {
                        "decision_id_sha256": hashlib.sha256(decision_id.encode()).hexdigest(),
                        "condition_id": condition,
                        "market_id": market_id_text,
                        "decision_ns": decision_ns,
                        "decision_source_ordinal": decision_ordinal,
                        "horizon_ms": horizon,
                        "followup_event_seq": event_seq,
                        "followup_occurred_ns": occurred_ns,
                        "reason": reason,
                        "expected_gap_reason": suffix,
                        "termination_reference": reference,
                    }
                )
                by_reason[reason] += 1
                by_horizon.setdefault(str(horizon), Counter())[reason] += 1
    finally:
        db.rollback()
        db.close()

    segment_bytes = 0
    segment_hashes: dict[str, str] = {}
    for name in sorted({item["reference"]["segment"] for item in references.values()}):
        path = raw_root / name
        if path.parent != raw_root or path.is_symlink() or not path.is_file():
            raise ValueError("Referenced finalized source segment is missing or unsafe")
        catalog = source_audit._read_catalog(path)
        segment_bytes += int(catalog["bytes"])
        if segment_bytes > max_source_bytes:
            raise ValueError("Referenced source segments exceed the explicit byte bound")
        actual_sha = file_hash(path)
        if actual_sha != catalog["sha256"]:
            raise ValueError("Referenced finalized source segment digest mismatch")
        segment_hashes[name] = actual_sha
    for entry in references.values():
        reference = entry["reference"]
        record = source_audit._read_record(raw_root / reference["segment"], reference)
        entry["record"] = record
        for label in entry["labels"]:
            if label.startswith("recorded_gap:"):
                expected = label.removeprefix("recorded_gap:")
                payload = record.get("payload")
                if record["kind"] != "gap" or not isinstance(payload, dict):
                    raise ValueError("Explicit recorded-gap censor does not reference a gap record")
                if payload.get("reason") != expected:
                    raise ValueError("Explicit gap censor reason differs from its source record")

    latest_indexed_ordinal = gap_snapshot["state"].get("last_ordinal")
    if not isinstance(latest_indexed_ordinal, int) or isinstance(latest_indexed_ordinal, bool):
        raise ValueError("Gap-detail last processed ordinal is invalid")
    matched_gap_ordinals: set[int] = set()
    candidate_gap_ordinals: set[int] = set()
    exact_gap_ordinals: set[int] = set()
    candidate_gap_ages_ns: list[int] = []
    link_counts: Counter[str] = Counter()
    by_horizon_link: dict[str, Counter[str]] = {}
    for outcome in outcomes:
        reason = outcome["reason"]
        reference = outcome["termination_reference"]
        terminal_record = references[
            (
                reference["segment"],
                reference["offset"],
                reference["compressed_record_sha256"],
            )
        ]["record"]
        if (
            terminal_record.get("ordinal") != reference["ordinal"]
            or terminal_record.get("received_ns") != reference["received_ns"]
        ):
            raise ValueError("Verified termination source differs from its campaign reference")

        linked: dict[str, Any] | None = None
        link_status: str
        if reason.startswith("recorded_gap:"):
            indexed = gap_by_ordinal.get(reference["ordinal"])
            if indexed is not None:
                if (
                    indexed["reason"] != outcome["expected_gap_reason"]
                    or indexed["received_ns"] != reference["received_ns"]
                    or indexed["segment_file"] != reference["segment"]
                ):
                    raise ValueError("Explicit source gap differs from the indexed gap event")
                linked = indexed
                link_status = "exact_recorded_gap_reference_verified_and_indexed"
            else:
                link_status = (
                    "exact_recorded_gap_reference_verified_not_yet_indexed"
                    if reference["ordinal"] > latest_indexed_ordinal
                    else "exact_recorded_gap_reference_missing_from_indexed_prefix"
                )
        else:
            same_market = gaps_by_market_reason.get(
                (outcome["market_id"], outcome["expected_gap_reason"]), []
            )
            candidates = [
                gap
                for gap in same_market
                if gap["ordinal"] < reference["ordinal"]
                and gap["received_ns"] <= reference["received_ns"]
            ]
            other_reason_prior_count = sum(
                gap["ordinal"] < reference["ordinal"]
                and gap["received_ns"] <= reference["received_ns"]
                for gap in gaps_by_market.get(outcome["market_id"], [])
                if gap["reason"] != outcome["expected_gap_reason"]
            )
            if candidates:
                linked = candidates[-1]
                link_status = "candidate_preceding_same_market_gap"
                outcome["other_prior_same_market_gap_count"] = other_reason_prior_count
            elif reference["ordinal"] > latest_indexed_ordinal:
                link_status = "termination_after_indexed_prefix"
                outcome["other_prior_same_market_gap_count"] = other_reason_prior_count
            else:
                link_status = "no_prior_same_market_gap_in_indexed_prefix"
                outcome["other_prior_same_market_gap_count"] = other_reason_prior_count

        outcome["link_status"] = link_status
        if linked is not None:
            outcome["matched_gap"] = {
                "ordinal": linked["ordinal"],
                "received_ns": linked["received_ns"],
                "reason": linked["reason"],
                "segment_index": linked["segment_index"],
                "segment_file": linked["segment_file"],
                "segment_sha256": linked["segment_sha256"],
                "market_id": outcome["market_id"],
                "age_to_termination_source_ns": reference["received_ns"] - linked["received_ns"],
            }
            matched_gap_ordinals.add(linked["ordinal"])
            if link_status == "candidate_preceding_same_market_gap":
                candidate_gap_ordinals.add(linked["ordinal"])
                candidate_gap_ages_ns.append(reference["received_ns"] - linked["received_ns"])
            elif link_status == "exact_recorded_gap_reference_verified_and_indexed":
                exact_gap_ordinals.add(linked["ordinal"])
        else:
            outcome["matched_gap"] = None
        link_counts[link_status] += 1
        by_horizon_link.setdefault(str(outcome["horizon_ms"]), Counter())[link_status] += 1

    # A scheduled gap-detail batch may have advanced while the rows were read.
    # Requiring identical sealed tails makes the join an atomic prefix snapshot.
    summary_after = read_finalized_gap_detail_summary(gap_detail_root)
    state_after = _read_sealed(
        gap_detail_root / "gap-detail-state-v1.json",
        maximum=MAX_STATE_BYTES,
        key="state_sha256",
        label="gap-detail state",
    )
    if (
        summary_after is None
        or summary_after.get("summary_sha256") != gap_snapshot["summary"].get("summary_sha256")
        or state_after.get("state_sha256") != gap_snapshot["state"].get("state_sha256")
    ):
        raise ValueError("Gap-detail prefix changed while attribution audit was running")

    summary = gap_snapshot["summary"]
    prefix_complete = summary.get("pending_segment_count") == 0
    age_bands = {
        "0_to_1s": sum(age <= 1_000_000_000 for age in candidate_gap_ages_ns),
        "1_to_60s": sum(1_000_000_000 < age <= 60_000_000_000 for age in candidate_gap_ages_ns),
        "60_to_300s": sum(60_000_000_000 < age <= 300_000_000_000 for age in candidate_gap_ages_ns),
        "300_to_3600s": sum(
            300_000_000_000 < age <= 3_600_000_000_000 for age in candidate_gap_ages_ns
        ),
        "over_3600s": sum(age > 3_600_000_000_000 for age in candidate_gap_ages_ns),
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "analysis_version": VERSION,
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "verified_complete_prefix" if prefix_complete else "verified_partial_prefix",
        "campaign": {
            "campaign_id": campaign_id,
            "campaign_plan_sha256": plan_sha256,
            "start_ns": start_ns,
            "end_ns": end_ns,
        },
        "gap_detail_index": {
            "analysis_version": summary["analysis_version"],
            "analysis_code_sha256": summary.get("analysis_code_sha256"),
            "analysis_code_files_verified": True,
            "summary_sha256": summary.get("summary_sha256"),
            "state_sha256": gap_snapshot["state"].get("state_sha256"),
            "prefix_catalog_sha256": summary.get("prefix_catalog_sha256"),
            "last_event_chain_sha256": summary.get("last_event_chain_sha256"),
            "processed_segment_count": summary.get("processed_segment_count"),
            "catalog_segment_count": summary.get("catalog_segment_count"),
            "pending_segment_count": summary.get("pending_segment_count"),
            "pending_source_bytes": summary.get("pending_source_bytes"),
            "last_processed_ordinal": summary.get("last_processed_ordinal"),
            "indexed_campaign_gap_events": summary.get("campaign_window_gap_event_count"),
            "indexed_event_files_verified": summary.get("processed_segment_count"),
            "indexed_event_bytes_hashed": gap_snapshot["indexed_event_bytes"],
            "indexed_campaign_window": summary.get("campaign_window_ns"),
            "active_segment_read": False,
            "complete": prefix_complete,
        },
        "query": {
            "censored_outcome_limit": limit,
            "censored_outcomes_scanned": scanned,
            "gap_censored_outcomes": len(outcomes),
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
        "source_verification": {
            "active_open_segments_read": False,
            "finalized_segment_byte_limit": max_source_bytes,
            "unique_finalized_segments_verified": len(segment_hashes),
            "finalized_segment_bytes_hashed": segment_bytes,
            "unique_source_records_verified": len(references),
            "exact_source_references_verified": True,
        },
        "gap_censors": {
            "outcomes_by_reason": dict(sorted(by_reason.items())),
            "outcomes_by_horizon_ms": {
                horizon: dict(sorted(reasons.items()))
                for horizon, reasons in sorted(by_horizon.items(), key=lambda item: int(item[0]))
            },
            "link_status_counts": dict(sorted(link_counts.items())),
            "link_status_by_horizon_ms": {
                horizon: dict(sorted(statuses.items()))
                for horizon, statuses in sorted(
                    by_horizon_link.items(), key=lambda item: int(item[0])
                )
            },
            "unique_gap_events_linked": len(matched_gap_ordinals),
            "unique_candidate_preceding_gap_events": len(candidate_gap_ordinals),
            "unique_exact_recorded_gap_events_indexed": len(exact_gap_ordinals),
            "candidate_preceding_gap_age_bands_to_termination_receiver_time_ns": age_bands,
            "same_market_preceding_gap_is_causal_proof": False,
        },
        "outcomes": outcomes,
        "limitations": [
            "The indexed gap prefix is incomplete; unmatched outcomes beyond its last ordinal remain unresolved.",
            "A preceding same-market gap with a matching reason is a temporal candidate link, not proof of direct causality or continuous book impairment.",
            "Gap receiver time is Reality recorder time, not an exchange quote timestamp.",
            "Gap-detail event files and their prefix chains are verified; this audit does not rehash every indexed raw source segment.",
            "The read-only SQLite event hash chain and full database integrity were not reverified.",
            "No source gap or public mark establishes order arrival, fills, or profitability.",
        ],
    }
    report["result_sha256"] = _canonical_sha(report)
    return report
