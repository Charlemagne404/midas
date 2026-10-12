"""Bounded validation-only policy selection followed by a preregistered fresh test."""

import json
import math
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.datasets import DatasetSpec, load, research_hash
from midas.arena.supervised import Predictor
from midas.arena.tournaments import GateSpec, TournamentSpec, run_tournament
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory.campaigns import revision


class PolicySearchSpec(Model):
    dataset_id: str
    model_id: str
    thresholds: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5)
    sizes: tuple[Literal["full", "half"], ...] = ("full", "half")
    validation_episodes: int = Field(default=160, ge=30, le=200)
    challenge_seed: int = Field(default=93071, ge=0, le=2**32 - 20000)
    challenge_episodes: int = Field(default=100, ge=30, le=300)

    @model_validator(mode="after")
    def bounded(self) -> "PolicySearchSpec":
        if not self.thresholds or not self.sizes or len(self.thresholds) * len(self.sizes) > 12:
            raise ValueError("Use one to twelve preregistered gates")
        if any(not math.isfinite(t) or not 0 <= t <= 1 for t in self.thresholds):
            raise ValueError("Thresholds must be finite probabilities")
        if (
            set(self.sizes) - {"full", "half"}
            or len(set(self.sizes)) != len(self.sizes)
            or len(set(self.thresholds)) != len(self.thresholds)
        ):
            raise ValueError("Invalid or duplicate gate configuration")
        return self


def select_policy(report: dict[str, Any], gates: tuple[GateSpec, ...]) -> dict[str, Any]:
    if report["configuration"]["partition"] != "validation" or report["configuration"].get(
        "challenge"
    ):
        raise ValueError("Policy selection requires validation-only outcomes")
    allowed = {g.identity: g for g in gates}
    control = next(r for r in report["leaderboard"] if r["policy"] == "no_trade")
    eligible = [
        r
        for r in report["leaderboard"]
        if r["policy"] in allowed
        and r["invariant_violations"] == 0
        and r["base_episodes"] >= 30
        and r["score"] > control["score"]
        and next(
            p["bootstrap_95"][0]
            for p in report["paired"]
            if p["policy"] == r["policy"] and p["control"] == "no_trade"
        )
        > 0
    ]
    if not eligible:
        return {
            "policy": "no_trade",
            "gate": None,
            "reason": "No gate clears validation downside score and paired mean uncertainty versus no-trade.",
        }
    best = max(r["score"] for r in eligible)
    tied = [
        allowed[r["policy"]]
        for r in eligible
        if math.isclose(r["score"], best, rel_tol=1e-9, abs_tol=1e-9)
    ]
    selected = min(tied, key=lambda g: (g.size != "half", g.threshold, g.identity))
    return {
        "policy": selected.identity,
        "gate": selected.model_dump(mode="json"),
        "tied_leaders": [g.identity for g in tied],
        "reason": "Maximize validation mean minus 5% tail loss, require paired mean CI lower bound > 0; prefer half-size then stricter risk threshold for ties.",
    }


def novel_seeds(root: Path, seed: int, episodes: int) -> None:
    planned = set(range(seed, seed + episodes))
    specs = [json.loads(p.read_text())["spec"] for p in root.glob("datasets/*/manifest.json")]
    for file in root.glob("tournaments/*/manifest.json"):
        record = json.loads(file.read_text())
        configuration = record["configuration"]
        generator = record.get("evaluation_generator") or configuration.get("challenge")
        if generator is None:
            dataset_file = (
                artifact_path(root, "datasets", configuration["dataset_id"]) / "manifest.json"
            )
            generator = json.loads(dataset_file.read_text())["spec"]
        specs.append(generator)
    for file in root.glob("tournaments/*/preparing.json"):
        challenge = json.loads(file.read_text())["configuration"].get("challenge")
        if challenge:
            specs.append(challenge)
    for spec in specs:
        if planned & set(range(spec["seed"], spec["seed"] + spec["episodes"])):
            raise ValueError("Fresh policy test overlaps previously registered scenario seeds")


