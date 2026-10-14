"""Real-observation Arena workflow: train/validation first, frozen final test once."""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .model_features import TARGET_VERSION, TARGETS, compact
from .model_features import VERSION as INPUT_VERSION
from .model_fitting import fit, predict, within_support
from .model_metrics import coverage, evaluate
from .model_registry import load, publish
from .research_access import consume_final_test, open_final_test
from .research_schema import LIMITATIONS, digest
from .research_validation import verify_rows
from .storage import atomic_json, file_hash

VERSION = "reality-arena-training-v1"


@dataclass(frozen=True)
class TrainingSpec:
    targets: tuple[str, ...] = tuple(TARGETS)
    horizon_ms: int = 1000
    seed: int = 20261014
    epochs: int = 40
    allow_mlp: bool = True
    mlp_min_relative_validation_gain: float = 0.02
    max_fit_seconds: int = 300
    max_models: int = 16
    budget_bytes: int = 512 * 1024**2
    reserve_bytes: int = 20 * 1024**3

    def __post_init__(self) -> None:
        if (
            not self.targets
            or len(set(self.targets)) != len(self.targets)
            or set(self.targets) - set(TARGETS)
        ):
            raise ValueError("Invalid training targets")
        if (
            not 1 <= self.horizon_ms <= 60000
            or not 0 <= self.seed < 2**32
            or not 1 <= self.epochs <= 100
            or not 1 <= self.max_models <= 24
            or not 1 <= self.max_fit_seconds <= 600
        ):
            raise ValueError("Unbounded training specification")
        if (
            not np.isfinite(self.mlp_min_relative_validation_gain)
            or not 0.02 <= self.mlp_min_relative_validation_gain <= 1
        ):
            raise ValueError("Invalid MLP improvement gate")
        if self.budget_bytes < 1024 or self.reserve_bytes < 1:
            raise ValueError("Invalid research storage budget")

    def dump(self) -> dict[str, Any]:
        return {**asdict(self), "targets": list(self.targets)}


def code_identity() -> dict[str, str]:
    result = {
        name: file_hash(Path(__file__).with_name(name))
        for name in (
            "model_training.py",
            "model_features.py",
            "model_fitting.py",
            "model_metrics.py",
            "model_registry.py",
            "research_access.py",
            "research_schema.py",
            "research_validation.py",
            "storage.py",
        )
    }
    result.update(
        {name: file_hash(code_path(name)) for name in ("arena_supervised.py", "arena_features.py")}
    )
    return result


def code_path(name: str) -> Path:
    if name in {"arena_supervised.py", "arena_features.py"}:
        return Path(__file__).parents[1] / "arena" / name.removeprefix("arena_")
    return Path(__file__).with_name(name)


def load_targets(
    dataset: Path,
    manifest: dict[str, Any],
    spec: TrainingSpec,
    partitions: set[str],
    *,
    ledger: Path | None = None,
    evaluation_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if not partitions <= {"train", "validation", "test"}:
        raise ValueError("Unknown partition")
    if "test" in partitions:
        if (
            ledger is None
            or evaluation_id is None
            or len(evaluation_id) != 64
            or not all(c in "0123456789abcdef" for c in evaluation_id)
        ):
            raise ValueError("Frozen final-test access is required")
        entry = json.loads((ledger / ("evaluation-" + evaluation_id + ".json")).read_text())
        if (
            entry["dataset_id"] != manifest["dataset_id"]
            or entry["state"] != "opened"
            or digest(entry["plan"]) != entry["plan_sha256"]
            or digest([entry["dataset_id"], entry["period"], entry["plan"]]) != evaluation_id
        ):
            raise ValueError("Final-test access missing, consumed or corrupted")
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in spec.targets}
    for line in (dataset / "examples.jsonl").open():
        row = json.loads(line)
        if row["horizon_ms"] != spec.horizon_ms or row["partition"] not in partitions:
            continue
        if (
            row["partition"] in {"train", "validation"}
            and row["market_generalization_partition"] != row["partition"]
        ):
            continue
        for name in spec.targets:
            out[name].append(compact(row, name))
    return out


def check_budget(root: Path, spec: TrainingSpec, anticipated: int = 8 * 1024**2) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free - anticipated < spec.reserve_bytes:
        raise ValueError("Research free-space reserve breached")
    if (
        sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) + anticipated
        > spec.budget_bytes
    ):
        raise ValueError("Training derivative budget exceeded")


