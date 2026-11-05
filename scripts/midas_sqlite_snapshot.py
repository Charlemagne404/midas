#!/usr/bin/env python3
"""Create, verify, and restore standalone SQLite snapshots without copying a live WAL file."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import stat
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
LARGE_DATABASE_BYTES = 5 * 1024**3
DATABASE_NAME = "database.sqlite"
MANIFEST_NAME = "manifest.json"
MANIFEST_HASH_NAME = "manifest.sha256"
INCOMPLETE_NAME = ".midas-incomplete.json"


class SnapshotError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()


def _require_admitted_scope(*, require_heavy_profile: bool = False) -> dict[str, Any]:
    declared = os.environ.get("MIDAS_RESOURCE_PREFLIGHT_CGROUP")
    if not declared:
        raise SnapshotError("run this command through scripts/midas_resource_preflight.py run")
    lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    actual = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), None)
    if actual is None or f"/sys/fs/cgroup{actual}" != declared:
        raise SnapshotError("resource-preflight cgroup does not match this process")
    cgroup = Path(declared)
    try:
        current = int((cgroup / "memory.current").read_text().strip())
        high = (cgroup / "memory.high").read_text().strip()
        maximum = (cgroup / "memory.max").read_text().strip()
    except (OSError, ValueError) as error:
        raise SnapshotError(f"cannot verify bounded task cgroup: {error}") from error
    if high in {"max", "infinity"} or maximum in {"max", "infinity"}:
        raise SnapshotError("the backup task cgroup must have finite MemoryHigh and MemoryMax")
    profile = os.environ.get("MIDAS_RESOURCE_PREFLIGHT_PROFILE")
    if profile not in {"heavy", "bounded-test"}:
        raise SnapshotError("resource preflight profile is missing or invalid")
    if require_heavy_profile and profile != "heavy":
        raise SnapshotError("large SQLite work requires a successful heavy resource preflight")
    return {
        "cgroup": actual,
        "memory_current_bytes": current,
        "memory_high_bytes": int(high),
        "memory_max_bytes": int(maximum),
        "preflight_at_utc": os.environ.get("MIDAS_RESOURCE_PREFLIGHT_AT_UTC"),
        "preflight_profile": profile,
    }


def _sqlite_connection(path: Path, *, readonly: bool) -> sqlite3.Connection:
    if readonly:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30.0)
        connection.execute("PRAGMA query_only=ON")
        return connection
    connection = sqlite3.connect(path, timeout=30.0)
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def _objects(connection: sqlite3.Connection) -> list[tuple[str, str, str, str | None]]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name, tbl_name"
    ).fetchall()
    return [(str(kind), str(name), str(table), sql) for kind, name, table, sql in rows]


def _schema_sha256(connection: sqlite3.Connection) -> str:
    canonical = json.dumps(_objects(connection), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _database_metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    revisions: list[str] = []
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "alembic_version" in tables:
        revisions = [
            str(row[0])
            for row in connection.execute(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            )
        ]
    return {
        "journal_mode": str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
        "schema_version": int(connection.execute("PRAGMA schema_version").fetchone()[0]),
        "user_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
        "page_size": int(connection.execute("PRAGMA page_size").fetchone()[0]),
        "page_count": int(connection.execute("PRAGMA page_count").fetchone()[0]),
        "freelist_count": int(connection.execute("PRAGMA freelist_count").fetchone()[0]),
        "alembic_revisions": revisions,
        "schema_sha256": _schema_sha256(connection),
    }


def _check_integrity(connection: sqlite3.Connection, mode: str) -> list[str]:
    pragma = "integrity_check" if mode == "full" else "quick_check"
    rows = [str(row[0]) for row in connection.execute(f"PRAGMA {pragma}")]
    if rows != ["ok"]:
        raise SnapshotError(f"SQLite PRAGMA {pragma} failed: {rows[:20]}")
    return rows


def _regular_file(path: Path, *, what: str) -> os.stat_result:
    if path.is_symlink():
        raise SnapshotError(f"{what} is a symlink: {path}")
    try:
        info = path.stat()
    except OSError as error:
        raise SnapshotError(f"cannot stat {what} {path}: {error}") from error
    if not stat.S_ISREG(info.st_mode):
        raise SnapshotError(f"{what} is not a regular file: {path}")
    return info


def _wal_identity(source: Path) -> dict[str, Any] | None:
    wal = Path(f"{source}-wal")
    if not wal.exists():
        return None
    info = _regular_file(wal, what="source WAL")
    return {
        "path": str(wal),
        "bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "inode": info.st_ino,
    }


def _rename_noreplace(source: Path, destination: Path) -> None:
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise SnapshotError("atomic no-replace directory publication is unsupported") from error
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    result = function(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return data


def create_snapshot(
    source: Path,
    destination: Path,
    *,
    integrity: str = "quick",
    reserve_mib: int = 5120,
    allow_large: bool = False,
) -> dict[str, Any]:
    source = source.expanduser().absolute()
    destination = destination.expanduser().absolute()
    source_info = _regular_file(source, what="SQLite source")
    if source_info.st_size == 0:
        raise SnapshotError("SQLite source is empty")
    if not destination.parent.is_dir() or destination.exists() or destination.is_symlink():
        raise SnapshotError("snapshot destination parent must exist and destination must not exist")
    if source == destination or source.is_relative_to(destination):
        raise SnapshotError("snapshot destination overlaps the SQLite source")
    admission = _require_admitted_scope(
        require_heavy_profile=source_info.st_size >= LARGE_DATABASE_BYTES
    )
    if source_info.st_size >= LARGE_DATABASE_BYTES and not allow_large:
        raise SnapshotError(
            f"source is {source_info.st_size} bytes; large snapshots require --allow-large after admission review"
        )
    if integrity not in {"quick", "full"}:
        raise SnapshotError("integrity mode must be quick or full")

    source_stat_before = {
        "path": str(source),
        "bytes": source_info.st_size,
        "mtime_ns": source_info.st_mtime_ns,
        "inode": source_info.st_ino,
        "owner_uid": source_info.st_uid,
        "owner_gid": source_info.st_gid,
    }
    wal_before = _wal_identity(source)
    staging = (
        destination.parent / f".{destination.name}.partial.{os.getpid()}.{uuid.uuid4().hex[:10]}"
    )
    staging.mkdir(mode=0o700)
    marker = {
        "format": FORMAT_VERSION,
        "uid": os.getuid(),
        "pid": os.getpid(),
        "boot_id": _boot_id(),
        "created_at_epoch": time.time(),
        "final_destination": str(destination),
    }
    destination_file = staging / DATABASE_NAME
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        _write_json(staging / INCOMPLETE_NAME, marker)
        source_connection = _sqlite_connection(source, readonly=True)
        source_metadata = _database_metadata(source_connection)
        estimated_bytes = source_metadata["page_count"] * source_metadata["page_size"]
        if estimated_bytes >= LARGE_DATABASE_BYTES:
            if not allow_large:
                raise SnapshotError(
                    f"logical database size is {estimated_bytes} bytes; pass --allow-large after admission review"
                )
            _require_admitted_scope(require_heavy_profile=True)
        filesystem = os.statvfs(destination.parent)
        available_bytes = filesystem.f_bavail * filesystem.f_frsize
        required_bytes = estimated_bytes + reserve_mib * 1024 * 1024
        if available_bytes < required_bytes:
            raise SnapshotError(
                f"insufficient destination capacity: available={available_bytes} required={required_bytes}"
            )

        destination_connection = _sqlite_connection(destination_file, readonly=False)
        os.chmod(destination_file, 0o600)
        source_connection.backup(destination_connection, pages=128, sleep=0.1)
        journal_mode = str(
            destination_connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        ).lower()
        if journal_mode != "delete":
            raise SnapshotError(
                f"standalone snapshot journal mode is {journal_mode}, expected delete"
            )
        integrity_result = _check_integrity(destination_connection, integrity)
        snapshot_metadata = _database_metadata(destination_connection)
        if snapshot_metadata["schema_sha256"] != source_metadata["schema_sha256"]:
            raise SnapshotError("snapshot schema fingerprint differs from source read transaction")
        destination_connection.close()
        destination_connection = None
        source_connection.close()
        source_connection = None

        destination_info = destination_file.stat()
        with destination_file.open("rb") as stream:
            os.fsync(stream.fileno())
        source_stat_after = source.stat()
        wal_after = _wal_identity(source)
        manifest = {
            "format": "midas-sqlite-snapshot",
            "format_version": FORMAT_VERSION,
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {
                **source_stat_before,
                "wal_before": wal_before,
                "stat_after": {
                    "bytes": source_stat_after.st_size,
                    "mtime_ns": source_stat_after.st_mtime_ns,
                    "inode": source_stat_after.st_ino,
                },
                "wal_after": wal_after,
                "metadata": source_metadata,
            },
            "snapshot": {
                "database": DATABASE_NAME,
                "bytes": destination_info.st_size,
                "sha256": _sha256_file(destination_file),
                "journal_mode": "delete",
                "metadata": snapshot_metadata,
                "integrity_check": integrity,
                "integrity_result": integrity_result,
            },
            "sqlite_runtime_version": sqlite3.sqlite_version,
            "admission": admission,
        }
        manifest_bytes = _write_json(staging / MANIFEST_NAME, manifest)
        hash_file = staging / MANIFEST_HASH_NAME
        with hash_file.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(hashlib.sha256(manifest_bytes).hexdigest().encode("ascii") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        (staging / INCOMPLETE_NAME).unlink()
        directory_fd = os.open(staging, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _rename_noreplace(staging, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return manifest
    except BaseException:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
        if staging.exists():
            shutil.rmtree(staging)
        raise


def verify_snapshot(directory: Path, *, integrity: str = "quick") -> dict[str, Any]:
    directory = directory.expanduser().absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise SnapshotError("snapshot path must be an existing directory, not a symlink")
    manifest_path = directory / MANIFEST_NAME
    hash_path = directory / MANIFEST_HASH_NAME
    database_path = directory / DATABASE_NAME
    for path, label in (
        (manifest_path, "snapshot manifest"),
        (hash_path, "manifest digest"),
        (database_path, "snapshot database"),
    ):
        _regular_file(path, what=label)
    manifest_bytes = manifest_path.read_bytes()
    expected_manifest_hash = hash_path.read_text(encoding="ascii").strip()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_hash:
        raise SnapshotError("snapshot manifest checksum mismatch")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise SnapshotError(f"invalid snapshot manifest: {error}") from error
    if (
        manifest.get("format") != "midas-sqlite-snapshot"
        or manifest.get("format_version") != FORMAT_VERSION
    ):
        raise SnapshotError("unsupported snapshot manifest format")
    snapshot = manifest.get("snapshot", {})
    _require_admitted_scope(
        require_heavy_profile=int(snapshot.get("bytes", 0)) >= LARGE_DATABASE_BYTES
    )
    if database_path.stat().st_size != snapshot.get("bytes"):
        raise SnapshotError("snapshot database size differs from manifest")
    if _sha256_file(database_path) != snapshot.get("sha256"):
        raise SnapshotError("snapshot database checksum mismatch")
    connection = _sqlite_connection(database_path, readonly=True)
    try:
        integrity_result = _check_integrity(connection, integrity)
        metadata = _database_metadata(connection)
        if metadata["schema_sha256"] != snapshot.get("metadata", {}).get("schema_sha256"):
            raise SnapshotError("snapshot database schema fingerprint differs from manifest")
    finally:
        connection.close()
    return {
        "decision": "VERIFIED",
        "snapshot_path": str(directory),
        "database_bytes": database_path.stat().st_size,
        "database_sha256": snapshot["sha256"],
        "integrity_check": integrity,
        "integrity_result": integrity_result,
        "metadata": metadata,
    }


def restore_snapshot(
    directory: Path, destination: Path, *, integrity: str = "quick"
) -> dict[str, Any]:
    admission = _require_admitted_scope()
    verified = verify_snapshot(directory, integrity=integrity)
    destination = destination.expanduser().absolute()
    if not destination.parent.is_dir() or destination.exists() or destination.is_symlink():
        raise SnapshotError("restore destination parent must exist and destination must not exist")
    source_path = Path(verified["snapshot_path"]) / DATABASE_NAME
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.restore.partial.", dir=destination.parent
    )
    temp_path = Path(temp_name)
    try:
        os.fchmod(temp_fd, 0o600)
        with os.fdopen(temp_fd, "wb") as output, source_path.open("rb") as source:
            shutil.copyfileobj(source, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if _sha256_file(temp_path) != verified["database_sha256"]:
            raise SnapshotError("restored copy checksum differs from verified snapshot")
        connection = _sqlite_connection(temp_path, readonly=True)
        try:
            result = _check_integrity(connection, integrity)
            metadata = _database_metadata(connection)
        finally:
            connection.close()
        os.link(temp_path, destination)
        temp_path.unlink()
        parent_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return {
            "decision": "RESTORED",
            "destination": str(destination),
            "database_bytes": destination.stat().st_size,
            "database_sha256": verified["database_sha256"],
            "integrity_result": result,
            "metadata": metadata,
            "admission": admission,
        }
    except BaseException:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def cleanup_incomplete(parent: Path, *, older_than_seconds: int, delete: bool) -> dict[str, Any]:
    parent = parent.expanduser().absolute()
    if parent.is_symlink() or not parent.is_dir() or older_than_seconds < 0:
        raise SnapshotError("cleanup parent must be a real directory and age must be nonnegative")
    now = time.time()
    current_boot = _boot_id()
    candidates: list[dict[str, Any]] = []
    for path in sorted(parent.glob(".*.partial.*")):
        if path.is_symlink() or not path.is_dir():
            continue
        marker_path = path / INCOMPLETE_NAME
        if marker_path.is_symlink() or not marker_path.is_file():
            continue
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            owner_matches = (
                marker.get("format") == FORMAT_VERSION and marker.get("uid") == os.getuid()
            )
            age = now - float(marker["created_at_epoch"])
            same_boot = marker.get("boot_id") == current_boot
            pid = int(marker["pid"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if not owner_matches or age < older_than_seconds:
            continue
        if same_boot:
            try:
                os.kill(pid, 0)
                continue
            except ProcessLookupError:
                pass
            except PermissionError:
                continue
        item = {"path": str(path), "age_seconds": int(age), "owner_pid": pid, "deletion": "pending"}
        if delete:
            shutil.rmtree(path)
            item["deletion"] = "removed"
        candidates.append(item)
    return {"decision": "CLEANUP_REVIEW", "delete_enabled": delete, "candidates": candidates}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    backup = commands.add_parser("backup", help="make a transactional online SQLite snapshot")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True, help="new snapshot directory")
    backup.add_argument("--integrity", choices=("quick", "full"), default="quick")
    backup.add_argument("--reserve-mib", type=int, default=5120)
    backup.add_argument("--allow-large", action="store_true")

    verify = commands.add_parser("verify", help="verify snapshot checksums and SQLite integrity")
    verify.add_argument("--snapshot", type=Path, required=True)
    verify.add_argument("--integrity", choices=("quick", "full"), default="quick")

    restore = commands.add_parser(
        "restore", help="restore a verified snapshot to a new isolated file"
    )
    restore.add_argument("--snapshot", type=Path, required=True)
    restore.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="new database file; existing files are never overwritten",
    )
    restore.add_argument("--integrity", choices=("quick", "full"), default="quick")

    cleanup = commands.add_parser(
        "cleanup-incomplete", help="review or remove stale snapshots created by this tool"
    )
    cleanup.add_argument("--parent", type=Path, required=True)
    cleanup.add_argument("--older-than-seconds", type=int, default=3600)
    cleanup.add_argument(
        "--delete", action="store_true", help="remove only verified stale partial directories"
    )
    return parser


def _handle_sigterm(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    args = build_parser().parse_args(argv)
    try:
        if args.action == "backup":
            result = create_snapshot(
                args.source,
                args.destination,
                integrity=args.integrity,
                reserve_mib=args.reserve_mib,
                allow_large=args.allow_large,
            )
        elif args.action == "verify":
            result = verify_snapshot(args.snapshot, integrity=args.integrity)
        elif args.action == "restore":
            result = restore_snapshot(args.snapshot, args.destination, integrity=args.integrity)
        else:
            result = cleanup_incomplete(
                args.parent,
                older_than_seconds=args.older_than_seconds,
                delete=args.delete,
            )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (SnapshotError, OSError, sqlite3.Error, ValueError, KeyError) as error:
        print(json.dumps({"decision": "FAILED", "error": str(error)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
