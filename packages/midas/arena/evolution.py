"""Preregistered, bounded multi-seed selection using validation evidence only."""

import json
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.datasets import load, research_hash
from midas.arena.supervised import TrainingSpec, train
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory.campaigns import revision


class Candidate(Model):
    family: Literal["logistic", "tree", "mlp"] = "mlp"
    hidden_size: int = Field(default=32, ge=4, le=256)
    learning_rate: float = Field(default=0.001, gt=0, le=0.1, allow_inf_nan=False)
    weight_decay: float = Field(default=0.0001, ge=0, le=1, allow_inf_nan=False)


class SweepSpec(Model):
    dataset_id: str
    candidates: tuple[Candidate, ...] = (Candidate(family="logistic"), Candidate())
    seeds: tuple[int, ...] = (11, 29)
    epochs: int = Field(default=80, ge=5, le=200)
    practical_brier_tolerance: float = Field(default=0.002, ge=0, le=0.05, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounded(self) -> "SweepSpec":
        if (
            not self.candidates
            or len(self.candidates) * len(self.seeds) > 12
            or len(self.seeds) < 2
        ):
            raise ValueError("Use at least two seeds and at most twelve training trials")
        if len(set(self.seeds)) != len(self.seeds) or any(not 0 <= s < 2**32 for s in self.seeds):
            raise ValueError("Training seeds must be unique uint32 values")
        if len({c.model_dump_json() for c in self.candidates}) != len(self.candidates):
            raise ValueError("Duplicate candidate configuration")
        return self


def select(trials: list[dict[str, Any]], spec: SweepSpec) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    for index, candidate in enumerate(spec.candidates):
        records = [t for t in trials if t["candidate_index"] == index and t["state"] == "COMPLETED"]
        if len(records) != len(spec.seeds):
            continue
        scores = [t["validation"]["brier"] for t in records]
        complexity = {
            "logistic": 20,
            "tree": 100,
            "mlp": 19 * candidate.hidden_size
            + candidate.hidden_size**2
            + 3 * candidate.hidden_size
            + 1,
        }[candidate.family]
        groups.append(
            {
                "candidate_index": index,
                "configuration": candidate.model_dump(mode="json"),
                "mean_validation_brier": float(np.mean(scores)),
                "seed_brier_range": [min(scores), max(scores)],
                "model_ids": [t["model_id"] for t in records],
                "complexity_preference": complexity,
            }
        )
    if not groups:
        raise ValueError("No candidate completed every preregistered training seed")
    best = min(g["mean_validation_brier"] for g in groups)
    equivalent = [
        g for g in groups if g["mean_validation_brier"] <= best + spec.practical_brier_tolerance
    ]
    chosen = min(
        equivalent,
        key=lambda g: (
            g["complexity_preference"],
            g["mean_validation_brier"],
            g["candidate_index"],
        ),
    )
    # Representative seed is chosen on validation, with the selection recorded.
    representative = min(
        (
            t
            for t in trials
            if t["candidate_index"] == chosen["candidate_index"] and t["state"] == "COMPLETED"
        ),
        key=lambda t: (t["validation"]["brier"], t["seed"]),
    )
    return {
        "candidates": groups,
        "selected_candidate_index": chosen["candidate_index"],
        "selected_model_id": representative["model_id"],
        "selection_partition": "validation",
        "criterion": "Mean validation Brier across seeds; prefer the simpler family within the preregistered tolerance. Representative seed minimizes validation Brier.",
        "practical_brier_tolerance": spec.practical_brier_tolerance,
        "caveat": "Seeds repeat optimization on the same dataset; they are not independent market samples. Complexity preference is a documented selection rule, not a measured compute benchmark.",
    }


def run_sweep(root: Path, spec: SweepSpec, progress: Any = None) -> dict[str, Any]:
    dataset, _ = load(root, spec.dataset_id)
    source_hash = research_hash()
    identity = (
        "sweep-" + digest([spec.model_dump(mode="json"), dataset["rows_sha256"], source_hash])[:24]
    )
    directory = artifact_path(root, "sweeps", identity)
    file = directory / "manifest.json"
    if file.exists():
        record: dict[str, Any] = json.loads(file.read_text())
        if record["state"] == "COMPLETED":
            return record
    else:
        record = {
            "sweep_id": identity,
            "state": "RUNNING",
            "created_at": time.time(),
            "code_revision": revision(),
            "source_hash": source_hash,
            "dataset_sha256": dataset["rows_sha256"],
            "configuration": spec.model_dump(mode="json"),
            "trials": [
                {"candidate_index": i, "seed": seed, "state": "PENDING", "model_id": None}
                for i, _ in enumerate(spec.candidates)
                for seed in spec.seeds
            ],
            "test_labels_used_for_selection": False,
        }
        atomic_json(file, record)
    trials = record["trials"]
    for number, trial in enumerate(trials):
        if trial["state"] == "COMPLETED":
            continue
        candidate = spec.candidates[trial["candidate_index"]]
        configuration = TrainingSpec(
            dataset_id=spec.dataset_id,
            seed=trial["seed"],
            epochs=spec.epochs,
            **candidate.model_dump(),
        )
        model_file = (
            artifact_path(root, "models", trial["model_id"]) / "manifest.json"
            if trial["model_id"]
            else None
        )

        class Progress:
            def __init__(self, item: dict[str, Any]) -> None:
                self.trial = item

            def __call__(self, done: int, total: int) -> None:
                self.trial["progress"] = {"done": done, "total": total}
                atomic_json(file, record)
                if progress:
                    progress(done, total)

            def register(self, kind: str, model_id: str) -> None:
                self.trial.update(model_id=model_id, state="RUNNING")
                atomic_json(file, record)
                register = getattr(progress, "register", None)
                if register:
                    register(kind, model_id)

        if model_file and model_file.exists():
            model = json.loads(model_file.read_text())
            if (
                model["dataset_sha256"] != dataset["rows_sha256"]
                or model["source_hash"] != source_hash
            ):
                raise ValueError("Completed sweep trial provenance changed")
        else:
            if trial["model_id"] and candidate.family == "mlp":
                checkpoint = artifact_path(root, "models", trial["model_id"]) / "checkpoint.json"
                if checkpoint.exists():
                    configuration = configuration.model_copy(
                        update={"resume_from": trial["model_id"]}
                    )
            model = train(root, configuration, Progress(trial))
        trial.update(
            state="COMPLETED",
            model_id=model["model_id"],
            validation=model["validation"],
            training_duration_seconds=model["training_duration_seconds"],
            artifact_sha256=model["artifact_sha256"],
        )
        atomic_json(file, record)
        if progress:
            progress(number + 1, len(trials))
    record.update(state="COMPLETED", completed_at=time.time(), selection=select(trials, spec))
    atomic_json(file, record)
    return record
