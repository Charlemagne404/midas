"""Explicit fixture operations: scheduling, bounded retries and disposable caches."""

import json
import shutil
from pathlib import Path

import pytest
from midas.reality.model_training import TrainingSpec, run
from midas.reality.research_schedule import clear_unpublished, prune_disposable, tick
from midas.reality.storage import atomic_json, file_hash
from test_reality_foundry import START, tape
from test_reality_training import dataset_fixture


def config(tmp_path):
    values = json.loads(Path("deploy/reality-research.json").read_text())
    for key, name in (
        ("raw_root", "raw"),
        ("state_root", "scheduled"),
        ("training_root", "training"),
        ("evaluation_ledger", "ledger"),
    ):
        values[key] = str(tmp_path / name)
    path = tmp_path / "config.json"
    atomic_json(path, values)
    return path, values


def test_daily_check_waits_for_coverage_without_fitting_or_touching_raw(tmp_path):
    tape(tmp_path / "raw")
    before = {p.name: file_hash(p) for p in (tmp_path / "raw").glob("*.seg")}
    path, values = config(tmp_path)
    state = tick(path, now_ns=START + 86400 * 10**9)
    assert state["state"] == "WAITING_FOR_COVERAGE"
    assert state["automatic_promotion"] is False
    assert before == {p.name: file_hash(p) for p in (tmp_path / "raw").glob("*.seg")}
    assert not list((tmp_path / "training").glob("runs/*"))
    values["enabled"] = False
    atomic_json(path, values)
    assert tick(path, now_ns=START + 86400 * 10**9)["state"] == "DISABLED"


def test_completed_week_does_not_self_trigger_new_experiments(tmp_path):
    tape(tmp_path / "raw")
    path, values = config(tmp_path)
    state_root = Path(values["state_root"])
    state_root.mkdir()
    atomic_json(
        state_root / "status.json",
        dict(state="INSUFFICIENT_EVIDENCE", fit_week="2026-W42", run_id="fixture"),
    )
    a = tick(path, now_ns=START)
    b = tick(path, now_ns=START + 1000)
    assert a["state"] == b["state"] == "ALREADY_ATTEMPTED_THIS_WEEK"
    assert b["run_id"] == "fixture"


def test_pruning_only_disposes_marked_completed_rows_and_preserves_regeneration(
    tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    cache.mkdir()
    training, ledger = tmp_path / "training", tmp_path / "ledger"
    paths = []
    for i in (1, 2):
        monkeypatch.setattr("test_reality_foundry.START", START + i * 86400 * 10**9)
        source, manifest = dataset_fixture(tmp_path / str(i))
        destination = cache / manifest["dataset_id"]
        shutil.copytree(source, destination)
        report = run(
            destination,
            training,
            ledger,
            TrainingSpec(
                targets=("quote_persistence",),
                horizon_ms=100,
                allow_mlp=False,
                reserve_bytes=1,
                budget_bytes=16 * 1024**2,
            ),
        )
        atomic_json(
            destination / "disposable-cache.json",
            dict(
                retention_class="completed_scheduled_example_cache",
                completed_ns=i,
                run_id=report["run_id"],
                report_sha256=file_hash(training / "runs" / report["run_id"] / "report.json"),
            ),
        )
        paths.append(destination)
    raw_before = {str(p): file_hash(p) for p in tmp_path.glob("*/raw/*.seg")}
    manifest_before = [file_hash(p / "manifest.json") for p in paths]
    changes = prune_disposable(cache, training, keep=1)
    assert len(changes) == 1 and changes[0]["raw_observations_removed"] is False
    assert not (paths[0] / "examples.jsonl").exists()
    assert (paths[1] / "examples.jsonl").exists()
    assert [file_hash(p / "manifest.json") for p in paths] == manifest_before
    assert all((p / "code").is_dir() for p in paths)
    assert raw_before == {str(p): file_hash(p) for p in tmp_path.glob("*/raw/*.seg")}
    assert (
        json.loads((paths[0] / "cache-availability.json").read_text())["state"]
        == "REGENERATABLE_ROWS_PRUNED"
    )


def test_unpublished_scratch_is_explicitly_disposable_and_symlinks_are_rejected(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    scratch = root / (".building-" + "a" * 32)
    scratch.mkdir()
    (scratch / "partial.jsonl").write_text("fixture")
    preserved = root / "published.json"
    preserved.write_text("preserved")
    result = clear_unpublished(root)
    assert result[0]["bytes"] == 7 and not scratch.exists() and preserved.exists()
    unsafe = root / (".building-" + "b" * 32)
    unsafe.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="Unexpected"):
        clear_unpublished(root)
