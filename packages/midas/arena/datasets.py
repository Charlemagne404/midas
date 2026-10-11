"""Frozen synthetic, episode-grouped datasets built from real simulator outcomes."""

import json
import time
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json, sha256
from midas.arena.features import FEATURE_VERSION, FEATURES, extract
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory import VERSION as SIMULATOR_VERSION
from midas.laboratory.campaigns import code_hash, revision
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import FAMILIES, generate
from midas.paper.broker import ExecutionModel


class DatasetSpec(Model):
    version: str = "synthetic-decision-1"
    episodes: int = Field(default=1000, ge=30, le=20000)
    seed: int = Field(default=42070, ge=0, le=2**32 - 20000)
    split_seed: int = Field(default=1977, ge=0)
    families: tuple[str, ...] = ("calm", "volatile", "thin", "deep", "one_sided", "disappearing")
    execution_models: tuple[str, ...] = ("optimistic", "standard", "conservative")
    observation_latency_ms: int = Field(default=100, ge=0, le=60000)

    @model_validator(mode="after")
    def supported(self) -> "DatasetSpec":
        if (
            not self.families
            or set(self.families) - set(FAMILIES)
            or "ledger_mutation" in self.families
        ):
            raise ValueError("Use valid scenario families without controlled software defects")
        if not self.execution_models or set(self.execution_models) - {
            "optimistic",
            "standard",
            "conservative",
        }:
            raise ValueError("Unknown execution models")
        if len(set(self.families)) != len(self.families) or len(set(self.execution_models)) != len(
            self.execution_models
        ):
            raise ValueError("Duplicate families or models")
        return self


def partition(base_episode_id: str, split_seed: int) -> str:
    # Hash assignment depends only on independent episode identity, never on labels/variants.
    fraction = int(digest(["episode-split-1", split_seed, base_episode_id])[:16], 16) / 2**64
    return "train" if fraction < 0.7 else "validation" if fraction < 0.85 else "test"


def first_decision(scenario: Any, retain: bool = False) -> Environment:
    env = Environment(scenario, retain=retain)
    while not env.finished:
        event = env.clock.peek()
        if event and event.kind == "decision":
            return env
        env.step()
    raise ValueError("Scenario contains no decision")


def sample(spec: DatasetSpec, index: int, model: str) -> dict[str, Any] | None:
    seed = spec.seed + index
    family = spec.families[index % len(spec.families)]
    execution = ExecutionModel.preset(model).model_copy(update={"seed": seed})
    scenario = generate(family, seed, execution).model_copy(
        update={"observation_latency_ms": spec.observation_latency_ms}
    )
    env = first_decision(scenario)
    observation = env.observe()
    features, eligible = extract(observation, scenario.account, scenario.observation_latency_ms)
    if not eligible:
        return None
    env.step()
    initial_ids = tuple(env.state["positions"])
    # A mathematical opportunity rejected by hard risk admission isn't an execution label.
    if not initial_ids:
        return None
    result = env.run()
    if not result["passed"] or not result["complete"]:
        raise ValueError(f"Invalid training simulation: {result['errors']}")
    orders = env.state["positions"][initial_ids[0]]["exchange"]["orders"]
    complete = len(orders) == 2 and all(o["status"] == "FILLED" for o in orders)
    # Base identity is shared across all execution variants. Seed stays metadata only.
    base_id = f"{family}:{seed}"
    return {
        "base_episode_id": base_id,
        "index": index,
        "family": family,
        "seed": seed,
        "execution_model": model,
        "partition": partition(base_id, spec.split_seed),
        "decision_time_ms": observation["time_ms"],
        "features": features,
        "label": int(complete),
        "scenario_hash": result["scenario_hash"],
        "result_hash": result["result_hash"],
        "strategy_version": result["strategy_version"],
        "simulation_version": result["simulator_version"],
        "economic_assumptions": result["economic_assumptions"],
    }


def research_hash() -> str:
    return digest(
        [code_hash(), [(p.name, sha256(p)) for p in sorted(Path(__file__).parent.glob("*.py"))]]
    )