def run_search(root: Path, spec: PolicySearchSpec, progress: Any = None) -> dict[str, Any]:
    dataset, _ = load(root, spec.dataset_id)
    predictor = Predictor.load(root, spec.model_id)
    model = json.loads((artifact_path(root, "models", spec.model_id) / "manifest.json").read_text())
    if (
        model["dataset_id"] != spec.dataset_id
        or predictor.parameters.get("label_target", "completion") != "unmatched"
    ):
        raise ValueError(
            "Risk policy search requires a model trained on the specified unmatched dataset"
        )
    source = research_hash()
    identity = (
        "search-"
        + digest(
            [spec.model_dump(mode="json"), dataset["rows_sha256"], model["artifact_sha256"], source]
        )[:24]
    )
    directory = artifact_path(root, "searches", identity)
    file = directory / "manifest.json"
    if file.exists():
        record: dict[str, Any] = json.loads(file.read_text())
        if record["state"] == "COMPLETED":
            return record
        record["owner_job_id"] = getattr(progress, "job_id", None) or record.get("owner_job_id")
        atomic_json(file, record)
    else:
        novel_seeds(root, spec.challenge_seed, spec.challenge_episodes)
        record = {
            "search_id": identity,
            "owner_job_id": getattr(progress, "job_id", None),
            "state": "RUNNING",
            "created_at": time.time(),
            "configuration": spec.model_dump(mode="json"),
            "dataset_sha256": dataset["rows_sha256"],
            "model_artifact_sha256": model["artifact_sha256"],
            "source_hash": source,
            "code_revision": revision(),
            "validation_tournament": None,
            "test_tournament": None,
            "selection": None,
            "test_used_for_selection": False,
            "limitations": [
                "Synthetic hypothetical research; no live execution or automatic promotion.",
                "Full-proposal risk scores do not separately calibrate half-size fills.",
                "Validation search has selection bias; the fresh test is not a tuning set.",
                "Exactly two stages; no adaptive threshold changes after final evaluation.",
            ],
        }
        atomic_json(file, record)
    gates = tuple(
        GateSpec(model_id=spec.model_id, threshold=t, size=size)
        for t in spec.thresholds
        for size in spec.sizes
    )
    for stage in ("validation", "test"):
        key = f"{stage}_tournament"
        if stage == "test":
            assert record["selection"] is not None
        configuration = TournamentSpec(
            dataset_id=spec.dataset_id,
            partition="validation" if stage == "validation" else "test",
            gates=gates
            if stage == "validation"
            else (
                (GateSpec.model_validate(record["selection"]["gate"]),)
                if record["selection"]["gate"]
                else ()
            ),
            max_episodes=spec.validation_episodes
            if stage == "validation"
            else spec.challenge_episodes,
            challenge=None
            if stage == "validation"
            else DatasetSpec(
                episodes=spec.challenge_episodes,
                seed=spec.challenge_seed,
                families=tuple(dataset["spec"]["families"]),
                observation_latency_ms=dataset["spec"]["observation_latency_ms"],
                label_target="unmatched",
                decision_scope=dataset["spec"].get("decision_scope", "initial"),
            ),
        )
        phase = getattr(progress, "phase", None)
        if phase:
            phase(f"{stage} policy comparison")

        class Progress:
            def __init__(self, stage_key: str) -> None:
                self.stage_key = stage_key

            def __call__(self, done: int, total: int) -> None:
                record["progress"] = {"done": done, "total": total}
                atomic_json(file, record)
                if progress:
                    progress(done, total)

            def register(self, kind: str, artifact_id: str) -> None:
                record[self.stage_key] = artifact_id
                atomic_json(file, record)
                callback = getattr(progress, "register", None)
                if callback:
                    callback(kind, artifact_id)

        previous = (
            artifact_path(root, "tournaments", record[key]) / "manifest.json"
            if record[key]
            else None
        )
        if previous and previous.exists():
            report = json.loads(previous.read_text())
            if (
                report["configuration"] != configuration.model_dump(mode="json")
                or report["source_hash"] != source
            ):
                raise ValueError("Saved policy stage provenance differs")
        else:
            report = run_tournament(root, configuration, Progress(key))
        record[key] = report["tournament_id"]
        if stage == "validation":
            record["selection"] = select_policy(report, gates)
        else:
            record["conclusion"] = report["conclusion"]
        atomic_json(file, record)
    record.update(state="COMPLETED", completed_at=time.time())
    atomic_json(file, record)
    return record
