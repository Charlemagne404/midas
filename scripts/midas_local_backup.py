#!/usr/bin/env python3
"""Run bounded MIDAS database and Veritas-state backups into local Restic."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import midas_sqlite_snapshot
    from midas_backup_support import BackupAdmissionError, require_admitted_scope
    from midas_veritas_snapshot import SnapshotError, create_snapshot, verify_snapshot
except ModuleNotFoundError:
    from scripts import midas_sqlite_snapshot
    from scripts.midas_backup_support import BackupAdmissionError, require_admitted_scope
    from scripts.midas_veritas_snapshot import SnapshotError, create_snapshot, verify_snapshot

MIB = 1024 * 1024
FORMAT_VERSION = 1
PROJECTED_RESTIC_OVERHEAD = 2 * 1024**3
HARD_MAX_BACKUP_BYTES = 100_000_000_000


class BackupError(RuntimeError):
    """A backup precondition or operation failed closed."""


def _run_json_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BackupError(f"could not inspect mounted filesystems: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BackupError(f"filesystem inspection failed: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise BackupError("filesystem inspection returned malformed JSON") from error


def _findmnt(path: Path, selector: str) -> dict[str, str]:
    value = _run_json_command(
        [
            "findmnt",
            "--json",
            selector,
            str(path),
            "--output",
            "TARGET,SOURCE,FSTYPE,UUID,MAJ:MIN",
        ]
    )
    filesystems = value.get("filesystems")
    if not isinstance(filesystems, list) or len(filesystems) != 1:
        raise BackupError(f"could not identify exactly one filesystem for {path}")
    entry = filesystems[0]
    if not isinstance(entry, dict):
        raise BackupError(f"filesystem identity for {path} is malformed")
    return {str(key).upper(): str(item) for key, item in entry.items()}


def _physical_device(major_minor: str) -> str:
    device = Path("/sys/dev/block") / major_minor
    try:
        resolved = device.resolve(strict=True)
    except OSError as error:
        raise BackupError(f"cannot resolve physical device for {major_minor}: {error}") from error
    if (resolved / "partition").is_file():
        resolved = resolved.parent
    return resolved.name


def _ensure_real_path(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise BackupError(f"{label} must not be a symlink: {path}")
    if not path.exists():
        raise BackupError(f"{label} does not exist: {path}")
    if path.resolve(strict=True) != path.absolute():
        raise BackupError(f"{label} resolves outside its configured path: {path}")


def load_config(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BackupError(f"backup policy must be a regular file: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError(f"cannot read backup policy: {error}") from error
    if not isinstance(config, dict) or config.get("format_version") != FORMAT_VERSION:
        raise BackupError("unsupported local backup policy format")
    return config


def verify_destination(config: dict[str, Any]) -> tuple[Path, Path, dict[str, str]]:
    target = config.get("target")
    if not isinstance(target, dict):
        raise BackupError("backup target policy is missing")
    mount = Path(str(target.get("mountpoint", ""))).absolute()
    root = Path(str(target.get("root", ""))).absolute()
    if not mount.is_absolute() or not root.is_relative_to(mount) or root == mount:
        raise BackupError("backup root must be a child of the configured mountpoint")
    try:
        preferred = int(target["preferred_bytes"])
        maximum = int(target["maximum_bytes"])
        reserve = int(target["free_reserve_bytes"])
    except (KeyError, TypeError, ValueError) as error:
        raise BackupError("backup storage limits are missing or malformed") from error
    if preferred <= 0 or maximum < preferred or maximum > HARD_MAX_BACKUP_BYTES or reserve < 0:
        raise BackupError("backup storage limits exceed the approved 100 GB hard budget")
    repository_name = str(target.get("repository", "repository"))
    if repository_name in {"", ".", ".."} or Path(repository_name).name != repository_name:
        raise BackupError("repository must be a single directory name inside the backup root")
    _ensure_real_path(mount, label="backup mountpoint")
    if not os.path.ismount(mount):
        raise BackupError(f"backup mountpoint is not mounted: {mount}")
    volume = _findmnt(mount, "--mountpoint")
    primary = _findmnt(Path("/"), "--target")
    if volume.get("TARGET") != str(mount):
        raise BackupError("backup path is not the exact configured mountpoint")
    if volume.get("FSTYPE") != str(target.get("filesystem", "")):
        raise BackupError("backup filesystem type differs from policy")
    if volume.get("UUID") != str(target.get("uuid", "")):
        raise BackupError("backup partition UUID differs from policy")
    if _physical_device(volume.get("MAJ:MIN", "")) == _physical_device(primary.get("MAJ:MIN", "")):
        raise BackupError("backup mount is not on a separate physical device")
    if os.stat(mount).st_dev == os.stat("/").st_dev:
        raise BackupError("backup mount resolves to the primary filesystem")
    _ensure_real_path(root, label="dedicated backup root")
    if not root.is_dir():
        raise BackupError("dedicated backup root must already exist as a real directory")
    if os.stat(root).st_dev != os.stat(mount).st_dev:
        raise BackupError("dedicated backup root is not on the approved mounted device")
    if root.stat().st_uid != os.getuid():
        raise BackupError("dedicated backup root is not owned by the current user")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise BackupError("dedicated backup root must not grant group or other access")
    if not shutil.disk_usage(mount).free:
        raise BackupError("backup filesystem reports no free space")
    repository = root / repository_name
    if not repository.is_relative_to(root):
        raise BackupError("repository path must be inside the dedicated backup root")
    if repository.is_symlink():
        raise BackupError("repository path must not be a symlink")
    return root, repository, volume


def _allocated_bytes(root: Path) -> int:
    root_info = root.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        raise BackupError(f"backup root is not a real directory: {root}")
    total = root_info.st_blocks * 512
    for current, directories, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in directories:
            item = parent / name
            info = item.lstat()
            if not stat.S_ISDIR(info.st_mode):
                if stat.S_ISLNK(info.st_mode):
                    raise BackupError(f"symlink directory in backup destination: {item}")
                raise BackupError(f"non-directory entry in backup destination: {item}")
            total += info.st_blocks * 512
        for name in files:
            item = parent / name
            info = item.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise BackupError(f"non-regular file in backup destination: {item}")
            total += info.st_blocks * 512
    return total


def _require_budget(current: int, additional: int, maximum: int, *, reserve: int = 0) -> None:
    if min(current, additional, reserve) < 0 or maximum <= 0:
        raise BackupError("storage budget inputs must be non-negative and bounded")
    if maximum > HARD_MAX_BACKUP_BYTES:
        raise BackupError("configured backup budget exceeds the approved 100 GB hard limit")
    projected = current + additional + reserve
    if projected > maximum:
        raise BackupError(
            f"projected MIDAS backup storage {projected} exceeds hard limit {maximum} bytes"
        )


def _source_size(source: Path) -> int:
    _ensure_real_path(source, label="SQLite source")
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
        raise BackupError(f"SQLite source is not a non-empty regular file: {source}")
    total = info.st_size
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{source}{suffix}")
        if sidecar.is_symlink():
            raise BackupError(f"SQLite sidecar must not be a symlink: {sidecar}")
        if sidecar.exists():
            sidecar_info = sidecar.stat()
            if not stat.S_ISREG(sidecar_info.st_mode):
                raise BackupError(f"SQLite sidecar is not a regular file: {sidecar}")
            total += sidecar_info.st_size
    return total


def _credential_path() -> Path:
    value = os.environ.get("RESTIC_PASSWORD_FILE")
    if not value:
        credential_directory = os.environ.get("CREDENTIALS_DIRECTORY")
        if credential_directory:
            # Transient systemd services expose credentials through this
            # directory. Installed unit files set RESTIC_PASSWORD_FILE
            # explicitly; this fallback keeps one-shot recovery runs inside
            # the same systemd credential boundary.
            value = str(Path(credential_directory) / "midas-restic-password")
        else:
            raise BackupError("Restic password must be supplied as a systemd credential")
    path = Path(value)
    _ensure_real_path(path, label="Restic credential")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not info.st_size:
        raise BackupError("Restic credential must be a non-empty regular file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise BackupError("Restic credential must not grant group or other access")
    return path


def _restic(repository: Path, password: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("restic")
    if executable is None:
        raise BackupError("restic is not installed")
    environment = os.environ.copy()
    environment["RESTIC_REPOSITORY"] = str(repository)
    environment["RESTIC_PASSWORD_FILE"] = str(password)
    cache = repository.parent / "cache"
    cache.mkdir(mode=0o700, exist_ok=True)
    if cache.is_symlink() or os.stat(cache).st_dev != os.stat(repository.parent).st_dev:
        raise BackupError("Restic cache must be a real directory on the approved backup disk")
    result = subprocess.run(
        [executable, "--cache-dir", str(cache), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=6 * 60 * 60,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BackupError(f"restic {arguments[0]} failed ({result.returncode}): {detail[-1200:]}")
    return result


@contextmanager
def _repository_lock(root: Path) -> Iterator[None]:
    path = root / ".midas-backup.lock"
    if path.is_symlink():
        raise BackupError("backup lock is a symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.fstat(descriptor).st_uid != os.getuid():
            raise BackupError("backup lock is not owned by the current user")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BackupError("another MIDAS local backup operation is active") from error
        yield
    finally:
        os.close(descriptor)


def _atomic_status(root: Path, filename: str, value: dict[str, Any]) -> None:
    directory = root / "status"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or os.stat(directory).st_dev != os.stat(root).st_dev:
        raise BackupError("backup status directory is unsafe")
    destination = directory / filename
    temporary = directory / f".{filename}.{uuid.uuid4().hex}.tmp"
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        parent = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def _snapshots(repository: Path, password: Path) -> list[dict[str, Any]]:
    result = _restic(repository, password, "snapshots", "--json")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise BackupError("restic snapshots returned malformed JSON") from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise BackupError("restic snapshot inventory is malformed")
    return value


def _latest_snapshot(
    snapshots: list[dict[str, Any]], *, tag: str, hostname: str
) -> dict[str, Any] | None:
    matching = [
        snapshot
        for snapshot in snapshots
        if snapshot.get("hostname") == hostname
        and isinstance(snapshot.get("tags"), list)
        and tag in snapshot["tags"]
    ]
    return max(matching, key=lambda item: str(item.get("time", "")), default=None)


def _source_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    values = config.get("sqlite_sources", [])
    if not isinstance(values, list):
        raise BackupError("SQLite backup policy is malformed")
    sources = [item for item in values if isinstance(item, dict)]
    veritas = config.get("veritas_source_analysis")
    if veritas is not None:
        if not isinstance(veritas, dict) or not isinstance(veritas.get("name"), str):
            raise BackupError("Veritas backup policy is malformed")
        sources.append(veritas)
    if len(sources) != len(values) + (1 if veritas is not None else 0):
        raise BackupError("backup policy contains a malformed source entry")
    names = [str(item.get("name", "")) for item in sources]
    if any(
        not name
        or not name[0].isascii()
        or not name[0].isalnum()
        or any(not (char.isascii() and char.isalnum()) and char not in "_-" for char in name)
        for name in names
    ) or len(set(names)) != len(names):
        raise BackupError("backup source names must be safe, present, and unique")
    return sources


def initialize(config: dict[str, Any]) -> dict[str, Any]:
    root, repository, volume = verify_destination(config)
    password = _credential_path()
    with _repository_lock(root):
        if repository.exists():
            raise BackupError("Restic repository already exists; refusing to replace it")
        target = config["target"]
        reserve = int(target["free_reserve_bytes"])
        available = os.statvfs(Path(target["mountpoint"]))
        free_bytes = available.f_bavail * available.f_frsize
        if free_bytes < reserve:
            raise BackupError("backup filesystem is below the configured free-space reserve")
        repository.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _restic(repository, password, "init")
    return {
        "status": "INITIALIZED",
        "repository": str(repository),
        "mount_uuid": volume.get("UUID"),
    }


def _snapshot_database(
    *,
    root: Path,
    repository: Path,
    password: Path,
    config: dict[str, Any],
    source_spec: dict[str, Any],
    source: Path,
) -> dict[str, Any]:
    target = config["target"]
    name = str(source_spec["name"])
    tag = f"midas-{name}"
    raw_bytes = _source_size(source)
    maximum = int(target["maximum_bytes"])
    reserve = int(target["free_reserve_bytes"])
    current = _allocated_bytes(root)
    # Bound the worst case before touching the destination: one standalone
    # SQLite snapshot plus one full, uncompressed Restic copy of that snapshot.
    _require_budget(
        current,
        2 * raw_bytes + PROJECTED_RESTIC_OVERHEAD,
        maximum,
        reserve=reserve,
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stage = root / "staging" / f"{stamp}-{name}-{uuid.uuid4().hex[:8]}"
    stage.mkdir(mode=0o700, parents=True, exist_ok=False)
    snapshot_dir = stage / "sqlite-snapshot"
    receipt_path = stage / "sqlite-receipt.json"
    helper = Path(__file__).resolve().with_name("midas_sqlite_snapshot.py")
    python = sys.executable
    try:
        subprocess.run(
            [
                python,
                str(helper),
                "backup",
                "--source",
                str(source),
                "--destination",
                str(snapshot_dir),
                "--integrity",
                "quick",
                "--reserve-mib",
                str(int(target["snapshot_reserve_mib"])),
                "--allow-large",
                "--receipt",
                str(receipt_path),
            ],
            check=True,
            timeout=6 * 60 * 60,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        database = snapshot_dir / "database.sqlite"
        if not database.is_file() or database.is_symlink():
            raise BackupError(f"{name} SQLite snapshot was not published")
        current = _allocated_bytes(root)
        _require_budget(
            current,
            database.stat().st_size + PROJECTED_RESTIC_OVERHEAD,
            maximum,
            reserve=reserve,
        )
        backup = _restic(
            repository,
            password,
            "backup",
            "--json",
            "--host",
            os.uname().nodename,
            "--tag",
            "midas-local",
            "--tag",
            "tier1",
            "--tag",
            tag,
            str(snapshot_dir),
        )
        summary: dict[str, Any] | None = None
        for line in backup.stdout.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("message_type") == "summary":
                summary = value
        snapshot_id = summary.get("snapshot_id") if summary else None
        if not isinstance(snapshot_id, str) or len(snapshot_id) < 8:
            raise BackupError("restic backup completed without a snapshot identifier")
        recorded = _snapshots(repository, password)
        if not any(item.get("id") == snapshot_id for item in recorded):
            raise BackupError("new Restic snapshot is missing from repository inventory")
        _restic(repository, password, "check")
        manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
        value = {
            "format": "midas-local-backup-receipt",
            "format_version": FORMAT_VERSION,
            "status": "VERIFIED",
            "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_name": name,
            "source_path": str(source),
            "source_bytes": raw_bytes,
            "restic_snapshot_id": snapshot_id,
            "restic_tag": tag,
            "sqlite_snapshot_sha256": manifest["snapshot"]["sha256"],
            "sqlite_integrity": manifest["snapshot"]["integrity_result"],
            "sqlite_integrity_mode": manifest["snapshot"]["integrity_check"],
            "verification_scope": (
                "SQLite quick integrity check and Restic metadata inventory; data packs "
                "are checked separately"
            ),
            "source_schema_sha256": manifest["source"]["metadata"]["schema_sha256"],
            "mount_uuid": target["uuid"],
            "hard_budget_bytes": maximum,
            "retention": "NOT_RUN_BY_BACKUP_JOB",
        }
        _atomic_status(root, f"latest-{name}.json", value)
        shutil.rmtree(stage)
        return value
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _snapshot_veritas_analysis(
    *,
    root: Path,
    repository: Path,
    password: Path,
    config: dict[str, Any],
    source_spec: dict[str, Any],
) -> dict[str, Any]:
    target = config["target"]
    name = str(source_spec["name"])
    tag = f"midas-{name}"
    try:
        max_capture = int(source_spec["maximum_capture_bytes"])
        minimum_gap = int(source_spec.get("minimum_timer_gap_seconds", 900))
        source_root = Path(str(source_spec["root"])).absolute()
        module_root = Path(str(source_spec["module_root"])).absolute()
        script_root = Path(str(source_spec["script_root"])).absolute()
        campaign = Path(str(source_spec["campaign_path"])).absolute()
        unit_names = [str(value) for value in source_spec["systemd_units"]]
        config_paths = [
            Path(str(value)).absolute() for value in source_spec["systemd_config_paths"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise BackupError("Veritas source-analysis backup policy is incomplete") from error
    if max_capture <= 0 or max_capture > 512 * 1024**2:
        raise BackupError("Veritas capture limit must be within 512 MiB")
    if os.stat(source_root).st_dev == os.stat(root).st_dev:
        raise BackupError("Veritas source-analysis data is on the backup destination device")
    maximum = int(target["maximum_bytes"])
    reserve = int(target["free_reserve_bytes"])
    current = _allocated_bytes(root)
    overhead = PROJECTED_RESTIC_OVERHEAD
    _require_budget(current, 2 * max_capture + overhead, maximum, reserve=reserve)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stage = root / "staging" / f"{stamp}-{name}-{uuid.uuid4().hex[:8]}"
    stage.mkdir(mode=0o700, parents=True, exist_ok=False)
    snapshot_dir = stage / "veritas-snapshot"
    try:
        manifest = create_snapshot(
            source_root=source_root,
            destination=snapshot_dir,
            module_root=module_root,
            script_root=script_root,
            campaign_path=campaign,
            systemd_units=unit_names,
            systemd_config_paths=config_paths,
            minimum_timer_gap_seconds=minimum_gap,
        )
        checked = verify_snapshot(snapshot_dir)
        if checked != manifest:
            raise BackupError("Veritas snapshot verification changed its manifest")
        snapshot_bytes = _allocated_bytes(snapshot_dir)
        if snapshot_bytes > max_capture:
            raise BackupError(
                f"Veritas snapshot is {snapshot_bytes} bytes, above its {max_capture}-byte capture bound"
            )
        current = _allocated_bytes(root)
        _require_budget(current, snapshot_bytes + overhead, maximum, reserve=reserve)
        backup_result = _restic(
            repository,
            password,
            "backup",
            "--json",
            "--host",
            os.uname().nodename,
            "--tag",
            "midas-local",
            "--tag",
            "tier1",
            "--tag",
            tag,
            str(snapshot_dir),
        )
        summary: dict[str, Any] | None = None
        for line in backup_result.stdout.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("message_type") == "summary":
                summary = value
        snapshot_id = summary.get("snapshot_id") if summary else None
        if not isinstance(snapshot_id, str) or len(snapshot_id) < 8:
            raise BackupError("Restic backup completed without a Veritas snapshot identifier")
        recorded = _snapshots(repository, password)
        if not any(item.get("id") == snapshot_id for item in recorded):
            raise BackupError("new Veritas snapshot is missing from Restic inventory")
        _restic(repository, password, "check")
        value = {
            "format": "midas-local-backup-receipt",
            "format_version": FORMAT_VERSION,
            "status": "VERIFIED",
            "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_name": name,
            "source_path": str(source_root),
            "source_bytes": snapshot_bytes,
            "restic_snapshot_id": snapshot_id,
            "restic_tag": tag,
            "checkpoint_schema_versions": sorted(
                {str(item["schema_version"]) for item in manifest["checkpoints"].values()}
            ),
            "checkpoint_state_sha256": {
                filename: value["state_sha256"]
                for filename, value in manifest["checkpoints"].items()
            },
            "event_count": manifest["ledger"]["event_count"],
            "last_event_chain_sha256": manifest["ledger"]["last_chain_sha256"],
            "campaign_sha256": manifest["checkpoints"][manifest["authoritative_checkpoint"]][
                "campaign_sha256"
            ],
            "analysis_code_sha256": manifest["checkpoints"][manifest["authoritative_checkpoint"]][
                "analysis_code_sha256"
            ],
            "verification_scope": (
                "sealed checkpoint and event-chain verification before Restic capture; "
                "Restic metadata check; full restore verification remains a separate operation"
            ),
            "mount_uuid": target["uuid"],
            "hard_budget_bytes": maximum,
            "retention": "NOT_RUN_BY_BACKUP_JOB",
        }
        _atomic_status(root, f"latest-{name}.json", value)
        return value
    except SnapshotError as error:
        raise BackupError(str(error)) from error
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def backup(config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        admission = require_admitted_scope(require_backup_profile=True)
    except BackupAdmissionError as error:
        raise BackupError(str(error)) from error
    root, repository, _ = verify_destination(config)
    password = _credential_path()
    if not repository.is_dir() or repository.is_symlink():
        raise BackupError("Restic repository is not initialized")
    sources = config.get("sqlite_sources", [])
    all_sources = _source_specs(config)
    if not all_sources:
        raise BackupError("backup policy contains no Tier 1 sources")
    results: list[dict[str, Any]] = []
    with _repository_lock(root):
        try:
            # Preserve the small, irreplaceable research recovery state before
            # starting the much longer full-database snapshots.
            veritas_spec = config.get("veritas_source_analysis")
            if veritas_spec is not None:
                results.append(
                    _snapshot_veritas_analysis(
                        root=root,
                        repository=repository,
                        password=password,
                        config=config,
                        source_spec=veritas_spec,
                    )
                )
            for source_spec in sources:
                if not isinstance(source_spec, dict):
                    raise BackupError("SQLite source policy entry is malformed")
                source = Path(str(source_spec.get("path", ""))).absolute()
                if os.stat(source).st_dev == os.stat(root).st_dev:
                    raise BackupError(f"{source} is on the backup destination device")
                results.append(
                    _snapshot_database(
                        root=root,
                        repository=repository,
                        password=password,
                        config=config,
                        source_spec=source_spec,
                        source=source,
                    )
                )
            _atomic_status(
                root,
                "last-run.json",
                {
                    "status": "SUCCESS",
                    "completed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "admission": admission,
                    "sources": [result["source_name"] for result in results],
                },
            )
            return results
        except Exception as error:
            _atomic_status(
                root,
                "last-run.json",
                {
                    "status": "FAILED",
                    "failed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "admission": admission,
                    "error": str(error),
                    "verified_this_run": [result["source_name"] for result in results],
                },
            )
            raise


def verify(
    config: dict[str, Any], *, read_data_subset: str, full_read: bool = False
) -> dict[str, Any]:
    try:
        require_admitted_scope(require_heavy_profile=True)
    except BackupAdmissionError as error:
        raise BackupError(str(error)) from error
    root, repository, volume = verify_destination(config)
    password = _credential_path()
    if not repository.is_dir() or repository.is_symlink():
        raise BackupError("Restic repository is not initialized")
    with _repository_lock(root):
        snapshots = _snapshots(repository, password)
        if not snapshots:
            raise BackupError("Restic repository has no recovery snapshots")
        check_args = (
            ["check", "--read-data"]
            if full_read
            else [
                "check",
                f"--read-data-subset={read_data_subset}",
            ]
        )
        _restic(repository, password, *check_args)
        usage = _allocated_bytes(root)
        value = {
            "status": "VERIFIED",
            "verified_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "snapshot_count": len(snapshots),
            "read_data_subset": "all" if full_read else read_data_subset,
            "allocated_bytes": usage,
            "preferred_budget_bytes": int(config["target"]["preferred_bytes"]),
            "hard_budget_bytes": int(config["target"]["maximum_bytes"]),
            "mount_uuid": volume.get("UUID"),
        }
        _atomic_status(root, "last-integrity-check.json", value)
        return value


def restore_check(config: dict[str, Any], source_name: str) -> dict[str, Any]:
    """Restore one verified snapshot to a private temporary path and validate it."""
    try:
        require_admitted_scope(require_backup_profile=True)
    except BackupAdmissionError as error:
        raise BackupError(str(error)) from error
    root, repository, volume = verify_destination(config)
    password = _credential_path()
    if not repository.is_dir() or repository.is_symlink():
        raise BackupError("Restic repository is not initialized")
    sources = _source_specs(config)
    matches = [source for source in sources if source.get("name") == source_name]
    if len(matches) != 1:
        raise BackupError(f"backup policy has no unique source named {source_name!r}")
    source = matches[0]
    receipt_path = root / "status" / f"latest-{source_name}.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise BackupError(f"verified backup receipt is missing for {source_name}")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError(f"backup receipt is unreadable for {source_name}") from error
    snapshot_id = receipt.get("restic_snapshot_id")
    source_bytes = receipt.get("source_bytes")
    if (
        receipt.get("status") != "VERIFIED"
        or receipt.get("source_name") != source_name
        or receipt.get("mount_uuid") != volume.get("UUID")
        or not isinstance(snapshot_id, str)
        or not isinstance(source_bytes, int)
        or isinstance(source_bytes, bool)
        or source_bytes <= 0
    ):
        raise BackupError(f"backup receipt is not a valid recovery point for {source_name}")

    base = Path(tempfile.gettempdir())
    if base.is_symlink() or not base.is_dir():
        raise BackupError("temporary restore root is missing or unsafe")
    filesystem = os.statvfs(base)
    available = filesystem.f_bavail * filesystem.f_frsize
    reserve = int(config["target"].get("snapshot_reserve_mib", 5120)) * MIB
    if available < source_bytes + reserve:
        raise BackupError(
            f"temporary restore space is insufficient: available={available}, "
            f"required={source_bytes + reserve}"
        )

    with _repository_lock(root):
        snapshots = _snapshots(repository, password)
        recorded = next((item for item in snapshots if item.get("id") == snapshot_id), None)
        expected_tag = f"midas-{source_name}"
        if (
            recorded is None
            or not isinstance(recorded.get("tags"), list)
            or expected_tag not in recorded["tags"]
            or "tier1" not in recorded["tags"]
        ):
            raise BackupError(f"recovery snapshot is absent or mistagged for {source_name}")
        try:
            with tempfile.TemporaryDirectory(prefix="midas-restore-check-", dir=base) as name:
                restore_root = Path(name)
                _restic(
                    repository,
                    password,
                    "restore",
                    snapshot_id,
                    "--target",
                    str(restore_root),
                    "--verify",
                )
                manifests = list(restore_root.rglob("manifest.json"))
                if len(manifests) != 1 or manifests[0].is_symlink():
                    raise BackupError(
                        "Restic restore did not produce exactly one safe source manifest"
                    )
                restored_source = manifests[0].parent
                veritas_spec = config.get("veritas_source_analysis")
                if isinstance(veritas_spec, dict) and source is veritas_spec:
                    evidence = verify_snapshot(restored_source)
                    validation = {
                        "checkpoint_schemas": sorted(
                            {
                                str(item["schema_version"])
                                for item in evidence["checkpoints"].values()
                            }
                        ),
                        "event_count": evidence["ledger"]["event_count"],
                        "last_event_chain_sha256": evidence["ledger"]["last_chain_sha256"],
                    }
                else:
                    evidence = midas_sqlite_snapshot.verify_snapshot(
                        restored_source, integrity="quick"
                    )
                    validation = {
                        "database_bytes": evidence["database_bytes"],
                        "database_sha256": evidence["database_sha256"],
                        "integrity_check": evidence["integrity_check"],
                        "integrity_result": evidence["integrity_result"],
                        "schema_sha256": evidence["metadata"]["schema_sha256"],
                    }
        except (SnapshotError, midas_sqlite_snapshot.SnapshotError) as error:
            raise BackupError(
                f"restored {source_name} failed source validation: {error}"
            ) from error

    result = {
        "format": "midas-local-restore-check",
        "format_version": FORMAT_VERSION,
        "status": "RESTORED_AND_VERIFIED",
        "verified_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_name": source_name,
        "restic_snapshot_id": snapshot_id,
        "mount_uuid": volume.get("UUID"),
        "restic_restore_verify": "passed",
        "source_validation": validation,
    }
    _atomic_status(root, f"latest-restore-check-{source_name}.json", result)
    return result


def prune(config: dict[str, Any]) -> dict[str, Any]:
    try:
        require_admitted_scope(require_heavy_profile=True)
    except BackupAdmissionError as error:
        raise BackupError(str(error)) from error
    root, repository, _ = verify_destination(config)
    password = _credential_path()
    if not repository.is_dir() or repository.is_symlink():
        raise BackupError("Restic repository is not initialized")
    retention = config.get("retention", {})
    minimum = int(retention.get("minimum_snapshots_per_source", 2))
    keep_daily = int(retention.get("keep_daily", 7))
    keep_weekly = int(retention.get("keep_weekly", 4))
    if minimum < 2 or keep_daily < 1 or keep_weekly < 1:
        raise BackupError("retention policy must preserve at least two snapshots per source")
    hostname = os.uname().nodename
    sources = _source_specs(config)
    if not sources:
        raise BackupError("backup policy contains no Tier 1 sources")
    with _repository_lock(root):
        inventory = _snapshots(repository, password)
        skipped: list[str] = []
        for source in sources:
            tag = f"midas-{source['name']}"
            matching = [
                item
                for item in inventory
                if item.get("hostname") == hostname
                and isinstance(item.get("tags"), list)
                and "midas-local" in item["tags"]
                and tag in item["tags"]
            ]
            if len(matching) < minimum:
                skipped.append(tag)
                continue
            latest_receipt = root / "status" / f"latest-{source['name']}.json"
            if latest_receipt.is_symlink() or not latest_receipt.is_file():
                raise BackupError(f"refusing to prune {tag}: latest verified receipt is missing")
            receipt = json.loads(latest_receipt.read_text(encoding="utf-8"))
            if receipt.get("status") != "VERIFIED" or receipt.get("restic_snapshot_id") not in {
                item.get("id") for item in matching
            }:
                raise BackupError(
                    f"refusing to prune {tag}: latest receipt is not in the repository"
                )
        if skipped:
            result = {
                "status": "SKIPPED_NEEDS_MORE_RECOVERY_POINTS",
                "completed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "sources_with_too_few_snapshots": skipped,
                "minimum_snapshots_per_source": minimum,
            }
            _atomic_status(root, "last-prune.json", result)
            return result
        current_usage = _allocated_bytes(root)
        prune_reserve = int(retention.get("prune_working_reserve_bytes", 10 * 1024**3))
        maximum = int(config["target"]["maximum_bytes"])
        if current_usage * 2 + prune_reserve > maximum:
            result = {
                "status": "SKIPPED_INSUFFICIENT_PRUNE_HEADROOM",
                "completed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "allocated_bytes": current_usage,
                "projected_working_bytes": current_usage * 2 + prune_reserve,
                "hard_budget_bytes": maximum,
            }
            _atomic_status(root, "last-prune.json", result)
            return result
        # Read a bounded, distributed subset before removing old snapshot refs.
        _restic(repository, password, "check", "--read-data-subset=1/32")
        for source in sources:
            tag = f"midas-{source['name']}"
            _restic(
                repository,
                password,
                "forget",
                "--group-by",
                "host,tags",
                "--host",
                hostname,
                "--tag",
                tag,
                "--keep-daily",
                str(keep_daily),
                "--keep-weekly",
                str(keep_weekly),
                "--keep-last",
                str(minimum),
                "--prune",
            )
        _atomic_status(
            root,
            "last-integrity-check.json",
            {
                "status": "VERIFIED",
                "verified_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "snapshot_count": len(inventory),
                "read_data_subset": "1/32",
                "allocated_bytes": _allocated_bytes(root),
                "mount_uuid": config["target"]["uuid"],
                "operation": "pre-prune-subset-check",
            },
        )
        usage = _allocated_bytes(root)
        maximum = int(config["target"]["maximum_bytes"])
        if usage > maximum:
            raise BackupError("repository exceeded its hard storage budget after pruning")
        result = {
            "status": "PRUNED",
            "completed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "allocated_bytes": usage,
            "preferred_budget_bytes": int(config["target"]["preferred_bytes"]),
            "hard_budget_bytes": maximum,
            "minimum_snapshots_per_source": minimum,
            "keep_daily": keep_daily,
            "keep_weekly": keep_weekly,
        }
        _atomic_status(root, "last-prune.json", result)
        return result


def status(config: dict[str, Any]) -> dict[str, Any]:
    root, repository, volume = verify_destination(config)
    target = config["target"]
    usage = _allocated_bytes(root)
    repository_initialized = repository.is_dir() and not repository.is_symlink()
    expected_sources = [str(item["name"]) for item in _source_specs(config)]
    records: dict[str, Any] = {}
    known_snapshots: set[str] = set()
    repository_readable = False
    repository_error: str | None = None
    if repository_initialized:
        try:
            known_snapshots = {
                str(item.get("id"))
                for item in _snapshots(repository, _credential_path())
                if item.get("id")
            }
            repository_readable = True
        except (BackupError, OSError) as error:
            repository_error = str(error)
    now = time.time()
    for name in expected_sources:
        path = root / "status" / f"latest-{name}.json"
        if path.is_symlink() or not path.is_file():
            records[name] = {"state": "missing"}
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(str(value["created_at_utc"]).replace("Z", "+00:00"))
        age = max(0, int(now - created.timestamp()))
        snapshot_id = value.get("restic_snapshot_id")
        records[name] = {
            "state": (
                "fresh"
                if value.get("status") == "VERIFIED"
                and age <= 8 * 86400
                and snapshot_id in known_snapshots
                else "stale"
            ),
            "age_seconds": age,
            "restic_snapshot_id": snapshot_id,
        }
    integrity_path = root / "status" / "last-integrity-check.json"
    integrity: dict[str, Any] = {"state": "missing"}
    if integrity_path.is_file() and not integrity_path.is_symlink():
        try:
            check = json.loads(integrity_path.read_text(encoding="utf-8"))
            checked_at = datetime.fromisoformat(
                str(check["verified_at_utc"]).replace("Z", "+00:00")
            )
            age = max(0, int(now - checked_at.timestamp()))
            recent = (
                check.get("status") == "VERIFIED"
                and check.get("mount_uuid") == target.get("uuid")
                and int(check.get("snapshot_count", 0)) > 0
                and check.get("read_data_subset") in {"all", "1/32"}
                and age <= 35 * 86400
            )
            integrity = {
                "state": "fresh" if recent else "stale",
                "age_seconds": age,
                "read_data_subset": check.get("read_data_subset"),
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            integrity = {"state": "invalid"}
    return {
        "status": (
            "READY"
            if repository_initialized
            and repository_readable
            and usage <= int(target["maximum_bytes"])
            and all(item.get("state") == "fresh" for item in records.values())
            and integrity.get("state") == "fresh"
            else "STALE_OR_MISSING"
        ),
        "mount_uuid": volume.get("UUID"),
        "repository_initialized": repository_initialized,
        "repository_readable": repository_readable,
        "repository_error": repository_error,
        "allocated_bytes": usage,
        "integrity_check": integrity,
        "preferred_budget_bytes": int(target["preferred_bytes"]),
        "hard_budget_bytes": int(target["maximum_bytes"]),
        "sources": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("check-destination", help="read-only verification of the backup disk")
    commands.add_parser("init", help="initialize a new empty Restic repository")
    commands.add_parser("backup", help="snapshot configured Tier 1 databases and Veritas state")
    restore_parser = commands.add_parser(
        "restore-check", help="restore one Tier 1 snapshot privately and verify its contents"
    )
    restore_parser.add_argument("--source-name", required=True)
    verify_parser = commands.add_parser("verify", help="check repository integrity")
    verify_parser.add_argument("--read-data-subset", default="1/32")
    verify_parser.add_argument(
        "--full", action="store_true", help="read and verify every stored data pack"
    )
    commands.add_parser("prune", help="verify recovery points, then apply bounded retention")
    commands.add_parser("status", help="show current recovery-point freshness and storage")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.action == "check-destination":
            root, repository, volume = verify_destination(config)
            result: Any = {
                "status": "READY",
                "backup_root": str(root),
                "repository": str(repository),
                "mount_uuid": volume.get("UUID"),
                "allocated_bytes": _allocated_bytes(root),
                "hard_budget_bytes": int(config["target"]["maximum_bytes"]),
            }
        elif args.action == "init":
            result = initialize(config)
        elif args.action == "backup":
            result = backup(config)
        elif args.action == "restore-check":
            result = restore_check(config, args.source_name)
        elif args.action == "verify":
            result = verify(
                config,
                read_data_subset=args.read_data_subset,
                full_read=args.full,
            )
        elif args.action == "prune":
            result = prune(config)
        else:
            result = status(config)
        print(json.dumps(result, sort_keys=True, indent=2))
        if args.action == "status" and result["status"] != "READY":
            return 2
        return 0
    except (BackupError, BackupAdmissionError, OSError, ValueError, KeyError) as error:
        print(f"midas-local-backup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
