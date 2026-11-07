from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/midas_sqlite_snapshot.py"
SPEC = importlib.util.spec_from_file_location("midas_sqlite_snapshot", SCRIPT)
assert SPEC and SPEC.loader
midas_sqlite_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(midas_sqlite_snapshot)


@pytest.fixture
def admitted_fixture_scope(monkeypatch):
    monkeypatch.setattr(
        midas_sqlite_snapshot,
        "_require_admitted_scope",
        lambda *, require_heavy_profile=False, require_backup_profile=False: {
            "cgroup": "/fixture",
            "memory_current_bytes": 0,
            "memory_high_bytes": 1024**3,
            "memory_max_bytes": 2 * 1024**3,
            "preflight_at_utc": "fixture",
            "preflight_profile": "bounded-test",
        },
    )


def test_wal_snapshot_restore_is_consistent_and_never_checkpoints_source(
    tmp_path: Path, admitted_fixture_scope
) -> None:
    source = tmp_path / "source.db"
    writer = sqlite3.connect(source)
    assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
    writer.executemany("INSERT INTO events(label) VALUES (?)", [("first",), ("second",)])
    writer.commit()
    wal = Path(f"{source}-wal")
    assert wal.exists()
    wal_bytes_before = wal.stat().st_size

    snapshot = tmp_path / "snapshot"
    manifest = midas_sqlite_snapshot.create_snapshot(source, snapshot, reserve_mib=0)
    assert manifest["source"]["metadata"]["journal_mode"] == "wal"
    assert manifest["snapshot"]["journal_mode"] == "delete"
    assert manifest["snapshot"]["integrity_result"] == ["ok"]
    assert wal.exists()
    assert wal.stat().st_size == wal_bytes_before
    assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    writer.execute("INSERT INTO events(label) VALUES ('after-snapshot')")
    writer.commit()
    assert writer.execute("SELECT count(*) FROM events").fetchone()[0] == 3

    verified = midas_sqlite_snapshot.verify_snapshot(snapshot)
    assert verified["decision"] == "VERIFIED"
    restored = tmp_path / "restored.db"
    receipt = midas_sqlite_snapshot.restore_snapshot(snapshot, restored)
    assert receipt["decision"] == "RESTORED"
    with sqlite3.connect(f"file:{restored}?mode=ro", uri=True) as recovered:
        assert recovered.execute("SELECT label FROM events ORDER BY id").fetchall() == [
            ("first",),
            ("second",),
        ]
    writer.close()


def test_existing_restore_destination_is_never_overwritten(
    tmp_path: Path, admitted_fixture_scope
) -> None:
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE state (value TEXT)")
        connection.execute("INSERT INTO state VALUES ('preserved')")
    snapshot = tmp_path / "snapshot"
    midas_sqlite_snapshot.create_snapshot(source, snapshot, reserve_mib=0)
    destination = tmp_path / "existing.db"
    destination.write_bytes(b"preserve-this")
    with pytest.raises(midas_sqlite_snapshot.SnapshotError):
        midas_sqlite_snapshot.restore_snapshot(snapshot, destination)
    assert destination.read_bytes() == b"preserve-this"


def test_manifest_checksum_detects_tampering(tmp_path: Path, admitted_fixture_scope) -> None:
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE state (value TEXT)")
    snapshot = tmp_path / "snapshot"
    midas_sqlite_snapshot.create_snapshot(source, snapshot, reserve_mib=0)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["snapshot"]["bytes"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(midas_sqlite_snapshot.SnapshotError, match="manifest checksum"):
        midas_sqlite_snapshot.verify_snapshot(snapshot)


def test_large_sqlite_work_requires_heavy_preflight_profile(monkeypatch, tmp_path: Path) -> None:
    cgroup = Path("/sys/fs/cgroup/midas-snapshot-test")
    real_read_text = Path.read_text

    def read_text(path, *args, **kwargs):
        if path == Path("/proc/self/cgroup"):
            return "0::/midas-snapshot-test\n"
        values = {
            cgroup / "memory.current": "0\n",
            cgroup / "memory.high": f"{1024**3}\n",
            cgroup / "memory.max": f"{2 * 1024**3}\n",
        }
        if path in values:
            return values[path]
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setenv("MIDAS_RESOURCE_PREFLIGHT_CGROUP", str(cgroup))
    monkeypatch.setenv("MIDAS_RESOURCE_PREFLIGHT_PROFILE", "bounded-test")
    with pytest.raises(midas_sqlite_snapshot.SnapshotError, match="successful heavy resource"):
        midas_sqlite_snapshot._require_admitted_scope(require_heavy_profile=True)


def test_incomplete_snapshot_cleanup_is_reviewable_and_scoped(tmp_path: Path) -> None:
    partial = tmp_path / ".snapshot.partial.999999999.deadbeef"
    partial.mkdir(mode=0o700)
    marker = {
        "format": midas_sqlite_snapshot.FORMAT_VERSION,
        "uid": os.getuid(),
        "pid": 999999999,
        "boot_id": midas_sqlite_snapshot._boot_id(),
        "created_at_epoch": time.time() - 7200,
        "final_destination": str(tmp_path / "snapshot"),
    }
    (partial / midas_sqlite_snapshot.INCOMPLETE_NAME).write_text(json.dumps(marker))
    review = midas_sqlite_snapshot.cleanup_incomplete(
        tmp_path,
        older_than_seconds=3600,
        delete=False,
    )
    assert review["candidates"][0]["deletion"] == "pending"
    assert partial.exists()
    cleanup = midas_sqlite_snapshot.cleanup_incomplete(
        tmp_path,
        older_than_seconds=3600,
        delete=True,
    )
    assert cleanup["candidates"][0]["deletion"] == "removed"
    assert not partial.exists()


def test_backup_receipt_records_success_without_overwrite(
    tmp_path: Path, admitted_fixture_scope, capsys
) -> None:
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO evidence DEFAULT VALUES")
    receipt = tmp_path / "receipts" / "run.json"
    receipt.parent.mkdir()
    args = [
        "backup",
        "--source",
        str(source),
        "--destination",
        str(tmp_path / "snapshot"),
        "--reserve-mib",
        "0",
        "--receipt",
        str(receipt),
    ]
    assert midas_sqlite_snapshot.main(args) == 0
    capsys.readouterr()
    recorded = json.loads(receipt.read_text())
    assert recorded["operation"] == "backup"
    assert recorded["decision"] == "CREATED"
    assert recorded["result"]["snapshot"]["sha256"]
    original = receipt.read_bytes()
    assert midas_sqlite_snapshot.main(args) == 1
    capsys.readouterr()
    assert receipt.read_bytes() == original


def test_backup_receipt_records_failure(tmp_path: Path, capsys) -> None:
    receipt = tmp_path / "failed-run.json"
    missing_source = tmp_path / "missing.db"
    assert (
        midas_sqlite_snapshot.main(
            [
                "backup",
                "--source",
                str(missing_source),
                "--destination",
                str(tmp_path / "missing-snapshot"),
                "--receipt",
                str(receipt),
            ]
        )
        == 1
    )
    capsys.readouterr()
    recorded = json.loads(receipt.read_text())
    assert recorded["decision"] == "FAILED"
    assert "cannot stat SQLite source" in recorded["error"]
