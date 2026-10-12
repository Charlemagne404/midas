import hashlib
import json
import tarfile
from pathlib import Path

import pytest
from midas.arena.artifacts import atomic_json, sha256

from scripts.arena_bundle import export
from scripts.compare_arena import compare


def tournament(root: Path, identity: str, values: list[float]) -> Path:
    directory = root / "tournaments" / identity
    rows = [
        {
            "id": str(i),
            "policy": "no_trade",
            "base_episode_id": "one",
            "execution_model": str(i),
            "scenario_hash": str(i),
            "passed": True,
            "metrics": {"net_simulated_pnl": str(value)},
        }
        for i, value in enumerate(values)
    ]
    atomic_json(directory / "rows.json", rows)
    atomic_json(
        directory / "manifest.json",
        {"variants": len(rows), "rows_sha256": sha256(directory / "rows.json")},
    )
    return directory


def test_comparison_groups_correlated_variants_and_rejects_mismatch(tmp_path):
    tournament(tmp_path, "control", [0, 0, 0])
    candidate = tournament(tmp_path, "candidate", [3, 0, 0])
    result = compare(tmp_path, "control", "candidate")["policies"][0]
    assert result["base_episodes"] == 1
    assert result["paired_variants"] == 3
    assert result["mean_pnl_difference"] == 1
    assert result["episode_bootstrap_95"] == [1, 1]
    rows = json.loads((candidate / "rows.json").read_text())
    rows[0]["scenario_hash"] = "different"
    atomic_json(candidate / "rows.json", rows)
    atomic_json(
        candidate / "manifest.json", {"variants": 3, "rows_sha256": sha256(candidate / "rows.json")}
    )
    with pytest.raises(ValueError, match="identical scenarios"):
        compare(tmp_path, "control", "candidate")
    (candidate / "rows.json").write_text("[]")
    with pytest.raises(ValueError, match="frozen hash"):
        compare(tmp_path, "control", "candidate")


def test_bundle_checksums_and_exclusive_publication(tmp_path):
    root = tmp_path / "arena"
    manifest = {
        "state": "RUNNING",
        "configuration": {"incumbent_model_ids": [], "dataset_id": "dataset"},
        "steps": [],
    }
    directory = root / "directors" / "director"
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(root / "datasets" / "dataset" / "rows.json", [])
    atomic_json(
        root / "datasets" / "dataset" / "manifest.json",
        {"rows_sha256": sha256(root / "datasets" / "dataset" / "rows.json")},
    )
    output = tmp_path / "evidence.tar.gz"
    with pytest.raises(ValueError, match="completed plans"):
        export(root, "director", output)
    manifest["state"] = "COMPLETED"
    atomic_json(directory / "manifest.json", manifest)
    result = export(root, "director", output)
    assert result["sha256"] == sha256(output)
    with tarfile.open(output) as archive:
        record = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        for name, expected in record["files"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
    with pytest.raises(ValueError, match="overwrite"):
        export(root, "director", output)
    assert result["sha256"] == sha256(output)
