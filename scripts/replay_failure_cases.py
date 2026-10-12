"""Freeze observed Arena losses into deterministic accounting regression cases."""

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.environment import ArenaEnv
from midas.economics.attestation import digest
from midas.laboratory.spec import Scenario

from scripts.attribute_arena_losses import amount, analyze
from scripts.capture_public_series import publish_exclusive


def result_core(result: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in result.items()
        if k not in {"result_hash", "journal_hash", "journal", "runtime"}
    }


def freeze(root: Path, tournament: str, policy: str) -> dict[str, Any]:
    attribution = analyze(root, tournament, policy)
    directory = artifact_path(root, "tournaments", tournament)
    manifest = json.loads((directory / "manifest.json").read_text())
    losses = [i for i in attribution["episodes"] if amount(i["net_pnl"]) < 0]
    if not losses:
        raise ValueError("No observed losses to freeze")
    if len(losses) > 100:
        raise ValueError("Regression corpus exceeds 100-case bound; select a smaller study")
    cases = []
    for item in sorted(losses, key=lambda i: i["row_id"]):
        replay = read_replay(directory / "replays" / (item["row_id"] + ".json"))
        if digest(replay) != item["replay_content_sha256"]:
            raise ValueError("Replay changed after attribution")
        cases.append(
            {
                "row_id": item["row_id"],
                "base_episode_id": item["base_episode_id"],
                "execution_model": item["execution_model"],
                "scenario": replay["result"]["scenario"],
                "reset_seed": manifest["configuration"]["seed"],
                "decisions": replay["decisions"],
                "expected_result_hash": replay["row"]["result_hash"],
                "expected_journal_hash": replay["result"]["journal_hash"],
                "expected_net_pnl": item["net_pnl"],
                "source_replay_content_sha256": item["replay_content_sha256"],
            }
        )
    return {
        "corpus_version": "arena-observed-loss-regressions-1",
        "corpus_id": "failure-corpus-" + digest([tournament, policy, cases])[:24],
        "tournament_id": tournament,
        "policy": policy,
        "source_hash": manifest["source_hash"],
        "rows_sha256": attribution["rows_sha256"],
        "producer_sha256": sha256(Path(__file__)),
        "cases": cases,
        "case_count": len(cases),
        "source_groups": len({c["base_episode_id"] for c in cases}),
        "limitations": [
            "Cases were selected after observing losses; regression corpus is not an independent evaluation",
            "Replays frozen action decisions with original explanations; does not rerun model inference",
            "Expected hashes enforce simulator financial and journal behavior; no policy promotion",
            "Golden results may need explicit scientific review after intended simulator semantics changes",
            "Synthetic hypothetical execution only; no empirical recovery-policy evidence",
        ],
    }


def verify_case(case: dict[str, Any]) -> dict[str, Any]:
    env = ArenaEnv(scenario=Scenario.model_validate(case["scenario"]), retain=True)
    env.reset(seed=case["reset_seed"])
    info: dict[str, Any] = {}
    done = False
    for decision in case["decisions"]:
        if done:
            raise ValueError("Saved action trace extends beyond termination")
        env.action_explanation = decision["explanation"]
        _, _, done, _, info = env.step(int(decision["requested_action"]))
    if not done:
        raise ValueError("Saved action trace does not reach termination")
    result = info["result"]
    if (
        not result["passed"]
        or not result["complete"]
        or digest(result_core(result)) != case["expected_result_hash"]
        or digest(result["journal"]) != case["expected_journal_hash"]
        or info["decision_trace"] != case["decisions"]
        or amount(result["metrics"]["net_simulated_pnl"]) != amount(case["expected_net_pnl"])
    ):
        raise ValueError("Failure regression changed financial result, journal or decisions")
    return {
        "row_id": case["row_id"],
        "result_hash": case["expected_result_hash"],
        "journal_hash": case["expected_journal_hash"],
        "passed": True,
    }


def verify(corpus: dict[str, Any]) -> dict[str, Any]:
    cases = corpus["cases"]
    if (
        corpus["corpus_version"] != "arena-observed-loss-regressions-1"
        or not 1 <= len(cases) <= 100
        or len(cases) != corpus["case_count"]
        or len({c["row_id"] for c in cases}) != len(cases)
        or len({c["base_episode_id"] for c in cases}) != corpus["source_groups"]
        or corpus["corpus_id"]
        != "failure-corpus-" + digest([corpus["tournament_id"], corpus["policy"], cases])[:24]
    ):
        raise ValueError("Invalid regression corpus identity or coverage")
    return {
        "corpus_id": corpus["corpus_id"],
        "corpus_content_sha256": digest(corpus),
        "producer_sha256": sha256(Path(__file__)),
        "cases": [verify_case(c) for c in cases],
        "scope": "Exact saved-action accounting regressions; not model inference or generalization evaluation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("freeze")
    create.add_argument("--root", type=Path, default=Path("data/arena"))
    create.add_argument("--tournament", required=True)
    create.add_argument("--policy", required=True)
    create.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--corpus", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        report = freeze(args.root, args.tournament, args.policy)
        payload = gzip.compress(
            json.dumps(report, sort_keys=True, allow_nan=False).encode(), mtime=0
        )
    else:
        with gzip.open(args.corpus, "rt") as file:
            corpus = json.load(file)
        report = verify(corpus)
        payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False).encode()
    publish_exclusive(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256(args.output),
                "corpus_id": report["corpus_id"],
                "cases": len(report["cases"]),
            }
        )
    )
