"""Frozen synthetic, episode-grouped datasets built from real simulator outcomes."""

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json, sha256
from midas.arena.cost_labels import VERSION as COST_LABEL_VERSION
from midas.arena.features import FEATURE_VERSION, FEATURES, extract
from midas.arena.persistence import LABEL_DEFINITION, LABEL_VERSION, first_arrival_label
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory import VERSION as SIMULATOR_VERSION
from midas.laboratory.campaigns import code_hash, revision
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import FAMILIES, Costs, generate
from midas.paper.broker import ExecutionModel


class DatasetSpec(Model):
    version: str = "synthetic-decision-1"
    episodes: int = Field(default=1000, ge=30, le=20000)
    seed: int = Field(default=42070, ge=0, le=2**32 - 20000)
    split_seed: int = Field(default=1977, ge=0)
    families: tuple[str, ...] = ("calm", "volatile", "thin", "deep", "one_sided", "disappearing")
    execution_models: tuple[str, ...] = ("optimistic", "standard", "conservative")
    observation_latency_ms: int = Field(default=100, ge=0, le=60000)
    label_target: Literal["completion", "unmatched", "persistence"] = "completion"
    decision_scope: Literal["initial", "first_admitted"] = "initial"
    retain_execution_costs: bool = False
    costs: Costs | None = None

    @model_validator(mode="after")
    def supported(self) -> "DatasetSpec":
        if self.costs is not None and not self.retain_execution_costs:
            raise ValueError("Explicit dataset costs require execution-cost evidence retention")
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


def first_decision(scenario: Any, retain: bool = False, cost_evidence: bool = False) -> Environment:
    from midas.arena.cost_environment import CostEnvironment

    env = (
        CostEnvironment(scenario, retain=retain)
        if cost_evidence
        else Environment(scenario, retain=retain)
    )
    while not env.finished:
        event = env.clock.peek()
        if event and event.kind == "decision":
            return env
        env.step()
    raise ValueError("Scenario contains no decision")


def initial_outcome(exchange: dict[str, Any]) -> dict[str, Any]:
    orders = exchange["orders"]
    if len(orders) != 2 or len({o["asset_id"] for o in orders}) != 2:
        raise ValueError("Initial proposal must contain two distinct legs")
    quantities = {o["asset_id"]: Decimal(0) for o in orders}
    order_ids = {o["id"] for o in orders}
    for entry in exchange["ledger"]:
        if entry["kind"] == "fill" and entry["order_id"] in order_ids:
            quantity = Decimal(entry["quantity"])
            if not quantity.is_finite() or quantity < 0:
                raise ValueError("Invalid initial fill quantity")
            quantities[entry["asset_id"]] += quantity
    first, second = quantities.values()
    unmatched = abs(first - second)
    return {
        "completion": int(all(o["status"] == "FILLED" for o in orders)),
        "unmatched": int(unmatched > 0),
        "residual_unmatched_shares": str(unmatched),
        "filled_shares_by_asset": {asset: str(quantity) for asset, quantity in quantities.items()},
    }


