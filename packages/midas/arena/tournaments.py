"""Matched held-out policy comparisons and episode-grouped uncertainty."""

import json
import math
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import Field, model_validator

from midas.arena.artifacts import artifact_path, atomic_json, atomic_replay, sha256
from midas.arena.datasets import DatasetSpec, load, research_hash
from midas.arena.environment import ArenaEnv
from midas.arena.features import extract
from midas.arena.rl import indices
from midas.arena.supervised import Predictor
from midas.core.models import Model
from midas.laboratory.campaigns import revision
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel


class TournamentSpec(Model):
    dataset_id: str
    model_ids: tuple[str, ...] = ()
    execution_models: tuple[str, ...] = ("optimistic", "standard", "conservative")
    max_episodes: int = Field(default=200, ge=2, le=2000)
    threshold: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    tail_loss_weight: float = Field(default=1, ge=0, le=10, allow_inf_nan=False)
    seed: int = Field(default=991, ge=0)
    adversarial: bool = False
    minimum_champion_episodes: int = Field(default=30, ge=30, le=2000)

    @model_validator(mode="after")
    def valid(self) -> "TournamentSpec":
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
        return self


def summaries(rows: list[dict[str, Any]], spec: TournamentSpec) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["policy"]].append(row)
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
        if policy != "no_trade":
            paired.append(
                {
                    "policy": policy,
                    "control": "no_trade",
                    "base_episodes": len(control.keys() & base.keys()),
                    "mean_difference": float(aggregate.mean()),
                    "bootstrap_95": ci,
                    "conclusion": "POSITIVE_SYNTHETIC_MEAN"
                    if ci[0] > 0
                    else "NO_CLEAR_ADVANTAGE_OVER_ABSTENTION",
                }
            )
    leaderboard.sort(key=lambda r: (r["invariant_violations"] > 0, -r["score"], r["policy"]))
    # Compare learned policies directly with deterministic controls on matched
    # episode groups, averaging correlated execution variants inside each group.
    for policy in sorted(policy_base):
        if policy in {"no_trade", "arbitrage", "conservative"}:
            continue
        for baseline in ("arbitrage", "conservative"):
            if baseline not in policy_base:
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
        and r["mean_pnl_episode_bootstrap_95"][0] > 0
        and r["score"] > 0
    ]
    return {
        "leaderboard": leaderboard,
        "paired": paired,
        "research_champion": eligible[0]["policy"] if eligible else None,
        "conclusion": "Candidate advantage within this synthetic environment only."
        if eligible
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
    dataset_spec = DatasetSpec.model_validate(manifest["spec"])
    held_out = indices(dataset_spec, "test")[: spec.max_episodes]
    if not held_out:
        raise ValueError("No independent evaluation scenarios")
    policies: dict[str, Any] = {
        "no_trade": None,
        "arbitrage": None,
        "conservative": None,
        "random": None,
    }
    artifacts = {}
    for identity in spec.model_ids:
        directory = artifact_path(root, "models", identity)
        record = json.loads((directory / "manifest.json").read_text())
        if record["dataset_id"] != spec.dataset_id:
            raise ValueError("Model must use the frozen tournament dataset")
        artifacts[identity] = record["artifact_sha256"]
        if record["family"] == "ppo":
            if sha256(directory / "policy.zip") != record["artifact_sha256"]:
                raise ValueError("PPO checksum mismatch")
            policies[identity] = PPO.load(directory / "policy.zip", device="cpu")
        else:
            policies[identity] = Predictor.load(root, identity)
    identity = "tournament-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "tournaments", identity)
    rows = []
    began = time.monotonic()
    total = len(held_out) * len(spec.execution_models) * len(policies)
    source_hash = research_hash()
    for index in held_out:
        seed = dataset_spec.seed + index
        family = dataset_spec.families[index % len(dataset_spec.families)]
        for execution_name in spec.execution_models:
            scenario = generate(
                family,
                seed,
                ExecutionModel.preset(execution_name).model_copy(update={"seed": seed}),
            ).model_copy(update={"observation_latency_ms": dataset_spec.observation_latency_ms})
            if spec.adversarial:
                from midas.laboratory.adversarial import mutate_sequence

                scenario = mutate_sequence(scenario, seed)
                if any(e.kind == "mutate" for e in scenario.events):
                    raise ValueError(
                        "Controlled accounting defects are not financial stress evaluations"
                    )
            for policy, model in policies.items():
                env = ArenaEnv(scenario=scenario, retain=True)
                obs, _ = env.reset(seed=spec.seed)
                rng = np.random.default_rng(seed + spec.seed)
                latency = []
                started = time.monotonic()
                attempted = 0
                assert env.env is not None
                while True:
                    features, eligible = extract(
                        env.env.observe(), scenario.account, scenario.observation_latency_ms
                    )
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
                    elif isinstance(model, Predictor):
                        action = int(
                            eligible and float(model.predict([features])[0]) >= spec.threshold
                        )
                    else:
                        action = int(model.predict(obs, deterministic=True)[0])
                    latency.append((time.perf_counter() - decision_started) * 1000)
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
                    "unmatched_incident": env.max_unmatched > 0,
                    "exposure_duration_ms": exposure_ms,
                    "risk_interventions": sum(
                        not d["risk"]["allowed"]
                        and d["evaluation"]["status"] == "VERIFIED_MATHEMATICAL"
                        for d in final["decisions"]
                    ),
                    "runtime_ms": (time.monotonic() - started) * 1000,
                    "inference_latency_ms": float(np.mean(latency)),
                    "policy_version": artifacts.get(
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
        "code_revision": revision(),
        "model_artifact_hashes": artifacts,
        "base_episodes": len(held_out),
        "variants": len(rows),
        "rows_sha256": sha256(directory / "rows.json"),
        "duration_seconds": time.monotonic() - began,
        "provenance": "GENERATED",
        "economically_verified": False,
        "execution_certainty": "HYPOTHETICAL_UNCALIBRATED",
        **summaries(rows, spec),
    }
    atomic_json(directory / "manifest.json", report)
    publish_findings(root, report)
    for model_id in spec.model_ids:
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
                "metrics": next(v for v in report["leaderboard"] if v["policy"] == model_id),
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
        "title": "No trading candidate clears the downside objective"
        if not report["research_champion"]
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
