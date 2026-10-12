"""Rule-based research plans: validation selection followed by frozen challenges."""

import json
import time
from pathlib import Path
from typing import Any

from pydantic import Field

from midas.arena.artifacts import artifact_path, atomic_json
from midas.arena.datasets import DatasetSpec, load, research_hash
from midas.arena.evolution import SweepSpec, run_sweep
from midas.arena.tournaments import TournamentSpec, run_tournament
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory.campaigns import revision


class DirectorSpec(Model):
    dataset_id: str
    incumbent_model_ids: tuple[str, ...] = Field(default=(), max_length=8)
    challenge_seed: int = Field(default=53071, ge=0, le=2**32 - 20000)
    episodes: int = Field(default=100, ge=30, le=300)
    training_epochs: int = Field(default=80, ge=5, le=200)


def run_director(root: Path, spec: DirectorSpec, progress: Any = None) -> dict[str, Any]:
    dataset, _ = load(root, spec.dataset_id)
    source_hash = research_hash()
    identity = (
        "director-"
        + digest([spec.model_dump(mode="json"), dataset["rows_sha256"], source_hash])[:24]
    )
    directory = artifact_path(root, "directors", identity)
    file = directory / "manifest.json"
    if file.exists():
        record: dict[str, Any] = json.loads(file.read_text())
        if record["state"] == "COMPLETED":
            return record
    else:
        record = {
            "director_id": identity,
            "state": "RUNNING",
            "created_at": time.time(),
            "code_revision": revision(),
            "source_hash": source_hash,
            "dataset_sha256": dataset["rows_sha256"],
            "configuration": spec.model_dump(mode="json"),
            "research_question": "Does model quality survive fresh seeds and a changed family/settlement relationship, and does input-support abstention improve downside?",
            "hypothesis": "Validation-selected simpler predictors remain competitive; unsupported-state abstention reduces extrapolation risk.",
            "planning_rule": "Initial data quality showed family/seed shortcuts and initial-state constants; select on validation, then test independent identities with reordered families.",
            "steps": [
                {"name": name, "state": "PENDING", "artifact": None}
                for name in (
                    "validation-only multi-seed selection",
                    "fresh challenge with support warnings",
                    "matched challenge with support abstention",
                )
            ],
            "stopping_condition": "Exactly three preregistered stages; no adaptive refitting or threshold selection after final evaluations.",
        }
        atomic_json(file, record)
    for index, step in enumerate(record["steps"]):
        if step["state"] == "COMPLETED":
            continue
        record["current_stage"] = step["name"]
        phase = getattr(progress, "phase", None)
        if phase:
            phase(step["name"])

        class Progress:
            def __init__(self, item: dict[str, Any]) -> None:
                self.step = item

            def __call__(self, done: int, total: int) -> None:
                self.step["progress"] = {"done": done, "total": total}
                atomic_json(file, record)
                if progress:
                    progress(done, total)

            def register(self, kind: str, artifact_id: str) -> None:
                self.step.update(state="RUNNING", artifact={"kind": kind, "identity": artifact_id})
                atomic_json(file, record)
                register = getattr(progress, "register", None)
                if register:
                    register(kind, artifact_id)

        callback = Progress(step)
        if index == 0:
            result = run_sweep(
                root, SweepSpec(dataset_id=spec.dataset_id, epochs=spec.training_epochs), callback
            )
            step["artifact"] = {"kind": "sweeps", "identity": result["sweep_id"]}
            record["selected_model_id"] = result["selection"]["selected_model_id"]
        else:
            policy_ids = tuple(
                dict.fromkeys((*spec.incumbent_model_ids, record["selected_model_id"]))
            )
            challenge = DatasetSpec(
                episodes=spec.episodes,
                seed=spec.challenge_seed,
                families=("one_sided", "deep", "volatile", "calm", "disappearing", "thin"),
                observation_latency_ms=dataset["spec"]["observation_latency_ms"],
            )
            configuration = TournamentSpec(
                dataset_id=spec.dataset_id,
                model_ids=policy_ids,
                challenge=challenge,
                max_episodes=spec.episodes,
                unsupported_input_policy="warn" if index == 1 else "abstain",
            )
            previous = step.get("artifact")
            previous_file = (
                artifact_path(root, previous["kind"], previous["identity"]) / "manifest.json"
                if previous and previous["kind"] == "tournaments"
                else None
            )
            if previous_file and previous_file.exists():
                result = json.loads(previous_file.read_text())
                if (
                    result["configuration"] != configuration.model_dump(mode="json")
                    or result["source_hash"] != source_hash
                ):
                    raise ValueError("Director stage provenance differs from the frozen plan")
            else:
                result = run_tournament(root, configuration, callback)
            step["artifact"] = {"kind": "tournaments", "identity": result["tournament_id"]}
            step["conclusion"] = result["conclusion"]
        step.update(state="COMPLETED", completed_at=time.time())
        atomic_json(file, record)
    record.update(
        state="COMPLETED",
        completed_at=time.time(),
        current_stage=None,
        interpretation="The plan completed real optimization and independent matched evaluations. Individual outcomes and uncertainty remain attached; no broad model promotion is automatic.",
    )
    atomic_json(file, record)
    finding = {
        "finding_id": identity,
        "director_id": identity,
        "title": "Fresh-seed and input-support research plan completed",
        "research_question": record["research_question"],
        "hypothesis": record["hypothesis"],
        "interpretation": record["interpretation"],
        "code_revision": record["code_revision"],
        "source_hash": source_hash,
        "seed": spec.challenge_seed,
        "configuration": spec.model_dump(mode="json"),
        "outcome": record["steps"],
        "created_at": time.time(),
        "caveats": [
            "Synthetic hypothetical execution only.",
            "Repeated warning/abstention studies share the same independent challenge identities.",
            "No final-evaluation outcome changes the fitted candidate or threshold.",
        ],
        "next_experiment": "Use paired challenge outcomes to investigate loss attribution and unmatched-risk labels; do not tune against the opened challenge.",
    }
    atomic_json(artifact_path(root, "findings", identity) / "manifest.json", finding)
    return record
