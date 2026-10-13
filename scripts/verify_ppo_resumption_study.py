"""Audit actual PPO continuation, fresh replay accounting and paired outcomes."""

import json
from pathlib import Path

import torch
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.datasets import DatasetSpec
from midas.economics.attestation import digest
from stable_baselines3 import PPO

from scripts.compare_policies import compare
from scripts.verify_generator_pair import ledger_audit


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root: Path, plan: dict, parent_id: str, child_id: str, tournament_id: str) -> dict:
    models = []
    for identity in (parent_id, child_id):
        directory = artifact_path(root, "models", identity)
        record = json.loads((directory / "manifest.json").read_text())
        require(
            record["family"] == "ppo" and record["source_hash"] == plan["source_hash"],
            "Training model source/family differs",
        )
        require(
            sha256(directory / "policy.zip") == record["artifact_sha256"], "PPO weights changed"
        )
        checkpoint = json.loads((directory / "checkpoint-manifest.json").read_text())
        require(
            Path(checkpoint["filename"]).name == checkpoint["filename"]
            and sha256(directory / checkpoint["filename"]) == checkpoint["artifact_sha256"],
            "Checkpoint payload differs",
        )
        require(
            checkpoint["boundary"] == "completed-optimizer-update",
            "Incomplete optimizer checkpoint",
        )
        model = PPO.load(directory / "policy.zip", device="cpu")
        require(
            model.num_timesteps == record["timesteps"]
            and model._n_updates == record["optimizer_updates"],
            "Actual trained counters differ",
        )
        models.append((record, checkpoint, model))
    parent, parent_checkpoint, parent_model = models[0]
    child, child_checkpoint, child_model = models[1]
    require(parent["configuration"] == plan["parent_training"], "Parent training differs from plan")
    expected = {
        **plan["parent_training"],
        "resume_from": parent_id,
        "timesteps": plan["child_total_timesteps"],
    }
    require(child["configuration"] == expected, "Child training differs from plan")
    require(
        parent["timesteps"] == plan["parent_training"]["timesteps"]
        and child["timesteps"] == plan["child_total_timesteps"],
        "Incomplete training budgets",
    )
    lineage = child["lineage"]
    require(
        lineage["parent_model_id"] == parent_id
        and lineage["checkpoint_sha256"] == parent_checkpoint["artifact_sha256"],
        "Resumption lineage differs",
    )
    require(
        lineage["parent_optimizer_updates"] == parent["optimizer_updates"]
        and lineage["global_rng_restored"]
        and not lineage["legacy_rollout_discarded"],
        "Unsupported continuation provenance",
    )
    require(
        child["new_timesteps"] == child["timesteps"] - parent["timesteps"]
        and child["new_optimizer_updates"]
        == child["optimizer_updates"] - parent["optimizer_updates"]
        > 0,
        "No actual new training",
    )
    require(
        child["curves"][: len(parent["curves"])] == parent["curves"], "Parent curves were rewritten"
    )
    initial = json.loads((root / "models" / child_id / "lineage.json").read_text())
    require(
        initial["initial_timesteps"] == parent["timesteps"]
        and initial["initial_optimizer_updates"] == parent["optimizer_updates"],
        "Initial child counters differ",
    )
    optimizers = [model.policy.optimizer.state_dict() for _, _, model in models]
    require(
        optimizers[0]["state"].keys() == optimizers[1]["state"].keys(),
        "Optimizer parameter identity differs",
    )
    expected_increment = child["new_optimizer_updates"] * (
        parent_model.n_steps // parent_model.batch_size
    )
    steps = []
    for key, values in optimizers[0]["state"].items():
        before = int(values["step"].item())
        after = int(optimizers[1]["state"][key]["step"].item())
        require(after - before == expected_increment, "Adam step continuation differs")
        steps.append({"parameter": key, "parent_steps": before, "child_steps": after})
    changed_parameters = sum(
        not torch.equal(value, child_model.policy.state_dict()[key])
        for key, value in parent_model.policy.state_dict().items()
    )
    require(changed_parameters > 0, "Continuation did not change trained parameters")
    directory = artifact_path(root, "tournaments", tournament_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    require(
        manifest["configuration"]["model_ids"] == [parent_id, child_id, plan["old_ppo_control"]]
        and manifest["configuration"]["challenge"]
        == DatasetSpec.model_validate(plan["challenge"]).model_dump(mode="json"),
        "Frozen tournament inputs differ",
    )
    for model_id, expected_hash in [
        (parent_id, parent["artifact_sha256"]),
        (child_id, child["artifact_sha256"]),
        (plan["old_ppo_control"], plan["old_ppo_sha256"]),
    ]:
        require(
            manifest["model_artifact_hashes"][model_id] == expected_hash
            and sha256(root / "models" / model_id / "policy.zip") == expected_hash,
            "Frozen policy binding differs",
        )
    require(
        manifest["source_hash"] == plan["source_hash"] and manifest["research_champion"] is None,
        "Tournament source/promotion differs",
    )
    require(sha256(directory / "rows.json") == manifest["rows_sha256"], "Frozen rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    challenge = DatasetSpec.model_validate(plan["challenge"])
    groups = plan["evaluation_source_groups"]
    require(
        0 < groups <= challenge.episodes and manifest["configuration"]["max_episodes"] == groups,
        "Declared source-group count differs",
    )
    policies = {
        parent_id,
        child_id,
        plan["old_ppo_control"],
        "no_trade",
        "arbitrage",
        "conservative",
        "random",
    }
    expected_grid = {
        (
            f"{challenge.families[i % len(challenge.families)]}:{challenge.seed + i}",
            execution,
            policy,
        )
        for i in range(groups)
        for execution in ("optimistic", "standard", "conservative")
        for policy in policies
    }
    actual_grid = {(r["base_episode_id"], r["execution_model"], r["policy"]) for r in rows}
    require(
        len(rows) == plan["correlated_variants_expected"] == len(expected_grid)
        and actual_grid == expected_grid,
        "Fresh study grid differs",
    )
    journal_states = 0
    for row in rows:
        replay = read_replay(directory / "replays" / (row["id"] + ".json"))
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        require(
            replay["row"] == row
            and digest(core) == row["result_hash"] == result["result_hash"]
            and digest(result["journal"]) == result["journal_hash"],
            "Replay financial/journal hash differs",
        )
        require(result["passed"] and result["complete"], "Invalid or incomplete simulation")
        journal_states += ledger_audit(result)
    paired = [
        compare(root, tournament_id, control, child_id)
        for control in (parent_id, plan["old_ppo_control"], "no_trade", "arbitrage")
    ]
    return {
        "parent_model_id": parent_id,
        "child_model_id": child_id,
        "tournament_id": tournament_id,
        "parent_timesteps": parent["timesteps"],
        "child_timesteps": child["timesteps"],
        "new_optimizer_updates": child["new_optimizer_updates"],
        "adam_steps": steps,
        "changed_parameter_tensors": changed_parameters,
        "verified_replays": len(rows),
        "independent_source_groups": groups,
        "journal_states_audited": journal_states,
        "paired_comparisons": paired,
        "leaderboard": manifest["leaderboard"],
        "producer_sha256": sha256(Path(__file__)),
        "limitations": [
            "One seed/architecture and bounded synthetic training; not multi-seed RL maturity.",
            "Environment/rollout reset; no uninterrupted trajectory equivalence.",
            "Optimizer restoration is exercised by separate tensor-level implementation tests; final archives establish continuing counters/updates.",
            "Synthetic hypothetical execution; no empirically calibrated fills or real-market profitability.",
        ],
    }