def build(root: Path, spec: DatasetSpec, progress: Any = None) -> dict[str, Any]:
    source_hash = research_hash()
    identity = (
        "dataset-" + digest([spec.model_dump(mode="json"), source_hash, FEATURE_VERSION])[:24]
    )
    directory = artifact_path(root, "datasets", identity)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        return load(root, identity)[0]
    rows = []
    began = time.monotonic()
    execution_revision = revision()
    for index in range(spec.episodes):
        checkpoint = directory / "episodes" / f"{index:06d}.json"
        if checkpoint.exists():
            episode_rows = json.loads(checkpoint.read_text())
        else:
            episode_rows = []
            for model in spec.execution_models:
                row = sample(spec, index, model)
                if row is not None:
                    episode_rows.append(row)
            atomic_json(checkpoint, episode_rows)
        rows.extend(episode_rows)
        if progress:
            progress(index + 1, spec.episodes)
    validate_rows(rows)
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "rows.json", rows)
    partitions = {
        name: sorted({r["base_episode_id"] for r in rows if r["partition"] == name})
        for name in ("train", "validation", "test")
    }
    manifest = {
        "dataset_id": identity,
        "version": spec.version,
        "created_at": time.time(),
        "provenance": "GENERATED",
        "source": "Midas Laboratory synthetic generator",
        "generator_version": SIMULATOR_VERSION,
        "simulation_version": SIMULATOR_VERSION,
        "spec": spec.model_dump(mode="json"),
        "feature_version": FEATURE_VERSION,
        "feature_schema": list(FEATURES),
        "label_definition": "Both initial risk-admitted proposal orders finish FILLED; later proposals do not affect label",
        "code_revision": execution_revision,
        "source_hash": source_hash,
        "rows_sha256": sha256(directory / "rows.json"),
        "rows": len(rows),
        "generated_base_episodes": spec.episodes,
        "eligible_base_episodes": len({r["base_episode_id"] for r in rows}),
        "excluded_variants": spec.episodes * len(spec.execution_models) - len(rows),
        "partition_identities": partitions,
        "partition_rows": {name: sum(r["partition"] == name for r in rows) for name in partitions},
        "label_frequency": {
            name: sum(r["label"] for r in rows if r["partition"] == name)
            / sum(r["partition"] == name for r in rows)
            for name in partitions
        },
        "duration_seconds": time.monotonic() - began,
        "limitations": [
            "Synthetic hypothetical fills; no empirical calibration or real profitability evidence",
            "Only first risk-admitted decision is labeled; rejected and ineligible variants excluded",
            "Episode variants are correlated; partitions group family/seed identities",
            "Generator settlement uses seed parity; seeds and identifiers are excluded from features",
            "Execution configuration is an assumption available to a research policy",
        ],
    }
    atomic_json(manifest_path, manifest)
    return manifest


def validate_rows(rows: list[dict[str, Any]]) -> None:
    import math

    seen: set[tuple[str, str]] = set()
    groups: dict[str, str] = {}
    for row in rows:
        key = (row["base_episode_id"], row["execution_model"])
        if key in seen:
            raise ValueError("Duplicate episode variant")
        seen.add(key)
        name = row["partition"]
        if name not in {"train", "validation", "test"}:
            raise ValueError("Unknown partition")
        if groups.setdefault(row["base_episode_id"], name) != name:
            raise ValueError("Episode variants leak across partitions")
        if row["label"] not in (0, 1) or len(row["features"]) != len(FEATURES):
            raise ValueError("Invalid label or feature schema")
        if not all(math.isfinite(value) for value in row["features"]):
            raise ValueError("Nonfinite features")
    if set(groups.values()) != {"train", "validation", "test"}:
        raise ValueError("Dataset needs nonempty independent partitions")


def load(root: Path, identity: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    directory = artifact_path(root, "datasets", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Dataset content hash mismatch")
    if (
        manifest["feature_schema"] != list(FEATURES)
        or manifest["feature_version"] != FEATURE_VERSION
    ):
        raise ValueError("Unsupported feature schema")
    rows = json.loads((directory / "rows.json").read_text())
    validate_rows(rows)
    for row in rows:
        if row["partition"] != partition(row["base_episode_id"], manifest["spec"]["split_seed"]):
            raise ValueError("Frozen partition assignment mismatch")
    actual = {
        name: sorted({r["base_episode_id"] for r in rows if r["partition"] == name})
        for name in ("train", "validation", "test")
    }
    if actual != manifest["partition_identities"] or len(rows) != manifest["rows"]:
        raise ValueError("Partition manifest mismatch")
    return manifest, rows
