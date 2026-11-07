from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import midas_local_backup as backup
from scripts import midas_sqlite_snapshot


def test_budget_projection_fails_closed_at_hard_limit():
    backup._require_budget(80, 15, 100, reserve=5)
    with pytest.raises(backup.BackupError, match="exceeds hard limit"):
        backup._require_budget(80, 16, 100, reserve=5)
    with pytest.raises(backup.BackupError, match="approved 100 GB hard limit"):
        backup._require_budget(0, 0, 100_000_000_001)


def test_allocated_size_counts_repository_files_and_rejects_symlinks(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    payload = root / "pack"
    payload.write_bytes(b"x" * 4096)

    assert backup._allocated_bytes(root) >= (root.stat().st_blocks + payload.stat().st_blocks) * 512

    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "external").symlink_to(outside, target_is_directory=True)
    with pytest.raises(backup.BackupError, match="symlink"):
        backup._allocated_bytes(root)


def test_source_size_includes_wal_and_shared_memory_sidecars(tmp_path: Path):
    source = tmp_path / "state.sqlite"
    source.write_bytes(b"db" * 1024)
    Path(f"{source}-wal").write_bytes(b"w" * 128)
    Path(f"{source}-shm").write_bytes(b"s" * 64)

    assert backup._source_size(source) == source.stat().st_size + 192


def test_source_size_rejects_a_symlinked_wal(tmp_path: Path):
    source = tmp_path / "state.sqlite"
    source.write_bytes(b"database")
    (tmp_path / "external-wal").write_bytes(b"wal")
    Path(f"{source}-wal").symlink_to(tmp_path / "external-wal")

    with pytest.raises(backup.BackupError, match="sidecar must not be a symlink"):
        backup._source_size(source)


def test_snapshot_selection_requires_expected_host_and_source_tag():
    snapshots = [
        {"id": "old", "hostname": "host-a", "tags": ["midas-api"], "time": "2026-11-01"},
        {"id": "new", "hostname": "host-a", "tags": ["midas-api"], "time": "2026-11-02"},
        {"id": "other-host", "hostname": "host-b", "tags": ["midas-api"], "time": "2026-11-03"},
    ]

    assert backup._latest_snapshot(snapshots, tag="midas-api", hostname="host-a")["id"] == "new"
    assert backup._latest_snapshot(snapshots, tag="reality", hostname="host-a") is None


def test_status_receipts_are_atomically_replaced_with_private_mode(tmp_path: Path):
    backup._atomic_status(tmp_path, "latest.json", {"status": "VERIFIED", "version": 1})
    backup._atomic_status(tmp_path, "latest.json", {"status": "VERIFIED", "version": 2})
    receipt = tmp_path / "status" / "latest.json"

    assert json.loads(receipt.read_text()) == {"status": "VERIFIED", "version": 2}
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert not list(receipt.parent.glob("*.tmp"))


def test_status_marks_missing_or_expired_recovery_points_stale(tmp_path: Path, monkeypatch):
    root = tmp_path / "backup"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    source = root / "unrelated-source"
    source.write_text("fixture")
    receipt_dir = root / "status"
    receipt_dir.mkdir(mode=0o700)
    created = datetime.now(UTC) - timedelta(days=9)
    (receipt_dir / "latest-database.json").write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "created_at_utc": created.isoformat(),
                "restic_snapshot_id": "0123456789abcdef",
            }
        )
    )
    monkeypatch.setattr(
        backup,
        "verify_destination",
        lambda _config: (
            root,
            root / "repository",
            {"UUID": "fixture"},
        ),
    )
    config = {
        "target": {
            "preferred_bytes": 64_000_000_000,
            "maximum_bytes": 100_000_000_000,
            "uuid": "fixture",
        },
        "sqlite_sources": [{"name": "database"}, {"name": "missing"}],
    }

    value = backup.status(config)

    assert value["status"] == "STALE_OR_MISSING"
    assert value["integrity_check"]["state"] == "missing"
    assert value["sources"]["database"]["state"] == "stale"
    assert value["sources"]["missing"]["state"] == "missing"


