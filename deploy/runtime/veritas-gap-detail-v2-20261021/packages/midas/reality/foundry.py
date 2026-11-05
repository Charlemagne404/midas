"""Immutable, bounded research datasets from finalized public recording prefixes.

The builder owns only its derivative root, never the recording writer lock.
Future observations are used exclusively by the label follower after features
and decision lineage have been frozen. A missing later observation is censored.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import time
import uuid
from collections import Counter, deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .reconstruction import Engine
from .research_measurements import (
    book_view,
    censor,
    effective_tick,
    example_identity,
    features,
    labels,
    pair_quality,
)
from .research_schema import (
    BUILDER_VERSION,
    FEATURE_VERSION,
    LABEL_VERSION,
    LIMITATIONS,
    DatasetSpec,
    digest,
)
from .storage import MAGIC, atomic_json, canonical, file_hash, manifest, records, sync_dir


def code_identity() -> dict[str, str]:
    directory = Path(__file__).parent
    return {
        name: file_hash(directory / name)
        for name in (
            "foundry.py",
            "research_schema.py",
            "research_measurements.py",
            "research_validation.py",
            "reconstruction.py",
            "storage.py",
        )
    }


def source_records(
    root: Path, value: dict[str, Any]
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    if value.get("schema_version") != 1 or value.get("format") != "midas-reality-framed-zlib-v1":
        raise ValueError("Unsupported raw source manifest")
    previous = 0
    for info in value["segments"]:
        if Path(info["file"]).name != info["file"]:
            raise ValueError("Unsafe source segment path")
        path = root / info["file"]
        if (
            path.is_symlink()
            or file_hash(path) != info["sha256"]
            or path.stat().st_size != info["bytes"]
        ):
            raise ValueError("Source segment integrity mismatch")
        first = last = count = 0
        kinds: Counter[str] = Counter()
        offset = len(MAGIC)
        with path.open("rb") as headers:
            for record, end in records(path):
                if record["ordinal"] != previous + 1:
                    raise ValueError("Source ordinal contamination")
                if count == 0:
                    first = record["ordinal"]
                previous = last = record["ordinal"]
                count += 1
                kinds[record["kind"]] += 1
                headers.seek(offset + 4)
                compressed_sha256 = headers.read(32).hex()
                ref = dict(
                    segment=info["file"],
                    segment_sha256=info["sha256"],
                    ordinal=record["ordinal"],
                    offset=offset,
                    end_offset=end,
                    compressed_record_sha256=compressed_sha256,
                    canonical_record_sha256=digest(record),
                    received_ns=record["received_ns"],
                    monotonic_ns=record["monotonic_ns"],
                )
                offset = end
                yield record, ref
        if (first, last, count, dict(kinds)) != (
            info["first"],
            info["last"],
            info["count"],
            info["kinds"],
        ):
            raise ValueError("Raw source catalog metadata mismatch")


def family_keys(market: dict[str, Any]) -> list[str]:
    return sorted(
        set(
            ["condition:" + market["condition"]]
            + ["event:" + str(x) for x in market.get("event_ids", [])]
            + (
                ["negative_risk:" + market["negative_risk_group"]]
                if market.get("negative_risk_group")
                else []
            )
        )
    )


def chronological_partition(
    row: dict[str, Any], boundaries: dict[str, int], spec: DatasetSpec
) -> str:
    start, end = row["feature_window_start_ns"], row["label_window_end_ns"]
    train_end, validation_end = boundaries["train_end_ns"], boundaries["validation_end_ns"]
    embargo = spec.embargo_ms * 10**6
    if end < train_end:
        return "train"
    if start >= train_end + embargo and end < validation_end:
        return "validation"
    if start >= validation_end + embargo:
        return "test"
    return "embargoed"


def examples(
    root: Path, value: dict[str, Any], spec: DatasetSpec, counters: Counter[str]
) -> Iterator[dict[str, Any]]:
    engine = Engine()
    refs: dict[int, dict[str, Any]] = {}
    cohort: dict[str, dict[str, Any]] = {}
    metadata_refs: dict[str, dict[str, Any]] = {}
    fee_refs: dict[str, dict[str, Any]] = {}
    tick_refs: dict[str, dict[str, Any]] = {}
    history: dict[str, deque[dict[str, Any]]] = {}
    trades: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    next_decision: dict[str, int] = {}
    comparison_bad: set[str] = set()
    producer_ref = None
    producer_hash = None
    previous_frame_utc = previous_frame_mono = None
    source_id = digest(value)
    made = 0
    stop_sampling = False

    def finish(
        item: dict[str, Any], result: dict[str, Any], end_ref: dict[str, Any] | None
    ) -> dict[str, Any]:
        row: dict[str, Any] = item["row"]
        row["labels"] = result
        row["label_source"] = dict(termination_ref=end_ref, future_book_refs=None)
        if result["status"] == "observed_public_measurement":
            row["label_source"]["future_book_refs"] = {
                name: {key: refs[books[key][0]] for key in ("snapshot", "last")}
                for name, books in item["future_views"].items()
            }
            row["observed_future_received_ns"] = {
                name: b["received_ns"] for name, b in item["future_views"].items()
            }
            row["effective_delays_ms"] = {
                name: (b["received_ns"] - row["decision_ns"]) / 10**6
                for name, b in item["future_views"].items()
            }
        counters["examples"] += 1
        counters["label:" + result["status"]] += 1
        if result.get("reason"):
            counters["censor:" + result["reason"]] += 1
        return row

    for record, ref in source_records(root, value):
        counters["raw_records"] += 1
        refs[record["ordinal"]] = ref
        kind = record["kind"]
        if kind == "checkpoint" and engine.digest() != record["payload"]["state_sha256"]:
            raise ValueError("Source online checkpoint mismatch")
        if kind == "checkpoint":
            counters["verified_checkpoints"] += 1
        if kind == "gap" and record["payload"].get("reason") == "process_start":
            producer_ref = ref
            producer_hash = record["payload"].get("implementation_sha256")
        if kind == "public_market_metadata":
            metadata_refs[record["market_id"]] = ref
        elif kind == "public_fee_metadata":
            fee_refs[record["asset_id"]] = ref
        elif kind == "snapshot_constraints":
            tick_refs[record["payload"]["asset_id"]] = ref
        barrier = None
        if kind == "frame":
            if (previous_frame_utc is not None and record["received_ns"] < previous_frame_utc) or (
                previous_frame_mono is not None and record["monotonic_ns"] < previous_frame_mono
            ):
                barrier = "receiver_clock_regression"
            previous_frame_utc, previous_frame_mono = record["received_ns"], record["monotonic_ns"]
        if kind == "gap":
            barrier = "recorded_gap:" + record["payload"]["reason"]
            comparison_bad.clear()
            history.clear()
            trades.clear()
            next_decision.clear()
            previous_frame_utc = previous_frame_mono = None
        engine.consume(record)
        now = engine.now_ns
        if kind == "discovery":
            cohort = {m["condition"]: m for m in record["cohort"]}
            for market in cohort.values():
                market["discovery_ref"] = ref
            active = set(engine.tokens)
            fee_refs = {t: r for t, r in fee_refs.items() if t in active}
            tick_refs = {t: r for t, r in tick_refs.items() if t in active}
            metadata_refs = {
                m["id"]: metadata_refs[m["id"]] for m in cohort.values() if m["id"] in metadata_refs
            }
        if kind == "book_comparison":
            assessment = record["payload"]
            token = assessment.get("asset_id")
            if token and assessment["assessment"] == "stable_local_lineage_divergence":
                comparison_bad.add(token)
            elif token and assessment["assessment"] == "stable_local_lineage_match_unsequenced":
                comparison_bad.discard(token)
        if kind == "frame":
            for token, book in engine.books.items():
                if book["last"][0] == record["ordinal"] and book["issue"] is None:
                    view = book_view(book, now)
                    queue = history.setdefault(token, deque(maxlen=10000))
                    queue.append(
                        dict(
                            received_ns=record["received_ns"],
                            best_ask=view["best_ask"],
                            ask_quantity=view["total_ask_quantity"],
                            ref=ref,
                        )
                    )
                    if book["snapshot"][0] == record["ordinal"]:
                        comparison_bad.discard(token)
            try:
                native = json.loads(record["payload"])
                for event in native if isinstance(native, list) else [native]:
                    if (
                        isinstance(event, dict)
                        and event.get("event_type") == "last_trade_price"
                        and event.get("asset_id") in engine.tokens
                    ):
                        trades[event["asset_id"]] = dict(
                            price=event.get("price"),
                            size=event.get("size"),
                            received_ns=record["received_ns"],
                            ref=ref,
                        )
            except (ValueError, TypeError):
                pass
        for queue in history.values():
            while queue and queue[0]["received_ns"] < now - spec.lookback_ms * 10**6:
                queue.popleft()
        remaining = []
        for item in pending:
            market = item["market"]
            quality = pair_quality(market, engine.books, now, spec, allow_empty_asks=True)
            if now > item["deadline_ns"]:
                yield finish(item, censor("future_observation_unavailable", disrupted=None), ref)
            elif barrier:
                yield finish(item, censor(barrier, disrupted=True), ref)
            elif market["condition"] not in cohort:
                yield finish(item, censor("market_left_cohort", disrupted=True), ref)
            elif any(t in comparison_bad for t in market["tokens"]):
                yield finish(item, censor("independent_book_divergence", disrupted=True), ref)
            elif quality is not None:
                yield finish(
                    item,
                    censor(
                        quality, disrupted=None if quality == "reported_expiry_reached" else True
                    ),
                    ref,
                )
            elif any(
                effective_tick(market, engine.books[t]) != item["ticks"][t]
                for t in market["tokens"]
            ):
                yield finish(item, censor("tick_regime_changed", disrupted=True), ref)
            elif kind == "frame" and all(
                engine.books[t]["received_ns"] >= item["target_ns"] for t in market["tokens"]
            ):
                item["future_views"] = {
                    o.lower(): book_view(engine.books[t], now) for t, o in market["tokens"].items()
                }
                yield finish(item, labels(item["baseline"], item["future_views"]), ref)
            else:
                remaining.append(item)
        pending = remaining
        if kind != "frame" or barrier or stop_sampling:
            continue
        if spec.start_ns is not None and now < spec.start_ns:
            continue
        if spec.end_ns is not None and now > spec.end_ns:
            stop_sampling = True
            continue
        for condition, market in sorted(cohort.items()):
            if now < next_decision.get(condition, 0):
                continue
            next_decision[condition] = now + spec.stride_ms * 10**6
            if not producer_hash or not re.fullmatch(r"[0-9a-f]{64}", producer_hash):
                counters["excluded:producer_source_unknown"] += 1
                continue
            quality = pair_quality(market, engine.books, now, spec)
            if quality is None and any(t in comparison_bad for t in market["tokens"]):
                quality = "independent_book_divergence"
            if quality:
                counters["excluded:" + quality] += 1
                continue
            source_refs = {
                "decision": ref,
                "discovery": market["discovery_ref"],
                "producer": producer_ref,
                "market_metadata": metadata_refs.get(market["id"]),
                "legs": {},
            }
            rolling_refs = []
            for t, o in market["tokens"].items():
                book = engine.books[t]
                source_refs["legs"][o.lower()] = {
                    key: refs[book[key][0]] for key in ("snapshot", "last")
                }
                source_refs["legs"][o.lower()]["tick"] = tick_refs.get(t)
                source_refs["legs"][o.lower()]["fee"] = fee_refs.get(t)
                rolling_refs.extend([p["ref"] for p in history.get(t, [])])
                trade = trades.get(t)
                if trade and trade["received_ns"] >= now - spec.lookback_ms * 10**6:
                    rolling_refs.append(trade["ref"])
            source_refs["rolling_window"] = list({r["ordinal"]: r for r in rolling_refs}.values())
            all_sources = list(walk_refs(source_refs))
            if any(r["ordinal"] > record["ordinal"] or r["received_ns"] > now for r in all_sources):
                raise ValueError("Future source reference in historical features")
            feature, baseline = features(
                market,
                engine.books,
                decision_ns=now,
                spec=spec,
                history={t: list(q) for t, q in history.items()},
                trades=trades,
            )
            temporal = (
                [ref]
                + rolling_refs
                + [
                    r
                    for leg in source_refs["legs"].values()
                    for key, r in leg.items()
                    if key in {"snapshot", "last"} and r is not None
                ]
            )
            for horizon in spec.horizons_ms:
                if made >= spec.max_examples:
                    stop_sampling = True
                    counters["bounded_example_limit_reached"] += 1
                    break
                made += 1
                target = now + horizon * 10**6
                deadline = target + spec.tolerance_ms(horizon) * 10**6
                row = dict(
                    schema_version=1,
                    id=example_identity(
                        source_id, market, record["ordinal"], horizon, spec.quantity
                    ),
                    decision_ordinal=record["ordinal"],
                    decision_ns=now,
                    decision_monotonic_ns=record["monotonic_ns"],
                    source_id=source_id,
                    producer_implementation_sha256=producer_hash,
                    reconstruction_version=engine.reconstruction_version,
                    feature_version=FEATURE_VERSION,
                    label_version=LABEL_VERSION,
                    horizon_ms=horizon,
                    future_tolerance_ms=spec.tolerance_ms(horizon),
                    feature_window_start_ns=min(r["received_ns"] for r in temporal),
                    label_window_end_ns=deadline,
                    market_id=market["id"],
                    condition=condition,
                    family_keys=family_keys(market),
                    day_utc=time.strftime("%Y-%m-%d", time.gmtime(now // 10**9)),
                    dependence_group=digest(
                        [source_id, family_keys(market), now // (spec.group_window_ms * 10**6)]
                    ),
                    features=feature,
                    feature_sha256=digest(feature),
                    feature_sources=source_refs,
                    hypothetical_context=dict(
                        quantity=spec.quantity,
                        capital=spec.hypothetical_capital,
                        unit="collateral_unit",
                        capital_is_not_market_fact=True,
                        orders_submitted=False,
                    ),
                    measurement_taxonomy=dict(
                        features="derived_public_measurements",
                        labels="derived_public_measurements",
                        actual_fills="unknown_counterfactual",
                        private_queue_position="unknown_counterfactual",
                    ),
                )
                pending.append(
                    dict(
                        row=row,
                        baseline=baseline,
                        market=market,
                        target_ns=target,
                        deadline_ns=deadline,
                        ticks={
                            t: effective_tick(market, engine.books[t]) for t in market["tokens"]
                        },
                    )
                )
        # Only retain references that can still be read by current books or rolling features.
        needed = {r["ordinal"] for q in history.values() for p in q for r in [p["ref"]]}
        needed.update(
            book[key][0] for book in engine.books.values() for key in ("snapshot", "last")
        )
        refs = {o: r for o, r in refs.items() if o in needed}
    for item in pending:
        yield finish(item, censor("source_prefix_ended", disrupted=None), None)


def walk_refs(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "canonical_record_sha256" in value:
            yield value
        else:
            for child in value.values():
                yield from walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_refs(child)


class Families:
    """Union all recorded event/condition/negative-risk aliases for isolation."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def root(self, key: str) -> str:
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def add(self, keys: list[str]) -> None:
        heads = sorted({self.root(key) for key in keys})
        for head in heads[1:]:
            self.parent[head] = heads[0]

    def identities(self) -> dict[str, str]:
        groups: dict[str, list[str]] = {}
        for key in self.parent:
            groups.setdefault(self.root(key), []).append(key)
        ids = {head: digest(sorted(keys)) for head, keys in groups.items()}
        return {key: ids[self.root(key)] for key in self.parent}


