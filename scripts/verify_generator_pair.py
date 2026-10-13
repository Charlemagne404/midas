"""Verify matched terminal-payout revisions and report grouped economic sensitivity."""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.generator_revisions import GeneratorRevision
from midas.economics.attestation import digest
from midas.laboratory.oracles import verify as rational_verify
from midas.laboratory.spec import Scenario
from midas.paper.broker import audit, initial


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def ledger_audit(result: dict) -> int:
    scenario = Scenario.model_validate(result["scenario"])
    for event in result["journal"]:
        state = initial(scenario.account)
        for position in event["after"]["positions"]:
            basis = defaultdict(lambda: Decimal(0))
            for entry in position["ledger"]:
                if entry["kind"] == "fill":
                    basis[entry["asset_id"]] += Decimal(entry["locked_delta"])
            state["positions"][position["id"]] = {
                "exchange": {
                    "market": scenario.market.model_dump(mode="json"),
                    "books": {a: b.model_dump(mode="json") for a, b in scenario.books.items()},
                    "starting": position["portfolio"]["starting_capital"],
                    "ledger": position["ledger"],
                    "orders": position["orders"],
                    "asset_costs": {a: str(v) for a, v in basis.items()},
                    "emergency_stop": False,
                    "settled": position["settled"],
                    "forced_rejections": [],
                    "peak_equity": position["portfolio"]["starting_capital"],
                    "max_drawdown": "0",
                },
                "decision": {},
                "execution_model": position["execution_model"],
                "created_ms": scenario.epoch_ms,
            }
        require(not rational_verify(state), "Independent rational ledger audit failed")
        require(not audit(state), "Independent Decimal ledger audit failed")
    return len(result["journal"])


def prefixes(replay: dict) -> tuple[list, list]:
    scenario = replay["result"]["scenario"]
    cutoff = scenario["epoch_ms"] + min(
        e["time_ms"] for e in scenario["events"] if e["kind"] == "settle"
    )
    return (
        [e for e in replay["result"]["journal"] if e["time_ms"] < cutoff],
        [e for e in replay["decisions"] if e["time_ms"] < cutoff],
    )


def verify(root: Path, plan: dict, identities: list[str]) -> dict:
    require(len(identities) == 2, "Require legacy and revised tournaments")
    manifests, indexed = [], []
    for index, identity in enumerate(identities):
        directory = artifact_path(root, "tournaments", identity)
        m = json.loads((directory / "manifest.json").read_text())
        require(
            m["configuration"] == plan["configurations"][index]["tournament"],
            "Tournament differs from plan",
        )
        require(m["source_hash"] == plan["source_hash"], "Source differs from plan")
        require(m["model_artifact_hashes"] == plan["weights"], "Weights differ from plan")
        require(m["research_champion"] is None, "Unexpected promotion")
        require(sha256(directory / "rows.json") == m["rows_sha256"], "Rows changed")
        rows = json.loads((directory / "rows.json").read_text())
        mapping = {(r["base_episode_id"], r["execution_model"], r["policy"]): r for r in rows}
        require(
            len(mapping) == len(rows) == plan["correlated_variants_per_revision"],
            "Incomplete or duplicate rows",
        )
        manifests.append(m)
        indexed.append(mapping)
    require(indexed[0].keys() == indexed[1].keys(), "Unmatched revision coverage")
    require(
        manifests[0]["dataset_sha256"] == manifests[1]["dataset_sha256"],
        "Different training datasets",
    )
    policies = {"no_trade", "arbitrage", "conservative", "random", *plan["weights"]}
    config = manifests[0]["configuration"]["challenge"]
    expected = {
        (
            f"{config['families'][i % len(config['families'])]}:{config['seed'] + i}",
            execution,
            policy,
        )
        for i in range(plan["source_groups"])
        for execution in manifests[0]["configuration"]["execution_models"]
        for policy in policies
    }
    require(indexed[0].keys() == expected, "Declared policy/source coverage differs")
    for identity, expected_hash in plan["weights"].items():
        directory = artifact_path(root, "models", identity)
        m = json.loads((directory / "manifest.json").read_text())
        path = directory / ("policy.zip" if m["family"] == "ppo" else "parameters.json")
        require(
            sha256(path) == expected_hash == m["artifact_sha256"], "Current fitted weights changed"
        )
    grouped = defaultdict(lambda: defaultdict(list))
    changed_groups, scenarios, journal_states = set(), {}, 0
    for key, first in indexed[0].items():
        second = indexed[1][key]
        pair = []
        for identity, row in zip(identities, (first, second), strict=True):
            directory = artifact_path(root, "tournaments", identity)
            replay = read_replay(directory / "replays" / (row["id"] + ".json"))
            result = replay["result"]
            core = {
                k: v
                for k, v in result.items()
                if k not in {"result_hash", "journal_hash", "journal", "runtime"}
            }
            require(
                replay["row"] == row
                and digest(core) == row["result_hash"] == result["result_hash"],
                "Financial payload changed",
            )
            require(
                digest(result["journal"]) == result["journal_hash"],
                "Journal payload changed",
            )
            require(
                result["passed"] and result["complete"] and row["passed"],
                "Invalid accounting or incomplete episode",
            )
            require(result["metrics"] == row["metrics"], "Row metrics differ")
            require(
                scenarios.setdefault((identity, key[:2]), digest(result["scenario"]))
                == digest(result["scenario"]),
                "Policy scenario inputs differ",
            )
            journal_states += ledger_audit(result)
            pair.append(replay)
        original = Scenario.model_validate(pair[0]["result"]["scenario"])
        revised = GeneratorRevision().apply(original)
        require(
            revised.model_dump(mode="json") == pair[1]["result"]["scenario"],
            "Revision changed undeclared inputs",
        )
        require(
            first["scenario_origin_hash"]
            == second["scenario_origin_hash"]
            == digest(original.model_dump(mode="json")),
            "Origin differs",
        )
        require(
            prefixes(pair[0]) == prefixes(pair[1]),
            "Pre-settlement journals or policy decisions differ",
        )
        if original.events != revised.events:
            changed_groups.add(key[0])
        grouped[key[2]][key[0]].append(
            float(second["metrics"]["net_simulated_pnl"])
            - float(first["metrics"]["net_simulated_pnl"])
        )
    comparisons = []
    for policy, groups in sorted(grouped.items()):
        values = np.array([np.mean(groups[k]) for k in sorted(groups)])
        rng = np.random.default_rng(991)
        bootstrap = rng.choice(values, size=(2000, len(values)), replace=True).mean(axis=1)
        comparisons.append(
            {
                "policy": policy,
                "source_groups": len(groups),
                "mean_revised_minus_legacy": float(values.mean()),
                "group_bootstrap_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
            }
        )
    return {
        "tournaments": identities,
        "source_hash": plan["source_hash"],
        "verified_replays": sum(len(x) for x in indexed),
        "journal_states_independently_audited": journal_states,
        "pairs_with_identical_pre_settlement_evidence": len(indexed[0]),
        "changed_settlement_groups": len(changed_groups),
        "comparisons": comparisons,
        "producer_sha256": sha256(Path(__file__)),
        "limitations": plan["limitations"],
    }
