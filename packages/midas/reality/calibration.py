"""Training-only public distribution calibration and preserved-generator comparison."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from midas.laboratory.spec import FAMILIES, generate
from midas.paper.broker import ExecutionModel

from .execution_research import VERSION as EXECUTION_VERSION
from .execution_research import compare_decision, families
from .quote_dynamics import collect
from .research_schema import LIMITATIONS, digest
from .research_validation import verify_rows
from .storage import canonical, file_hash

VERSION = "reality-training-calibration-v1"
METRICS = (
    "spread",
    "top_ask_quantity",
    "total_ask_quantity",
    "displayed_cost_premium_per_share",
    "quote_age_ms",
    "freshness_ms",
    "cross_outcome_skew_ms",
    "update_frames_per_second",
    "lookback_best_ask_change",
    "lookback_ask_quantity_change",
    "adverse_ask_movement",
    "best_ask_pair_movement",
    "displayed_cost_change",
    "quoted_exit_value_change",
    "original_quote_depth_retention",
    "effective_delay_ms",
)


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return dict(count=0, quantiles=None)
    values = sorted(values)
    return dict(
        count=len(values),
        mean=sum(values) / len(values),
        quantiles={str(p): values[round((len(values) - 1) * p)] for p in (0, 0.05, 0.5, 0.95, 1)},
    )


def persistence(rows: list[dict[str, Any]], target: str, seed: int = 19) -> dict[str, Any]:
    eligible = [r for r in rows if target != "opportunity_persistence" or r["initial_opportunity"]]
    known = [r for r in eligible if r["labels"].get(target) is not None]
    successes = sum(bool(r["labels"][target]) for r in known)
    n = len(eligible)
    clusters: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in known:
        clusters[r["family_id"]][r["dependence_group"]].append(int(bool(r["labels"][target])))
    rng = random.Random(seed)
    boot = []
    keys = sorted(clusters)
    # Resample families then time blocks; variants in a block remain together.
    if len(keys) >= 3:
        for _ in range(200):
            values = []
            for family in rng.choices(keys, k=len(keys)):
                blocks = sorted(clusters[family])
                for block in rng.choices(blocks, k=len(blocks)):
                    values.extend(clusters[family][block])
            boot.append(sum(values) / len(values))
    return dict(
        eligible=n,
        measured=len(known),
        unknown=n - len(known),
        successes=successes,
        conditional_measured_rate=successes / len(known) if known else None,
        missing_outcome_identification_bounds=[successes / n, (successes + n - len(known)) / n]
        if n
        else None,
        family_count=len(keys),
        time_block_count=sum(len(v) for v in clusters.values()),
        exploratory_cluster_bootstrap_95=[sorted(boot)[5], sorted(boot)[194]] if boot else None,
        interval_notice="Exploratory family/time-block resampling; single-day coverage, informative missingness and unsequenced feed prevent population confidence or fill inference.",
    )


def measure(row: dict[str, Any]) -> dict[str, list[float]]:
    f, label = row["features"], row["labels"]
    result: dict[str, list[float]] = {key: [] for key in METRICS}
    for v in f["legs"].values():
        pairs = {
            "spread": v["spread"],
            "top_ask_quantity": v["displayed_depth"]["asks"][0][1],
            "total_ask_quantity": v["total_ask_quantity"],
            "quote_age_ms": v["quote_age_ns"] / 10**6,
            "freshness_ms": v["age_ns"] / 10**6,
            "lookback_best_ask_change": v["best_ask_change"],
            "lookback_ask_quantity_change": v["ask_quantity_change"],
        }
        for key, value in pairs.items():
            if value is not None:
                result[key].append(float(value))
        result["update_frames_per_second"].append(
            v["recent_book_update_frames"] / (v["lookback_ns"] / 10**9)
        )
    result["cross_outcome_skew_ms"].append(f["cross_outcome_skew_ns"] / 10**6)
    q = float(row["hypothetical_context"]["quantity"])
    if f["displayed_acquisition_cost"] is not None:
        result["displayed_cost_premium_per_share"].append(
            float(f["displayed_acquisition_cost"]) / q - float(f["best_ask_pair_sum"])
        )
    if label["status"] == "observed_public_measurement":
        for key in ("adverse_ask_movement", "best_ask_pair_movement", "quoted_exit_value_change"):
            if label[key] is not None:
                result[key].append(float(label[key]))
        if (
            label["displayed_acquisition_cost"] is not None
            and f["displayed_acquisition_cost"] is not None
        ):
            result["displayed_cost_change"].append(
                float(label["displayed_acquisition_cost"]) - float(f["displayed_acquisition_cost"])
            )
        for leg, value in label["depth_at_original_quotes"].items():
            initial = float(f["legs"][leg]["displayed_depth"]["asks"][0][1])
            result["original_quote_depth_retention"].append(float(value) / initial)
        result["effective_delay_ms"].extend(row["effective_delays_ms"].values())
    return result


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    anchors = {r["anchor"]: r for r in rows}
    return dict(
        rows=len(rows),
        anchors=len({r["anchor"] for r in rows}),
        markets=len({r["market_id"] for r in rows}),
        families=len({r["family_id"] for r in rows}),
        days=sorted({r["day_utc"] for r in rows}),
        time_blocks=len({r["dependence_group"] for r in rows}),
        statuses=dict(Counter(r["labels"]["status"] for r in rows)),
        censor_reasons=dict(
            Counter(r["labels"]["reason"] for r in rows if r["labels"]["status"] == "censored")
        ),
        quote_persistence=persistence(rows, "quote_persistence"),
        opportunity_persistence=persistence(rows, "opportunity_persistence"),
        displayed_quantity_supported=persistence(rows, "displayed_quantity_supported"),
        metrics={
            key: distribution(
                [
                    v
                    for r in (list(anchors.values()) if key in METRICS[:11] else rows)
                    for v in r["measurements"][key]
                ]
            )
            for key in METRICS
        },
    )


def synthetic_comparison(horizons: list[int]) -> dict[str, Any]:
    """Regenerate bounded controls without reading/writing protected experiments."""
    initial: dict[str, list[float]] = defaultdict(list)
    outcomes: dict[int, list[dict[str, Any]]] = defaultdict(list)
    scenario_hashes = []
    for family in FAMILIES:
        for seed in range(16):
            s = generate(family, seed)
            scenario_hashes.append(digest(s.model_dump(mode="json")))
            original = {k: b.model_dump(mode="json") for k, b in s.books.items()}
            for b in original.values():
                initial["spread"].append(
                    float(b["asks"][0]["price"]) - float(b["bids"][0]["price"])
                )
                initial["top_ask_quantity"].append(float(b["asks"][0]["size"]))
            for h in horizons:
                books = dict(original)
                for event in sorted(s.events, key=lambda e: (e.time_ms, e.priority, e.id)):
                    if event.time_ms <= h and event.kind == "market":
                        books.update(event.payload.get("books", {}))
                exists = all(
                    any(
                        level["price"] == original[k]["asks"][0]["price"]
                        and float(level["size"]) > 0
                        for level in b["asks"]
                    )
                    for k, b in books.items()
                )
                disappeared = any(not b["asks"] for b in books.values())
                outcomes[h].append(
                    dict(
                        quote_persistence=exists,
                        liquidity_disappearance=disappeared,
                        apparent_discrepancy=all(b["asks"] for b in books.values())
                        and sum(float(b["asks"][0]["price"]) for b in books.values()) < 1,
                    )
                )
    return dict(
        source="SYNTHETIC_REGENERATED_CONTROLS",
        generator="midas.laboratory.spec.generate",
        selection="All 19 families, seeds 0..15; equal family weighting, not historical result weighting",
        scenarios=len(scenario_hashes),
        scenario_bundle_sha256=digest(scenario_hashes),
        metrics={key: distribution(v) for key, v in initial.items()},
        horizons={
            str(h): {key: sum(int(r[key]) for r in rows) / len(rows) for key in rows[0]}
            for h, rows in outcomes.items()
        },
        original_execution_presets={
            name: ExecutionModel.preset(name).model_dump(mode="json")
            for name in ("optimistic", "standard", "conservative")
        },
        incomparable_components=[
            "Private matching/queue/acknowledgment and submission latency have no public execution counterpart.",
            "Synthetic future state is known at exact schedule time; real futures require new synchronized observations.",
            "Original generated market legs update synchronously; observed arrival skew is measured separately.",
            "Synthetic resolution at 2/8 seconds or absent is imposed; real capital settlement is unmeasured.",
        ],
        protected_historical_artifacts_modified=False,
    )


def scenario_sensitivity(candidates: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    experiments = {}
    for quantity in ("5", "10", "25"):
        for capital in ("10", "100", "1000"):
            outcomes: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for variants in candidates.values():
                for result in compare_decision(variants, quantity=quantity, capital=capital):
                    outcomes[result["scenario"]].append(result)
            experiments[f"quantity={quantity};capital={capital}"] = {
                name: dict(
                    matched_decisions=len(results),
                    causal_decisions=dict(Counter(r["decision"] for r in results)),
                    followup_statuses=dict(Counter(r["status"] for r in results)),
                    reasons=dict(Counter(r["reason"] for r in results if r["reason"])),
                    hypothetical_lower_pnl=distribution(
                        [
                            float(r["hypothetical_pnl_bounds"][0])
                            for r in results
                            if r["hypothetical_pnl_bounds"]
                        ]
                    ),
                    hypothetical_upper_pnl=distribution(
                        [
                            float(r["hypothetical_pnl_bounds"][1])
                            for r in results
                            if r["hypothetical_pnl_bounds"]
                        ]
                    ),
                    unmatched_quantity=distribution(
                        [
                            float(r["unmatched_quantity"])
                            for r in results
                            if "unmatched_quantity" in r
                        ]
                    ),
                    examples=(
                        [r for r in results if r["decision"] == "hypothetical_candidate"][:8]
                        or results[:2]
                    ),
                )
                for name, results in outcomes.items()
            }
    return dict(
        unit="collateral_unit",
        evidence_kind="hypothetical_assumptions",
        quantity_grid=[5, 10, 25],
        capital_grid=[10, 100, 1000],
        paired_on="Same causal anchor and initial features; each family uses its matching requested followup horizon",
        fee_source="https://docs.polymarket.com/trading/fees",
        actual_profitability="unknown_counterfactual",
        experiments=experiments,
    )


def build(dataset: Path, output: Path) -> dict[str, Any]:
    start = time.monotonic()
    manifest = json.loads((dataset / "manifest.json").read_text())
    verify_rows(dataset / "examples.jsonl", manifest)
    if manifest["identity"]["spec"]["source_kind"] != "genuine_public_recording":
        raise ValueError("Calibration requires explicitly genuine observations")
    rows = []
    conditions: set[str] = set()
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in (dataset / "examples.jsonl").open():
        r = json.loads(line)
        if r["partition"] != "train" or r["market_generalization_partition"] != "train":
            continue
        conditions.add(r["condition"])
        anchor = digest([r["condition"], r["decision_ordinal"]])
        candidates[anchor].append(
            {
                key: r[key]
                for key in (
                    "id",
                    "condition",
                    "decision_ordinal",
                    "feature_sha256",
                    "horizon_ms",
                    "features",
                    "labels",
                    "hypothetical_context",
                )
            }
        )
        measurements = measure(r)
        rows.append(
            dict(
                id=r["id"],
                anchor=anchor,
                horizon_ms=r["horizon_ms"],
                market_id=r["market_id"],
                family_id=r["family_id"],
                day_utc=r["day_utc"],
                dependence_group=r["dependence_group"],
                labels=r["labels"],
                initial_opportunity=float(r["features"]["theoretical_edge_per_unit_before_fees"])
                > 0
                and r["features"]["quantity_supported"],
                selection_role=r["features"]["market"].get("selection_role"),
                measurements=measurements,
            )
        )
    if not rows:
        raise ValueError("No accepted training coverage")
    horizons = sorted({r["horizon_ms"] for r in rows})
    code_files = [
        Path(__file__),
        Path(__file__).with_name("execution_research.py"),
        Path(__file__).with_name("quote_dynamics.py"),
        Path(__file__).with_name("foundry.py"),
        Path(__file__).with_name("research_measurements.py"),
        Path(__file__).with_name("research_schema.py"),
        Path(__file__).with_name("research_validation.py"),
        Path(__file__).with_name("reconstruction.py"),
        Path(__file__).with_name("storage.py"),
    ]
    synthetic_files = [
        Path(__file__).parents[1] / "laboratory/spec.py",
        Path(__file__).parents[1] / "simulation/fixtures.py",
        Path(__file__).parents[1] / "paper/broker.py",
    ]
    identity = dict(
        version=VERSION,
        execution_version=EXECUTION_VERSION,
        dataset_id=manifest["dataset_id"],
        rows_sha256=manifest["rows_sha256"],
        partition="chronological train AND market-generalization train",
        code={p.name: file_hash(p) for p in code_files + synthetic_files},
        bootstrap_seed=19,
        bootstrap_draws=200,
        assumptions=[a.manifest() for a in families()],
    )
    dynamics = collect(manifest, conditions)
    dynamics_report = {
        k: distribution(v) if isinstance(v, list) else v for k, v in dynamics.items()
    }
    report: dict[str, Any] = dict(
        calibration_id=digest(identity),
        identity=identity,
        state="insufficient_population_evidence",
        receipt_observed_dynamics=dynamics_report,
        economic_sensitivity=scenario_sensitivity(candidates),
        overall=summary(rows),
        horizons={str(h): summary([r for r in rows if r["horizon_ms"] == h]) for h in horizons},
        strata={
            str(role): summary([r for r in rows if r["selection_role"] == role])
            for role in sorted({r["selection_role"] for r in rows}, key=str)
        },
        synthetic_comparison=synthetic_comparison(horizons),
        empirical_joint_kernel=[
            {k: r[k] for k in ("id", "horizon_ms", "family_id", "dependence_group", "labels")}
            for r in rows
            if r["labels"]["status"] == "observed_public_measurement"
        ],
        limitations=LIMITATIONS
        + [
            "Calibration excludes validation/final-test and held-out families.",
            "Pointwise original-price presence can include disappearance/reappearance; it is not continuous quote lifetime or survival of an order.",
            "Quote age is receiver-observed and snapshot-reset, not a venue lifetime distribution.",
            "Kernel is conditional on observed futures, not a population execution law; missingness bounds must accompany sampling.",
            "Spread and depth changes use causal lookback features; future labels measure original-price depth, paired ask and exit changes.",
            "Position-size cost premium is displayed depth walking, not causal impact of an unsubmitted order.",
        ],
        generated_seconds=time.monotonic() - start,
    )
    content = canonical(report)
    if len(content) > 32 * 1024**2:
        raise ValueError("Calibration artifact budget exceeded")
    output.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output).free - len(content) < 20 * 1024**3:
        raise ValueError("Calibration would breach host free-space reserve")
    if sum(p.stat().st_size for p in output.glob("*.json")) + len(content) > 256 * 1024**2:
        raise ValueError("Calibration root derivative budget exceeded")
    target = output / (report["calibration_id"] + ".json")
    if target.exists():
        old: dict[str, Any] = json.loads(target.read_text())
        if old["identity"] != identity or {
            k: v for k, v in old.items() if k != "generated_seconds"
        } != {k: v for k, v in report.items() if k != "generated_seconds"}:
            raise ValueError("Immutable calibration conflict")
        return old
    # Exclusive creation; incomplete interrupted writes are visibly invalid on reuse.
    with target.open("xb") as handle:
        handle.write(content)
    for p in code_files + synthetic_files:
        if file_hash(p) != identity["code"][p.name]:
            target.unlink()
            raise ValueError("Calibration source changed during build")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build(args.dataset, args.output)
    print(
        json.dumps(
            {k: report[k] for k in ("calibration_id", "state", "overall", "generated_seconds")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