def test_status_requires_recent_read_data_verification(tmp_path: Path, monkeypatch):
    root = tmp_path / "backup"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    repository = root / "repository"
    repository.mkdir()
    receipt_dir = root / "status"
    receipt_dir.mkdir(mode=0o700)
    now = datetime.now(UTC).isoformat()
    (receipt_dir / "latest-database.json").write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "created_at_utc": now,
                "restic_snapshot_id": "snapshot-1",
            }
        )
    )
    (receipt_dir / "last-integrity-check.json").write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "verified_at_utc": now,
                "snapshot_count": 1,
                "read_data_subset": "1/32",
                "mount_uuid": "fixture",
            }
        )
    )
    monkeypatch.setattr(backup, "verify_destination", lambda _config: (root, repository, {}))
    monkeypatch.setattr(backup, "_credential_path", lambda: tmp_path / "unused")
    monkeypatch.setattr(backup, "_snapshots", lambda *_args: [{"id": "snapshot-1"}])
    config = {
        "target": {
            "preferred_bytes": 64_000_000_000,
            "maximum_bytes": 100_000_000_000,
            "uuid": "fixture",
        },
        "sqlite_sources": [{"name": "database"}],
    }

    value = backup.status(config)

    assert value["status"] == "READY"
    assert value["integrity_check"]["state"] == "fresh"


def test_policy_loader_requires_known_format_version(tmp_path: Path):
    config = tmp_path / "policy.json"
    config.write_text('{"format_version":2}')

    with pytest.raises(backup.BackupError, match="unsupported"):
        backup.load_config(config)


