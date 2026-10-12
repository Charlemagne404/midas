"""Verify matched cost-policy replays and recompute saved decision-time preferences."""

import argparse
import json
from pathlib import Path

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.cost_policy import CostGateSpec, CostPolicy
from midas.arena.features import extract
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario


def verify(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "tournaments", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    bindings = manifest["cost_policy_bindings"]
    policies = {
        key: CostPolicy(root, CostGateSpec.model_validate(value["specification"]))
        for key, value in bindings.items()
    }
    coverage = {}
    scenario_hashes = {}
    decisions_checked = 0
    requested = 0
    for row in rows:
        key = (row["base_episode_id"], row["execution_model"])
        seen = coverage.setdefault(row["policy"], set())
        if key in seen:
            raise ValueError("Duplicate policy coverage")
        seen.add(key)
        replay = read_replay(directory / "replays" / (row["id"] + ".json"))
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if (
            replay["row"] != row
            or digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
            or not result["passed"]
            or not result["complete"]
        ):
            raise ValueError("Replay hash/accounting/completion mismatch")
        scenario_digest = digest(result["scenario"])
        if scenario_hashes.setdefault(key, scenario_digest) != scenario_digest:
            raise ValueError("Matched policies received different scenario inputs")
        if row["policy"] not in bindings:
            continue
        binding = bindings[row["policy"]]
        policy = policies[row["policy"]]
        scenario = Scenario.model_validate(result["scenario"])
        entries = [e for e in result["journal"] if e["kind"] == "decision"]
        if len(entries) != len(replay["decisions"]):
            raise ValueError("Decision trace coverage differs")
        if len(result["final_portfolio"]["positions"]) > 1:
            raise ValueError("Cost policy opened multiple positions")
        for entry, decision in zip(entries, replay["decisions"], strict=True):
            observation = dict(entry["observation"])
            observation["portfolio"] = entry["before"]
            observation["time_ms"] = entry["time_ms"]
            try:
                features, eligible = extract(
                    observation, scenario.account, scenario.observation_latency_ms
                )
            except ValueError as error:
                if not str(error).startswith("Future "):
                    raise
                features, eligible = [0.0] * 19, False
            action, details = policy.decide(
                features,
                eligible,
                observation,
                scenario,
                bool(entry["before"]["positions"]),
                binding["kind"],
            )
            if action != decision["action"] or any(
                decision["explanation"].get(k) != value for k, value in details.items()
            ):
                raise ValueError("Saved cost preference differs from observed-input recomputation")
            decisions_checked += 1
            requested += action
    expected_policies = (
        {"no_trade", "arbitrage", "conservative", "random"}
        | set(bindings)
        | set(manifest.get("policy_bindings", {}))
        | set(manifest["configuration"]["model_ids"])
    )
    if set(coverage) != expected_policies or len(coverage["no_trade"]) != manifest[
        "base_episodes"
    ] * len(manifest["configuration"]["execution_models"]):
        raise ValueError("Policy/scenario count differs from declared experiment")
    if len(rows) != manifest["variants"] or any(
        v != coverage["no_trade"] for v in coverage.values()
    ):
        raise ValueError("Incomplete matched coverage")
    if any(
        manifest["model_artifact_hashes"][p.specification.model_id] != p.manifest["artifact_sha256"]
        for p in policies.values()
    ):
        raise ValueError("Frozen model hashes changed")
    if any(
        p.completion_manifest is not None
        and manifest["model_artifact_hashes"][p.completion_manifest["model_id"]]
        != p.completion_manifest["artifact_sha256"]
        for p in policies.values()
    ):
        raise ValueError("Frozen completion model hashes changed")
    return {
        "tournament_id": identity,
        "replays_verified": len(rows),
        "source_groups": manifest["base_episodes"],
        "cost_decisions_recomputed": decisions_checked,
        "cost_requests": requested,
        "scope": "Saved financial hashes, matched coverage, first-position scope and observed-input preferences; reuses recorded inference implementation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload)
