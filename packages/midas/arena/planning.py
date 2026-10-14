"""Evidence-bound question selection and finite executable research plans."""

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import DatasetSpec, load, observation_lineage, research_hash
from midas.arena.director import DirectorSpec, run_director
from midas.arena.evolution import Candidate, SweepSpec
from midas.core.models import Model
from midas.economics.attestation import digest


class PlanningSpec(Model):
    dataset_id: str
    mode: Literal["auto", "capacity"] = "auto"
    research_question: str | None = Field(default=None, max_length=500)
    challenge_seed: int = Field(default=603071, ge=0, le=2**32 - 20000)
    episodes: int = Field(default=100, ge=30, le=150)
    epochs: int = Field(default=80, ge=5, le=200)


def fresh_groups(root: Path, spec: PlanningSpec, dataset: dict) -> list[str]:
    families = ("one_sided", "deep", "volatile", "calm", "disappearing", "thin")
    wanted = {
        f"{families[i % len(families)]}:{spec.challenge_seed + i}" for i in range(spec.episodes)
    }
    occupied = set()
    for path in (root / "datasets").glob("*/manifest.json"):
        manifest = json.loads(path.read_text())
        for values in manifest.get("partition_identities", {}).values():
            occupied.update(values)
    for path in (root / "tournaments").glob("*/manifest.json"):
        manifest = json.loads(path.read_text())
        rows_path = path.parent / "rows.json"
        if sha256(rows_path) != manifest["rows_sha256"]:
            raise ValueError("Archived scenario rows changed")
        occupied.update(r["base_episode_id"] for r in json.loads(rows_path.read_text()))
    for path in (root / "jobs").glob("*/job.json"):
        configuration = json.loads(path.read_text())["configuration"]
        tournament = configuration.get("tournament")
        if tournament and tournament.get("challenge"):
            challenge = DatasetSpec.model_validate(tournament["challenge"])
            occupied.update(
                f"{challenge.families[i % len(challenge.families)]}:{challenge.seed + i}"
                for i in range(min(challenge.episodes, tournament["max_episodes"]))
            )
        director = configuration.get("director")
        if director:
            occupied.update(
                f"{families[i % len(families)]}:{director['challenge_seed'] + i}"
                for i in range(director["episodes"])
            )
    occupied_seeds = {
        int(value.rsplit(":", 1)[-1]) for value in occupied if value.rsplit(":", 1)[-1].isdigit()
    }
    if wanted & occupied or occupied_seeds & set(
        range(spec.challenge_seed, spec.challenge_seed + spec.episodes)
    ):
        raise ValueError("Planned challenge reuses existing training/evaluation identities")
    return sorted(wanted)


