"""Copy a pinned Veritas snapshot set and rebuild both v6 catalogs offline.

This tool reads only finalized ``snapshots/scan-*.json.gz`` evidence from the
source root. It copies those files into a new mission-owned directory, then
rebuilds the snapshot and independent-analysis catalogs in bounded batches.
It makes no public requests and never writes to the source root.

The command uses the same host/Reality admission checks as the isolated Reality
validation workers. Run it under a transient user systemd scope with a bounded
memory and CPU policy for additional containment. Interrupted copies and
catalog rebuilds can resume from their durable state with ``--resume``.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import resource
import sqlite3
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from midas.veritas import analysis_catalog, scan_catalog
from midas.veritas.continuous_analysis import (
    MAX_ANALYSIS_EVENT_BYTES,
    MAX_ANALYSIS_SUMMARY_BYTES,
    rebuild_analysis_catalog,
)
from midas.veritas.continuous_analysis import (
    VERSION as ANALYSIS_VERSION,
)

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
STATE_NAME = "veritas-v6-offline-replay-state.json"
INPUT_MANIFEST_NAME = "veritas-v6-source-snapshot-manifest.json"
RECEIPT_NAME = "veritas-v6-offline-replay-receipt.json"
VERIFICATION_NAME = "veritas-v6-offline-replay-postrun-verification.json"
MAX_SNAPSHOT_BYTES = 48 * 1024**2
MAX_SNAPSHOT_COUNT = 100_000
DEFAULT_MAX_SOURCE_BYTES = 4 * 1024**3
COPY_CHUNK_BYTES = 1024 * 1024
ADMISSION_CHECK_BYTES = 32 * 1024**2
DEFAULT_COPY_RATE_BYTES_PER_SECOND = 2 * 1024**2
COPIED_PHASES = {"CATALOGS", "SNAPSHOT_CATALOG", "ANALYSIS_CATALOG", "VERIFYING", "COMPLETE"}
PROTECTED_DATA_ROOTS = tuple(
    (Path.home() / name / "data").resolve() for name in ("midas", "midas-reality", "midas-veritas")
)


class ReplayError(RuntimeError):
    """A safety, identity, or completeness check failed."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(COPY_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_code_identity() -> dict[str, Any]:
    package_root = Path(analysis_catalog.__file__).resolve().parent
    source_files = []
    for path in sorted(package_root.rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ReplayError(f"Candidate Veritas source is not a regular file: {path}")
        source_files.append(
            {"path": path.relative_to(package_root).as_posix(), "sha256": sha256_file(path)}
        )
    manifest = {
        "package_root": str(package_root),
        "source_files": source_files,
        "replay_script_sha256": sha256_file(Path(__file__).resolve()),
    }
    manifest["source_manifest_sha256"] = sha256_bytes(canonical(manifest))
    return manifest


def _process_cgroup_metrics() -> dict[str, Any]:
    try:
        entry = next(
            line
            for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        )
        root = Path("/sys/fs/cgroup")
        group = root / entry.partition("::")[2].lstrip("/")
        if not group.resolve().is_relative_to(root.resolve()):
            return {"available": False, "reason": "cgroup_path_outside_root"}
        metrics: dict[str, Any] = {"available": True, "path": entry.partition("::")[2]}
        for name in ("memory.current", "memory.peak", "memory.events", "cpu.stat", "io.stat"):
            path = group / name
            if path.is_file():
                metrics[name] = path.read_text().strip()
        return metrics
    except (OSError, StopIteration):
        return {"available": False, "reason": "cgroup_telemetry_unavailable"}


def _postrun_verification_document(
    receipt: dict[str, Any], candidate_code_identity: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    original_code = receipt.get("candidate_code", {})
    package_matches = original_code.get("package_root") == candidate_code_identity.get(
        "package_root"
    ) and original_code.get("source_files") == candidate_code_identity.get("source_files")
    if not package_matches:
        raise ReplayError("Current verifier package sources differ from the completed replay")
    package_manifest = {
        "package_root": candidate_code_identity["package_root"],
        "source_files": candidate_code_identity["source_files"],
    }
    catalogs = receipt.get("catalogs", {})
    events = receipt.get("analysis_event_manifest", {})
    summary = receipt.get("published_summary", {})
    document = {
        "schema_version": 1,
        "status": "COMPLETED_OUTPUTS_REVERIFIED",
        "verified_at_ns": time.time_ns(),
        "network_requests": 0,
        "source_snapshot_manifest_sha256": receipt.get("source_snapshot_manifest_sha256"),
        "source_snapshot_count": receipt.get("source_snapshot_count"),
        "source_snapshot_bytes": receipt.get("source_snapshot_bytes"),
        "original_replay_receipt_sha256": sha256_bytes(canonical(receipt)),
        "original_replay_driver_sha256": original_code.get("replay_script_sha256"),
        "current_verifier_driver_sha256": candidate_code_identity.get("replay_script_sha256"),
        "package_source_files_match": True,
        "package_source_manifest_sha256": sha256_bytes(canonical(package_manifest)),
        "current_verifier_source_manifest_sha256": candidate_code_identity.get(
            "source_manifest_sha256"
        ),
        "catalogs": {
            "snapshot_catalog_version": catalogs.get("snapshot_catalog_version"),
            "snapshot_catalog_indexed": catalogs.get("snapshot_catalog_indexed"),
            "snapshot_catalog_quarantined": catalogs.get("snapshot_catalog_quarantined"),
            "snapshot_catalog_integrity_issues": catalogs.get("snapshot_catalog_integrity_issues"),
            "snapshot_catalog_sha256": catalogs.get("snapshot_catalog_sha256"),
            "analysis_catalog_version": catalogs.get("analysis_catalog_version"),
            "analysis_processed": catalogs.get("analysis_processed"),
            "analysis_quarantined": catalogs.get("analysis_quarantined"),
            "analysis_catalog_sha256": catalogs.get("analysis_catalog_sha256"),
        },
        "analysis_event_count": events.get("event_count"),
        "analysis_event_file_manifest_sha256": events.get("event_file_manifest_sha256"),
        "published_summary_sha256": summary.get("sha256"),
        "copy_checkpoint_reconciliation": state.get("copy_checkpoint_reconciled"),
        "resource_snapshot": _process_cgroup_metrics(),
    }
    document["verification_sha256"] = sha256_bytes(canonical(document))
    return document


def atomic_json(path: Path, value: Any) -> None:
    if path.is_symlink():
        raise ReplayError(f"Refusing to replace symlink: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.is_symlink():
        raise ReplayError(f"Refusing symlinked temporary file: {temporary}")
    data = canonical(value) + b"\n"
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _stat_identity(path: Path) -> dict[str, int]:
    info = path.stat(follow_symlinks=False)
    if not path.is_file() or path.is_symlink():
        raise ReplayError(f"Snapshot is not a regular file: {path.name}")
    return {
        "bytes": info.st_size,
        "device": info.st_dev,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
    }


def capture_snapshot_inventory(source_root: Path, *, max_source_bytes: int) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve(strict=True)
    snapshots = source_root / "snapshots"
    if source_root.is_symlink() or snapshots.is_symlink() or not snapshots.is_dir():
        raise ReplayError("Source snapshot directory is missing or unsafe")
    files = []
    total_bytes = 0
    with os.scandir(snapshots) as entries:
        for entry in entries:
            if not (entry.name.startswith("scan-") and entry.name.endswith(".json.gz")):
                continue
            if not re.fullmatch(r"scan-[A-Za-z0-9._-]{1,160}\.json\.gz", entry.name):
                raise ReplayError(
                    f"Snapshot filename is outside the accepted identity format: {entry.name}"
                )
            path = Path(entry.path)
            identity = _stat_identity(path)
            if not 1 <= identity["bytes"] <= MAX_SNAPSHOT_BYTES:
                raise ReplayError(f"Snapshot size is outside the accepted bound: {entry.name}")
            total_bytes += identity["bytes"]
            if total_bytes > max_source_bytes:
                raise ReplayError(
                    f"Pinned snapshots exceed the explicit source-byte budget: {total_bytes}"
                )
            files.append({"name": entry.name, **identity})
            if len(files) > MAX_SNAPSHOT_COUNT:
                raise ReplayError("Pinned snapshot count exceeds the metadata bound")
    files.sort(key=lambda item: item["name"])
    if not files:
        raise ReplayError("No finalized Veritas snapshots were found")
    manifest = {
        "schema_version": 1,
        "captured_ns": time.time_ns(),
        "source_root": str(source_root),
        "snapshot_directory": "snapshots",
        "snapshot_count": len(files),
        "snapshot_bytes": total_bytes,
        "file_identity_basis": "sorted finalized filename, device, inode, size, mtime_ns, ctime_ns",
        "files": files,
    }
    manifest["inventory_sha256"] = sha256_bytes(canonical(manifest))
    return manifest


def _validate_output_path(source_root: Path, output_root: Path) -> tuple[Path, Path]:
    source_root = source_root.expanduser()
    output_root = output_root.expanduser()
    if source_root.is_symlink():
        raise ReplayError("Source root cannot be a symlink")
    if output_root.is_symlink():
        raise ReplayError("Output root cannot be a symlink")
    source_root = source_root.resolve(strict=True)
    output_root = output_root.resolve()
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ReplayError("Output root cannot be inside the source research store")
    if source_root.is_relative_to(output_root):
        raise ReplayError("Output root cannot contain the source research store")
    for protected in PROTECTED_DATA_ROOTS:
        if output_root == protected or output_root.is_relative_to(protected):
            raise ReplayError("Output root cannot be inside a protected MIDAS data root")
    return source_root, output_root


def _read_state(output_root: Path) -> dict[str, Any]:
    state_path = output_root / STATE_NAME
    if state_path.is_symlink() or not state_path.is_file():
        raise ReplayError("Resume state is missing or unsafe")
    if state_path.stat().st_size > 32 * 1024**2:
        raise ReplayError("Resume state exceeds its metadata bound")
    try:
        state = json.loads(state_path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError("Resume state is unreadable") from error
    if state.get("schema_version") != 1:
        raise ReplayError("Resume state schema version mismatch")
    return state


def _checkpoint_admission_check(
    output_root: Path, state_path: Path, admission_check: Callable[[], Any]
) -> Any:
    try:
        return admission_check()
    except (ValueError, ReplayError) as error:
        if state_path.is_file() and not state_path.is_symlink():
            try:
                state = _read_state(output_root)
                rejections = state.setdefault("admission_rejections", [])
                if not isinstance(rejections, list):
                    rejections = []
                rejections.append(
                    {
                        "phase": state.get("phase"),
                        "reason": str(error),
                        "sampled_ns": time.time_ns(),
                    }
                )
                state["admission_rejections"] = rejections[-20:]
                state["updated_ns"] = time.time_ns()
                atomic_json(state_path, state)
            except (OSError, ReplayError, json.JSONDecodeError):
                pass
        raise


def _verify_pinned_source(path: Path, expected: dict[str, Any]) -> None:
    actual = _stat_identity(path)
    if actual != {key: expected[key] for key in actual}:
        raise ReplayError(f"Pinned source snapshot identity changed: {path.name}")


def copy_snapshot_set(
    source_root: Path,
    output_root: Path,
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    copy_rate_bytes_per_second: int = DEFAULT_COPY_RATE_BYTES_PER_SECOND,
    resume: bool = False,
    admit: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Copy or resume a checksummed finalized snapshot set in a new output root."""
    if copy_rate_bytes_per_second <= 0:
        raise ReplayError("Snapshot copy rate must be positive")
    source_root, output_root = _validate_output_path(source_root, output_root)
    snapshots = source_root / "snapshots"
    output_snapshots = output_root / "snapshots"
    state_path = output_root / STATE_NAME
    if not resume:
        if output_root.exists():
            raise ReplayError("New replay output must not already exist; use --resume")
        inventory = capture_snapshot_inventory(source_root, max_source_bytes=max_source_bytes)
        _ensure_output_capacity(output_root.parent, inventory)
        output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        output_snapshots.mkdir(mode=0o700)
        state = {
            "schema_version": 1,
            "phase": "COPYING",
            "source_root": str(source_root),
            "source_inventory": inventory,
            "completed_files": {},
            "in_progress_file": None,
            "started_ns": time.time_ns(),
            "updated_ns": time.time_ns(),
            "max_source_bytes": max_source_bytes,
            "copy_rate_bytes_per_second": copy_rate_bytes_per_second,
        }
        atomic_json(state_path, state)
    else:
        if not output_root.is_dir() or output_root.is_symlink() or not output_snapshots.is_dir():
            raise ReplayError("Resume output root or snapshots directory is missing or unsafe")
        state = _read_state(output_root)
        if state.get("source_root") != str(source_root):
            raise ReplayError("Resume source path differs from the pinned source root")
        inventory = state.get("source_inventory")
        if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
            raise ReplayError("Pinned source inventory is missing or invalid")
        if int(inventory.get("snapshot_bytes", 0)) > max_source_bytes:
            raise ReplayError("Pinned source inventory exceeds the current explicit byte budget")
        stored_copy_rate = state.get("copy_rate_bytes_per_second")
        if stored_copy_rate is not None and stored_copy_rate != copy_rate_bytes_per_second:
            raise ReplayError("Resume copy rate differs from the durable replay configuration")
        state["copy_rate_bytes_per_second"] = copy_rate_bytes_per_second
        state["updated_ns"] = time.time_ns()
        atomic_json(state_path, state)
        recorded_hash = inventory.get("inventory_sha256")
        unsigned = {key: value for key, value in inventory.items() if key != "inventory_sha256"}
        if recorded_hash != sha256_bytes(canonical(unsigned)):
            raise ReplayError("Pinned source inventory checksum mismatch")
        if state.get("phase") in COPIED_PHASES:
            manifest_path = output_root / INPUT_MANIFEST_NAME
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise ReplayError("Completed snapshot copy is missing its source manifest")
            if manifest_path.stat().st_size > 32 * 1024**2:
                raise ReplayError("Copied source manifest exceeds its metadata bound")
            copied_manifest = json.loads(manifest_path.read_bytes())
            if not isinstance(copied_manifest, dict):
                raise ReplayError("Copied source manifest is not an object")
            recorded_manifest_hash = copied_manifest.get("manifest_sha256")
            unsigned_manifest = {
                key: value for key, value in copied_manifest.items() if key != "manifest_sha256"
            }
            if recorded_manifest_hash != sha256_bytes(canonical(unsigned_manifest)):
                raise ReplayError("Copied source manifest checksum mismatch")
            if recorded_manifest_hash != state.get("copied_manifest_sha256"):
                raise ReplayError("Copied source manifest differs from durable replay state")
            if copied_manifest.get("source_inventory_sha256") != recorded_hash:
                raise ReplayError("Copied source manifest refers to a different pinned inventory")
            _verify_copied_manifest(output_root, copied_manifest, inventory, admit=admit)
            return copied_manifest

    if state.get("phase") != "COPYING":
        raise ReplayError(f"Cannot resume snapshot copy from phase {state.get('phase')!r}")
    pinned_files = inventory["files"]
    completed = state.get("completed_files")
    if not isinstance(completed, dict):
        raise ReplayError("Snapshot copy progress is malformed")

    allowed_partial = state.get("in_progress_file")
    for entry in os.scandir(output_snapshots):
        path = Path(entry.path)
        if entry.name.endswith(".copying"):
            if (
                entry.name != f"{allowed_partial}.copying"
                or path.is_symlink()
                or not path.is_file()
            ):
                raise ReplayError(f"Unidentified partial snapshot in output: {entry.name}")
        elif entry.name not in completed:
            raise ReplayError(f"Unidentified snapshot in output: {entry.name}")

    for index, info in enumerate(pinned_files, start=1):
        name = info["name"]
        source = snapshots / name
        target = output_snapshots / name
        if source.parent != snapshots or target.parent != output_snapshots:
            raise ReplayError("Snapshot path escaped its pinned directory")
        if index % 25 == 1 and admit is not None:
            admit()
        _verify_pinned_source(source, info)
        if name in completed:
            if (
                target.is_symlink()
                or not target.is_file()
                or sha256_file(target) != completed[name]
            ):
                raise ReplayError(f"Previously copied snapshot checksum mismatch: {name}")
            continue
        if admit is not None:
            admit()
        temporary = target.with_name(target.name + ".copying")
        if temporary.is_symlink():
            raise ReplayError(f"Refusing symlinked partial snapshot: {temporary.name}")
        state["in_progress_file"] = name
        state["updated_ns"] = time.time_ns()
        atomic_json(state_path, state)
        source_hash = hashlib.sha256()
        copied_bytes = 0
        copy_started = time.monotonic()
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        source_stat = os.fstat(source_fd)
        if (
            source_stat.st_dev != info["device"]
            or source_stat.st_ino != info["inode"]
            or source_stat.st_size != info["bytes"]
            or source_stat.st_mtime_ns != info["mtime_ns"]
            or source_stat.st_ctime_ns != info["ctime_ns"]
        ):
            os.close(source_fd)
            raise ReplayError(f"Pinned source snapshot changed before open: {name}")
        try:
            temporary_fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
            )
        except BaseException:
            os.close(source_fd)
            raise
        with os.fdopen(source_fd, "rb") as incoming, os.fdopen(temporary_fd, "wb") as outgoing:
            while chunk := incoming.read(COPY_CHUNK_BYTES):
                outgoing.write(chunk)
                source_hash.update(chunk)
                copied_bytes += len(chunk)
                if copied_bytes % ADMISSION_CHECK_BYTES < len(chunk) and admit is not None:
                    admit()
            outgoing.flush()
            os.fsync(outgoing.fileno())
        _verify_pinned_source(source, info)
        digest = source_hash.hexdigest()
        if copied_bytes != info["bytes"]:
            raise ReplayError(f"Snapshot copy failed byte-count validation: {name}")
        remaining_delay = copied_bytes / copy_rate_bytes_per_second - (
            time.monotonic() - copy_started
        )
        if remaining_delay > 0:
            time.sleep(remaining_delay)
            if admit is not None:
                admit()
        _verify_pinned_source(source, info)
        os.replace(temporary, target)
        directory_fd = os.open(output_snapshots, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        completed[name] = digest
        state["completed_files"] = completed
        state["in_progress_file"] = None
        state["updated_ns"] = time.time_ns()
        atomic_json(state_path, state)
        if index % 25 == 0:
            print(f"copied {index}/{len(pinned_files)} finalized snapshots", flush=True)

    if len(completed) != len(pinned_files):
        raise ReplayError("Copied snapshot count differs from the pinned input set")
    copied_files = []
    for index, info in enumerate(pinned_files, start=1):
        if index % 25 == 1 and admit is not None:
            admit()
        digest = completed[info["name"]]
        copied_files.append({"name": info["name"], "bytes": info["bytes"], "sha256": digest})
        if sha256_file(output_snapshots / info["name"]) != digest:
            raise ReplayError(f"Final copied snapshot checksum mismatch: {info['name']}")
    expected_names = {item["name"] for item in pinned_files}
    observed_names = {entry.name for entry in os.scandir(output_snapshots)}
    if observed_names != expected_names:
        raise ReplayError("Output snapshot directory does not match the pinned input set")
    source_manifest = {
        "schema_version": 1,
        "source_inventory_sha256": inventory["inventory_sha256"],
        "source_root": str(source_root),
        "captured_ns": inventory["captured_ns"],
        "snapshot_count": len(copied_files),
        "snapshot_bytes": sum(item["bytes"] for item in copied_files),
        "files": copied_files,
    }
    source_manifest["manifest_sha256"] = sha256_bytes(canonical(source_manifest))
    atomic_json(output_root / INPUT_MANIFEST_NAME, source_manifest)
    state["phase"] = "CATALOGS"
    state["copied_manifest_sha256"] = source_manifest["manifest_sha256"]
    state["updated_ns"] = time.time_ns()
    atomic_json(state_path, state)
    return source_manifest


def _verify_copied_manifest(
    output_root: Path,
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    *,
    admit: Callable[[], Any] | None = None,
) -> None:
    """Re-hash every copied input before resuming from a catalog phase."""
    files = manifest.get("files")
    pinned = inventory.get("files")
    if not isinstance(files, list) or not isinstance(pinned, list) or len(files) != len(pinned):
        raise ReplayError("Copied snapshot manifest does not match the pinned inventory count")
    if (
        manifest.get("snapshot_count") != len(files)
        or manifest.get("snapshot_bytes") != sum(int(item.get("bytes", -1)) for item in files)
        or manifest.get("source_root") != inventory.get("source_root")
        or manifest.get("source_inventory_sha256") != inventory.get("inventory_sha256")
    ):
        raise ReplayError("Copied snapshot manifest totals or source identity are inconsistent")
    expected_names: set[str] = set()
    for index, (copied, source) in enumerate(zip(files, pinned, strict=True), start=1):
        if index % 25 == 1 and admit is not None:
            admit()
        if (
            not isinstance(copied, dict)
            or copied.get("name") != source.get("name")
            or copied.get("bytes") != source.get("bytes")
            or not re.fullmatch(r"[0-9a-f]{64}", str(copied.get("sha256", "")))
        ):
            raise ReplayError("Copied snapshot manifest differs from its pinned source inventory")
        name = str(copied["name"])
        target = output_root / "snapshots" / name
        if (
            target.parent != output_root / "snapshots"
            or target.is_symlink()
            or not target.is_file()
        ):
            raise ReplayError(f"Copied snapshot is missing or unsafe: {name}")
        if target.stat().st_size != copied["bytes"] or sha256_file(target) != copied["sha256"]:
            raise ReplayError(f"Copied snapshot checksum mismatch: {name}")
        expected_names.add(name)
    observed_names = {entry.name for entry in os.scandir(output_root / "snapshots")}
    if observed_names != expected_names:
        raise ReplayError("Copied snapshot directory differs from its pinned manifest")


def _quick_check(database: Path) -> str:
    if database.is_symlink() or not database.is_file():
        raise ReplayError(f"Expected SQLite catalog is missing or unsafe: {database.name}")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=5.0)
    try:
        row = connection.execute("PRAGMA quick_check").fetchone()
        result = str(row[0]) if row else "missing"
    finally:
        connection.close()
    if result != "ok":
        raise ReplayError(f"SQLite quick_check failed for {database.name}: {result}")
    return result


def _catalog_counts(root: Path, expected_snapshot_count: int) -> dict[str, Any]:
    scan_path = root / scan_catalog.CATALOG_NAME
    analysis_path = root / analysis_catalog.ANALYSIS_CATALOG_NAME
    _quick_check(scan_path)
    _quick_check(analysis_path)
    scan_db = sqlite3.connect(f"file:{scan_path}?mode=ro", uri=True, timeout=5.0)
    analysis_db = sqlite3.connect(f"file:{analysis_path}?mode=ro", uri=True, timeout=5.0)
    try:
        scan_version = scan_db.execute(
            "SELECT value FROM catalog_meta WHERE key='catalog_version'"
        ).fetchone()
        scan_indexed = scan_db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        scan_quarantined = scan_db.execute("SELECT COUNT(*) FROM quarantines").fetchone()[0]
        scan_issues = scan_db.execute(
            "SELECT COUNT(*) FROM integrity_issues WHERE status != 'CURRENT'"
        ).fetchone()[0]
        scan_quarantine_rows = {
            str(row[0]): str(row[1])
            for row in scan_db.execute("SELECT scan_id, snapshot_file_sha256 FROM quarantines")
        }
        analysis_version = analysis_db.execute(
            "SELECT value FROM catalog_meta WHERE key='catalog_version'"
        ).fetchone()
        analysis_processed = analysis_db.execute("SELECT COUNT(*) FROM analysis_events").fetchone()[
            0
        ]
        analysis_quarantined = analysis_db.execute("SELECT COUNT(*) FROM quarantines").fetchone()[0]
        analysis_quarantine_rows = {
            str(row[0]): str(row[1])
            for row in analysis_db.execute("SELECT scan_id, snapshot_sha256 FROM quarantines")
        }
        analysis_artifact_rows = {
            str(row[0]): {
                "snapshot_sha256": str(row[1]),
                "event_sha256": str(row[2]),
                "event_file": str(row[3]),
            }
            for row in analysis_db.execute(
                "SELECT scan_id, snapshot_sha256, event_sha256, event_file FROM analysis_events"
            )
        }
        catalog_rows = {
            str(row[0]): str(row[1])
            for row in scan_db.execute("SELECT scan_id, snapshot_file_sha256 FROM scans")
        }
        analysis_rows = {
            str(row[0]): str(row[1])
            for row in analysis_db.execute("SELECT scan_id, snapshot_sha256 FROM analysis_events")
        }
    finally:
        scan_db.close()
        analysis_db.close()
    if int(scan_indexed) + int(scan_quarantined) != expected_snapshot_count:
        raise ReplayError("Snapshot catalog indexed plus quarantined count differs from input set")
    if int(analysis_processed) + int(analysis_quarantined) != expected_snapshot_count:
        raise ReplayError(
            "Analysis catalog processed plus quarantined count differs from input set"
        )
    if int(scan_issues) != 0:
        raise ReplayError("Snapshot catalog integrity audit found non-current entries")
    return {
        "snapshot_catalog_version": int(scan_version[0]) if scan_version else None,
        "snapshot_catalog_indexed": int(scan_indexed),
        "snapshot_catalog_quarantined": int(scan_quarantined),
        "snapshot_catalog_integrity_issues": int(scan_issues),
        "analysis_catalog_version": int(analysis_version[0]) if analysis_version else None,
        "analysis_processed": int(analysis_processed),
        "analysis_quarantined": int(analysis_quarantined),
        "snapshot_catalog_rows": catalog_rows,
        "snapshot_catalog_quarantine_rows": scan_quarantine_rows,
        "analysis_catalog_rows": analysis_rows,
        "analysis_quarantine_rows": analysis_quarantine_rows,
        "analysis_artifact_rows": analysis_artifact_rows,
        "snapshot_catalog_sha256": sha256_file(scan_path),
        "analysis_catalog_sha256": sha256_file(analysis_path),
        "snapshot_catalog_quick_check": "ok",
        "analysis_catalog_quick_check": "ok",
    }


def _verify_catalog_lineage(manifest: dict[str, Any], counts: dict[str, Any]) -> None:
    expected = {item["name"].removesuffix(".json.gz"): item["sha256"] for item in manifest["files"]}
    scan_rows = counts["snapshot_catalog_rows"]
    scan_quarantines = counts["snapshot_catalog_quarantine_rows"]
    analysis_rows = counts["analysis_catalog_rows"]
    analysis_quarantines = counts["analysis_quarantine_rows"]
    analysis_artifacts = counts["analysis_artifact_rows"]
    if any(expected.get(scan_id) != digest for scan_id, digest in scan_rows.items()):
        raise ReplayError("Snapshot catalog contains a missing or mismatched snapshot identity")
    if any(expected.get(scan_id) != digest for scan_id, digest in scan_quarantines.items()):
        raise ReplayError("Snapshot catalog quarantine has a missing or mismatched identity")
    if any(expected.get(scan_id) != digest for scan_id, digest in analysis_rows.items()):
        raise ReplayError("Analysis catalog contains a missing or mismatched snapshot identity")
    if any(expected.get(scan_id) != digest for scan_id, digest in analysis_quarantines.items()):
        raise ReplayError("Analysis quarantine has a missing or mismatched identity")
    if set(scan_rows) | set(scan_quarantines) != set(expected):
        raise ReplayError("Snapshot catalog does not exactly cover the pinned input identities")
    if set(analysis_rows) | set(analysis_quarantines) != set(expected):
        raise ReplayError("Analysis catalog does not exactly cover the pinned input identities")
    if set(scan_rows) & set(scan_quarantines) or set(analysis_rows) & set(analysis_quarantines):
        raise ReplayError("A pinned snapshot is both indexed and quarantined")
    if set(scan_rows) - set(expected) or set(analysis_rows) - set(expected):
        raise ReplayError("A catalog row is outside the pinned snapshot set")
    if set(analysis_artifacts) != set(analysis_rows):
        raise ReplayError("Analysis event artifacts do not match indexed catalog rows")
    if any(
        analysis_artifacts[scan_id]["snapshot_sha256"] != digest
        for scan_id, digest in analysis_rows.items()
    ):
        raise ReplayError("Analysis event artifact refers to a different source snapshot")


def _verify_analysis_event_artifacts(root: Path, counts: dict[str, Any]) -> dict[str, Any]:
    artifacts = counts["analysis_artifact_rows"]
    event_hashes: list[dict[str, str]] = []
    expected_directory = analysis_catalog.ANALYSIS_EVENTS_DIRECTORY
    for scan_id, metadata in sorted(artifacts.items()):
        expected_relative = f"analysis-events/{expected_directory}/{scan_id}.json"
        if metadata["event_file"] != expected_relative:
            raise ReplayError(
                f"Analysis catalog event path differs from v6 evidence layout: {scan_id}"
            )
        directory = root / "analysis-events" / expected_directory
        path = root / expected_relative
        if (root / "analysis-events").is_symlink() or directory.is_symlink():
            raise ReplayError("Analysis event directory contains a symlink")
        if path.is_symlink() or not path.is_file():
            raise ReplayError(f"Analysis event file is missing or unsafe: {scan_id}")
        if path.stat().st_size > MAX_ANALYSIS_EVENT_BYTES:
            raise ReplayError(f"Analysis event exceeds its reader bound: {scan_id}")
        raw = path.read_bytes()
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ReplayError(f"Analysis event is not valid JSON: {scan_id}") from error
        if not isinstance(event, dict):
            raise ReplayError(f"Analysis event is not an object: {scan_id}")
        event_material = dict(event)
        stored_digest = event_material.pop("analysis_event_sha256", None)
        digest = sha256_bytes(canonical(event_material))
        if (
            stored_digest != digest
            or metadata["event_sha256"] != digest
            or event.get("scan_id") != scan_id
            or event.get("analysis_version") != ANALYSIS_VERSION
            or event.get("snapshot_file_sha256") != metadata["snapshot_sha256"]
        ):
            raise ReplayError(f"Analysis event identity or checksum mismatch: {scan_id}")
        event_hashes.append(
            {
                "scan_id": scan_id,
                "event_file_sha256": sha256_bytes(raw),
                "event_sha256": digest,
            }
        )
    return {
        "event_count": len(event_hashes),
        "event_file_manifest_sha256": sha256_bytes(canonical(event_hashes)),
        "event_files": event_hashes,
    }


def _read_and_verify_summary(root: Path) -> tuple[Path, dict[str, Any]]:
    summary_path = root / "research-summary.json"
    if summary_path.is_symlink() or not summary_path.is_file():
        raise ReplayError("Bounded v6 analysis summary is missing or unsafe")
    if summary_path.stat().st_size > MAX_ANALYSIS_SUMMARY_BYTES:
        raise ReplayError("Published v6 analysis summary exceeds its reader bound")
    try:
        summary = json.loads(summary_path.read_bytes())
    except json.JSONDecodeError as error:
        raise ReplayError("Published v6 analysis summary is not valid JSON") from error
    if not isinstance(summary, dict):
        raise ReplayError("Published v6 analysis summary is not an object")
    summary_material = dict(summary)
    stored_digest = summary_material.pop("analysis_summary_sha256", None)
    if stored_digest != sha256_bytes(canonical(summary_material)):
        raise ReplayError("Published v6 summary checksum does not match its content")
    if summary.get("analysis_version") != ANALYSIS_VERSION:
        raise ReplayError("Published summary analysis version differs from candidate code")
    if summary.get("independent_reference_version") != analysis_catalog.REFERENCE_VERSION:
        raise ReplayError(
            "Published summary independent reference version differs from candidate code"
        )
    if summary.get("pending_snapshot_count") != 0:
        raise ReplayError("Published summary still reports pending snapshots")
    return summary_path, summary


def _verify_completed_replay(
    root: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    candidate_code_identity: dict[str, Any],
) -> None:
    counts = _catalog_counts(root, int(manifest["snapshot_count"]))
    if counts["snapshot_catalog_version"] != scan_catalog.CATALOG_VERSION:
        raise ReplayError("Snapshot catalog version differs from the candidate code")
    if counts["analysis_catalog_version"] != analysis_catalog.ANALYSIS_CATALOG_VERSION:
        raise ReplayError("Analysis catalog version differs from the candidate code")
    _verify_catalog_lineage(manifest, counts)
    event_manifest = _verify_analysis_event_artifacts(root, counts)
    summary_path, summary = _read_and_verify_summary(root)
    if (
        receipt.get("source_snapshot_manifest_sha256") != manifest.get("manifest_sha256")
        or receipt.get("candidate_code", {}).get("source_manifest_sha256")
        != candidate_code_identity.get("source_manifest_sha256")
        or receipt.get("catalogs") != counts
        or receipt.get("published_summary", {}).get("sha256") != sha256_file(summary_path)
        or receipt.get("published_summary", {}).get("analysis_summary_sha256")
        != summary.get("analysis_summary_sha256")
        or receipt.get("analysis_event_manifest") != event_manifest
    ):
        raise ReplayError("Completed replay artifacts differ from the durable receipt")


def _ensure_output_capacity(parent: Path, inventory: dict[str, Any]) -> int:
    # Reserve the source copy, one bounded event per snapshot, and catalog headroom.
    required = (
        int(inventory["snapshot_bytes"])
        + int(inventory["snapshot_count"]) * MAX_ANALYSIS_EVENT_BYTES
        + 64 * 1024**2
    )
    stats = os.statvfs(parent)
    available = stats.f_bavail * stats.f_frsize
    if available < required:
        raise ReplayError(
            f"Insufficient output space: need at least {required} bytes, have {available}"
        )
    return required


def _wait_for_stable_admission(
    *, stability_seconds: int, timeout_seconds: int, sample_seconds: int = 10
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
    import reality_full_scale_validation as reality_validation

    reality_validation.ensure_no_active_validation_units()
    started = time.monotonic()
    first = None
    samples: list[dict[str, Any]] = []
    while first is None:
        if time.monotonic() - started >= timeout_seconds:
            raise ReplayError("Initial resource admission did not pass before timeout")
        try:
            first = reality_validation.admission()
        except ValueError as error:
            if not reality_validation.is_transient_pressure_rejection(error):
                raise
            samples.append({"rejected": str(error), "sampled_ns": time.time_ns()})
            time.sleep(sample_seconds)
    samples.append(first)
    stable_seconds = 0
    while stable_seconds < stability_seconds:
        if time.monotonic() - started >= timeout_seconds:
            raise ReplayError("Sustained resource admission did not pass before timeout")
        time.sleep(sample_seconds)
        try:
            current = reality_validation.admission(first["memory_events"])
        except ValueError as error:
            if not reality_validation.is_transient_pressure_rejection(error):
                raise
            stable_seconds = 0
            samples.append({"rejected": str(error), "sampled_ns": time.time_ns()})
            continue
        if current["pid"] != first["pid"]:
            raise ReplayError("Protected Reality recorder identity changed during admission")
        stable_seconds += sample_seconds
        samples.append(current)
    return first, samples


def _current_admission(initial: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
    import reality_full_scale_validation as reality_validation

    current = reality_validation.admission(initial["memory_events"])
    if current["pid"] != initial["pid"]:
        raise ReplayError("Protected Reality recorder identity changed during replay")
    return current


def run_replay(
    source_root: Path,
    output_root: Path,
    *,
    batch_size: int = 25,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    copy_rate_bytes_per_second: int = DEFAULT_COPY_RATE_BYTES_PER_SECOND,
    resume: bool = False,
    initial_admission: dict[str, Any] | None = None,
    preflight_admission_samples: list[dict[str, Any]] | None = None,
    admit: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if not 1 <= batch_size <= 50:
        raise ReplayError("Catalog batch size must be between 1 and 50 snapshots")
    source_root, output_root = _validate_output_path(source_root, output_root)
    started_ns = time.time_ns()
    started_monotonic = time.monotonic()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    state_path = output_root / STATE_NAME
    if initial_admission is None and admit is None:
        initial_admission, admission_samples = _wait_for_stable_admission(
            stability_seconds=60, timeout_seconds=300
        )
    else:
        admission_samples = list(preflight_admission_samples or [])
        if initial_admission is not None and not admission_samples:
            admission_samples.append(initial_admission)
    if admit is None and initial_admission is not None:

        def admission_guard() -> dict[str, Any]:
            return _current_admission(initial_admission)

        admit = admission_guard
    if admit is not None:
        raw_admit = admit

        def checked_admission() -> Any:
            return _checkpoint_admission_check(output_root, state_path, raw_admit)

        admit = checked_admission
    if admit is not None:
        admit()

    candidate_code_identity = _candidate_code_identity()
    if resume:
        state = _read_state(output_root)
        complete_receipt: dict[str, Any] | None = None
        if state.get("phase") == "COMPLETE":
            receipt_path = output_root / RECEIPT_NAME
            if receipt_path.is_file() and not receipt_path.is_symlink():
                complete_receipt = json.loads(receipt_path.read_bytes())
                if state.get("receipt_sha256") != sha256_bytes(canonical(complete_receipt)):
                    raise ReplayError("Completed replay receipt checksum differs from state")
            else:
                raise ReplayError("Completed replay is missing its receipt")
        source_manifest = copy_snapshot_set(
            source_root,
            output_root,
            max_source_bytes=max_source_bytes,
            copy_rate_bytes_per_second=copy_rate_bytes_per_second,
            resume=True,
            admit=admit,
        )
        if complete_receipt is not None:
            receipt_code_identity = complete_receipt.get("candidate_code", {})
            if receipt_code_identity.get("package_root") != candidate_code_identity.get(
                "package_root"
            ) or receipt_code_identity.get("source_files") != candidate_code_identity.get(
                "source_files"
            ):
                raise ReplayError(
                    "Veritas package source changed since the completed replay was produced"
                )
            state_code_identity = state.get("candidate_code_identity")
            receipt_driver_identity = {
                key: receipt_code_identity.get(key)
                for key in (
                    "package_root",
                    "source_files",
                    "replay_script_sha256",
                    "source_manifest_sha256",
                )
            }
            if state_code_identity != receipt_driver_identity:
                raise ReplayError(
                    "Completed replay code identity differs between state and receipt"
                )
            _verify_completed_replay(
                output_root, source_manifest, complete_receipt, receipt_code_identity
            )
            expected_completed = {item["name"]: item["sha256"] for item in source_manifest["files"]}
            if (
                state.get("completed_files") != expected_completed
                or state.get("in_progress_file") is not None
            ):
                state["completed_files"] = expected_completed
                state["in_progress_file"] = None
                state["copy_checkpoint_reconciled"] = {
                    "source_manifest_sha256": source_manifest["manifest_sha256"],
                    "completed_file_count": len(expected_completed),
                    "reconciled_ns": time.time_ns(),
                    "reason": "reconstructed from the checksummed copied-input manifest",
                }
                state["updated_ns"] = time.time_ns()
                atomic_json(state_path, state)
            return complete_receipt
        state = _read_state(output_root)
    else:
        source_manifest = copy_snapshot_set(
            source_root,
            output_root,
            max_source_bytes=max_source_bytes,
            copy_rate_bytes_per_second=copy_rate_bytes_per_second,
            resume=False,
            admit=admit,
        )
        state = _read_state(output_root)

    source_count = int(source_manifest["snapshot_count"])
    stored_code_identity = state.get("candidate_code_identity")
    if stored_code_identity is not None and stored_code_identity != candidate_code_identity:
        raise ReplayError("Candidate source changed since the resumable replay began")
    state["candidate_code_identity"] = candidate_code_identity
    atomic_json(state_path, state)
    last_scan_result = state.get("last_snapshot_catalog_batch", {})
    if last_scan_result.get("status") != "CURRENT":
        state["phase"] = "SNAPSHOT_CATALOG"
        atomic_json(state_path, state)
        while True:
            if admit is not None:
                admission_samples.append(admit())
            last_scan_result = scan_catalog.rebuild_catalog(
                output_root, limit=min(batch_size, scan_catalog.MAX_RECONCILE_PER_RUN)
            )
            state["phase"] = "SNAPSHOT_CATALOG"
            state["last_snapshot_catalog_batch"] = last_scan_result
            state["updated_ns"] = time.time_ns()
            atomic_json(state_path, state)
            if last_scan_result["status"] != "REBUILDING":
                break
            if (
                last_scan_result["result"]["indexed_this_run"] == 0
                and last_scan_result["result"]["quarantined_this_run"] == 0
            ):
                raise ReplayError("Snapshot catalog made no progress while work remains")

    last_analysis_result = state.get("last_analysis_batch", {})
    if last_analysis_result.get("status") != "CURRENT":
        state["phase"] = "ANALYSIS_CATALOG"
        atomic_json(state_path, state)
        while True:
            if admit is not None:
                admission_samples.append(admit())
            last_analysis_result = rebuild_analysis_catalog(
                output_root,
                max_pending=min(batch_size, 100),
            )
            state["phase"] = "ANALYSIS_CATALOG"
            state["last_analysis_batch"] = last_analysis_result
            state["updated_ns"] = time.time_ns()
            atomic_json(state_path, state)
            if last_analysis_result["status"] != "REBUILDING":
                break
            analysis_batch = last_analysis_result["analysis"]
            if (
                analysis_batch.get("processed_this_run", 0) == 0
                and analysis_batch.get("quarantined_this_run", 0) == 0
            ):
                raise ReplayError("Analysis catalog made no progress while work remains")

    counts = _catalog_counts(output_root, source_count)
    if counts["snapshot_catalog_version"] != scan_catalog.CATALOG_VERSION:
        raise ReplayError("Snapshot catalog version differs from the candidate code")
    if counts["analysis_catalog_version"] != analysis_catalog.ANALYSIS_CATALOG_VERSION:
        raise ReplayError("Analysis catalog version differs from the candidate code")
    _verify_catalog_lineage(source_manifest, counts)
    analysis_event_manifest = _verify_analysis_event_artifacts(output_root, counts)
    summary_path, summary = _read_and_verify_summary(output_root)
    state_value = analysis_catalog.current_state(output_root)
    scan_summary = scan_catalog.summary(output_root)
    reference_summary = analysis_catalog.reference_version_summary(output_root)
    state["phase"] = "VERIFYING"
    atomic_json(state_path, state)
    cpu_after = resource.getrusage(resource.RUSAGE_SELF)
    cgroup_metrics = _process_cgroup_metrics()
    receipt = {
        "schema_version": 1,
        "status": (
            "COMPLETE_WITH_QUARANTINE"
            if counts["snapshot_catalog_quarantined"] or counts["analysis_quarantined"]
            else "COMPLETE"
        ),
        "verification_complete": True,
        "network_requests": 0,
        "source_root": str(source_root),
        "output_root": str(output_root),
        "source_snapshot_manifest_sha256": source_manifest["manifest_sha256"],
        "source_inventory_sha256": source_manifest["source_inventory_sha256"],
        "source_snapshot_count": source_count,
        "source_snapshot_bytes": int(source_manifest["snapshot_bytes"]),
        "snapshot_copy_rate_bytes_per_second": copy_rate_bytes_per_second,
        "source_first_snapshot": source_manifest["files"][0]["name"],
        "source_last_snapshot": source_manifest["files"][-1]["name"],
        "candidate_code": {
            **candidate_code_identity,
            "analysis_version": summary.get("analysis_version"),
            "independent_reference_version": summary.get("independent_reference_version"),
            "snapshot_catalog_version": counts["snapshot_catalog_version"],
            "analysis_catalog_version": counts["analysis_catalog_version"],
        },
        "catalogs": counts,
        "analysis_event_manifest": analysis_event_manifest,
        "scan_catalog_summary": scan_summary,
        "analysis_state": {
            "processed_snapshot_count": state_value["processed_snapshot_count"],
            "quarantined_snapshot_count": state_value["quarantined_snapshot_count"],
            "unique_market_id_count": state_value["unique_market_id_count"],
            "unique_candidate_market_id_count": state_value["unique_candidate_market_id_count"],
            "last_processed_snapshot_file": state_value["last_processed_snapshot_file"],
        },
        "independent_reference_summary": reference_summary,
        "published_summary": {
            "path": "research-summary.json",
            "bytes": summary_path.stat().st_size,
            "sha256": sha256_file(summary_path),
            "analysis_summary_sha256": summary.get("analysis_summary_sha256"),
            "status": summary.get("status"),
            "pending_snapshot_count": summary.get("pending_snapshot_count"),
        },
        "started_ns": started_ns,
        "completed_ns": time.time_ns(),
        "elapsed_seconds": round(time.monotonic() - started_monotonic, 6),
        "process_cpu_seconds": round(
            (cpu_after.ru_utime + cpu_after.ru_stime) - (cpu_before.ru_utime + cpu_before.ru_stime),
            6,
        ),
        "process_block_io_operations": {
            "input_delta": int(cpu_after.ru_inblock - cpu_before.ru_inblock),
            "output_delta": int(cpu_after.ru_oublock - cpu_before.ru_oublock),
        },
        "process_peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024,
        "cgroup_resource_snapshot": cgroup_metrics,
        "admission_samples": admission_samples,
        "admission_rejections": state.get("admission_rejections", []),
        "limitations": [
            "The source boundary is the sorted finalized-file set observed at capture time; later files are outside this replay.",
            "Repeated snapshots and market observations are dependent and are not independent trial counts.",
            "The source snapshots preserve their original lineage; this replay creates derived v6 catalogs only in the isolated output root.",
            "Public order-book evidence does not establish fills, queue position, acknowledgments, realized P&L, or profitability.",
        ],
    }
    atomic_json(output_root / RECEIPT_NAME, receipt)
    state["phase"] = "COMPLETE"
    state["updated_ns"] = time.time_ns()
    state["receipt_sha256"] = sha256_bytes(canonical(receipt))
    atomic_json(state_path, state)
    return receipt


@contextlib.contextmanager
def _exclusive_output_lock(output_root: Path) -> Iterator[None]:
    output_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_name = f".{output_root.name}.veritas-v6-replay.lock"
    lock_path = output_root.parent / lock_name
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise ReplayError(f"Another replay owns output root {output_root}") from error
    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-source-bytes", type=int, default=DEFAULT_MAX_SOURCE_BYTES)
    parser.add_argument(
        "--copy-rate-bytes-per-second", type=int, default=DEFAULT_COPY_RATE_BYTES_PER_SECOND
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--admission-window-seconds", type=int, default=60)
    parser.add_argument("--admission-timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.max_source_bytes <= 0 or args.copy_rate_bytes_per_second <= 0:
        parser.error("source byte budget and copy rate must be positive")
    if args.admission_window_seconds < 60 or args.admission_timeout_seconds <= 0:
        parser.error("admission window must be at least 60 seconds and timeout positive")
    try:
        os.nice(19)
        source_root, output_root = _validate_output_path(args.source_root, args.output_root)
        initial_admission, samples = _wait_for_stable_admission(
            stability_seconds=args.admission_window_seconds,
            timeout_seconds=args.admission_timeout_seconds,
        )
        with _exclusive_output_lock(output_root):
            receipt = run_replay(
                source_root,
                output_root,
                batch_size=args.batch_size,
                max_source_bytes=args.max_source_bytes,
                copy_rate_bytes_per_second=args.copy_rate_bytes_per_second,
                resume=args.resume,
                initial_admission=initial_admission,
                preflight_admission_samples=samples,
            )
            verification = None
            if args.resume and receipt.get("verification_complete"):
                verifier_code_identity = _candidate_code_identity()
                state = _read_state(output_root)
                verification = _postrun_verification_document(
                    receipt, verifier_code_identity, state
                )
                atomic_json(output_root / VERIFICATION_NAME, verification)
        catalogs = receipt.get("catalogs", {})
        output = {
            "status": receipt.get("status"),
            "source_snapshot_count": receipt.get("source_snapshot_count"),
            "source_snapshot_bytes": receipt.get("source_snapshot_bytes"),
            "source_snapshot_manifest_sha256": receipt.get("source_snapshot_manifest_sha256"),
            "snapshot_catalog_indexed": catalogs.get("snapshot_catalog_indexed"),
            "snapshot_catalog_quarantined": catalogs.get("snapshot_catalog_quarantined"),
            "analysis_processed": catalogs.get("analysis_processed"),
            "analysis_quarantined": catalogs.get("analysis_quarantined"),
            "snapshot_catalog_sha256": catalogs.get("snapshot_catalog_sha256"),
            "analysis_catalog_sha256": catalogs.get("analysis_catalog_sha256"),
            "analysis_event_manifest_sha256": receipt.get("analysis_event_manifest", {}).get(
                "event_file_manifest_sha256"
            ),
            "original_receipt_sha256": sha256_bytes(canonical(receipt)),
            "postrun_verification": VERIFICATION_NAME if verification else None,
            "postrun_verification_sha256": (
                verification.get("verification_sha256") if verification else None
            ),
        }
        print(json.dumps(output, indent=2))
    except (OSError, ValueError, ReplayError, sqlite3.Error) as error:
        print(
            f"Veritas v6 offline replay stopped safely: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
