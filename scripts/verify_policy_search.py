"""Audit a frozen search and independently recompute its validation decision."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def choose(rows: list[dict[str, Any]], bindings: dict[str, Any], seed: int, weight: float) -> str:
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    valid: dict[str, bool] = {}
    coverage: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        policy, base = row["policy"], row["base_episode_id"]
        identity = base, row["execution_model"]
        if identity in coverage[policy]:
            raise ValueError("Duplicate search observation")
        coverage[policy].add(identity)
        groups[policy][base].append(float(row["metrics"]["net_simulated_pnl"]))
        if not math.isfinite(groups[policy][base][-1]):
            raise ValueError("Nonfinite search outcome")
        valid[policy] = valid.get(policy, True) and row["passed"]
    if (
        "no_trade" not in groups
        or not valid["no_trade"]
        or any(v != coverage["no_trade"] for v in coverage.values())
    ):
        raise ValueError("Search control is invalid or unmatched")

    def score(policy: str) -> float:
        values = np.asarray([value for values in groups[policy].values() for value in values])
        tail = np.sort(values)[: max(1, math.ceil(0.05 * len(values)))]
        return float(values.mean()) - weight * max(0.0, -float(tail.mean()))

    control = score("no_trade")
    eligible = []
    for policy in bindings:
        if policy not in groups:
            raise ValueError("Bound gate has no outcomes")
        bases = sorted(groups[policy])
        if len(bases) < 30 or not valid[policy] or score(policy) <= control:
            continue
        deltas = np.asarray(
            [np.mean(groups[policy][base]) - np.mean(groups["no_trade"][base]) for base in bases]
        )
        rng = np.random.default_rng(seed)
        bootstrap = [
            float(rng.choice(deltas, len(deltas), replace=True).mean()) for _ in range(500)
        ]
        if float(np.quantile(bootstrap, 0.025)) > 0:
            eligible.append(policy)
    if not eligible:
        return "no_trade"
    best = max(score(policy) for policy in eligible)
    tied = [p for p in eligible if math.isclose(score(p), best, rel_tol=1e-9, abs_tol=1e-9)]
    return min(tied, key=lambda p: (bindings[p]["size"] != "half", bindings[p]["threshold"], p))


def verify_search(root: Path, identity: str, full_replays: bool = False) -> dict[str, Any]:
    record = json.loads((artifact_path(root, "searches", identity) / "manifest.json").read_text())
    if record["state"] != "COMPLETED":
        raise ValueError("Search is not completed")
    spec = record["configuration"]
    dataset_dir = artifact_path(root, "datasets", spec["dataset_id"])
    dataset = json.loads((dataset_dir / "manifest.json").read_text())
    if (
        sha256(dataset_dir / "rows.json") != record["dataset_sha256"]
        or dataset["rows_sha256"] != record["dataset_sha256"]
    ):
        raise ValueError("Search dataset provenance differs")
    model_dir = artifact_path(root, "models", spec["model_id"])
    model = json.loads((model_dir / "manifest.json").read_text())
    if (
        model["dataset_id"] != spec["dataset_id"]
        or sha256(model_dir / "parameters.json") != record["model_artifact_sha256"]
        or model["artifact_sha256"] != record["model_artifact_sha256"]
    ):
        raise ValueError("Search model provenance differs")
    stages = []
    for key in ("validation_tournament", "test_tournament"):
        directory = artifact_path(root, "tournaments", record[key])
        manifest = json.loads((directory / "manifest.json").read_text())
        if (
            sha256(directory / "rows.json") != manifest["rows_sha256"]
            or manifest["source_hash"] != record["source_hash"]
            or manifest["dataset_sha256"] != record["dataset_sha256"]
        ):
            raise ValueError("Search stage provenance differs")
        rows = json.loads((directory / "rows.json").read_text())
        if len(rows) != manifest["variants"]:
            raise ValueError("Incomplete search stage")
        expected_policies = {"no_trade", "arbitrage", "conservative", "random"} | set(
            manifest["policy_bindings"]
        )
        if {r["policy"] for r in rows} != expected_policies:
            raise ValueError("Search policies differ from planned controls and bindings")
        coverage: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for row in rows:
            pair = row["base_episode_id"], row["execution_model"]
            if pair in coverage[row["policy"]] or not row["passed"]:
                raise ValueError("Invalid or duplicate search outcome")
            coverage[row["policy"]].add(pair)
            if full_replays:
                replay = read_replay(directory / "replays" / f"{row['id']}.json")
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
                ):
                    raise ValueError("Search replay integrity failed")
            binding = manifest["policy_bindings"].get(row["policy"])
            if binding and row["policy_version"] != digest(
                [binding, record["model_artifact_sha256"]]
            ):
                raise ValueError("Gate outcome uses different parameters or weights")
        if any(v != coverage["no_trade"] for v in coverage.values()):
            raise ValueError("Search policies have different episode coverage")
        stages.append((manifest, rows))
    validation, rows = stages[0]
    final, final_rows = stages[1]
    if (
        validation["configuration"]["partition"] != "validation"
        or validation["configuration"]["challenge"]
        or record["test_used_for_selection"]
    ):
        raise ValueError("Selection was not confined to validation")
    expected = [
        {"model_id": spec["model_id"], "threshold": t, "size": size}
        for t in spec["thresholds"]
        for size in spec["sizes"]
    ]
    bindings = validation["policy_bindings"]
    if sorted(digest(v) for v in bindings.values()) != sorted(digest(v) for v in expected):
        raise ValueError("Validation candidates differ from preregistration")
    for policy, binding in bindings.items():
        if policy != "gate-" + digest(["gate-1", binding])[:20]:
            raise ValueError("Gate identity differs from its binding")
    selected = choose(
        rows,
        bindings,
        validation["configuration"]["seed"],
        validation["configuration"]["tail_loss_weight"],
    )
    if selected != record["selection"]["policy"]:
        raise ValueError(
            "Recorded selection differs from independently recomputed validation result"
        )
    chosen = bindings.get(selected)
    if record["selection"]["gate"] != chosen or list(final["policy_bindings"].values()) != (
        [chosen] if chosen else []
    ):
        raise ValueError("Final policy differs from frozen selection")
    challenge = final["configuration"]["challenge"]
    if (
        final["configuration"]["partition"] != "test"
        or challenge["seed"] != spec["challenge_seed"]
        or challenge["episodes"] != spec["challenge_episodes"]
    ):
        raise ValueError("Final generator differs from preregistration")
    if any(
        dataset["spec"]["seed"] <= r["seed"] < dataset["spec"]["seed"] + dataset["spec"]["episodes"]
        for r in final_rows
    ):
        raise ValueError("Final test overlaps the model dataset")
    if {r["seed"] for r in rows} & {r["seed"] for r in final_rows}:
        raise ValueError("Validation and final seeds overlap")
    return {
        "search_id": identity,
        "selected_policy": selected,
        "validation_variants": len(rows),
        "test_variants": len(final_rows),
        "verified": True,
        "full_replay_verification": full_replays,
        "scope": "Frozen lineage and independent validation selection recomputation; full replay audit remains separate.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--search", required=True)
    parser.add_argument("--full-replays", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify_search(args.root, args.search, args.full_replays), indent=2))
