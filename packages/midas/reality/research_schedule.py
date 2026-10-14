"""Bounded daily checks and at most one frozen offline research plan per UTC week."""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from .foundry import build
from .model_training import TrainingSpec, code_identity, run
from .research_schema import DatasetSpec, digest
from .research_validation import audit_public_labels
from .storage import atomic_json, file_hash, manifest, records

DAY_NS = 86400 * 10**9


def prune_disposable(
    dataset_root: Path, training_root: Path, *, keep: int = 1
) -> list[dict[str, Any]]:
    """Only completed, explicitly marked scheduled JSONL caches. Never raw/code/manifests."""
    completed = []
    for marker in dataset_root.glob("*/disposable-cache.json"):
        directory = marker.parent
        if directory.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", directory.name):
            raise ValueError("Unsafe disposable-cache directory")
        entry = json.loads(marker.read_text())
        if entry.get("retention_class") != "completed_scheduled_example_cache":
            continue
        completed.append((entry["completed_ns"], directory, entry))
    changes: list[dict[str, Any]] = []
    if not completed:
        return changes
    with (training_root / "training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for _, directory, entry in sorted(completed, reverse=True)[keep:]:
            rows = directory / "examples.jsonl"
            if not rows.exists():
                continue
            info = json.loads((directory / "manifest.json").read_text())
            if not re.fullmatch(r"[0-9a-f]{64}", entry["run_id"]):
                raise ValueError("Invalid disposable-cache run identity")
            run_directory = training_root / "runs" / entry["run_id"]
            progress = json.loads((run_directory / "progress.json").read_text())
            report = json.loads((run_directory / "report.json").read_text())
            if (
                progress["state"] != "SUCCEEDED"
                or progress["report_sha256"] != entry["report_sha256"]
                or file_hash(run_directory / "report.json") != entry["report_sha256"]
                or info["dataset_id"] != directory.name
                or digest(info["identity"]) != directory.name
                or file_hash(rows) != info["rows_sha256"]
                or rows.is_symlink()
                or not (directory / "code").is_dir()
                or report["identity"]["dataset_id"] != info["dataset_id"]
                or report["identity"]["rows_sha256"] != info["rows_sha256"]
            ):
                raise ValueError("Disposable cache lacks verified completed provenance")
            change = dict(
                retention_class=entry["retention_class"],
                dataset_id=directory.name,
                rows_sha256=info["rows_sha256"],
                bytes=rows.stat().st_size,
                pruned_ns=time.time_ns(),
                raw_observations_removed=False,
                manifests_and_code_preserved=True,
                regeneration="Use frozen Foundry code, retained source manifest and spec in a separate derivative root",
            )
            # Write-ahead notice makes an interrupted deletion visible.
            atomic_json(directory / "cache-availability.json", dict(state="PRUNING", **change))
            rows.unlink()
            atomic_json(
                directory / "cache-availability.json",
                dict(state="REGENERATABLE_ROWS_PRUNED", **change),
            )
            changes.append(change)
    return changes


def clear_unpublished(dataset_root: Path) -> list[dict[str, Any]]:
    changes = []
    dataset_root.mkdir(parents=True, exist_ok=True)
    with (dataset_root / "builder.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for path in dataset_root.glob(".building-*"):
            if (
                not re.fullmatch(r"\.building-[0-9a-f]{32}", path.name)
                or path.is_symlink()
                or not path.is_dir()
            ):
                raise ValueError("Unexpected unpublished derivative path")
            if any(p.is_symlink() for p in path.rglob("*")):
                raise ValueError("Unpublished derivative contains symlink")
            size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
            shutil.rmtree(path)
            changes.append(
                dict(
                    retention_class="unpublished_scheduled_builder_scratch",
                    path=path.name,
                    bytes=size,
                    raw_observations_removed=False,
                )
            )
    return changes


def tick(config_path: Path, *, now_ns: int | None = None) -> dict[str, Any]:
    config = json.loads(config_path.read_text())
    if (
        config["schema_version"] != 1
        or not 7 <= config["minimum_recorded_days"] <= 30
        or not 7 <= config["window_days"] <= 28
        or not 1 <= config["max_retries_per_week"] <= 2
        or config["reserve_bytes"] < 20 * 1024**3
        or not 64 * 1024**2 <= config["dataset_budget_bytes"] <= 4 * 1024**3
        or not 32 * 1024**2 <= config["training_budget_bytes"] <= 2 * 1024**3
        or not 1 <= config["completed_caches_to_keep"] <= 4
    ):
        raise ValueError("Invalid bounded research schedule")
    raw = Path(config["raw_root"]).resolve()
    state_root = Path(config["state_root"]).resolve()
    training_root = Path(config["training_root"]).resolve()
    ledger = Path(config["evaluation_ledger"]).resolve()
    for p in (state_root, training_root, ledger):
        if p == raw or p.is_relative_to(raw) or raw.is_relative_to(p):
            raise ValueError("Scheduled derivatives must be separate from raw observations")
    state_root.mkdir(parents=True, exist_ok=True)
    training_root.mkdir(parents=True, exist_ok=True)
    with (state_root / "schedule.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(state="BUSY", reason="live scheduler owns lock")
        return _tick(
            config, config_path, raw, state_root, training_root, ledger, now_ns or time.time_ns()
        )


def _tick(
    config: dict[str, Any],
    config_path: Path,
    raw: Path,
    state_root: Path,
    training_root: Path,
    ledger: Path,
    now: int,
) -> dict[str, Any]:
    status_path = state_root / "status.json"
    previous = json.loads(status_path.read_text()) if status_path.exists() else {}
    week = time.strftime("%G-W%V", time.gmtime(now / 10**9))
    source = manifest(raw)
    state: dict[str, Any] = dict(
        checked_ns=now,
        config_sha256=file_hash(config_path),
        week=week,
        collector_dependency="none; read-only finalized catalogs",
        active_forward_campaigns_modified=False,
        automatic_promotion=False,
    )

    def publish(state_name: str, **details: Any) -> dict[str, Any]:
        state.update(state=state_name, **details)
        atomic_json(status_path, state)
        return state

    if not config["enabled"]:
        return publish("DISABLED")
    if previous.get("fit_week") == week and previous.get("state") in {
        "SUCCEEDED",
        "INSUFFICIENT_EVIDENCE",
        "FAILED",
        "LIMIT_REACHED",
    }:
        return publish(
            "ALREADY_ATTEMPTED_THIS_WEEK",
            fit_week=week,
            prior_terminal_state=previous["state"],
            run_id=previous.get("run_id"),
        )
    if previous.get("fit_week") == week and previous.get("state") == "ALREADY_ATTEMPTED_THIS_WEEK":
        return publish("ALREADY_ATTEMPTED_THIS_WEEK", fit_week=week, run_id=previous.get("run_id"))
    if not source["segments"]:
        return publish("WAITING_FOR_OBSERVATIONS")
    first_file = raw / source["segments"][0]["file"]
    if file_hash(first_file) != source["segments"][0]["sha256"]:
        raise ValueError("Initial source segment corruption")
    first = next(records(first_file))[0]["received_ns"]
    if now - first < config["minimum_recorded_days"] * DAY_NS:
        return publish(
            "WAITING_FOR_COVERAGE",
            recorded_span_days=max(0, (now - first) / DAY_NS),
            minimum_recorded_days=config["minimum_recorded_days"],
            next_eligible_ns=first + config["minimum_recorded_days"] * DAY_NS,
            explanation="Raw span is only a trigger; training still checks actual target/family/time coverage.",
        )
    week_root = state_root / "weeks" / week
    week_root.mkdir(parents=True, exist_ok=True)
    frozen = week_root / "input.json"
    if frozen.exists():
        frozen_input = json.loads(frozen.read_text())
        if (
            frozen_input["config_sha256"] != file_hash(config_path)
            or frozen_input["training_code"] != code_identity()
        ):
            return publish(
                "FAILED",
                fit_week=week,
                reason="Frozen weekly input/code changed; require a new future period",
            )
    else:
        frozen_input = dict(
            config_sha256=file_hash(config_path),
            source_manifest=source,
            training_code=code_identity(),
            start_ns=max(first, now - config["window_days"] * DAY_NS),
            end_ns=now,
            attempts=0,
        )
    if frozen_input["attempts"] >= 1 + config["max_retries_per_week"]:
        return publish("LIMIT_REACHED", fit_week=week, reason="bounded weekly attempt limit")
    frozen_input["attempts"] += 1
    atomic_json(frozen, frozen_input)
    state["fit_week"] = week
    dataset_root = state_root / "datasets"
    if dataset_root.is_symlink() or not dataset_root.resolve().is_relative_to(state_root):
        raise ValueError("Unsafe scheduled dataset root")
    pruning = []
    try:
        if config["disposable_example_cache_pruning"]:
            pruning.extend(
                prune_disposable(
                    dataset_root, training_root, keep=config["completed_caches_to_keep"]
                )
            )
        if config["unpublished_builder_scratch_pruning"]:
            pruning.extend(clear_unpublished(dataset_root))
        if pruning:
            atomic_json(
                week_root / ("pruning-" + str(now) + ".json"),
                dict(changes=pruning, raw_observations_removed=False),
            )
        publish(
            "BUILDING_DATASET", fit_week=week, attempt=frozen_input["attempts"], pruning=pruning
        )
        ds = DatasetSpec(
            horizons_ms=(1000,),
            stride_ms=120000,
            max_examples=100000,
            start_ns=frozen_input["start_ns"],
            end_ns=frozen_input["end_ns"],
            derivative_budget_bytes=config["dataset_budget_bytes"],
            reserve_bytes=config["reserve_bytes"],
        )
        data = build(raw, dataset_root, ds, frozen_input["source_manifest"])
        dataset = dataset_root / data["dataset_id"]
        publish("AUDITING_PUBLIC_LABELS", fit_week=week, dataset_id=data["dataset_id"])
        proof = week_root / "source-audit.json"
        if proof.exists():
            bundle = json.loads(proof.read_text())
            if (
                bundle["dataset"]["rows_sha256"] != data["rows_sha256"]
                or bundle["audit"]["dataset_id"] != data["dataset_id"]
            ):
                raise ValueError("Interrupted weekly audit identity changed")
        else:
            audit = audit_public_labels(dataset / "examples.jsonl", data, raw)
            bundle = dict(dataset=data, audit=audit)
            atomic_json(proof, bundle)
        publish("TRAINING_FROZEN_PLAN", fit_week=week, dataset_id=data["dataset_id"])
        result = run(
            dataset,
            training_root,
            ledger,
            TrainingSpec(
                budget_bytes=config["training_budget_bytes"], reserve_bytes=config["reserve_bytes"]
            ),
            audit=proof,
        )
        report_path = training_root / "runs" / result["run_id"] / "report.json"
        atomic_json(
            dataset / "disposable-cache.json",
            dict(
                retention_class="completed_scheduled_example_cache",
                completed_ns=time.time_ns(),
                run_id=result["run_id"],
                report_sha256=file_hash(report_path),
            ),
        )
        return publish(
            "INSUFFICIENT_EVIDENCE" if result["state"].startswith("insufficient") else "SUCCEEDED",
            fit_week=week,
            dataset_id=data["dataset_id"],
            run_id=result["run_id"],
            report_sha256=file_hash(report_path),
            model_count=result.get("model_count", 0),
            no_forward_thresholds_retuned=True,
        )
    except Exception as error:
        publish("FAILED", fit_week=week, error_type=type(error).__name__, error=str(error))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(tick(args.config), indent=2))


if __name__ == "__main__":
    main()
