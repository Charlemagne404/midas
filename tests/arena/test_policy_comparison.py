import json

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, read_replay, sha256
from midas.economics.attestation import digest

from scripts.compare_policies import compare


def fixture(root):
    directory = root / "tournaments" / "league"
    rows = []
    for group in range(2):
        for execution in ("standard", "optimistic"):
            for policy, value in (("no_trade", 0), ("completion", 1), ("risk", 2)):
                result = {"metrics": {"net_simulated_pnl": str(value)}, "passed": True}
                row = {
                    "id": str(len(rows)),
                    "policy": policy,
                    "base_episode_id": str(group),
                    "execution_model": execution,
                    "scenario_hash": "same",
                    "metrics": result["metrics"],
                    "passed": True,
                    "result_hash": digest(result),
                }
                result.update(journal=[], journal_hash=digest([]), result_hash=row["result_hash"])
                rows.append(row)
                atomic_replay(
                    directory / "replays" / f"{row['id']}.json", {"row": row, "result": result}
                )
    atomic_json(directory / "rows.json", rows)
    atomic_json(
        directory / "manifest.json",
        {
            "rows_sha256": sha256(directory / "rows.json"),
            "variants": len(rows),
            "configuration": {"tail_loss_weight": 1},
            "evaluation_design": "VALIDATION",
        },
    )
    return directory


def test_pairing_and_grouped_interval(tmp_path):
    fixture(tmp_path)
    report = compare(tmp_path, "league", "completion", "risk")
    assert report["base_episodes"] == 2
    assert report["paired_variants"] == 4
    assert report["mean_candidate_minus_control"] == 1
    assert report["group_bootstrap_mean_interval"] == [1, 1]
    assert report["evaluation_design"] == "VALIDATION"


@pytest.mark.parametrize("mutation", ["coverage", "scenario", "journal"])
def test_pair_comparison_rejects_incomplete_or_changed_evidence(tmp_path, mutation):
    directory = fixture(tmp_path)
    rows = json.loads((directory / "rows.json").read_text())
    if mutation == "journal":
        row = next(r for r in rows if r["policy"] == "risk")
        path = directory / "replays" / f"{row['id']}.json"
        replay = read_replay(path)
        replay["result"]["journal"].append({"changed": True})
        atomic_replay(path, replay)
    else:
        if mutation == "coverage":
            rows.pop()
        else:
            next(r for r in rows if r["policy"] == "risk")["scenario_hash"] = "different"
        atomic_json(directory / "rows.json", rows)
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest.update(rows_sha256=sha256(directory / "rows.json"), variants=len(rows))
        atomic_json(directory / "manifest.json", manifest)
    with pytest.raises(ValueError):
        compare(tmp_path, "league", "completion", "risk")
