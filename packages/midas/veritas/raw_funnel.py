"""Aggregate a campaign-period market opportunity funnel from finalized raw records."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from midas.reality.execution_research import fee_rate
from midas.reality.foundry import source_records
from midas.reality.research_measurements import pair_quality
from midas.reality.research_schema import digest
from midas.reality.shadow_campaign import verify as verify_campaign
from midas.reality.shadow_source import Context
from midas.reality.shadow_worker import spec_for
from midas.reality.storage import manifest

from .economics import walk_asks

D = Decimal
BLOCK_NS = 300 * 10**9
MAX_SOURCE_BYTES = 20 * 1024**3
MAX_EDGE_BINS = 50_000


def _market_counters() -> Counter[str]:
    return Counter()


def _edge_summary(histogram: Counter[str]) -> dict[str, Any] | None:
    if not histogram:
        return None
    values = sorted((D(value), count) for value, count in histogram.items())
    total = sum(count for _, count in values)

    def nearest_rank(fraction: Decimal) -> str:
        target = max(1, int((fraction * total).to_integral_value(rounding=ROUND_CEILING)))
        cumulative = 0
        for value, count in values:
            cumulative += count
            if cumulative >= target:
                return str(value)
        raise AssertionError("Edge histogram count is inconsistent")

    return {
        "count": total,
        "minimum": str(values[0][0]),
        "p25_nearest_rank": nearest_rank(D("0.25")),
        "median_nearest_rank": nearest_rank(D("0.50")),
        "p75_nearest_rank": nearest_rank(D("0.75")),
        "maximum": str(values[-1][0]),
        "positive_count": sum(count for value, count in values if value > 0),
    }


def analyze_raw_opportunity_funnel(
    campaign_root: Path,
    *,
    max_source_bytes: int = MAX_SOURCE_BYTES,
) -> dict[str, Any]:
    """Summarize every touched paired market state in a frozen campaign window.

    The source time is the recorded receiver timestamp, not offline wall time.
    Repeated frame states are correlated observations. This audit reports no
    fill, execution probability, or realized economic result.
    """
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

    raw_root = Path(identity["raw_root"]).resolve()
    source_manifest = manifest(raw_root)
    segments = source_manifest["segments"]
    if any(
        not isinstance(info.get("file"), str) or not info["file"].endswith(".seg")
        for info in segments
    ):
        raise ValueError("Source manifest contains a non-finalized segment")
    source_bytes = sum(int(info["bytes"]) for info in segments)
    if source_bytes > max_source_bytes:
        raise ValueError("Finalized source snapshot exceeds its byte bound")
    last_ordinal = max((int(info["last"]) for info in segments), default=0)

    spec = spec_for(plan)
    quantity = D(identity["quantity"])
    start_ns, end_ns = identity["start_ns"], identity["end_ns"]
    context = Context()
    record_kinds: Counter[str] = Counter()
    period_record_kinds: Counter[str] = Counter()
    gap_reasons: Counter[str] = Counter()
    quality_reasons: Counter[str] = Counter()
    market_data: dict[str, dict[str, Any]] = {}
    condition_blocks: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    edge_histogram: Counter[str] = Counter()
    engine_checkpoints = 0
    replayed_records = 0
    period_frames = 0
    excluded_producer_frames = 0
    excluded_reconstruction_frames = 0
    clock_regression_frames = 0
    touched_states = 0
    valid_states = 0
    positive_top_states = 0
    complete_quantity_states = 0
    positive_top_complete_quantity_states = 0
    positive_depth_pre_fee_states = 0
    positive_depth_minimum_notional_satisfied_states = 0
    known_fee_regime_states = 0
    unknown_fee_regime_states = 0
    first_period_ns: int | None = None
    last_period_ns: int | None = None

    for record, ref in source_records(raw_root, source_manifest):
        replayed_records += 1
        record_kinds[record["kind"]] += 1
        if record["kind"] == "checkpoint":
            engine_checkpoints += 1
        now = record["received_ns"]
        in_period = start_ns <= now < end_ns
        if in_period:
            period_record_kinds[record["kind"]] += 1
            first_period_ns = now if first_period_ns is None else min(first_period_ns, now)
            last_period_ns = now if last_period_ns is None else max(last_period_ns, now)
            if record["kind"] == "gap":
                gap_reasons[record["payload"].get("reason", "unknown")] += 1

        barrier = context.consume(record, ref)
        if record["kind"] != "discovery":
            # This funnel does not consume rolling trade or quote history.
            context.history.clear()
            context.trades.clear()
        if not in_period or record["kind"] != "frame":
            context.refs.clear()
            continue

        period_frames += 1
        if context.producer_hash not in identity["allowed_producer_hashes"]:
            excluded_producer_frames += 1
            context.refs.clear()
            continue
        if context.engine.reconstruction_version not in identity["allowed_reconstruction_versions"]:
            excluded_reconstruction_frames += 1
            context.refs.clear()
            continue
        if barrier == "receiver_clock_regression":
            clock_regression_frames += 1

        block_start = (now // BLOCK_NS) * BLOCK_NS
        for condition, market in context.cohort.items():
            tokens = list(market["tokens"])
            if not any(
                token in context.engine.books
                and context.engine.books[token]["last"][0] == record["ordinal"]
                for token in tokens
            ):
                continue

            market_id = str(market["id"])
            item = market_data.setdefault(
                condition,
                {
                    "market_id": market_id,
                    "condition": condition,
                    "family_id": None,
                    "states": _market_counters(),
                    "quality_reasons": Counter(),
                    "edge_histogram": Counter(),
                },
            )
            state_counts: Counter[str] = item["states"]
            touched_states += 1
            state_counts["touched_market_frame_states"] += 1
            block = condition_blocks[(condition, block_start)]
            block["touched_market_frame_states"] += 1

            reason = pair_quality(market, context.engine.books, now, spec)
            if reason is None and any(token in context.bad for token in tokens):
                reason = "independent_book_divergence"
            if reason is not None:
                quality_reasons[reason] += 1
                item["quality_reasons"][reason] += 1
                state_counts["quality_invalid_states"] += 1
                block["quality_invalid_states"] += 1
                continue

            valid_states += 1
            state_counts["quality_valid_states"] += 1
            block["quality_valid_states"] += 1
            books = [context.engine.books[token] for token in tokens]
            best_asks = [min(book["asks"]) for book in books]
            top_edge = Decimal(1) - sum(best_asks, Decimal(0))
            edge_key = str(top_edge)
            edge_histogram[edge_key] += 1
            item["edge_histogram"][edge_key] += 1
            if len(edge_histogram) > MAX_EDGE_BINS:
                raise ValueError("Distinct raw edge values exceeded the histogram bound")

            if top_edge > 0:
                positive_top_states += 1
                state_counts["positive_top_ask_pair_states"] += 1
                block["positive_top_ask_pair_states"] += 1

            walks = [
                walk_asks(
                    [[str(price), str(size)] for price, size in sorted(book["asks"].items())],
                    quantity,
                )
                for book in books
            ]
            depth_complete = all(bool(walk["complete_at_requested_quantity"]) for walk in walks)
            if depth_complete:
                complete_quantity_states += 1
                state_counts["quantity_depth_complete_states"] += 1
                block["quantity_depth_complete_states"] += 1
                acquisition = sum(
                    (D(walk["displayed_notional_for_supported_quantity"]) for walk in walks),
                    Decimal(0),
                )
                depth_edge = quantity - acquisition
                minimum = market.get("minimum_order_size")
                try:
                    minimum_notional = D(str(minimum))
                    minimum_notional_satisfied = (
                        minimum_notional.is_finite() and minimum_notional > 0
                    )
                    minimum_notional_satisfied = minimum_notional_satisfied and all(
                        D(walk["displayed_notional_for_supported_quantity"]) >= minimum_notional
                        for walk in walks
                    )
                except (ArithmeticError, TypeError, ValueError):
                    minimum_notional_satisfied = False
                if top_edge > 0:
                    positive_top_complete_quantity_states += 1
                    state_counts["positive_top_with_quantity_depth_states"] += 1
                    block["positive_top_with_quantity_depth_states"] += 1
                if depth_edge > 0:
                    positive_depth_pre_fee_states += 1
                    state_counts["positive_full_depth_pre_fee_states"] += 1
                    block["positive_full_depth_pre_fee_states"] += 1
                    if minimum_notional_satisfied:
                        positive_depth_minimum_notional_satisfied_states += 1
                        state_counts["positive_full_depth_minimum_notional_satisfied_states"] += 1
                        block["positive_full_depth_minimum_notional_satisfied_states"] += 1

            rate = fee_rate({"market": {"fee_regime": market.get("fee_regime")}})
            if rate is None:
                unknown_fee_regime_states += 1
                state_counts["fee_regime_unavailable_states"] += 1
            else:
                known_fee_regime_states += 1
                state_counts["fee_regime_available_states"] += 1

        context.refs.clear()

    if len(edge_histogram) > MAX_EDGE_BINS:
        raise ValueError("Distinct raw edge values exceeded the histogram bound")

    final_family_map = context.families.identities()
    markets = []
    for condition, item in sorted(
        market_data.items(), key=lambda pair: (pair[1]["market_id"], pair[0])
    ):
        item["family_id"] = final_family_map.get("condition:" + condition)
        markets.append(
            {
                "market_id": item["market_id"],
                "condition": condition,
                "family_id": item["family_id"],
                "counts": dict(sorted(item["states"].items())),
                "quality_reasons": dict(sorted(item["quality_reasons"].items())),
                "pre_fee_top_edge_distribution": _edge_summary(item["edge_histogram"]),
            }
        )
    family_blocks: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    for (condition, block_start), counts in condition_blocks.items():
        family_id = final_family_map.get("condition:" + condition, "unassigned")
        family_blocks[(family_id, block_start)].update(counts)
    blocks = [
        {
            "family_id": family_id,
            "block_start_ns": block_start,
            "counts": dict(sorted(counts.items())),
        }
        for (family_id, block_start), counts in sorted(family_blocks.items())
    ]

    captured_ns = time.time_ns()
    return {
        "analysis_version": "veritas-raw-opportunity-funnel-v2",
        "captured_at_utc": datetime.fromtimestamp(captured_ns / 10**9, UTC).isoformat(
            timespec="microseconds"
        ),
        "captured_ns": captured_ns,
        "campaign_id": campaign_id,
        "source_root": str(raw_root),
        "source_manifest_sha256": digest(source_manifest),
        "source_segments": len(segments),
        "source_bytes": source_bytes,
        "source_last_finalized_ordinal": last_ordinal,
        "active_segment_read": False,
        "raw_records_replayed": replayed_records,
        "record_kinds": dict(sorted(record_kinds.items())),
        "verified_source_checkpoints": engine_checkpoints,
        "campaign_window_ns": {"start": start_ns, "end_exclusive": end_ns},
        "source_receipt_window_ns": {"first": first_period_ns, "last": last_period_ns},
        "period_record_kinds": dict(sorted(period_record_kinds.items())),
        "gap_reasons_in_window": dict(sorted(gap_reasons.items())),
        "period_frame_records": period_frames,
        "frames_excluded_unsupported_producer": excluded_producer_frames,
        "frames_excluded_unsupported_reconstruction": excluded_reconstruction_frames,
        "receiver_clock_regression_frames": clock_regression_frames,
        "touched_market_frame_states": touched_states,
        "quality_valid_states": valid_states,
        "quality_invalid_reason_counts": dict(sorted(quality_reasons.items())),
        "positive_top_ask_pair_states": positive_top_states,
        "quantity_requested": str(quantity),
        "quantity_depth_complete_states": complete_quantity_states,
        "positive_top_with_quantity_depth_states": positive_top_complete_quantity_states,
        "positive_full_depth_pre_fee_states": positive_depth_pre_fee_states,
        "positive_full_depth_minimum_notional_satisfied_states": positive_depth_minimum_notional_satisfied_states,
        "fee_regime_available_states": known_fee_regime_states,
        "fee_regime_unavailable_states": unknown_fee_regime_states,
        "pre_fee_top_edge_distribution": _edge_summary(edge_histogram),
        "family_five_minute_blocks": blocks,
        "markets": markets,
        "limitations": [
            "Source receiver time is used for frame states; offline replay time and worker processing lag are not reconstructed.",
            "Counts are repeated market-frame observations, not independent opportunities or venue-wide prevalence.",
            "Displayed depth is public quote support only; it does not establish order arrival, matching, fills, or market impact.",
            "Full-depth values are pre-fee; fee regime availability is counted but no fee or settlement assumption is applied here.",
            "Minimum order requirements are checked against each leg's displayed USDC notional, not share quantity.",
            "Only cataloged finalized segments are included; an active segment is excluded.",
        ],
    }
