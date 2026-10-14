"""Matched held-out policy comparisons and episode-grouped uncertainty."""

import json
import math
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json, atomic_replay, sha256
from midas.arena.cost_policy import CostGateSpec, CostPolicy
from midas.arena.datasets import DatasetSpec, load, observation_lineage, research_hash
from midas.arena.economic_regimes import EconomicRegime
from midas.arena.environment import ArenaEnv
from midas.arena.generator_revisions import GeneratorRevision
from midas.arena.rl import indices
from midas.arena.supervised import Predictor
from midas.core.models import Model
from midas.economics.attestation import digest
from midas.laboratory.campaigns import revision
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel


class GateSpec(Model):
    model_id: str
    threshold: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    size: Literal["full", "half"] = "full"

    @property
    def identity(self) -> str:
        return "gate-" + digest(["gate-1", self.model_dump(mode="json")])[:20]


class TournamentSpec(Model):
    purpose: Literal["research", "performance_replay"] = "research"
    dataset_id: str
    model_ids: tuple[str, ...] = ()
    gates: tuple[GateSpec, ...] = Field(default=(), max_length=12)
    cost_gates: tuple[CostGateSpec, ...] = Field(default=(), max_length=4)
    execution_models: tuple[str, ...] = ("optimistic", "standard", "conservative")
    max_episodes: int = Field(default=200, ge=2, le=2000)
    threshold: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    tail_loss_weight: float = Field(default=1, ge=0, le=10, allow_inf_nan=False)
    seed: int = Field(default=991, ge=0)
    adversarial: bool = False
    minimum_champion_episodes: int = Field(default=30, ge=30, le=2000)
    challenge: DatasetSpec | None = None
    partition: Literal["validation", "test"] = "test"
    unsupported_input_policy: Literal["warn", "abstain"] = "abstain"
    economic_regime: EconomicRegime | None = None
    generator_revision: GeneratorRevision | None = None

    @model_validator(mode="after")
    def valid(self) -> "TournamentSpec":
        if self.generator_revision is not None and self.challenge is None:
            raise ValueError(
                "Generator revision requires a fresh challenge, not frozen dataset reuse"
            )
        if not self.execution_models or set(self.execution_models) - {
            "optimistic",
            "standard",
            "conservative",
        }:
            raise ValueError("Unknown execution model")
        if len(set(self.model_ids)) != len(self.model_ids) or len(
            set(self.execution_models)
        ) != len(self.execution_models):
            raise ValueError("Duplicate tournament inputs")
        if len({gate.identity for gate in self.gates}) != len(self.gates):
            raise ValueError("Duplicate policy gate configuration")
        if len({g.identity("forecast") for g in self.cost_gates}) != len(self.cost_gates):
            raise ValueError("Duplicate cost preference configuration")
        return self


