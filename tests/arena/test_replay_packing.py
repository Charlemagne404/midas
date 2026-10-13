import gzip
import json
import sqlite3
from contextlib import closing

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, read_replay, sha256
from midas.economics.attestation import digest

from scripts.pack_replays import pack, prune, restore


def fixture(root):
    directory = root / "tournaments/tournament-test"
    rows, expected = [], {}
    for i in range(3):
        core = {"passed": True, "complete": True, "metrics": {"fixture_number": i}}
        journal = [{"kind": "fixture", "value": i}]
        result = {
            **core,
            "result_hash": digest(core),
            "journal_hash": digest(journal),
            "journal": journal,
        }
        row = {"id": str(i), "result_hash": result["result_hash"]}
        replay = {"row": row, "result": result}
        path = directory / "replays" / (str(i) + ".json")
        if i == 0:
            atomic_json(path, replay)
        else:
            atomic_replay(path, replay)
        rows.append(row)
        expected[str(i)] = replay
    atomic_json(directory / "rows.json", rows)
    atomic_json(
        directory / "manifest.json",
        {"state": "COMPLETED", "rows_sha256": sha256(directory / "rows.json")},
    )
    return directory, expected


def test_pack_restores_original_bytes_and_preserves_lookup(tmp_path):
    directory, expected = fixture(tmp_path)
    loose = {p.name: p.read_bytes() for p in (directory / "replays").iterdir()}
    report = pack(tmp_path, "tournaments", "tournament-test")
    assert report["replays"] == 3 and not report["loose_files_removed"]
    for filename, payload in loose.items():
        assert (directory / "replays" / filename).read_bytes() == payload
        (directory / "replays" / filename).unlink()
    for name, replay in expected.items():
        assert read_replay(directory / "replays" / (name + ".json")) == replay
    destination = tmp_path / "restored"
    assert restore(directory / "replays", destination) == 3
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == loose
    with pytest.raises(FileExistsError):
        restore(directory / "replays", destination)


def test_packed_checksum_and_schema_rejected(tmp_path):
    directory, _ = fixture(tmp_path)
    pack(tmp_path, "tournaments", "tournament-test")
    for p in (directory / "replays").glob("*.json*"):
        p.unlink()
    database = directory / "replays/replays.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "update replays set payload=? where name='0.json'", (gzip.compress(b"{}"),)
        )
        connection.commit()
    with pytest.raises(ValueError, match="checksum"):
        read_replay(directory / "replays/0.json")
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("pragma user_version=2")
    with pytest.raises(ValueError, match="schema"):
        read_replay(directory / "replays/1.json")


def test_refuses_replacement_and_changed_study(tmp_path):
    directory, _ = fixture(tmp_path)
    pack(tmp_path, "tournaments", "tournament-test")
    with pytest.raises(ValueError, match="Existing"):
        pack(tmp_path, "tournaments", "tournament-test")


