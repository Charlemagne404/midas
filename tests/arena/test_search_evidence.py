import hashlib
import json
import tarfile

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, sha256
from midas.economics.attestation import digest

from scripts.arena_bundle import export_search, export_tournament
from scripts.verify_policy_search import verify_search


def fixture_search(root):
    model_dir = root / "models" / "model"
    atomic_json(model_dir / "parameters.json", {"label_target": "unmatched"})
    weight = sha256(model_dir / "parameters.json")
    atomic_json(
        model_dir / "manifest.json",
        {
            "model_id": "model",
            "dataset_id": "dataset",
            "family": "logistic",
            "artifact_sha256": weight,
        },
    )
    dataset_dir = root / "datasets" / "dataset"
    atomic_json(dataset_dir / "rows.json", [])
    data_hash = sha256(dataset_dir / "rows.json")
    atomic_json(
        dataset_dir / "manifest.json",
        {"rows_sha256": data_hash, "spec": {"seed": 0, "episodes": 30}},
    )
    bindings = {}
    for size in ("full", "half"):
        config = {"model_id": "model", "threshold": 0.1, "size": size}
        bindings["gate-" + digest(["gate-1", config])[:20]] = config
    selected = next(p for p, b in bindings.items() if b["size"] == "half")
    for stage in ("validation", "test"):
        bound = bindings if stage == "validation" else {selected: bindings[selected]}
        rows = []
        for i in range(30):
            for policy in ("no_trade", "arbitrage", "conservative", "random", *bound):
                rows.append(
                    {
                        "policy": policy,
                        "base_episode_id": f"{stage}-{i}",
                        "seed": i if stage == "validation" else 100 + i,
                        "execution_model": "standard",
                        "passed": True,
                        "metrics": {"net_simulated_pnl": "1" if policy in bound else "0"},
                        "policy_version": digest([bound[policy], weight])
                        if policy in bound
                        else "no-trade-1",
                    }
                )
        directory = root / "tournaments" / stage
        for index, row in enumerate(rows):
            row["id"] = str(index)
            result = {"metrics": row["metrics"], "passed": True}
            row["result_hash"] = digest(result)
            result.update(result_hash=row["result_hash"], journal=[], journal_hash=digest([]))
            atomic_replay(directory / "replays" / f"{index}.json", {"row": row, "result": result})
        atomic_json(directory / "rows.json", rows)
        atomic_json(
            directory / "manifest.json",
            {
                "model_artifact_hashes": {"model": weight},
                "variants": len(rows),
                "rows_sha256": sha256(directory / "rows.json"),
                "source_hash": "source",
                "dataset_sha256": data_hash,
                "policy_bindings": bound,
                "configuration": {
                    "dataset_id": "dataset",
                    "partition": "validation" if stage == "validation" else "test",
                    "seed": 991,
                    "tail_loss_weight": 1,
                    "challenge": None if stage == "validation" else {"seed": 100, "episodes": 30},
                },
            },
        )
    record = {
        "search_id": "search",
        "state": "COMPLETED",
        "source_hash": "source",
        "configuration": {
            "model_id": "model",
            "dataset_id": "dataset",
            "thresholds": [0.1],
            "sizes": ["full", "half"],
            "challenge_seed": 100,
            "challenge_episodes": 30,
        },
        "dataset_sha256": data_hash,
        "model_artifact_sha256": weight,
        "validation_tournament": "validation",
        "test_tournament": "test",
        "test_used_for_selection": False,
        "selection": {"policy": selected, "gate": bindings[selected]},
    }
    atomic_json(root / "searches" / "search" / "manifest.json", record)
    return record


def test_independent_search_verification_and_bundle(tmp_path):
    root = tmp_path / "arena"
    record = fixture_search(root)
    result = verify_search(root, "search")
    assert result["selected_policy"] == record["selection"]["policy"]
    assert result["validation_variants"] == 180
    assert result["test_variants"] == 150
    output = tmp_path / "search.tar.gz"
    exported = export_search(root, "search", output)
    assert exported["sha256"] == sha256(output)
    with tarfile.open(output) as archive:
        manifest = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        assert manifest["search_id"] == "search"
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
    record["selection"]["policy"] = "no_trade"
    atomic_json(root / "searches" / "search" / "manifest.json", record)
    with pytest.raises(ValueError, match="recomputed"):
        verify_search(root, "search")


def test_final_policy_cannot_change_after_selection(tmp_path):
    fixture_search(tmp_path)
    file = tmp_path / "tournaments" / "test" / "manifest.json"
    record = json.loads(file.read_text())
    record["policy_bindings"] = {}
    atomic_json(file, record)
    with pytest.raises(ValueError, match="planned controls and bindings"):
        verify_search(tmp_path, "search")


def test_search_export_refuses_missing_replays(tmp_path):
    fixture_search(tmp_path)
    (tmp_path / "tournaments" / "validation" / "replays" / "0.json.gz").unlink()
    with pytest.raises(FileNotFoundError):
        export_search(tmp_path, "search", tmp_path / "broken.tar.gz")
    assert not (tmp_path / "broken.tar.gz").exists()


def test_standalone_tournament_export_preserves_replay_evidence(tmp_path):
    fixture_search(tmp_path)
    output = tmp_path / "tournament.tar.gz"
    record = export_tournament(tmp_path, "test", output)
    assert record["tournament_id"] == "test"
    with tarfile.open(output) as archive:
        manifest = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        assert "tournaments/test/replays/0.json.gz" in manifest["files"]