def summaries(rows: list[dict[str, Any]], spec: TournamentSpec) -> dict[str, Any]:
    if not rows or not any(r["policy"] == "no_trade" for r in rows):
        raise ValueError("Comparison requires a no-trade control and complete observations")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["policy"]].append(row)
    expected = {(r["base_episode_id"], r["execution_model"]) for r in groups["no_trade"]}
    for values in groups.values():
        identities = [(r["base_episode_id"], r["execution_model"]) for r in values]
        if len(set(identities)) != len(identities) or set(identities) != expected:
            raise ValueError("Unmatched or duplicate policy episode coverage")
    leaderboard = []
    paired = []
    policy_base: dict[str, dict[str, float]] = {}
    control = {r["base_episode_id"]: 0.0 for r in rows if r["policy"] == "no_trade"}
    for policy, values in groups.items():
        pnl = np.array([float(v["metrics"]["net_simulated_pnl"]) for v in values])
        base: dict[str, list[float]] = defaultdict(list)
        for r in values:
            base[r["base_episode_id"]].append(float(r["metrics"]["net_simulated_pnl"]))
        aggregate = np.array([np.mean(base[g]) for g in sorted(base)])
        policy_base[policy] = {g: float(np.mean(values)) for g, values in base.items()}
        rng = np.random.default_rng(spec.seed)
        bootstrap = [
            float(rng.choice(aggregate, len(aggregate), replace=True).mean()) for _ in range(500)
        ]
        ci = np.quantile(bootstrap, [0.025, 0.975]).tolist()
        tail = np.sort(pnl)[: max(1, math.ceil(0.05 * len(pnl)))]
        tail_loss = max(0, -float(tail.mean()))
        record = {
            "policy": policy,
            "variants": len(values),
            "base_episodes": len(base),
            "total_pnl": float(pnl.sum()),
            "mean_pnl": float(pnl.mean()),
            "median_pnl": float(np.median(pnl)),
            "quantiles": np.quantile(pnl, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
            "profitable_fraction": float(np.mean(pnl > 0)),
            "losing_fraction": float(np.mean(pnl < 0)),
            "no_trade_fraction": float(np.mean([v["metrics"]["orders"] == 0 for v in values])),
            "worst_loss": float(pnl.min()),
            "cvar_05_loss": tail_loss,
            "max_drawdown": max(float(v["metrics"]["max_drawdown"]) for v in values),
            "mean_capital_utilization": float(
                np.mean([float(v["metrics"]["max_utilization"]) for v in values])
            ),
            "attempted_trades": sum(v["attempted_trades"] for v in values),
            "completed_two_leg_positions": sum(v["completed_two_leg_positions"] for v in values),
            "partial_orders": sum(v["metrics"]["partial_orders"] for v in values),
            "unmatched_exposure_incidents": sum(v["unmatched_incident"] for v in values),
            "average_exposure_duration_ms": float(
                np.mean([v["exposure_duration_ms"] for v in values])
            ),
            "risk_interventions": sum(v["risk_interventions"] for v in values),
            "unsupported_decisions": sum(v.get("unsupported_decisions", 0) for v in values),
            "invariant_violations": sum(not v["passed"] for v in values),
            "mean_runtime_ms": float(np.mean([v["runtime_ms"] for v in values])),
            "mean_inference_latency_ms": float(
                np.mean([v["inference_latency_ms"] for v in values])
            ),
            "mean_pnl_episode_bootstrap_95": ci,
            "score": float(pnl.mean()) - spec.tail_loss_weight * tail_loss,
            "by_execution": {
                name: float(
                    np.mean(
                        [
                            float(v["metrics"]["net_simulated_pnl"])
                            for v in values
                            if v["execution_model"] == name
                        ]
                    )
                )
                for name in spec.execution_models
            },
        }
        leaderboard.append(record)
    leaderboard.sort(key=lambda r: (r["invariant_violations"] > 0, -r["score"], r["policy"]))
    # Compare learned policies directly with deterministic controls on matched
    # episode groups, averaging correlated execution variants inside each group.
    for policy in sorted(policy_base):
        if policy == "no_trade":
            continue
        controls = (
            "no_trade",
            "arbitrage",
            "conservative",
            *(gate.identity(kind) for gate in spec.cost_gates for kind in ("quoted", "scope")),
        )
        for baseline in controls:
            if baseline not in policy_base or baseline == policy:
                continue
            shared = sorted(policy_base[policy].keys() & policy_base[baseline].keys())
            differences = np.array(
                [policy_base[policy][g] - policy_base[baseline][g] for g in shared]
            )
            rng = np.random.default_rng(spec.seed)
            bootstrap = [
                float(rng.choice(differences, len(differences), replace=True).mean())
                for _ in range(500)
            ]
            ci = np.quantile(bootstrap, [0.025, 0.975]).tolist()
            paired.append(
                {
                    "policy": policy,
                    "control": baseline,
                    "base_episodes": len(shared),
                    "mean_difference": float(differences.mean()),
                    "bootstrap_95": ci,
                    "conclusion": "POSITIVE_SYNTHETIC_MEAN"
                    if ci[0] > 0
                    else "NO_CLEAR_MEAN_ADVANTAGE",
                }
            )
    eligible = [
        r
        for r in leaderboard
        if r["policy"] != "no_trade"
        and r["base_episodes"] >= spec.minimum_champion_episodes
        and r["invariant_violations"] == 0
        and next(
            p["bootstrap_95"][0]
            for p in paired
            if p["policy"] == r["policy"] and p["control"] == "no_trade"
        )
        > 0
        and r["score"] > next(c["score"] for c in leaderboard if c["policy"] == "no_trade")
    ]
    leaders = (
        [
            r["policy"]
            for r in eligible
            if math.isclose(r["score"], eligible[0]["score"], rel_tol=1e-9, abs_tol=1e-9)
        ]
        if eligible
        else []
    )
    for position, record in enumerate(leaderboard):
        record["rank"] = next(
            i + 1
            for i, other in enumerate(leaderboard[: position + 1])
            if other["invariant_violations"] == record["invariant_violations"]
            and math.isclose(other["score"], record["score"], rel_tol=1e-9, abs_tol=1e-9)
        )
    return {
        "leaderboard": leaderboard,
        "paired": paired,
        "research_champion": leaders[0] if len(leaders) == 1 else None,
        "research_leaders": leaders,
        "ranking_version": "episode-objective-ties-2",
        "conclusion": "Candidate advantage within this synthetic environment only."
        if len(leaders) == 1
        else "Candidates tie for the strongest synthetic downside score; no unique champion."
        if leaders
        else "Insufficient independent synthetic episodes for champion designation."
        if len(control) < spec.minimum_champion_episodes
        else "No candidate demonstrates an advantage over no-trade under the configured downside-aware objective.",
        "ranking_objective": f"mean virtual P&L minus {spec.tail_loss_weight} times 5% tail loss; any invariant failure disqualifies",
        "uncertainty_note": "Bootstrap resamples base episodes with all execution variants grouped. Generated uncertainty does not establish real market generalization.",
    }


def run_tournament(root: Path, spec: TournamentSpec, progress: Any = None) -> dict[str, Any]:
    import torch
    from stable_baselines3 import PPO

    torch.set_num_threads(1)
    manifest, _ = load(root, spec.dataset_id)
    evaluation_lineage = observation_lineage(root, spec.dataset_id)
    dataset_spec = DatasetSpec.model_validate(manifest["spec"])
    training_spec = dataset_spec
    if spec.challenge:
        dataset_spec = spec.challenge
        held_out = list(range(min(spec.max_episodes, dataset_spec.episodes)))
        old_ids = {
            f"{training_spec.families[i % len(training_spec.families)]}:{training_spec.seed + i}"
            for i in range(training_spec.episodes)
        }
        new_ids = {
            f"{dataset_spec.families[i % len(dataset_spec.families)]}:{dataset_spec.seed + i}"
            for i in held_out
        }
        old_seeds = set(range(training_spec.seed, training_spec.seed + training_spec.episodes))
        new_seeds = {dataset_spec.seed + i for i in held_out}
        if old_ids & new_ids or old_seeds & new_seeds:
            raise ValueError("Fresh challenge overlaps the original dataset episode identities")
        if spec.partition != "test":
            raise ValueError(
                "Fresh challenges are independent evaluation, not validation selection"
            )
    else:
        held_out = indices(dataset_spec, spec.partition)[: spec.max_episodes]
    if not held_out:
        raise ValueError("No independent evaluation scenarios")
    policies: dict[str, Any] = {
        "no_trade": None,
        "arbitrage": None,
        "conservative": None,
        "random": None,
    }
    artifacts = {}
    bindings = {gate.identity: gate for gate in spec.gates}
    loaded: dict[str, Any] = {}
    model_datasets = {}
    referenced_models = tuple(
        dict.fromkeys((*spec.model_ids, *(gate.model_id for gate in spec.gates)))
    )
    for identity in referenced_models:
        directory = artifact_path(root, "models", identity)
        record = json.loads((directory / "manifest.json").read_text())
        model_manifest, _ = load(root, record["dataset_id"])
        if model_manifest["rows_sha256"] != record["dataset_sha256"]:
            raise ValueError("Model training dataset hash differs from frozen artifact")
        dataset_binding = observation_lineage(root, record["dataset_id"])
        if (
            dataset_binding["source_dataset_id"] != evaluation_lineage["source_dataset_id"]
            or dataset_binding["observation_hash"] != evaluation_lineage["observation_hash"]
            or (record["family"] == "ppo" and record["dataset_id"] != spec.dataset_id)
        ):
            raise ValueError("Model must use the frozen tournament observations and partitions")
        model_datasets[identity] = {
            **dataset_binding,
            "rows_sha256": model_manifest["rows_sha256"],
            "label_target": model_manifest.get("label_target", "completion"),
        }
        artifacts[identity] = record["artifact_sha256"]
        if record["family"] == "ppo":
            if sha256(directory / "policy.zip") != record["artifact_sha256"]:
                raise ValueError("PPO checksum mismatch")
            loaded[identity] = PPO.load(directory / "policy.zip", device="cpu")
        else:
            loaded[identity] = Predictor.load(root, identity)
        if identity in spec.model_ids:
            policies[identity] = loaded[identity]
    for policy, configured in bindings.items():
        model = loaded[configured.model_id]
        if not isinstance(model, Predictor):
            raise ValueError("Probability gates require a supervised predictor")
        policies[policy] = model
    cost_bindings: dict[str, dict[str, Any]] = {}
    for gate in spec.cost_gates:
        model = CostPolicy(root, gate)
        if model.manifest["dataset_id"] != spec.dataset_id:
            raise ValueError("Cost model must use the frozen tournament dataset")
        artifacts[gate.model_id] = model.manifest["artifact_sha256"]
        model_datasets[gate.model_id] = {
            **evaluation_lineage,
            "rows_sha256": manifest["rows_sha256"],
            "label_target": "initial_position_friction_usd",
        }
        if model.completion_manifest is not None:
            completion = model.completion_manifest
            completion_id = completion["model_id"]
            if completion["dataset_id"] != spec.dataset_id and spec.challenge is None:
                raise ValueError("Cross-cohort joint completion requires a fresh challenge")
            artifacts[completion_id] = completion["artifact_sha256"]
            model_datasets[completion_id] = {
                **observation_lineage(root, completion["dataset_id"]),
                "rows_sha256": completion["dataset_sha256"],
                "label_target": "completion",
                "evaluation_note": "Separately trained frozen cohort evaluated on a fresh common challenge",
            }
        for kind in ("forecast", "quoted", "scope"):
            policy = gate.identity(kind)
            policies[policy] = model
            cost_bindings[policy] = {"specification": gate.model_dump(mode="json"), "kind": kind}
    referenced_models = tuple(
        dict.fromkeys(
            (
                *referenced_models,
                *(g.model_id for g in spec.cost_gates),
                *(
                    g.completion_model_id
                    for g in spec.cost_gates
                    if g.completion_model_id is not None
                ),
            )
        )
    )
    identity = "tournament-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "tournaments", identity)
    rows = []
    began = time.monotonic()
    execution_revision = revision()
    total = len(held_out) * len(spec.execution_models) * len(policies)
    source_hash = research_hash()
    register = getattr(progress, "register", None)
    if register:
        register("tournaments", identity)
    atomic_json(
        directory / "preparing.json",
        {
            "configuration": spec.model_dump(mode="json"),
            "source_hash": source_hash,
            "dataset_sha256": manifest["rows_sha256"],
        },
    )
    for index in held_out:
        seed = dataset_spec.seed + index
        family = dataset_spec.families[index % len(dataset_spec.families)]
        for execution_name in spec.execution_models:
            scenario = generate(
                family,
                seed,
                ExecutionModel.preset(execution_name).model_copy(update={"seed": seed}),
            ).model_copy(update={"observation_latency_ms": dataset_spec.observation_latency_ms})
            if dataset_spec.costs is not None:
                scenario = scenario.model_copy(update={"costs": dataset_spec.costs})
            if spec.adversarial:
                from midas.laboratory.adversarial import mutate_sequence

                scenario = mutate_sequence(scenario, seed)
                if any(e.kind == "mutate" for e in scenario.events):
                    raise ValueError(
                        "Controlled accounting defects are not financial stress evaluations"
                    )
            origin_hash = digest(scenario.model_dump(mode="json"))
            if spec.generator_revision:
                scenario = spec.generator_revision.apply(scenario)
            if spec.economic_regime:
                scenario = spec.economic_regime.apply(scenario)
            for policy, model in policies.items():
                env = ArenaEnv(scenario=scenario, retain=True)
                obs, _ = env.reset(seed=spec.seed)
                rng = np.random.default_rng(seed + spec.seed)
                latency = []
                started = time.monotonic()
                attempted = 0
                unsupported = 0
                assert env.env is not None
                while True:
                    features, eligible = env.decision_features()
                    explanation: dict[str, Any] = {
                        "policy": policy,
                        "mathematically_eligible": eligible,
                    }
                    decision_started = time.perf_counter()
                    if policy == "no_trade":
                        action = 0
                    elif policy == "arbitrage":
                        action = int(eligible)
                    elif policy == "conservative":
                        action = (
                            2 if eligible and features[12] >= 0.03 and features[6] <= 1000 else 0
                        )
                    elif policy == "random":
                        action = int(rng.integers(0, 3)) if eligible else 0
                    elif isinstance(model, CostPolicy):
                        action, details = model.decide(
                            features,
                            eligible,
                            env.env.observe(),
                            scenario,
                            bool(env.env.state["positions"]),
                            cost_bindings[policy]["kind"],
                        )
                        explanation.update(details)
                        unsupported += int(
                            eligible and not details["input_support"]["supported"][0]
                        )
                    elif isinstance(model, Predictor):
                        binding = bindings.get(policy)
                        threshold = binding.threshold if binding else spec.threshold
                        support = model.support([features]) if eligible else None
                        out_of_support = support is not None and not support["supported"][0]
                        unsupported += int(out_of_support)
                        probability = (
                            float(model.predict([features])[0])
                            if eligible
                            and not (out_of_support and spec.unsupported_input_policy == "abstain")
                            else None
                        )
                        target = model.parameters.get("label_target", "completion")
                        action = int(
                            probability is not None and model.permits(probability, threshold)
                        )
                        if action and binding and binding.size == "half":
                            action = 2
                        if out_of_support and spec.unsupported_input_policy == "abstain":
                            action = 0
                        explanation.update(
                            completion_score=probability if target == "completion" else None,
                            unmatched_risk_score=probability if target == "unmatched" else None,
                            persistence_score=probability if target == "persistence" else None,
                            label_target=target,
                            threshold=threshold,
                            requested_size=binding.size if binding else "full",
                            score_size_assumption="Score refers to the full mathematical proposal; reduced-size execution is not separately calibrated",
                            interpretation="Assumption control score; not calibrated probability"
                            if model.parameters["family"] == "heuristic"
                            else f"Modeled {target} probability under hypothetical execution",
                            reason="Request a proposal; independent risk admission remains required"
                            if action
                            else "Abstain: ineligible evidence or target-specific probability gate rejected",
                            input_support=support,
                            unsupported_input_policy=spec.unsupported_input_policy,
                        )
                        if out_of_support:
                            explanation["reason"] = (
                                "Input lies outside training feature ranges; "
                                + (
                                    "abstain"
                                    if spec.unsupported_input_policy == "abstain"
                                    else "unvalidated extrapolation warning"
                                )
                            )
                    else:
                        action = int(model.predict(obs, deterministic=True)[0])
                    latency.append((time.perf_counter() - decision_started) * 1000)
                    if "reason" not in explanation:
                        explanation["reason"] = {
                            "no_trade": "Configured no-trade control",
                            "arbitrage": "Submit a full mathematical proposal only when eligible",
                            "conservative": "Half-size proposal requires edge >= 0.03 and age <= 1000 ms",
                            "random": "Seeded diagnostic control; no learned intelligence",
                        }.get(policy, "Saved PPO policy selected this action deterministically")
                    env.action_explanation = explanation
                    attempted += int(action != 0)
                    obs, _, done, _, info = env.step(action)
                    if done:
                        break
                result = info["result"]
                final = result["final_portfolio"]
                positions = final["positions"]
                complete = sum(
                    len(p["orders"]) == 2 and all(o["status"] == "FILLED" for o in p["orders"])
                    for p in positions
                )
                exposure_ms = 0
                for left, right in zip(result["journal"], result["journal"][1:], strict=False):
                    if float(left["after"].get("net_exposure_shares", 0)) != 0:
                        exposure_ms += right["time_ms"] - left["time_ms"]
                row_id = f"{index}-{execution_name}-{policy}"
                row = {
                    "id": row_id,
                    "index": index,
                    "base_episode_id": f"{family}:{seed}",
                    "family": family,
                    "seed": seed,
                    "execution_model": execution_name,
                    "policy": policy,
                    "passed": result["passed"],
                    "metrics": result["metrics"],
                    "completed_two_leg_positions": complete,
                    "attempted_trades": attempted,
                    "unsupported_decisions": unsupported,
                    "unmatched_incident": env.max_unmatched > 0,
                    "exposure_duration_ms": exposure_ms,
                    "risk_interventions": sum(
                        not d["risk"]["allowed"]
                        and d["evaluation"]["status"] == "VERIFIED_MATHEMATICAL"
                        for d in final["decisions"]
                    ),
                    "runtime_ms": (time.monotonic() - started) * 1000,
                    "inference_latency_ms": float(np.mean(latency)),
                    "policy_version": digest(
                        [cost_bindings[policy], artifacts[model.specification.model_id]]
                        + (
                            [artifacts[model.specification.completion_model_id]]
                            if model.specification.completion_model_id is not None
                            else []
                        )
                    )
                    if policy in cost_bindings
                    else digest(
                        [
                            bindings[policy].model_dump(mode="json"),
                            artifacts[bindings[policy].model_id],
                        ]
                    )
                    if policy in bindings
                    else artifacts.get(
                        policy,
                        {
                            "arbitrage": "binary-depth-2",
                            "conservative": "arena-conservative-size-1",
                            "no_trade": "no-trade-1",
                            "random": "arena-random-1",
                        }.get(policy),
                    ),
                    "simulator_version": result["simulator_version"],
                    "initial_capital": str(scenario.account.capital),
                    "result_hash": result["result_hash"],
                    "scenario_hash": result["scenario_hash"],
                    "scenario_origin_hash": origin_hash,
                    "risk_limits": scenario.account.limits.model_dump(mode="json"),
                    "economic_assumptions": scenario.costs.model_dump(mode="json"),
                }
                rows.append(row)
                # Every replay is saved, independently of future model/source availability.
                atomic_replay(
                    directory / "replays" / f"{row_id}.json",
                    {"result": result, "decisions": info["decision_trace"], "row": row},
                )
                if progress:
                    progress(len(rows), total)
    atomic_json(directory / "rows.json", rows)
    report = {
        "tournament_id": identity,
        "created_at": time.time(),
        "configuration": spec.model_dump(mode="json"),
        "dataset_sha256": manifest["rows_sha256"],
        "source_hash": source_hash,
        "code_revision": execution_revision,
        "model_artifact_hashes": artifacts,
        "model_dataset_bindings": model_datasets,
        "evaluation_observation_lineage": evaluation_lineage,
        "economic_regime_units": {
            "depth_multiplier": "ratio of synthetic shares at every bid/ask level",
            "taker_fee_rate": "hypothetical fee rate under the existing synthetic fee formula",
            "additional_submission_latency_ms": "milliseconds added to execution latency",
        },
        "policy_bindings": {
            policy: binding.model_dump(mode="json") for policy, binding in bindings.items()
        },
        "cost_policy_bindings": cost_bindings,
        "base_episodes": len(held_out),
        "variants": len(rows),
        "rows_sha256": sha256(directory / "rows.json"),
        "duration_seconds": time.monotonic() - began,
        "provenance": "GENERATED",
        "economically_verified": False,
        "execution_certainty": "HYPOTHETICAL_UNCALIBRATED",
        "evaluation_design": "FRESH_GENERATOR_CHALLENGE"
        if spec.challenge
        else spec.partition.upper(),
        "evaluation_generator": dataset_spec.model_dump(mode="json"),
        "generator_revision": spec.generator_revision.model_dump(mode="json")
        if spec.generator_revision
        else None,
        "generator_revision_note": "Challenge-only synthetic settlement change; fixed policies and no empirical outcome calibration."
        if spec.generator_revision
        else "Legacy generated settlement rules.",
        "common_random_numbers_note": "Shared seeds pair source scenarios. Action-dependent order paths and random draws do not guarantee identical execution noise.",
        **summaries(rows, spec),
    }
    if spec.partition == "validation" and spec.challenge is None:
        report.update(
            research_champion=None,
            research_leaders=[],
            conclusion="Validation comparison for policy selection; independent evaluation is still required.",
        )
    if spec.purpose == "performance_replay":
        report.update(
            evaluation_design="PERFORMANCE_REPLAY",
            research_champion=None,
            research_leaders=[],
            conclusion="Saved-specification replay for performance measurement; no new independent research evidence.",
        )
    atomic_json(directory / "manifest.json", report)
    publish_findings(root, report)
    for model_id in referenced_models:
        model_directory = artifact_path(root, "models", model_id)
        model_record = json.loads((model_directory / "manifest.json").read_text())
        evaluations = model_record.setdefault("policy_evaluations", [])
        evaluations.append(
            {
                "tournament_id": identity,
                "base_episodes": len(held_out),
                "dataset_sha256": manifest["rows_sha256"],
                "adversarial": spec.adversarial,
                "artifact_sha256": model_record["artifact_sha256"],
                "metrics": next(
                    (v for v in report["leaderboard"] if v["policy"] == model_id), None
                ),
                "gate_metrics": [
                    v
                    for v in report["leaderboard"]
                    if v["policy"] == model_id
                    or (v["policy"] in bindings and bindings[v["policy"]].model_id == model_id)
                    or (
                        v["policy"] in cost_bindings
                        and model_id
                        in {
                            cost_bindings[v["policy"]]["specification"]["model_id"],
                            cost_bindings[v["policy"]]["specification"].get("completion_model_id"),
                        }
                    )
                ],
            }
        )
        model_record["state"] = "EVALUATED"
        atomic_json(model_directory / "manifest.json", model_record)
    return report


def publish_findings(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    from midas.economics.attestation import digest

    identity = "finding-" + digest([report["tournament_id"], "downside-objective-1"])[:24]
    finding = {
        "finding_id": identity,
        "title": "Performance replay completed"
        if report.get("evaluation_design") == "PERFORMANCE_REPLAY"
        else "Validation policy comparison completed"
        if report.get("evaluation_design") == "VALIDATION"
        else "No trading candidate clears the downside objective"
        if not (report.get("research_leaders") or report["research_champion"])
        else "A candidate clears the synthetic downside objective",
        "research_question": "Do trained policies improve matched simulated outcomes relative to deterministic controls and abstention?",
        "hypothesis": "A learned execution filter or PPO policy improves outcomes without worsening tail losses.",
        "experiment_configuration": report["configuration"],
        "tournament_id": report["tournament_id"],
        "input_artifacts": {
            "rows_sha256": report["rows_sha256"],
            "dataset_sha256": report["dataset_sha256"],
        },
        "source_hash": report["source_hash"],
        "code_revision": report.get("code_revision"),
        "seed": report["configuration"]["seed"],
        "created_at": time.time(),
        "interpretation": report["conclusion"],
        "outcome": report["leaderboard"],
        "uncertainty": report["paired"],
        "caveats": [
            "Synthetic generated markets and uncalibrated fills only.",
            "Positive mean P&L does not guarantee a positive downside score.",
            "Execution variants share underlying episodes; they are not independent samples.",
            "Tail estimates from this bounded sample do not establish guaranteed loss bounds.",
            "Generator settlement seed parity and family order may create unrealistic shortcuts.",
        ],
        "next_experiment": "Evaluate independently reordered scenario families and shifted settlement rules; test sizing and execution-risk gates on validation before freezing another test.",
    }
    atomic_json(artifact_path(root, "findings", identity) / "manifest.json", finding)
    return finding
