"""Reload frozen weights and reproduce every saved policy action and accounting transition."""

import argparse
import json
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.cost_policy import CostGateSpec, CostPolicy
from midas.arena.datasets import research_hash
from midas.arena.environment import ArenaEnv
from midas.arena.reproduce import reproduce as replay_accounting
from midas.arena.supervised import Predictor
from midas.laboratory.spec import Scenario


def request(policy, model, env, observation, config, rng):
    features, eligible = env.decision_features()
    if policy == "no_trade":
        return 0, {}
    if policy == "arbitrage":
        return int(eligible), {}
    if policy == "conservative":
        return (2 if eligible and features[12] >= 0.03 and features[6] <= 1000 else 0), {}
    if policy == "random":
        return (int(rng.integers(0, 3)) if eligible else 0), {}
    if isinstance(model, CostPolicy):
        binding = config["cost_policy_bindings"][policy]
        assert env.env is not None
        return model.decide(
            features,
            eligible,
            env.env.observe(),
            env.fixed_scenario,
            bool(env.env.state["positions"]),
            binding["kind"],
        )
    if isinstance(model, Predictor):
        binding = config.get("policy_bindings", {}).get(policy)
        threshold = binding["threshold"] if binding else config["configuration"]["threshold"]
        support = model.support([features]) if eligible else None
        unsupported = support is not None and not support["supported"][0]
        score = (
            float(model.predict([features])[0])
            if eligible
            and not (
                unsupported and config["configuration"]["unsupported_input_policy"] == "abstain"
            )
            else None
        )
        action = int(score is not None and model.permits(score, threshold))
        if action and binding and binding["size"] == "half":
            action = 2
        target = model.parameters.get("label_target", "completion")
        return action, {
            "completion_score": score if target == "completion" else None,
            "unmatched_risk_score": score if target == "unmatched" else None,
            "persistence_score": score if target == "persistence" else None,
            "input_support": support,
            "threshold": threshold,
        }
    return int(model.predict(observation, deterministic=True)[0]), {}


def reproduce(root: Path, identity: str, row_id: str) -> dict:
    import torch
    from stable_baselines3 import PPO

    torch.set_num_threads(1)
    directory = artifact_path(root, "tournaments", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["source_hash"] != research_hash():
        raise ValueError("Inference reproduction requires the exact research source")
    proof = replay_accounting(root, identity, row_id)
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    matches = [r for r in rows if r["id"] == row_id]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate selected row")
    row = matches[0]
    saved = read_replay(directory / "replays" / (row_id + ".json"))
    if saved["row"] != row:
        raise ValueError("Saved row differs")
    for model_id, expected in manifest["model_artifact_hashes"].items():
        model_dir = artifact_path(root, "models", model_id)
        record = json.loads((model_dir / "manifest.json").read_text())
        weights = model_dir / ("policy.zip" if record["family"] == "ppo" else "parameters.json")
        if sha256(weights) != expected or record["artifact_sha256"] != expected:
            raise ValueError("Frozen model weights changed")
    policy, model = row["policy"], None
    if policy in manifest.get("cost_policy_bindings", {}):
        model = CostPolicy(
            root,
            CostGateSpec.model_validate(manifest["cost_policy_bindings"][policy]["specification"]),
        )
    elif policy not in {"no_trade", "arbitrage", "conservative", "random"}:
        binding = manifest.get("policy_bindings", {}).get(policy)
        model_id = binding["model_id"] if binding else policy
        model_dir = artifact_path(root, "models", model_id)
        record = json.loads((model_dir / "manifest.json").read_text())
        model = (
            PPO.load(model_dir / "policy.zip", device="cpu")
            if record["family"] == "ppo"
            else Predictor.load(root, model_id)
        )
    env = ArenaEnv(scenario=Scenario.model_validate(saved["result"]["scenario"]), retain=True)
    observation, _ = env.reset(seed=manifest["configuration"]["seed"])
    rng = np.random.default_rng(row["seed"] + manifest["configuration"]["seed"])
    done, final = False, None
    for decision in saved["decisions"]:
        if done or observation.tolist() != decision["observation"]:
            raise ValueError("Policy observation or termination differs")
        action, details = request(policy, model, env, observation, manifest, rng)
        if str(action) != decision["requested_action"] or any(
            decision["explanation"].get(k) != v for k, v in details.items()
        ):
            raise ValueError("Frozen inference differs from saved request or score")
        env.action_explanation = decision["explanation"]
        observation, _, done, _, info = env.step(action)
        if env.env is None or env.env.decisions[-1:] != [decision]:
            raise ValueError("Reexecuted decision trace differs")
        final = info.get("result")
    if (
        not done
        or final is None
        or final["result_hash"] != proof["result_hash"]
        or final["journal_hash"] != proof["journal_hash"]
    ):
        raise ValueError("Policy inference did not reproduce final accounting")
    return {
        **proof,
        "mode": "FROZEN_INFERENCE_AND_ACCOUNTING_REEXECUTION",
        "source_hash": manifest["source_hash"],
        "policy": policy,
        "decisions_recomputed": len(saved["decisions"]),
        "producer_sha256": sha256(Path(__file__)),
        "limitation": "Reuses frozen inference and broker implementations; independent arithmetic audits are separate. No retraining or empirical economics.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("row_id")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reproduce(args.root, args.identity, args.row_id)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
