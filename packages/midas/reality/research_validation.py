"""Independent dataset causality, label contract, grouping and partition audit."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .research_schema import FEATURE_VERSION, LABEL_VERSION, TARGETS, DatasetSpec, digest
from .storage import file_hash


def refs_in(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if "canonical_record_sha256" in value:
            return [value]
        return [ref for child in value.values() for ref in refs_in(child)]
    if isinstance(value, list):
        return [ref for child in value for ref in refs_in(child)]
    return []


def verify_rows(path: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    if (
        file_hash(path) != artifact["rows_sha256"]
        or digest(artifact["identity"]) != artifact["dataset_id"]
    ):
        raise ValueError("Dataset identity or row artifact corruption")
    spec = DatasetSpec.from_dict(artifact["identity"]["spec"])
    source = {s["file"]: s for s in artifact["identity"]["source_manifest"]["segments"]}
    seen = set()
    group_parts: dict[str, set[str]] = {}
    split_bounds: dict[str, list[int]] = {}
    anchor_parts: dict[tuple[str, int], set[str]] = {}
    coverage: dict[str, dict[str, set[str]]] = {}
    counts: Counter[str] = Counter()
    for line in path.open():
        row = json.loads(line)
        if row["id"] in seen:
            raise ValueError("Duplicate example identity")
        seen.add(row["id"])
        if row["feature_version"] != FEATURE_VERSION or row["label_version"] != LABEL_VERSION:
            raise ValueError("Inconsistent feature or label version")
        if digest(row["features"]) != row["feature_sha256"]:
            raise ValueError("Feature corruption")
        if row["features"]["market"]["protocol"] != "v1" or set(row["features"]["legs"]) != {
            "yes",
            "no",
        }:
            raise ValueError("Unsupported market-pair semantics")
        if len({leg["asset_id"] for leg in row["features"]["legs"].values()}) != 2:
            raise ValueError("Repeated outcome identity")
        if (
            row["feature_window_start_ns"] > row["decision_ns"]
            or row["label_window_end_ns"] < row["decision_ns"]
        ):
            raise ValueError("Invalid example time window")
        if row["hypothetical_context"]["orders_submitted"] is not False:
            raise ValueError("Research example incorrectly claims submitted orders")
        for ref in refs_in(row["feature_sources"]):
            if ref["ordinal"] > row["decision_ordinal"] or ref["received_ns"] > row["decision_ns"]:
                raise ValueError("Future-information leakage in historical features")
            if (
                ref["segment"] not in source
                or ref["segment_sha256"] != source[ref["segment"]]["sha256"]
            ):
                raise ValueError("Source coverage/hash mismatch")
            if (
                not source[ref["segment"]]["first"]
                <= ref["ordinal"]
                <= source[ref["segment"]]["last"]
            ):
                raise ValueError("Reference outside source segment")
        if row["horizon_ms"] not in spec.horizons_ms or row[
            "future_tolerance_ms"
        ] != spec.tolerance_ms(row["horizon_ms"]):
            raise ValueError("Label horizon/spec corruption")
        if (
            row["label_window_end_ns"]
            != row["decision_ns"] + (row["horizon_ms"] + row["future_tolerance_ms"]) * 10**6
        ):
            raise ValueError("Label horizon window corruption")
        label = row["labels"]
        if (
            label["label_version"] != LABEL_VERSION
            or label["execution_ground_truth"] != "unknown_counterfactual"
        ):
            raise ValueError("Hypothetical execution incorrectly presented as observed")
        if any("fill" in key.lower() and key != "execution_ground_truth" for key in label):
            raise ValueError("Public-data label cannot claim fills")
        if label["status"] == "censored":
            if not label["reason"] or any(
                label[target] is not None for target in TARGETS if target != "market_disruption"
            ):
                raise ValueError("Censored observations converted into outcomes")
        elif label["status"] == "observed_public_measurement":
            for delay in row["effective_delays_ms"].values():
                if not row["horizon_ms"] <= delay <= row["horizon_ms"] + row["future_tolerance_ms"]:
                    raise ValueError("Sub-event interpolation or invalid future horizon")
            for ref in refs_in(row["label_source"]):
                if (
                    ref["segment"] not in source
                    or ref["segment_sha256"] != source[ref["segment"]]["sha256"]
                ):
                    raise ValueError("Label source coverage/hash mismatch")
            received = list(row["observed_future_received_ns"].values())
            if max(received) - min(received) > spec.max_skew_ms * 10**6:
                raise ValueError("Unqualified complementary observation skew")
            if (
                label["opportunity_target_status"] == "no_initial_discrepancy"
                and label["opportunity_persistence"] is not None
            ):
                raise ValueError("No-opportunity examples converted into negative opportunities")
        else:
            raise ValueError("Unknown public-observation label status")
        partition = row["partition"]
        if partition not in {"train", "validation", "test", "embargoed"}:
            raise ValueError("Random/unrecognized partition")
        counts[partition] += 1
        cov = coverage.setdefault(partition, dict(markets=set(), days=set(), groups=set()))
        cov["markets"].add(row["market_id"])
        cov["days"].add(row["day_utc"])
        cov["groups"].add(row["dependence_group"])
        if partition != "embargoed":
            group_parts.setdefault(row["dependence_group"], set()).add(partition)
            anchor_parts.setdefault((row["condition"], row["decision_ordinal"]), set()).add(
                partition
            )
            bounds = split_bounds.setdefault(
                partition, [row["feature_window_start_ns"], row["label_window_end_ns"]]
            )
            bounds[0] = min(bounds[0], row["feature_window_start_ns"])
            bounds[1] = max(bounds[1], row["label_window_end_ns"])
        if row.get("market_generalization_partition") in {"train", "validation"} and row[
            "family_id"
        ] in artifact.get("heldout_families", []):
            raise ValueError("Repeated event/market family leaked into held-out-market training")
    if any(len(parts) > 1 for parts in group_parts.values()) or any(
        len(parts) > 1 for parts in anchor_parts.values()
    ):
        raise ValueError("Correlated or overlapping variants leak across partitions")
    ordered = [split_bounds[p] for p in ("train", "validation", "test") if p in split_bounds]
    for previous, later in zip(ordered, ordered[1:], strict=False):
        if previous[1] + spec.embargo_ms * 10**6 > later[0]:
            raise ValueError("Chronological split contamination or overlapping horizons")
    if dict(counts) != artifact["partition_counts"] or len(seen) != artifact["counts"]["examples"]:
        raise ValueError("Dataset sample-count corruption")
    for partition, cov in coverage.items():
        for key, actual in cov.items():
            if sorted(actual) != artifact["coverage"][partition][key]:
                raise ValueError("Effective sample coverage corruption")
    return dict(
        examples=len(seen),
        partition_counts=dict(counts),
        chronological_isolation=True,
        unknown_execution_enforced=True,
        independent_rows_not_claimed=True,
    )


def audit_public_labels(path: Path, artifact: dict[str, Any], raw_root: Path) -> dict[str, Any]:
    """Reconstruct one prefix and independently check labels against public depth.

    SQLite keeps the reference/row index on disposable disk instead of retaining
    a potentially large JSONL dataset in memory. Production feature/label helpers
    are deliberately not used for numerical reference calculations.
    """
    import sqlite3
    import tempfile
    from decimal import Decimal, localcontext

    from .foundry import source_records
    from .reconstruction import Engine

    verify_rows(path, artifact)
    checked = references = 0
    baseline: dict[str, dict[str, Any]] = {}
    pending: dict[str, dict[str, Any]] = {}
    spec = DatasetSpec.from_dict(artifact["identity"]["spec"])
    current_producer = None
    independent_bad: set[str] = set()
    prior_clock: tuple[int, int] | None = None
    markets: dict[str, dict[str, Any]] = {}

    def visible_value(book: dict[str, Any], side: str, requested: Decimal) -> Decimal | None:
        values = sorted(book[side].items(), reverse=side == "bids")
        cumulative = Decimal(0)
        total = Decimal(0)
        for price, amount in values:
            left = requested - cumulative
            if left <= amount:
                return Decimal(total + left * price)
            total += amount * price
            cumulative += amount
        return None

    with tempfile.TemporaryDirectory(prefix="midas-label-audit-") as temporary:
        db = sqlite3.connect(str(Path(temporary) / "index.sqlite"))
        db.execute(
            "create table samples(id text primary key, decision integer, future integer, body text)"
        )
        db.execute("create table refs(ordinal integer, body text, primary key(ordinal,body))")
        for line in path.open():
            row = json.loads(line)
            final = row["label_source"].get("termination_ref")
            db.execute(
                "insert into samples values(?,?,?,?)",
                (row["id"], row["decision_ordinal"], final["ordinal"] if final else -1, line),
            )
            for ref in refs_in(row["feature_sources"]) + refs_in(row["label_source"]):
                db.execute(
                    "insert or ignore into refs values(?,?)",
                    (ref["ordinal"], json.dumps(ref, sort_keys=True)),
                )
        db.execute("create index decisions on samples(decision)")
        db.execute("create index futures on samples(future)")
        db.commit()
        engine = Engine()
        with localcontext() as context:
            context.prec = 160
            for record, actual_ref in source_records(
                raw_root, artifact["identity"]["source_manifest"]
            ):
                ordinal = record["ordinal"]
                for (encoded,) in db.execute("select body from refs where ordinal=?", (ordinal,)):
                    if json.loads(encoded) != actual_ref:
                        raise ValueError("Raw-record reference hash/timestamp/offset corruption")
                    references += 1
                if (
                    record["kind"] == "checkpoint"
                    and record["payload"]["state_sha256"] != engine.digest()
                ):
                    raise ValueError("Independent source replay checkpoint mismatch")
                if record["kind"] == "gap" and record["payload"].get("reason") == "process_start":
                    current_producer = record["payload"].get("implementation_sha256")
                if record["kind"] == "discovery":
                    markets = {m["condition"]: m for m in record["cohort"]}
                clock_regressed = False
                if record["kind"] == "gap":
                    independent_bad.clear()
                    prior_clock = None
                elif record["kind"] == "book_comparison":
                    data = record["payload"]
                    if (
                        data.get("asset_id")
                        and data["assessment"] == "stable_local_lineage_divergence"
                    ):
                        independent_bad.add(data["asset_id"])
                    elif (
                        data.get("asset_id")
                        and data["assessment"] == "stable_local_lineage_match_unsequenced"
                    ):
                        independent_bad.discard(data["asset_id"])
                if record["kind"] == "frame":
                    current_clock = (record["received_ns"], record["monotonic_ns"])
                    clock_regressed = prior_clock is not None and (
                        current_clock[0] < prior_clock[0] or current_clock[1] < prior_clock[1]
                    )
                    prior_clock = current_clock
                engine.consume(record)
                for t, book in engine.books.items():
                    if (
                        record["kind"] == "frame"
                        and book["snapshot"][0] == ordinal
                        and book["issue"] is None
                    ):
                        independent_bad.discard(t)
                for item in pending.values():
                    if item["invalid_seen"]:
                        continue
                    row = item["row"]
                    unavailable = (
                        record["kind"] == "gap"
                        or clock_regressed
                        or engine.now_ns > row["label_window_end_ns"]
                        or row["condition"] not in markets
                    )
                    current_books = [engine.books.get(t) for t in item["tokens"].values()]
                    if not unavailable:
                        unavailable = any(
                            book is None
                            or book["issue"]
                            or book.get("timing_uncertainty")
                            or engine.now_ns - book["received_ns"] > spec.max_freshness_ms * 10**6
                            for book in current_books
                        )
                    if not unavailable:
                        metadata = markets[row["condition"]]
                        unavailable = any(
                            t in independent_bad for t in item["tokens"].values()
                        ) or (
                            metadata.get("end_ns") is not None
                            and engine.now_ns >= metadata["end_ns"]
                        )
                        for name, t in item["tokens"].items():
                            tick = (
                                engine.books[t]["tick"]
                                or metadata.get("public_market_constraints", {}).get(
                                    "minimum_tick_size"
                                )
                                or metadata.get("tick_size")
                            )
                            if str(tick) != str(row["features"]["legs"][name]["tick_size"]):
                                unavailable = True
                    if unavailable:
                        item["invalid_seen"] = True
                        if row["labels"]["status"] == "observed_public_measurement":
                            raise ValueError(
                                "Observed label bridges an unavailable/uncertain source interval"
                            )
                        continue
                    books = {name: engine.books[t] for name, t in item["tokens"].items()}
                    stamps = [book["received_ns"] for book in books.values()]
                    ready = (
                        record["kind"] == "frame"
                        and min(stamps) >= row["decision_ns"] + row["horizon_ms"] * 10**6
                        and max(stamps) - min(stamps) <= spec.max_skew_ms * 10**6
                    )
                    if ready:
                        if row["labels"]["status"] != "observed_public_measurement":
                            raise ValueError(
                                "Selective censoring despite an available future observation"
                            )
                        if ordinal != item["future_ordinal"]:
                            raise ValueError(
                                "Label skipped the first qualifying future observation"
                            )
                for (encoded,) in db.execute(
                    "select body from samples where decision=?", (ordinal,)
                ):
                    row = json.loads(encoded)
                    if current_producer != row["producer_implementation_sha256"]:
                        raise ValueError("Producer source provenance corruption")
                    if row["source_id"] != digest(artifact["identity"]["source_manifest"]):
                        raise ValueError("Training example references a different raw prefix")
                    tokens = {
                        name: leg["asset_id"] for name, leg in row["features"]["legs"].items()
                    }
                    if row["condition"] not in markets or {
                        t: o.lower() for t, o in markets[row["condition"]]["tokens"].items()
                    } != {t: o for o, t in tokens.items()}:
                        raise ValueError("Market/condition/outcome identity leakage")
                    original = {}
                    quantity = Decimal(row["hypothetical_context"]["quantity"])
                    for name, token in tokens.items():
                        book = engine.books[token]
                        ask, bid = min(book["asks"]), max(book["bids"], default=None)
                        leg = row["features"]["legs"][name]
                        if (
                            Decimal(leg["best_ask"]) != ask
                            or (Decimal(leg["best_bid"]) if leg["best_bid"] is not None else None)
                            != bid
                        ):
                            raise ValueError("Decision-time quote feature corruption")
                        if leg["age_ns"] != row["decision_ns"] - book["received_ns"]:
                            raise ValueError("Decision-time freshness corruption")
                        original[name] = dict(
                            price=ask,
                            amount=book["asks"][ask],
                            exit_value=visible_value(book, "bids", quantity),
                        )
                    baseline[row["id"]] = dict(original=original, tokens=tokens, quantity=quantity)
                    pending[row["id"]] = dict(
                        tokens=tokens,
                        future_ordinal=row["label_source"]["termination_ref"]["ordinal"]
                        if row["label_source"].get("termination_ref")
                        else -1,
                        row=row,
                        invalid_seen=False,
                    )
                for (encoded,) in db.execute("select body from samples where future=?", (ordinal,)):
                    row = json.loads(encoded)
                    base = baseline.pop(row["id"])
                    pending.pop(row["id"], None)
                    if row["labels"]["status"] != "observed_public_measurement":
                        continue
                    present = []
                    remaining = {}
                    future_sum = original_sum = acquisition_sum = exit_difference = Decimal(0)
                    future_prices_known = True
                    all_acquisition = all_exits = True
                    for name, token in base["tokens"].items():
                        book = engine.books[token]
                        if book["issue"] or book.get("timing_uncertainty"):
                            raise ValueError("Uncertain observation labeled as known")
                        old = base["original"][name]
                        available = book["asks"].get(old["price"], Decimal(0))
                        present.append(available > 0)
                        remaining[name] = min(old["amount"], available)
                        original_sum += old["price"]
                        if book["asks"]:
                            future_sum += min(book["asks"])
                        else:
                            future_prices_known = False
                        cost = visible_value(book, "asks", base["quantity"])
                        exit_value = visible_value(book, "bids", base["quantity"])
                        if cost is None:
                            all_acquisition = False
                        else:
                            acquisition_sum += cost
                        if exit_value is None or old["exit_value"] is None:
                            all_exits = False
                        else:
                            exit_difference += exit_value - old["exit_value"]
                        if row["observed_future_received_ns"][name] != book["received_ns"]:
                            raise ValueError("Fabricated future observation timing")
                    label = row["labels"]
                    if (
                        label["quote_persistence"] != all(present)
                        or {k: Decimal(v) for k, v in label["depth_at_original_quotes"].items()}
                        != remaining
                    ):
                        raise ValueError("Quote/depth label corruption")
                    if (
                        Decimal(label["adverse_ask_movement"])
                        if label["adverse_ask_movement"] is not None
                        else None
                    ) != (
                        max(Decimal(0), future_sum - original_sum) if future_prices_known else None
                    ):
                        raise ValueError("Adverse movement label corruption")
                    if (
                        Decimal(label["displayed_acquisition_cost"])
                        if label["displayed_acquisition_cost"] is not None
                        else None
                    ) != (acquisition_sum if all_acquisition else None):
                        raise ValueError("Displayed cost label corruption or double-counted fees")
                    if (
                        Decimal(label["quoted_exit_value_change"])
                        if label["quoted_exit_value_change"] is not None
                        else None
                    ) != (exit_difference if all_exits else None):
                        raise ValueError("Quoted exit measurement corruption")
                    if original_sum < 1 and label["opportunity_persistence"] != (
                        future_sum < 1 and all_acquisition
                    ):
                        raise ValueError("Opportunity label corruption")
                    checked += 1
        db.close()
    return dict(
        observed_labels_independently_checked=checked,
        raw_references_checked=references,
        private_execution_ground_truth="unknown",
    )