def propose(root: Path, spec: PlanningSpec) -> dict:
    dataset, _ = load(root, spec.dataset_id)
    if dataset.get("label_target", "completion") != "completion":
        raise ValueError("Capacity question requires a completion dataset")
    lineage = observation_lineage(root, spec.dataset_id)
    source_id = lineage["source_dataset_id"]
    evidence = []
    models = []
    for path in sorted((root / "models").glob("*/manifest.json")):
        model = json.loads(path.read_text())
        if (
            model["family"] not in {"logistic", "mlp"}
            or model.get("label_target", "completion") != "completion"
            or not model.get("validation")
        ):
            continue
        if (
            observation_lineage(root, model["dataset_id"])["observation_hash"]
            != lineage["observation_hash"]
        ):
            continue
        weights = path.parent / "parameters.json"
        if sha256(weights) != model["artifact_sha256"]:
            raise ValueError("Planning predictor weights changed")
        models.append(model)
        evidence.append(
            {
                "kind": "models",
                "identity": model["model_id"],
                "manifest_sha256": sha256(path),
                "artifact_sha256": model["artifact_sha256"],
            }
        )
    widths = sorted({m["configuration"]["hidden_size"] for m in models if m["family"] == "mlp"})
    plateau = []
    for path in sorted((root / "findings").glob("*/manifest.json")):
        finding = json.loads(path.read_text())
        outcome = finding.get("outcome", {})
        if (
            not isinstance(outcome, dict)
            or outcome.get("independent_source_groups", 0) < 30
            or outcome.get("changed_parameter_tensors", 0) <= 0
        ):
            continue
        parent_id = outcome.get("parent_model_id")
        if not parent_id:
            continue
        parent_manifest = json.loads(
            (artifact_path(root, "models", parent_id) / "manifest.json").read_text()
        )
        if parent_manifest["family"] != "ppo":
            continue
        if (
            not parent_id
            or observation_lineage(
                root,
                json.loads(
                    (artifact_path(root, "models", parent_id) / "manifest.json").read_text()
                )["dataset_id"],
            )["observation_hash"]
            != lineage["observation_hash"]
        ):
            continue
        paired = next(
            (p for p in outcome.get("paired_comparisons", []) if p.get("control") == parent_id),
            None,
        )
        if (
            not paired
            or paired.get("mean_candidate_minus_control") != 0
            or paired.get("nonzero_variant_differences") != 0
        ):
            continue
        tour = artifact_path(root, "tournaments", outcome["tournament_id"])
        manifest = json.loads((tour / "manifest.json").read_text())
        if sha256(tour / "rows.json") != manifest["rows_sha256"]:
            raise ValueError("Plateau evidence rows changed")
        rows = json.loads((tour / "rows.json").read_text())
        child_id = outcome.get("child_model_id")
        matched = {
            policy: {
                (r["base_episode_id"], r["execution_model"]): r["metrics"]["net_simulated_pnl"]
                for r in rows
                if r["policy"] == policy
            }
            for policy in (parent_id, child_id)
        }
        if (
            not matched[parent_id]
            or matched[parent_id] != matched[child_id]
            or len(rows) != outcome["verified_replays"]
        ):
            raise ValueError("Planning plateau claim differs from actual paired outcomes")
        plateau.append(finding["finding_id"])
        evidence.append(
            {
                "kind": "findings",
                "identity": finding["finding_id"],
                "manifest_sha256": sha256(path),
                "tournament_id": outcome["tournament_id"],
                "rows_sha256": manifest["rows_sha256"],
            }
        )
    if not widths or not models:
        raise ValueError("No completed comparable neural/linear validation evidence")
    if spec.mode == "auto" and (not plateau or any(w != 32 for w in widths)):
        raise ValueError(
            "No eligible automatic capacity question; inspect evidence rather than repeat completed work"
        )
    candidates = (Candidate(family="mlp", hidden_size=16), Candidate(family="mlp", hidden_size=64))
    SweepSpec(dataset_id=spec.dataset_id, candidates=candidates, seeds=(11, 29), epochs=spec.epochs)
    incumbents = []
    for family in ("logistic", "mlp"):
        available = [m for m in models if m["family"] == family]
        if available:
            incumbents.append(
                min(available, key=lambda m: (m["validation"]["brier"], m["model_id"]))["model_id"]
            )
    question = (
        spec.research_question
        or "Does a bounded 16/64-width completion-model comparison improve validation quality and fresh synthetic downside relative to existing predictors?"
    )
    director = DirectorSpec(
        dataset_id=spec.dataset_id,
        incumbent_model_ids=tuple(incumbents),
        challenge_seed=spec.challenge_seed,
        episodes=spec.episodes,
        training_epochs=spec.epochs,
        research_question=question,
        sweep_candidates=candidates,
        sweep_seeds=(11, 29),
        minimum_champion_episodes=2000,
    )
    groups = fresh_groups(root, spec, dataset)
    frozen = {
        "configuration": spec.model_dump(mode="json"),
        "source_hash": research_hash(),
        "dataset_sha256": dataset["rows_sha256"],
        "source_collection": source_id,
        "evidence": evidence,
        "director": director.model_dump(mode="json"),
        "challenge_identities": groups,
        "planning_rule": "Completed PPO optimization plateau plus comparable classifier evidence restricted to width32 => change hypothesis to preregistered width16/64, two training seeds, validation-only selection, frozen fresh support comparisons."
        if spec.mode == "auto"
        else "Explicit bounded capacity template; preregister width16/64 and validation-only selection. No automatic plateau inference.",
        "observed_classifier_widths": widths,
        "plateau_findings": sorted(plateau),
        "question": question,
    }
    identity = "plan-" + digest(frozen)[:24]
    path = artifact_path(root, "plans", identity) / "manifest.json"
    if path.exists():
        record = json.loads(path.read_text())
        if record["frozen"] != frozen:
            raise ValueError("Existing research plan differs")
        return record
    record = {
        "plan_id": identity,
        "state": "PROPOSED",
        "created_at": time.time(),
        "frozen": frozen,
        "budget": {
            "training_trials": 4,
            "tournaments": 2,
            "source_groups": spec.episodes,
            "correlated_variants_max": spec.episodes * 3 * 7 * 2,
            "worker_cpu_cores": 1,
            "worker_memory_mb": 4096,
        },
        "limitations": [
            "Finite rule-based template, not unrestricted natural-language scientific reasoning.",
            "Past findings prioritize the hypothesis; they do not select weights/thresholds from the new challenge.",
            "Warning/abstention studies intentionally share one fresh cohort, not two independent datasets.",
            "No automatic model promotion or real-market profitability claim.",
        ],
    }
    for item in evidence:
        original = artifact_path(root, item["kind"], item["identity"]) / "manifest.json"
        if sha256(original) != item["manifest_sha256"]:
            raise ValueError("Planning evidence changed during proposal")
        atomic_bytes(
            path.parent / "inputs" / item["kind"] / item["identity"] / "manifest.json",
            original.read_bytes(),
        )
    atomic_json(path, record)
    return record