def test_pruning_is_verified_idempotent_and_api_compatible(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router

    directory, expected = fixture(tmp_path)
    pack(tmp_path, "tournaments", "tournament-test")
    first = prune(tmp_path, "tournaments", "tournament-test")
    assert first["loose_files_removed"]
    assert not list((directory / "replays").glob("*.json.gz"))
    assert prune(tmp_path, "tournaments", "tournament-test") == first
    app = FastAPI()
    app.include_router(router(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/arena/tournaments/tournament-test/replay/1").json() == expected["1"]


def test_active_jobs_and_modified_loose_files_block_maintenance(tmp_path):
    directory, _ = fixture(tmp_path)
    atomic_json(tmp_path / "jobs/job-test/job.json", {"state": "QUEUED"})
    with pytest.raises(ValueError, match="queued"):
        pack(tmp_path, "tournaments", "tournament-test")
    atomic_json(tmp_path / "jobs/job-test/job.json", {"state": "COMPLETED"})
    pack(tmp_path, "tournaments", "tournament-test")
    source = directory / "replays/0.json"
    source.write_text("{}")
    with pytest.raises(ValueError, match="Loose"):
        prune(tmp_path, "tournaments", "tournament-test")
    assert (directory / "replays/1.json.gz").exists()
    with pytest.raises(FileNotFoundError):
        read_replay(directory / "replays/missing.json")
    (directory / "rows.json").write_text("[]")
    with pytest.raises(ValueError, match="rows"):
        pack(tmp_path, "tournaments", "tournament-test")


def test_real_tournament_reproduces_and_exports_from_packed_store(tmp_path):
    from midas.arena.datasets import DatasetSpec, build
    from midas.arena.reproduce import reproduce
    from midas.arena.tournaments import TournamentSpec, run_tournament

    from scripts.arena_bundle import export_tournament
    from scripts.finalize_joint_cost_study import verify_bundle

    data = build(tmp_path, DatasetSpec(episodes=30, seed=1717))
    study = run_tournament(
        tmp_path,
        TournamentSpec(
            dataset_id=data["dataset_id"],
            challenge=DatasetSpec(episodes=30, seed=483071),
            max_episodes=2,
            execution_models=("standard",),
        ),
    )
    identity = study["tournament_id"]
    pack(tmp_path, "tournaments", identity)
    prune(tmp_path, "tournaments", identity)
    rows = json.loads((tmp_path / "tournaments" / identity / "rows.json").read_text())
    assert len(rows) == 8
    for row in rows:
        assert reproduce(tmp_path, identity, row["id"])["verified"]
    output = tmp_path.parent / (identity + ".tar.gz")
    export_tournament(tmp_path, identity, output)
    assert verify_bundle(output) > 8


def test_cold_retention_is_exact_idempotent_and_api_compatible(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router
    from scripts.archive_replays import archive

    root = tmp_path / "arena"
    root.mkdir()
    directory, expected = fixture(root)
    originals = {p.name: p.read_bytes() for p in (directory / "replays").iterdir()}
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    prepared = archive(root, "tournaments", "tournament-test")
    assert prepared["hot_copy_present"]
    result = archive(root, "tournaments", "tournament-test", prune=True)
    assert not result["hot_copy_present"]
    assert result == archive(root, "tournaments", "tournament-test", prune=True)
    assert restore(directory / "replays", tmp_path / "restored") == 3
    assert {p.name: p.read_bytes() for p in (tmp_path / "restored").iterdir()} == originals
    for name, replay in expected.items():
        assert read_replay(directory / "replays" / (name + ".json")) == replay
    app = FastAPI()
    app.include_router(router(root))
    with TestClient(app) as client:
        assert client.get("/api/arena/tournaments/tournament-test/replay/1").json() == expected["1"]
        status = client.get("/api/arena").json()["cold_storage"]
        assert status["references"] == 1 and status["stores"] == 1
        assert status["missing_stores"] == 0 and status["bytes"] > 0


def test_cold_budget_and_corruption_never_remove_hot_evidence(tmp_path, monkeypatch):
    from scripts import archive_replays as tool

    root = tmp_path / "arena"
    root.mkdir()
    directory, _ = fixture(root)
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    monkeypatch.setattr(tool, "COLD_LIMIT", 1)
    with pytest.raises(ValueError, match="budget"):
        tool.archive(root, "tournaments", "tournament-test", prune=True)
    assert (directory / "replays/replays.sqlite").exists()
    monkeypatch.setattr(tool, "COLD_LIMIT", 1024**3)
    record = tool.archive(root, "tournaments", "tournament-test")
    cold = tmp_path / "arena-cold" / record["database_sha256"] / "replays.sqlite"
    cold.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        tool.archive(root, "tournaments", "tournament-test", prune=True)
    assert (directory / "replays/replays.sqlite").exists()


def test_cold_publication_failure_is_recoverable_without_duplicate_copy(tmp_path, monkeypatch):
    from scripts import archive_replays as tool

    root = tmp_path / "arena"
    root.mkdir()
    directory, expected = fixture(root)
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    publish = tool.atomic_json
    monkeypatch.setattr(
        tool, "atomic_json", lambda *args: (_ for _ in ()).throw(OSError("crash before marker"))
    )
    with pytest.raises(OSError, match="crash"):
        tool.archive(root, "tournaments", "tournament-test", prune=True)
    assert (directory / "replays/replays.sqlite").exists()
    assert not (directory / "replays/cold.json").exists()
    monkeypatch.setattr(tool, "atomic_json", publish)
    tool.archive(root, "tournaments", "tournament-test", prune=True)
    assert len(list((tmp_path / "arena-cold").glob("*/replays.sqlite"))) == 1
    assert read_replay(directory / "replays/1.json") == expected["1"]


def test_replay_read_retries_when_hot_store_disappears_after_lookup(tmp_path, monkeypatch):
    from midas.arena import artifacts

    from scripts.archive_replays import archive

    root = tmp_path / "arena"
    root.mkdir()
    directory, expected = fixture(root)
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    archive(root, "tournaments", "tournament-test")
    connect = artifacts.sqlite3.connect

    def race(source_uri, **kwargs):
        local = directory / "replays/replays.sqlite"
        if local.exists():
            local.unlink()
        return connect(source_uri, **kwargs)

    monkeypatch.setattr(artifacts.sqlite3, "connect", race)
    assert read_replay(directory / "replays/1.json") == expected["1"]


def test_invalid_cold_reference_and_symlink_are_rejected(tmp_path):
    from scripts.archive_replays import archive

    root = tmp_path / "arena"
    root.mkdir()
    directory, _ = fixture(root)
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    record = archive(root, "tournaments", "tournament-test", prune=True)
    marker = directory / "replays/cold.json"
    saved = marker.read_text()
    changed = json.loads(saved)
    changed["database_sha256"] = "../../escape"
    atomic_json(marker, changed)
    with pytest.raises(ValueError, match="reference"):
        read_replay(directory / "replays/1.json")
    marker.write_text(saved)
    cold = tmp_path / "arena-cold" / record["database_sha256"] / "replays.sqlite"
    moved = cold.with_suffix(".saved")
    cold.rename(moved)
    cold.symlink_to(moved)
    with pytest.raises(ValueError, match="symlink"):
        read_replay(directory / "replays/1.json")


def test_cold_missing_payload_and_active_job_are_visible(tmp_path):
    from scripts.archive_replays import archive

    root = tmp_path / "arena"
    root.mkdir()
    directory, _ = fixture(root)
    pack(root, "tournaments", "tournament-test")
    prune(root, "tournaments", "tournament-test")
    atomic_json(root / "jobs/job-test/job.json", {"state": "RUNNING"})
    with pytest.raises(ValueError, match="active"):
        archive(root, "tournaments", "tournament-test", prune=True)
    atomic_json(root / "jobs/job-test/job.json", {"state": "COMPLETED"})
    record = archive(root, "tournaments", "tournament-test", prune=True)
    (tmp_path / "arena-cold" / record["database_sha256"] / "replays.sqlite").unlink()
    with pytest.raises(FileNotFoundError):
        read_replay(directory / "replays/1.json")


def test_real_cold_tournament_exports_self_contained_and_reproduces(tmp_path):
    import tarfile

    from midas.arena.datasets import DatasetSpec, build
    from midas.arena.reproduce import reproduce
    from midas.arena.tournaments import TournamentSpec, run_tournament

    from scripts.archive_replays import archive
    from scripts.arena_bundle import export_tournament
    from scripts.finalize_joint_cost_study import verify_bundle

    root = tmp_path / "arena"
    root.mkdir()
    data = build(root, DatasetSpec(episodes=30, seed=1717))
    study = run_tournament(
        root,
        TournamentSpec(
            dataset_id=data["dataset_id"],
            challenge=DatasetSpec(episodes=30, seed=483071),
            max_episodes=2,
            execution_models=("standard",),
        ),
    )
    identity = study["tournament_id"]
    pack(root, "tournaments", identity)
    prune(root, "tournaments", identity)
    archive(root, "tournaments", identity, prune=True)
    rows = json.loads((root / "tournaments" / identity / "rows.json").read_text())
    for row in rows:
        assert reproduce(root, identity, row["id"])["verified"]
    output = tmp_path / "bundle.tar.gz"
    export_tournament(root, identity, output)
    assert verify_bundle(output) > 8
    extracted = tmp_path / "extracted"
    with tarfile.open(output) as bundle:
        assert not any(p.name.endswith("cold.json") for p in bundle)
        bundle.extractall(extracted, filter="data")
    for row in rows:
        assert reproduce(extracted, identity, row["id"])["verified"]
