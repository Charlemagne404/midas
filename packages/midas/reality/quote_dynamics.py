"""Receipt-observed quote spells, right-censored at every known quality barrier."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .foundry import source_records
from .reconstruction import Engine


def collect(manifest: dict[str, Any], conditions: set[str]) -> dict[str, Any]:
    engine = Engine()
    end = manifest["boundaries"]["train_end_ns"]
    freshness = manifest["identity"]["spec"]["max_freshness_ms"] * 10**6
    spells: dict[str, dict[str, Any]] = {}
    completed: list[float] = []
    censored: list[float] = []
    spread_changes: list[float] = []
    depth_changes: list[float] = []
    intervals: list[float] = []
    reasons: Counter[str] = Counter()
    comparisons_bad: set[str] = set()
    producer = None
    processed = checkpoints = 0
    previous_clock: tuple[int, int] | None = None

    def close(asset: str, now: int, reason: str | None) -> None:
        prior = spells.pop(asset)
        # A stale spell can be observed only through its freshness boundary.
        until = min(now, prior["receipt"] + freshness)
        duration = max(0, until - prior["start"]) / 10**6
        if reason:
            censored.append(duration)
            reasons[reason] += 1
        else:
            completed.append(duration)

    for record, _ in source_records(
        Path(manifest["source_root"]), manifest["identity"]["source_manifest"]
    ):
        now = record["received_ns"]
        if now >= end:
            break
        processed += 1
        kind = record["kind"]
        if kind == "checkpoint":
            if engine.digest() != record["payload"]["state_sha256"]:
                raise ValueError("Quote dynamics checkpoint mismatch")
            checkpoints += 1
        barrier = None
        if (
            kind == "frame"
            and previous_clock
            and (now < previous_clock[0] or record["monotonic_ns"] < previous_clock[1])
        ):
            barrier = "receiver_clock_regression"
        if kind == "frame":
            previous_clock = (now, record["monotonic_ns"])
        if kind == "gap":
            barrier = "recorded_gap"
            comparisons_bad.clear()
            previous_clock = None
            if record["payload"].get("reason") == "process_start":
                producer = record["payload"].get("implementation_sha256")
        if barrier:
            for asset in list(spells):
                close(asset, now, barrier)
        engine.consume(record)
        now = engine.now_ns
        if kind == "book_comparison":
            assessment = record["payload"]
            asset = assessment.get("asset_id")
            if asset and assessment["assessment"] == "stable_local_lineage_divergence":
                comparisons_bad.add(asset)
            elif asset and assessment["assessment"] == "stable_local_lineage_match_unsequenced":
                comparisons_bad.discard(asset)
        for asset in list(spells):
            book = engine.books.get(asset)
            if book is None or engine.tokens.get(asset) not in conditions:
                close(asset, now, "retired_or_excluded")
            elif now - spells[asset]["receipt"] > freshness:
                close(asset, now, "stale")
            elif book["issue"] or book.get("timing_uncertainty") or asset in comparisons_bad:
                close(asset, now, "book_quality_or_comparison")
            elif (
                book["snapshot"] != spells[asset]["snapshot"]
                or book["tick"] != spells[asset]["tick"]
            ):
                close(asset, now, "snapshot_or_tick_reset")
        for asset, book in engine.books.items():
            if (
                not producer
                or engine.tokens.get(asset) not in conditions
                or book["issue"]
                or book.get("timing_uncertainty")
                or asset in comparisons_bad
                or now - book["received_ns"] > freshness
            ):
                continue
            if book["last"][0] != record["ordinal"]:
                continue
            ask = min(book["asks"]) if book["asks"] else None
            bid = max(book["bids"]) if book["bids"] else None
            spread = float(ask - bid) if ask is not None and bid is not None else None
            depth = float(sum(book["asks"].values()))
            prior = spells.get(asset)
            if prior:
                if book["received_ns"] > prior["receipt"]:
                    intervals.append((book["received_ns"] - prior["receipt"]) / 10**6)
                    depth_changes.append(depth - prior["depth"])
                    if spread is not None and prior["spread"] is not None:
                        spread_changes.append(spread - prior["spread"])
                if ask != prior["ask"]:
                    close(asset, now, None)
                    prior = None
            if ask is None:
                continue
            spells[asset] = dict(
                start=prior["start"] if prior else now,
                ask=ask,
                receipt=book["received_ns"],
                snapshot=book["snapshot"],
                tick=book["tick"],
                depth=depth,
                spread=spread,
            )
        if len(completed) + len(censored) + len(intervals) > 500000:
            raise ValueError("Quote-dynamics derivative memory bound exceeded")
    for asset in list(spells):
        close(asset, end, "training_boundary")
    return dict(
        records=processed,
        verified_checkpoints=checkpoints,
        conditions=len(conditions),
        completed_quote_spells_ms=completed,
        right_censored_quote_spells_ms=censored,
        censor_reasons=dict(reasons),
        spread_changes=spread_changes,
        aggregate_ask_depth_changes=depth_changes,
        update_intervals_ms=intervals,
        definition="Receiver-observed best-ask spells within valid unsequenced lineage; snapshot/tick/gap/quality/staleness barriers censor. Changes within one raw frame are unresolved. Not venue lifetimes or same-order survival.",
    )