def execute(root: Path, identity: str, progress=None) -> dict:
    path = artifact_path(root, "plans", identity) / "manifest.json"
    record = json.loads(path.read_text())
    frozen = record["frozen"]
    if record["state"] == "COMPLETED":
        return record
    if record["state"] != "PROPOSED":
        raise ValueError("Research plan requires explicit recovery")
    if (
        frozen["source_hash"] != research_hash()
        or load(root, frozen["configuration"]["dataset_id"])[0]["rows_sha256"]
        != frozen["dataset_sha256"]
    ):
        raise ValueError("Planned source or dataset changed")
    for item in frozen["evidence"]:
        source = artifact_path(root, item["kind"], item["identity"]) / "manifest.json"
        if sha256(source) != item["manifest_sha256"]:
            raise ValueError("Bound planning evidence changed")
        snapshot = path.parent / "inputs" / item["kind"] / item["identity"] / "manifest.json"
        if sha256(snapshot) != item["manifest_sha256"]:
            raise ValueError("Captured planning evidence changed")
    fresh_groups(
        root,
        PlanningSpec.model_validate(frozen["configuration"]),
        load(root, frozen["configuration"]["dataset_id"])[0],
    )
    from midas.arena.jobs import artifact_usage

    if artifact_usage(root)[0] >= 1024**3 - 96 * 1024**2:
        raise ValueError("Research plan waits for at least 96MiB Arena headroom")
    record.update(state="RUNNING", started_at=time.time())
    for job_path in (root / "jobs").glob("*/job.json"):
        job = json.loads(job_path.read_text())
        if job.get("state") == "RUNNING" and job["configuration"].get("plan_id") == identity:
            record["owner_job_id"] = job["job_id"]
    register = getattr(progress, "register", None)
    if register:
        register("plans", identity)
    atomic_json(path, record)
    try:
        result = run_director(root, DirectorSpec.model_validate(frozen["director"]), progress)
        record.update(
            state="COMPLETED",
            completed_at=time.time(),
            director_id=result["director_id"],
            selected_model_id=result["selected_model_id"],
        )
        atomic_json(path, record)
        return record
    except BaseException as error:
        record.update(state="FAILED", error=f"{type(error).__name__}: {error}")
        atomic_json(path, record)
        raise