def sample(spec: DatasetSpec, index: int, model: str) -> dict[str, Any] | None:
    seed = spec.seed + index
    family = spec.families[index % len(spec.families)]
    execution = ExecutionModel.preset(model).model_copy(update={"seed": seed})
    scenario = generate(family, seed, execution).model_copy(
        update={"observation_latency_ms": spec.observation_latency_ms}
    )
    if spec.costs is not None:
        scenario = scenario.model_copy(update={"costs": spec.costs})
    env = first_decision(scenario, cost_evidence=spec.retain_execution_costs)
    ordinal = 0
    while not env.finished:
        ordinal += 1
        observation = env.observe()
        features, eligible = extract(observation, scenario.account, scenario.observation_latency_ms)
        if spec.decision_scope == "initial" and not eligible:
            return None
        env.step()
        initial_ids = tuple(env.state["positions"])
        # A rejected proposal isn't an execution label. First-admitted sampling
        # advances the actual event engine without opening an earlier position.
        if initial_ids:
            break
        if spec.decision_scope == "initial":
            return None
        while not env.finished:
            event = env.clock.peek()
            if event and event.kind == "decision":
                break
            env.step()
    else:
        return None
    persistence = None
    if spec.label_target == "persistence":
        persistence = first_arrival_label(env, initial_ids[0])
    quoted_cost = None
    if spec.retain_execution_costs:
        from midas.arena.cost_labels import quote_baseline

        quoted_cost = quote_baseline(
            observation, features[FEATURES.index("proposed_quantity")], scenario.costs
        )
    result = env.run()
    if not result["passed"] or not result["complete"]:
        raise ValueError(f"Invalid training simulation: {result['errors']}")
    outcome = initial_outcome(env.state["positions"][initial_ids[0]]["exchange"])
    # Base identity is shared across all execution variants. Seed stays metadata only.
    base_id = f"{family}:{seed}"
    row = {
        "base_episode_id": base_id,
        "index": index,
        "family": family,
        "seed": seed,
        "execution_model": model,
        "partition": partition(base_id, spec.split_seed),
        "decision_time_ms": observation["time_ms"],
        "decision_ordinal": ordinal,
        "features": features,
        "label": persistence["label"] if persistence is not None else outcome[spec.label_target],
        "label_target": spec.label_target,
        "label_version": persistence["label_version"]
        if persistence is not None
        else "initial-proposal-outcomes-2",
        "decision_scope": spec.decision_scope,
        "initial_outcome": outcome,
        "scenario_hash": result["scenario_hash"],
        "result_hash": result["result_hash"],
        "strategy_version": result["strategy_version"],
        "simulation_version": result["simulator_version"],
        "economic_assumptions": result["economic_assumptions"],
    }
    if spec.retain_execution_costs:
        from midas.arena.cost_environment import CostEnvironment
        from midas.arena.cost_labels import outcome as cost_outcome

        assert quoted_cost is not None and isinstance(env, CostEnvironment)
        row["execution_cost_outcome"] = cost_outcome(
            env.state["positions"][initial_ids[0]]["exchange"],
            observation,
            scenario.costs,
            env.last_ts,
            quoted_cost,
            env.financing_trace,
        )
    if persistence is not None:
        row["persistence_outcome"] = persistence
    return row


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
        "label_target": spec.label_target,
        "label_version": LABEL_VERSION
        if spec.label_target == "persistence"
        else "initial-proposal-outcomes-2",
        "decision_scope": spec.decision_scope,
        "execution_cost_label": COST_LABEL_VERSION if spec.retain_execution_costs else None,
        "label_definition": (
            LABEL_DEFINITION
            if spec.label_target == "persistence"
            else "Both sampled risk-admitted proposal orders finish FILLED; later proposals do not affect label"
            if spec.label_target == "completion"
            else "Unequal acquired shares across sampled proposal legs after all its fills, before settlement; both zero fills and matched partial fills are negative. Later proposals do not affect label."
        ),
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
            f"Only {spec.decision_scope} decision scope is labeled; rejected and ineligible variants excluded. Later portfolio states remain outside this dataset.",
            "Episode variants are correlated; partitions group family/seed identities",
            "Generator settlement uses seed parity; seeds and identifiers are excluded from features",
            "Execution configuration is an assumption available to a research policy",
            "Residual unmatched shares are post-execution labels only; not decision features or guaranteed loss severity",
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
    scope = manifest.get("decision_scope", "initial")
    if scope != manifest["spec"].get("decision_scope", "initial"):
        raise ValueError("Dataset decision scope differs from frozen specification")
    if manifest.get("label_target", "completion") != manifest["spec"].get(
        "label_target", "completion"
    ):
        raise ValueError("Dataset target differs from frozen specification")
    validate_rows(rows)
    for row in rows:
        if manifest["spec"].get("retain_execution_costs", False):
            from midas.arena.cost_labels import label as cost_label

            if row.get("execution_cost_outcome", {}).get("version") != manifest.get(
                "execution_cost_label"
            ):
                raise ValueError("Cost row version differs from frozen dataset manifest")
            cost_label(row)
        if row.get("decision_scope", "initial") != scope:
            raise ValueError("Row decision scope differs from manifest")
        target = manifest.get("label_target", "completion")
        if row.get("label_target", "completion") != target:
            raise ValueError("Row label target differs from manifest")
        if target == "persistence":
            if (
                row["label"] != row["persistence_outcome"]["label"]
                or row["label_version"] != LABEL_VERSION
            ):
                raise ValueError("Persistence label differs from saved venue outcome")
        elif "initial_outcome" in row and row["label"] != row["initial_outcome"][target]:
            raise ValueError("Label differs from saved initial proposal outcome")
        if row["partition"] != partition(row["base_episode_id"], manifest["spec"]["split_seed"]):
            raise ValueError("Frozen partition assignment mismatch")
    actual = {
        name: sorted({r["base_episode_id"] for r in rows if r["partition"] == name})
        for name in ("train", "validation", "test")
    }
    if actual != manifest["partition_identities"] or len(rows) != manifest["rows"]:
        raise ValueError("Partition manifest mismatch")
    return manifest, rows


def observation_lineage(root: Path, identity: str) -> dict[str, str]:
    """Verify target-only derivations and identify their shared frozen observations."""
    seen: set[str] = set()
    original_id = identity
    while True:
        if identity in seen:
            raise ValueError("Cyclic dataset derivation")
        seen.add(identity)
        manifest, rows = load(root, identity)
        if manifest["dataset_id"] != identity:
            raise ValueError("Dataset manifest identity mismatch")
        ignored = {"label", "label_target"}
        observations = [{k: v for k, v in row.items() if k not in ignored} for row in rows]
        lineage = manifest.get("derivation")
        if not lineage:
            return {
                "dataset_id": original_id,
                "source_dataset_id": identity,
                "observation_hash": digest(observations),
            }
        parent_id = lineage["source_dataset_id"]
        parent, parent_rows = load(root, parent_id)
        producer = artifact_path(root, "datasets", identity) / "derivation-producer.py"
        if (
            lineage.get("version") != "paired-target-1"
            or lineage["target"] != manifest["label_target"]
            or parent["rows_sha256"] != lineage["source_rows_sha256"]
            or sha256(producer) != lineage["producer_sha256"]
            or any(
                type(row["label"]) is not int
                or row.get("initial_outcome", {}).get(manifest["label_target"]) != row["label"]
                for row in rows
            )
            or any(
                manifest.get(key) != parent.get(key)
                for key in (
                    "source_hash",
                    "feature_schema",
                    "feature_version",
                    "decision_scope",
                    "generator_version",
                    "simulation_version",
                    "provenance",
                )
            )
            or observations
            != [{k: v for k, v in row.items() if k not in ignored} for row in parent_rows]
            or {k: v for k, v in manifest["spec"].items() if k != "label_target"}
            != {k: v for k, v in parent["spec"].items() if k != "label_target"}
        ):
            raise ValueError("Target derivation changes frozen observation provenance")
        identity = parent_id
