"""Independent capacity selection and matched fresh-accounting verification."""

import json
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.arena.datasets import load
from midas.arena.supervised import Predictor
from midas.economics.attestation import digest
from sklearn.preprocessing import StandardScaler

from scripts.verify_generator_pair import ledger_audit


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "plans", identity)
    plan = json.loads((directory / "manifest.json").read_text())
    require(plan["state"] == "COMPLETED", "Plan not completed")
    frozen = plan["frozen"]
    for item in frozen["evidence"]:
        require(
            sha256(directory / "inputs" / item["kind"] / item["identity"] / "manifest.json")
            == item["manifest_sha256"],
            "Selection evidence snapshot differs",
        )
    director_path = artifact_path(root, "directors", plan["director_id"])
    director = json.loads((director_path / "manifest.json").read_text())
    require(
        director["state"] == "COMPLETED"
        and director["source_hash"] == frozen["source_hash"]
        and director["configuration"] == frozen["director"],
        "Director differs from frozen plan",
    )
    require(
        len(director["steps"]) == 3 and all(s["state"] == "COMPLETED" for s in director["steps"]),
        "Director stage coverage incomplete",
    )
    sweep_id = director["steps"][0]["artifact"]["identity"]
    sweep = json.loads((artifact_path(root, "sweeps", sweep_id) / "manifest.json").read_text())
    dataset, rows = load(root, frozen["configuration"]["dataset_id"])
    require(
        dataset["rows_sha256"] == frozen["dataset_sha256"] == sweep["dataset_sha256"],
        "Training data changed",
    )
    require(
        not sweep["test_labels_used_for_selection"]
        and sweep["source_hash"] == frozen["source_hash"],
        "Invalid selection scope/source",
    )
    candidates = sweep["configuration"]["candidates"]
    seeds = sweep["configuration"]["seeds"]
    require(
        candidates == frozen["director"]["sweep_candidates"]
        and seeds == frozen["director"]["sweep_seeds"],
        "Preregistered architectures/seeds differ",
    )
    expected = {(i, s) for i in range(len(candidates)) for s in seeds}
    require(
        len(sweep["trials"]) == 4
        and {(t["candidate_index"], t["seed"]) for t in sweep["trials"]} == expected,
        "Training coverage differs",
    )
    training = np.array(
        [r["features"] for r in rows if r["partition"] == "train"], dtype=np.float32
    )
    validation = [r for r in rows if r["partition"] == "validation"]
    features = np.array([r["features"] for r in validation])
    labels = np.array([r["label"] for r in validation], dtype=np.float64)
    scaler = StandardScaler().fit(training)
    checked = []
    for trial in sweep["trials"]:
        model_directory = artifact_path(root, "models", trial["model_id"])
        model = json.loads((model_directory / "manifest.json").read_text())
        require(
            trial["state"] == "COMPLETED" and model["family"] == "mlp" and model["test"] is None,
            "Incomplete/non-neural or opened-final-test trial",
        )
        require(
            model["source_hash"] == frozen["source_hash"]
            and model["dataset_sha256"] == dataset["rows_sha256"]
            and model["configuration"]["hidden_size"]
            == candidates[trial["candidate_index"]]["hidden_size"]
            and model["configuration"]["seed"] == trial["seed"],
            "Fitted trial configuration differs",
        )
        require(
            sha256(model_directory / "parameters.json")
            == trial["artifact_sha256"]
            == model["artifact_sha256"],
            "Fitted weights differ",
        )
        predictor = Predictor.load(root, trial["model_id"])
        require(
            np.array_equal(scaler.mean_, predictor.parameters["mean"])
            and np.array_equal(scaler.scale_, predictor.parameters["scale"]),
            "Transform not fitted on training-only rows",
        )
        prediction = np.asarray(predictor.predict(features), dtype=np.float64)
        brier = float(np.mean((prediction - labels) ** 2))
        require(
            abs(brier - model["validation"]["brier"]) < 1e-7
            and model["validation"] == trial["validation"],
            "Validation evidence differs from actual weights",
        )
        checked.append(
            {
                "model_id": trial["model_id"],
                "hidden_size": model["configuration"]["hidden_size"],
                "seed": trial["seed"],
                "validation_brier": brier,
                "stored_brier": trial["validation"]["brier"],
                "final_test": "unopened",
            }
        )
    means = [
        float(
            np.mean(
                [t["validation"]["brier"] for t in sweep["trials"] if t["candidate_index"] == i]
            )
        )
        for i in range(len(candidates))
    ]
    best = min(means)
    eligible = [
        i
        for i, score in enumerate(means)
        if score <= best + sweep["configuration"]["practical_brier_tolerance"]
    ]

    def complexity(i):
        return (
            19 * candidates[i]["hidden_size"]
            + candidates[i]["hidden_size"] ** 2
            + 3 * candidates[i]["hidden_size"]
            + 1
        )

    chosen = min(eligible, key=lambda i: (complexity(i), means[i], i))
    representative = min(
        [t for t in sweep["trials"] if t["candidate_index"] == chosen],
        key=lambda t: (t["validation"]["brier"], t["seed"]),
    )["model_id"]
    require(
        sweep["selection"]["selected_model_id"]
        == director["selected_model_id"]
        == plan["selected_model_id"]
        == representative
        and sweep["selection"]["selection_partition"] == "validation",
        "Independent selection disagrees",
    )
    policies = {
        *frozen["director"]["incumbent_model_ids"],
        representative,
        "no_trade",
        "arbitrage",
        "conservative",
        "random",
    }
    identities = set(frozen["challenge_identities"])
    maps = []
    states = 0
    variant_count = 0
    studies = []
    for stage_index, step in enumerate(director["steps"][1:]):
        tour_id = step["artifact"]["identity"]
        path = artifact_path(root, "tournaments", tour_id)
        manifest = json.loads((path / "manifest.json").read_text())
        require(
            manifest["source_hash"] == frozen["source_hash"]
            and manifest["research_champion"] is None
            and manifest["configuration"]["minimum_champion_episodes"]
            == frozen["director"]["minimum_champion_episodes"]
            == 2000
            and sha256(path / "rows.json") == manifest["rows_sha256"],
            "Fresh evaluation source/rows/promotion differs",
        )
        require(
            manifest["configuration"]["unsupported_input_policy"]
            == ("warn" if stage_index == 0 else "abstain"),
            "Support comparison differs",
        )
        values = json.loads((path / "rows.json").read_text())
        expected_grid = {
            (base, execution, policy)
            for base in identities
            for execution in ("optimistic", "standard", "conservative")
            for policy in policies
        }
        require(
            len(values) == len(expected_grid)
            and {(r["base_episode_id"], r["execution_model"], r["policy"]) for r in values}
            == expected_grid,
            "Matched fresh evaluation coverage differs",
        )
        pnl = {}
        scenario_hashes = {}
        for row in values:
            replay = read_replay(path / "replays" / (row["id"] + ".json"))
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
                "Replay accounting/journal hash differs",
            )
            require(result["passed"] and result["complete"], "Invalid/incomplete replay")
            require(
                result["metrics"] == row["metrics"], "Summary metrics differ from actual replay"
            )
            states += ledger_audit(result)
            key = (row["base_episode_id"], row["execution_model"], row["policy"])
            pnl[key] = float(row["metrics"]["net_simulated_pnl"])
            scenario_hashes[key] = digest(result["scenario"])
        maps.append((pnl, scenario_hashes))
        variant_count += len(values)
        studies.append(
            {
                "tournament_id": tour_id,
                "leaderboard": manifest["leaderboard"],
                "rows_sha256": manifest["rows_sha256"],
            }
        )
    require(maps[0][1] == maps[1][1], "Warning/abstention scenarios are not matched")
    differences = []
    for policy in sorted(policies):
        groups = np.array(
            [
                np.mean(
                    [
                        maps[1][0][base, execution, policy] - maps[0][0][base, execution, policy]
                        for execution in ("optimistic", "standard", "conservative")
                    ]
                )
                for base in sorted(identities)
            ]
        )
        rng = np.random.default_rng(771)
        bootstrap = rng.choice(groups, size=(2000, len(groups)), replace=True).mean(axis=1)
        differences.append(
            {
                "policy": policy,
                "mean_abstain_minus_warn": float(groups.mean()),
                "group_bootstrap_95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
                "source_groups": len(groups),
            }
        )
    return {
        "plan_id": identity,
        "director_id": director["director_id"],
        "sweep_id": sweep_id,
        "selected_model_id": representative,
        "candidate_validation_means": means,
        "trials_verified": checked,
        "selection_verified": True,
        "independent_source_groups": len(identities),
        "correlated_variants_verified": variant_count,
        "journal_states_audited": states,
        "matched_studies": studies,
        "paired_support_comparisons": differences,
        "producer_sha256": sha256(Path(__file__)),
        "limitations": [
            "Training seeds repeat one dataset; matched support studies share one new cohort.",
            "Validation quality does not imply economically robust decisions.",
            "Prior plateau selected the question, not new challenge weights/thresholds; no promotion.",
            "Synthetic hypothetical evidence, no empirical fills or real profitability.",
        ],
    }