def build(
    root: Path, destination: Path, spec: DatasetSpec, source: dict[str, Any] | None = None
) -> dict[str, Any]:
    from .research_validation import verify_rows

    root, destination = root.resolve(), destination.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Derivatives must be separate from raw recordings")
    source = manifest(root) if source is None else source
    identity = dict(
        builder_version=BUILDER_VERSION,
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        spec=spec.dump(),
        source_manifest=source,
        code_sha256=code_identity(),
    )
    dataset_id = digest(identity)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "builder.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another dataset builder owns this derivative root") from None
        final = destination / dataset_id
        if final.exists():
            result: dict[str, Any] = json.loads((final / "manifest.json").read_text())
            if (
                result["identity"] != json.loads(canonical(identity))
                or file_hash(final / "examples.jsonl") != result["rows_sha256"]
            ):
                raise ValueError("Immutable dataset artifact corruption")
            verify_rows(final / "examples.jsonl", result)
            return result
        temp = destination / (".building-" + uuid.uuid4().hex)
        temp.mkdir(mode=0o700)
        counters: Counter[str] = Counter()
        start = time.monotonic()
        first = last = None
        used = 0
        families = Families()
        existing_bytes = sum(p.stat().st_size for p in destination.rglob("*") if p.is_file())
        try:
            with (temp / "unpartitioned.jsonl").open("wb") as output:
                for row in examples(root, source, spec, counters):
                    first = row["decision_ns"] if first is None else min(first, row["decision_ns"])
                    last = row["decision_ns"] if last is None else max(last, row["decision_ns"])
                    families.add(row["family_keys"])
                    encoded = canonical(row) + b"\n"
                    used += len(encoded)
                    if (
                        existing_bytes + used * 2 + 1024** 2 > spec.derivative_budget_bytes
                        or shutil.disk_usage(destination).free < spec.reserve_bytes + len(encoded)
                    ):
                        raise OSError(
                            "Derivative budget or disk reserve reached; raw originals preserved"
                        )
                    output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            span = (last - first) if first is not None and last is not None else 0
            boundaries = dict(
                train_end_ns=int(first + span * spec.train_fraction) if first is not None else 0,
                validation_end_ns=int(
                    first + span * (spec.train_fraction + spec.validation_fraction)
                )
                if first is not None
                else 0,
            )
            aliases = families.identities()
            family_ids = sorted(set(aliases.values()))
            heldout_families = (
                sorted(family_ids, key=lambda f: digest(["market-holdout-v1", f]))[
                    : max(1, len(family_ids) // 5)
                ]
                if len(family_ids) >= 3
                else []
            )
            group_partitions: dict[str, set[str]] = {}
            with (temp / "unpartitioned.jsonl").open() as rows:
                for line in rows:
                    row = json.loads(line)
                    group = digest(
                        [
                            row["source_id"],
                            aliases[row["family_keys"][0]],
                            row["decision_ns"] // (spec.group_window_ms * 10**6),
                        ]
                    )
                    partition = chronological_partition(row, boundaries, spec)
                    if partition != "embargoed":
                        group_partitions.setdefault(group, set()).add(partition)
            crossing_groups = {g for g, parts in group_partitions.items() if len(parts) > 1}
            partition_counts: Counter[str] = Counter()
            coverage: dict[str, Any] = {}
            with (
                (temp / "examples.jsonl").open("wb") as output,
                (temp / "unpartitioned.jsonl").open() as rows,
            ):
                for line in rows:
                    row = json.loads(line)
                    row["family_id"] = aliases[row["family_keys"][0]]
                    row["dependence_group"] = digest(
                        [
                            row["source_id"],
                            row["family_id"],
                            row["decision_ns"] // (spec.group_window_ms * 10**6),
                        ]
                    )
                    row["partition"] = chronological_partition(row, boundaries, spec)
                    if row["dependence_group"] in crossing_groups:
                        row["partition"] = "embargoed"
                    row["market_generalization_partition"] = (
                        "test"
                        if row["partition"] == "test" and row["family_id"] in heldout_families
                        else row["partition"]
                        if row["partition"] in {"train", "validation"}
                        and row["family_id"] not in heldout_families
                        else "excluded"
                    )
                    partition_counts[row["partition"]] += 1
                    group = coverage.setdefault(
                        row["partition"],
                        dict(
                            markets=set(),
                            families=set(),
                            days=set(),
                            groups=set(),
                            observed=0,
                            censored=0,
                        ),
                    )
                    group["markets"].add(row["market_id"])
                    group["families"].add(row["family_id"])
                    group["days"].add(row["day_utc"])
                    group["groups"].add(row["dependence_group"])
                    group[
                        "observed"
                        if row["labels"]["status"] == "observed_public_measurement"
                        else "censored"
                    ] += 1
                    output.write(canonical(row) + b"\n")
                output.flush()
                os.fsync(output.fileno())
            (temp / "unpartitioned.jsonl").unlink()
            for group in coverage.values():
                for key in ("markets", "families", "days", "groups"):
                    group[key] = sorted(group[key])
            result = dict(
                schema_version=1,
                dataset_id=dataset_id,
                identity=identity,
                rows_sha256=file_hash(temp / "examples.jsonl"),
                counts=dict(counters),
                boundaries=boundaries,
                family_aliases=aliases,
                heldout_families=heldout_families,
                cross_day_generalization_available=len(
                    {day for cov in coverage.values() for day in cov["days"]}
                )
                >= 2,
                partition_counts=dict(partition_counts),
                coverage=coverage,
                first_decision_ns=first,
                last_decision_ns=last,
                limitations=LIMITATIONS,
                state="research_dataset_not_scientifically_validated",
                source_root=str(root),
                generated_seconds=time.monotonic() - start,
                created_ns=time.time_ns(),
            )
            if code_identity() != identity["code_sha256"]:
                raise ValueError("Builder code changed during dataset generation")
            atomic_json(temp / "manifest.json", result)
            verify_rows(temp / "examples.jsonl", result)
            code = temp / "code" / "midas" / "reality"
            code.mkdir(parents=True)
            for path in Path(__file__).parent.glob("*.py"):
                shutil.copy2(path, code / path.name)
            (code.parent / "__init__.py").write_text('"""Frozen dataset-builder code bundle."""\n')
            os.replace(temp, final)
            sync_dir(destination)
            return result
        except BaseException:
            # This is a disposable unpublished derivative, not original observations.
            shutil.rmtree(temp)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        if args.output is None:
            parser.error("build requires a separate --output derivative root")
        spec = (
            DatasetSpec.from_dict(json.loads(args.spec.read_text())) if args.spec else DatasetSpec()
        )
        source = json.loads(args.source_manifest.read_text()) if args.source_manifest else None
        result = build(args.root, args.output, spec, source)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in ("dataset_id", "counts", "partition_counts", "generated_seconds")
                },
                indent=2,
            )
        )
    else:
        from .research_validation import verify_rows

        result = json.loads((args.root / "manifest.json").read_text())
        verify_rows(args.root / "examples.jsonl", result)
        print(json.dumps(dict(dataset_id=result["dataset_id"], verified=True), indent=2))


if __name__ == "__main__":
    main()