def eligibility(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
    val_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    kind: str,
    economic_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_by = {
        name: coverage(rows)
        for name, rows in (("train", train), ("validation", validation), ("test", test))
    }
    reasons = []
    if len({r["day_utc"] for r in train + validation + test}) < 7:
        reasons.append("fewer_than_seven_utc_days")
    for name, minimum in (("train", 100), ("validation", 50), ("test", 50)):
        c = coverage_by[name]
        if c["eligible_decisions"] == 0 or c["unknown_targets"] / c["eligible_decisions"] > 0.3:
            reasons.append(name + "_excessive_unknown_target_fraction")
        if c["family_time_blocks"] < minimum or c["families"] < 5:
            reasons.append(name + "_insufficient_family_time_coverage")
        if kind == "classification" and (
            c["class_counts"] is None
            or min(c["class_counts"].get("0.0", 0), c["class_counts"].get("1.0", 0)) < 20
        ):
            reasons.append(name + "_insufficient_class_support")
    if (
        val_metrics.get("baseline_relative_skill", 0) is None
        or val_metrics.get("baseline_relative_skill", 0) < 0.02
    ):
        reasons.append("no_meaningful_validation_control_improvement")
    if (
        test_metrics.get("baseline_relative_skill", 0) is None
        or test_metrics.get("baseline_relative_skill", 0) <= 0
    ):
        reasons.append("no_frozen_test_control_improvement")
    interval = test_metrics.get("exploratory_paired_delta_95")
    if interval is None or interval[1] >= 0:
        reasons.append("paired_grouped_improvement_not_established")
    if kind == "classification" and test_metrics.get("ece", 1) > 0.1:
        reasons.append("conditional_calibration_gate_failed")
    if (
        economic_evidence is None
        or economic_evidence.get("evidence_kind") != "paired_hypothetical_scenarios"
        or economic_evidence.get("matched_opportunities", 0) < 30
        or economic_evidence.get("families", 0) < 3
        or economic_evidence.get("conservative_delta_lower_95", 0) <= 0
    ):
        reasons.append("matched_economic_decision_usefulness_not_established")
    return dict(
        state="insufficient_evidence" if reasons else "validated_on_recordings",
        policy_eligible=not reasons,
        forward_mode="experimental_prediction_probe_only",
        reasons=reasons,
        coverage=coverage_by,
        gate_version="reality-eligibility-v1",
        promotion=False,
        note="Development inference can be technically reproducible without scientific or economic validation.",
    )


def verify_audit(manifest: dict[str, Any], audit: Path | None) -> dict[str, Any]:
    if manifest["identity"]["spec"]["source_kind"] == "labeled_fixture":
        return dict(state="fixture_contract_only", real_evidence=False)
    if audit is None:
        raise ValueError("Genuine training requires a pinned independent source-audit bundle")
    bundle = json.loads(audit.read_text())
    if (
        bundle["dataset"]["dataset_id"] != manifest["dataset_id"]
        or bundle["dataset"]["rows_sha256"] != manifest["rows_sha256"]
        or bundle["audit"]["dataset_id"] != manifest["dataset_id"]
        or bundle["audit"]["observed_labels_independently_checked"]
        != manifest["counts"].get("label:observed_public_measurement", -1)
    ):
        raise ValueError("Independent source-audit bundle does not match dataset")
    return dict(
        state="independent_source_audit_pinned",
        bundle_sha256=file_hash(audit),
        evidence=bundle["audit"],
    )


def run(
    dataset: Path, root: Path, ledger: Path, spec: TrainingSpec, *, audit: Path | None = None
) -> dict[str, Any]:
    manifest = json.loads((dataset / "manifest.json").read_text())
    raw = Path(manifest["source_root"]).resolve()
    if (
        root.resolve() == raw
        or root.resolve().is_relative_to(raw)
        or raw.is_relative_to(root.resolve())
        or root.resolve().is_relative_to(dataset.resolve())
    ):
        raise ValueError("Training must use a separate derivative root")
    root.mkdir(parents=True, exist_ok=True)
    with (root / "training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(dataset, root, ledger, spec, manifest, audit)


def _run(
    dataset: Path,
    root: Path,
    ledger: Path,
    spec: TrainingSpec,
    manifest: dict[str, Any],
    audit: Path | None,
) -> dict[str, Any]:
    source = code_identity()
    identity = dict(
        version=VERSION,
        dataset_id=manifest["dataset_id"],
        rows_sha256=manifest["rows_sha256"],
        spec=spec.dump(),
        code=source,
        toolchain={
            name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn", "torch")
        },
        independent_audit_bundle_sha256=file_hash(audit) if audit is not None else None,
    )
    run_id = digest(identity)
    directory = root / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    progress_path = directory / "progress.json"
    progress: dict[str, Any] = (
        json.loads(progress_path.read_text())
        if progress_path.exists()
        else dict(run_id=run_id, identity=identity, models={}, created_ns=time.time_ns())
    )

    def update(state: str, **details: Any) -> None:
        progress.update(state=state, pid=os.getpid(), updated_ns=time.time_ns(), **details)
        atomic_json(progress_path, progress)

    if progress["identity"] != identity:
        raise ValueError("Interrupted job identity changed")
    if progress.get("state") == "SUCCEEDED":
        if file_hash(directory / "report.json") != progress["report_sha256"]:
            raise ValueError("Completed training report corruption")
        for refs in progress["models"].values():
            for ref in refs:
                load(root, ref["model_id"], ref["weights_sha256"])
        completed: dict[str, Any] = json.loads((directory / "report.json").read_text())
        if completed.get("final_test_opened"):
            entry = json.loads(
                (ledger / ("evaluation-" + completed["evaluation_id"] + ".json")).read_text()
            )
            if (
                entry["state"] != "consumed"
                or entry["result_sha256"] != progress["report_sha256"]
                or digest(entry["plan"]) != entry["plan_sha256"]
            ):
                raise ValueError("Completed final-test ledger corruption")
        return completed
    began = time.monotonic()
    try:
        check_budget(root, spec)
        update("VERIFYING_DATASET")
        verify_rows(dataset / "examples.jsonl", manifest)
        audit_proof = verify_audit(manifest, audit)
        for name in source:
            component = "arena" if name.startswith("arena_") else "reality"
            path = directory / "code" / "midas" / component / name.removeprefix("arena_")
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(code_path(name).read_bytes())
            if file_hash(path) != source[name]:
                raise ValueError("Frozen training source corruption")
        for package in (
            directory / "code" / "midas",
            directory / "code" / "midas" / "reality",
            directory / "code" / "midas" / "arena",
        ):
            (package / "__init__.py").write_text(
                "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
            )
        if (directory / "report.json").exists() and progress.get("report_sha256"):
            if file_hash(directory / "report.json") != progress["report_sha256"]:
                raise ValueError("Interrupted result corruption")
            report = json.loads((directory / "report.json").read_text())
            entry = json.loads(
                (ledger / ("evaluation-" + report["evaluation_id"] + ".json")).read_text()
            )
            if entry["state"] == "opened":
                consume_final_test(ledger, report["evaluation_id"], progress["report_sha256"])
            elif entry.get("result_sha256") != progress["report_sha256"]:
                raise ValueError("Consumed result mismatch")
            update("SUCCEEDED", recovered_after_result_publication=True)
            return dict(report)
        update("LOADING_TRAIN_VALIDATION")
        development = load_targets(dataset, manifest, spec, {"train", "validation"})
        reports: dict[str, Any] = {}
        selected = {}
        for target_name in spec.targets:
            kind = TARGETS[target_name]
            all_rows = development[target_name]
            train = [r for r in all_rows if r["partition"] == "train" and r["y"] is not None]
            validation = [
                r for r in all_rows if r["partition"] == "validation" and r["y"] is not None
            ]
            reports[target_name] = dict(
                kind=kind,
                coverage={
                    p: coverage([r for r in all_rows if r["partition"] == p])
                    for p in ("train", "validation")
                },
                candidates=[],
                skipped=[],
            )
            if not train or not validation:
                reports[target_name].update(
                    state="insufficient_evidence",
                    reason="no_applicable_measured_train_or_validation_targets",
                )
                continue
            families = ["constant", "heuristic"]
            if len(train) >= 20 and len(validation) >= 10 and len({r["y"] for r in train}) >= 2:
                families += ["logistic" if kind == "classification" else "linear", "tree"]
            else:
                reports[target_name]["skipped"].append(
                    dict(
                        families=["logistic", "linear", "tree", "mlp"],
                        reason="insufficient_training_target_variation_or_coverage",
                    )
                )
            yrows = np.array([r["x"] for r in validation])
            cached = {ref["family"]: ref for ref in progress["models"].get(target_name, [])}
            progress["models"].setdefault(target_name, [])

            def candidate(
                family: str,
                target_name: str = target_name,
                train: list[dict[str, Any]] = train,
                validation: list[dict[str, Any]] = validation,
                cached: dict[str, Any] = cached,
            ) -> dict[str, Any]:
                update("FITTING", target=target_name, family=family)
                if family in cached:
                    info = load(root, cached[family]["model_id"], cached[family]["weights_sha256"])[
                        "info"
                    ]
                else:
                    if sum(len(v) for v in progress["models"].values()) >= spec.max_models:
                        raise ValueError("Planned model-count budget exceeded")
                    params, curves = fit(
                        train,
                        validation,
                        target_name,
                        family,
                        seed=spec.seed,
                        epochs=spec.epochs,
                        max_seconds=spec.max_fit_seconds,
                    )
                    info = publish(
                        root,
                        dict(
                            dataset_id=manifest["dataset_id"],
                            target=target_name,
                            family=family,
                            input_version=INPUT_VERSION,
                            target_version=TARGET_VERSION,
                            source_kind=manifest["identity"]["spec"]["source_kind"],
                            horizon_ms=spec.horizon_ms,
                            quantity=manifest["identity"]["spec"]["quantity"],
                            training_run_id=run_id,
                            code=source,
                        ),
                        params,
                        dict(
                            scientific_state="experimental",
                            policy_eligible=False,
                            curves=curves,
                            training_coverage=coverage(train),
                            supported_protocols=["v1"],
                            limitations=LIMITATIONS,
                        ),
                    )
                    ref = dict(
                        model_id=info["model_id"],
                        weights_sha256=info["weights_sha256"],
                        family=family,
                        target=target_name,
                    )
                    progress["models"][target_name].append(ref)
                    cached[family] = ref
                    update("FITTING", models=progress["models"])
                return dict(info)

            infos = [candidate(family) for family in families]
            constant = load(root, infos[0]["model_id"])["parameters"]
            cp = predict(constant, yrows)
            entries = []
            for info in infos:
                params = load(root, info["model_id"])["parameters"]
                entries.append(
                    dict(
                        model_id=info["model_id"],
                        family=params["family"],
                        weights_sha256=info["weights_sha256"],
                        validation=evaluate(
                            validation,
                            predict(params, yrows),
                            kind,
                            cp,
                            within_support(params, yrows),
                        ),
                    )
                )
            best = min(entries, key=lambda e: (e["validation"]["score"], e["family"]))
            improvement = (
                1 - best["validation"]["score"] / entries[0]["validation"]["score"]
                if entries[0]["validation"]["score"]
                else 0
            )
            if (
                spec.allow_mlp
                and len(train) >= 100
                and len(validation) >= 50
                and best["family"] not in {"constant", "heuristic"}
                and improvement >= spec.mlp_min_relative_validation_gain
            ):
                info = candidate("mlp")
                params = load(root, info["model_id"])["parameters"]
                entries.append(
                    dict(
                        model_id=info["model_id"],
                        family="mlp",
                        weights_sha256=info["weights_sha256"],
                        validation=evaluate(
                            validation,
                            predict(params, yrows),
                            kind,
                            cp,
                            within_support(params, yrows),
                        ),
                    )
                )
                best = min(entries, key=lambda e: (e["validation"]["score"], e["family"]))
            elif "mlp" not in {f for s in reports[target_name]["skipped"] for f in s["families"]}:
                reports[target_name]["skipped"].append(
                    dict(
                        families=["mlp"],
                        reason="lightweight_validation_gain_or_coverage_gate_not_met",
                    )
                )
            reports[target_name].update(
                state="development_only",
                candidates=entries,
                selected_by_validation=best["model_id"],
                selection_is_not_promotion=True,
            )
            selected[target_name] = best["model_id"]
        if code_identity() != source:
            raise ValueError("Training code changed before final-test freeze")
        frozen = [ref for refs in progress["models"].values() for ref in refs]
        if not frozen:
            report = dict(
                run_id=run_id,
                identity=identity,
                state="insufficient_evidence",
                targets=reports,
                source_audit=audit_proof,
                final_test_opened=False,
            )
            atomic_json(directory / "report.json", report)
            update("SUCCEEDED", report_sha256=file_hash(directory / "report.json"))
            return report
        plan = dict(
            version="reality-final-analysis-v1",
            selection_partition="validation",
            frozen_candidates=frozen,
            controls=[r for r in frozen if r["family"] in {"constant", "heuristic"}],
            selected_by_validation=selected,
            target_version=TARGET_VERSION,
            input_version=INPUT_VERSION,
            horizon_ms=spec.horizon_ms,
            classification_threshold=0.5,
            threshold_retuning=False,
            promotion=False,
            analysis="Conditional target metrics, family/time uncertainty, matched controls, support and unseen-family slices; no claim of fills or money",
            eligibility_version="reality-eligibility-v1",
        )
        update("FREEZING_FINAL_TEST_PLAN")
        entry = open_final_test(manifest, ledger, plan)
        atomic_json(directory / "frozen-plan.json", entry)
        update("EVALUATING_FROZEN_TEST", evaluation_id=entry["evaluation_id"])
        final = load_targets(
            dataset, manifest, spec, {"test"}, ledger=ledger, evaluation_id=entry["evaluation_id"]
        )
        for target_name in spec.targets:
            rows = final[target_name]
            reports[target_name]["coverage"]["test"] = coverage(rows)
            known = [r for r in rows if r["y"] is not None]
            if target_name not in selected:
                continue
            constant_ref = next(
                r for r in frozen if r["target"] == target_name and r["family"] == "constant"
            )
            cp = predict(
                load(root, constant_ref["model_id"])["parameters"], [r["x"] for r in known]
            )
            for item in reports[target_name]["candidates"]:
                params = load(root, item["model_id"], item["weights_sha256"])["parameters"]
                xp = [r["x"] for r in known]
                pred = predict(params, xp)
                item["test"] = evaluate(
                    known, pred, TARGETS[target_name], cp, within_support(params, xp)
                )
                held = [
                    i for i, r in enumerate(known) if r["market_generalization_partition"] == "test"
                ]
                item["heldout_family_test"] = evaluate(
                    [known[i] for i in held], pred[held], TARGETS[target_name], cp[held]
                )
            chosen = next(
                e
                for e in reports[target_name]["candidates"]
                if e["model_id"] == selected[target_name]
            )
            reports[target_name]["eligibility"] = eligibility(
                [r for r in development[target_name] if r["partition"] == "train"],
                [r for r in development[target_name] if r["partition"] == "validation"],
                rows,
                chosen["validation"],
                chosen["test"],
                TARGETS[target_name],
            )
        if (
            code_identity() != source
            or file_hash(dataset / "examples.jsonl") != manifest["rows_sha256"]
        ):
            raise ValueError("Frozen source changed during final evaluation")
        report = dict(
            run_id=run_id,
            identity=identity,
            state="insufficient_scientific_evidence",
            targets=reports,
            source_audit=audit_proof,
            evaluation_id=entry["evaluation_id"],
            plan_sha256=entry["plan_sha256"],
            final_test_opened=True,
            model_count=len(frozen),
            scientific_champion=None,
            elapsed_seconds=time.monotonic() - began,
            limitations=LIMITATIONS
            + [
                "Targets are conditional on observable futures; missingness is informative.",
                "Sparse single-day coverage cannot establish generalization or policy usefulness.",
                "Validation selection is development-only; frozen test outcomes cannot retune weights or thresholds.",
            ],
        )
        atomic_json(directory / "report.json", report)
        update("FINALIZING_RESULT", report_sha256=file_hash(directory / "report.json"))
        consume_final_test(ledger, entry["evaluation_id"], progress["report_sha256"])
        update("SUCCEEDED")
        return report
    except Exception as error:
        update("FAILED", error_type=type(error).__name__, error=str(error))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--audit-bundle", type=Path)
    args = parser.parse_args()
    values = json.loads(args.spec.read_text()) if args.spec else {}
    if "targets" in values:
        values["targets"] = tuple(values["targets"])
    report = run(
        args.dataset, args.root, args.ledger, TrainingSpec(**values), audit=args.audit_bundle
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("run_id", "state", "model_count", "elapsed_seconds")
                if k in report
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