def test_restic_credential_can_come_from_systemd_credentials_directory(
    tmp_path: Path, monkeypatch
):
    credential_dir = tmp_path / "credentials"
    credential_dir.mkdir(mode=0o700)
    password = credential_dir / "midas-restic-password"
    password.write_text("fixture credential\n")
    password.chmod(0o400)
    monkeypatch.delenv("RESTIC_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(credential_dir))

    assert backup._credential_path() == password


def test_prune_skips_when_a_source_has_only_one_recovery_point(tmp_path: Path, monkeypatch):
    root = tmp_path / "backup"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    repository = root / "repository"
    repository.mkdir()
    password = tmp_path / "password"
    password.write_text("fixture-password\n")
    password.chmod(0o600)
    monkeypatch.setenv("RESTIC_PASSWORD_FILE", str(password))
    monkeypatch.setattr(backup, "require_admitted_scope", lambda **_kwargs: {})
    monkeypatch.setattr(
        backup,
        "verify_destination",
        lambda _config: (root, repository, {"UUID": "fixture"}),
    )
    monkeypatch.setattr(backup, "_credential_path", lambda: password)
    monkeypatch.setattr(
        backup,
        "_snapshots",
        lambda *_args: [
            {"id": "only-point", "hostname": "host-a", "tags": ["midas-local", "midas-database"]}
        ],
    )
    monkeypatch.setattr(
        backup,
        "_restic",
        lambda *_args: pytest.fail("prune must not run with only one recovery point"),
    )
    config = {
        "target": {"maximum_bytes": 100_000_000_000, "preferred_bytes": 64_000_000_000},
        "retention": {"minimum_snapshots_per_source": 2, "keep_daily": 7, "keep_weekly": 4},
        "sqlite_sources": [{"name": "database"}],
    }

    result = backup.prune(config)

    assert result["status"] == "SKIPPED_NEEDS_MORE_RECOVERY_POINTS"
    assert result["sources_with_too_few_snapshots"] == ["midas-database"]
    assert (
        json.loads((root / "status" / "last-prune.json").read_text())["status"] == result["status"]
    )


def test_full_verification_reads_every_repository_pack(tmp_path: Path, monkeypatch):
    root = tmp_path / "backup"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    repository = root / "repository"
    repository.mkdir()
    password = tmp_path / "password"
    password.write_text("fixture-password\n")
    password.chmod(0o600)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(backup, "require_admitted_scope", lambda **_kwargs: {})
    monkeypatch.setattr(
        backup,
        "verify_destination",
        lambda _config: (root, repository, {"UUID": "fixture"}),
    )
    monkeypatch.setattr(backup, "_credential_path", lambda: password)
    monkeypatch.setattr(backup, "_snapshots", lambda *_args: [{"id": "point"}])
    monkeypatch.setattr(
        backup,
        "_restic",
        lambda _repository, _password, *args: calls.append(args) or None,
    )
    monkeypatch.setattr(backup, "_allocated_bytes", lambda _root: 4096)
    monkeypatch.setattr(backup, "_atomic_status", lambda *_args: None)
    config = {
        "target": {"preferred_bytes": 64_000_000_000, "maximum_bytes": 100_000_000_000},
        "sqlite_sources": [],
    }

    result = backup.verify(config, read_data_subset="1/32", full_read=True)

    assert calls == [("check", "--read-data")]
    assert result["read_data_subset"] == "all"


def test_disposable_restic_backup_check_and_restore(tmp_path: Path, monkeypatch):
    if shutil.which("restic") is None:
        pytest.skip("Restic executable is required for the disposable integration test")
    source_dir = Path("/dev/shm")
    if not source_dir.is_dir():
        pytest.skip("a separate temporary filesystem is required by the source safety check")
    source = source_dir / f"midas-backup-{os.getpid()}-{tmp_path.name}.sqlite"
    if source.exists():
        pytest.skip("the disposable source path is already in use")
    root = tmp_path / "backup"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    if os.stat(source_dir).st_dev == os.stat(root).st_dev:
        pytest.skip("temporary source and repository need different devices")
    with sqlite3.connect(source) as connection:
        connection.execute("create table state (key text primary key, value text not null)")
        connection.executemany(
            "insert into state values (?, ?)",
            [(f"key-{index:04d}", f"value-{index:04d}") for index in range(128)],
        )
    password = tmp_path / "restic-password"
    password.write_text("disposable test secret\n")
    password.chmod(0o600)
    monkeypatch.setenv("RESTIC_PASSWORD_FILE", str(password))
    repository = root / "repository"
    config = {
        "target": {
            "mountpoint": str(tmp_path),
            "uuid": "fixture-uuid",
            "maximum_bytes": 8 * 1024**3,
            "preferred_bytes": 4 * 1024**3,
            "free_reserve_bytes": 0,
            "snapshot_reserve_mib": 64,
        },
        "sqlite_sources": [{"name": "fixture", "path": str(source)}],
        "retention": {"minimum_snapshots_per_source": 2},
    }
    monkeypatch.setattr(
        backup,
        "verify_destination",
        lambda _config: (root, repository, {"UUID": "fixture-uuid"}),
    )
    monkeypatch.setattr(backup, "require_admitted_scope", lambda **_kwargs: {"decision": "ADMIT"})

    # The Restic integration test exercises the disposable database and archive
    # path. Resource admission is covered by its own tests; keep the helper in
    # process here so the test does not pretend a user service cgroup is admitted.
    monkeypatch.setattr(midas_sqlite_snapshot, "_require_admitted_scope", lambda **_kwargs: {})
    real_subprocess_run = subprocess.run

    def run_sqlite_snapshot(command, **_kwargs):
        parsed = list(command)
        if not any(str(part).endswith("midas_sqlite_snapshot.py") for part in parsed):
            return real_subprocess_run(command, **_kwargs)
        source_path = Path(parsed[parsed.index("--source") + 1])
        destination_path = Path(parsed[parsed.index("--destination") + 1])
        reserve = int(parsed[parsed.index("--reserve-mib") + 1])
        midas_sqlite_snapshot.create_snapshot(
            source_path,
            destination_path,
            integrity="quick",
            reserve_mib=reserve,
            allow_large="--allow-large" in parsed,
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(backup.subprocess, "run", run_sqlite_snapshot)
    try:
        assert backup.initialize(config)["status"] == "INITIALIZED"
        captured = backup.backup(config)
        assert captured[0]["sqlite_integrity"] == ["ok"]
        restore_check = backup.restore_check(config, "fixture")
        assert restore_check["status"] == "RESTORED_AND_VERIFIED"
        assert restore_check["source_validation"]["integrity_result"] == ["ok"]
        checked = backup.verify(config, read_data_subset="1/32", full_read=True)
        assert checked["read_data_subset"] == "all"
        assert backup.status(config)["status"] == "READY"

        restored = tmp_path / "restored"
        restored.mkdir()
        backup._restic(
            repository,
            password,
            "restore",
            captured[0]["restic_snapshot_id"],
            "--target",
            str(restored),
            "--verify",
        )
        restored_db = next(restored.rglob("database.sqlite"))
        with sqlite3.connect(restored_db) as connection:
            assert connection.execute("pragma integrity_check").fetchone()[0] == "ok"
            assert connection.execute("select count(*) from state").fetchone()[0] == 128
    finally:
        for path in (source, Path(f"{source}-wal"), Path(f"{source}-shm")):
            path.unlink(missing_ok=True)
