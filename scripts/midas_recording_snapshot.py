#!/usr/bin/env python3
"""Snapshot finalized Reality recording segments and restore them to a new root."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import shutil
import signal
import stat
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from midas_backup_support import (
        BackupAdmissionError,
        require_admitted_scope,
        validate_receipt_path,
        write_receipt,
    )
except ModuleNotFoundError:
    from scripts.midas_backup_support import (
        BackupAdmissionError,
        require_admitted_scope,
        validate_receipt_path,
        write_receipt,
    )

from midas.reality.storage import manifest as recording_manifest
from midas.reality.storage import read_manifest

FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
MANIFEST_HASH_NAME = "manifest.sha256"
RECORDING_MANIFEST_NAME = "recording-manifest.json"


class RecordingSnapshotError(RuntimeError):
    pass


def _require_heavy_scope() -> dict[str, Any]:
    try:
        return require_admitted_scope(require_heavy_profile=True)
    except BackupAdmissionError as error:
        raise RecordingSnapshotError(str(error)) from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return data


def _rename_noreplace(source: Path, destination: Path) -> None:
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise RecordingSnapshotError(
            "atomic no-replace directory publication is unsupported"
        ) from error
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
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), str(destination))


def _source_lock(root: Path) -> int:
    path = root / "writer.lock"
    if path.is_symlink() or not path.is_file():
        raise RecordingSnapshotError("recording writer.lock must be an existing regular file")
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise RecordingSnapshotError(
            f"cannot open recording writer.lock safely: {error}"
        ) from error
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise RecordingSnapshotError("recording writer.lock is not a regular file")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(fd)
        raise RecordingSnapshotError("a Reality writer still owns this recording root") from error
    return fd


def _regular_file(path: Path, label: str) -> os.stat_result:
    if path.is_symlink():
        raise RecordingSnapshotError(f"{label} is a symlink: {path}")
    try:
        info = path.stat()
    except OSError as error:
        raise RecordingSnapshotError(f"cannot stat {label} {path}: {error}") from error
    if not stat.S_ISREG(info.st_mode):
        raise RecordingSnapshotError(f"{label} is not a regular file: {path}")
    return info


def _inventory(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    open_segments = sorted(path.name for path in root.glob("*.open"))
    if open_segments:
        raise RecordingSnapshotError(
            "recording root still contains open segments; stop the recorder cleanly before snapshot: "
            + ", ".join(open_segments[:5])
        )

    value = recording_manifest(root)
    expected_names: set[str] = set()
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for item in value["segments"]:
        name = item.get("file")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".seg"):
            raise RecordingSnapshotError("recording manifest contains an unsafe segment name")
        if name in expected_names:
            raise RecordingSnapshotError(f"duplicate segment in recording manifest: {name}")
        expected_names.add(name)
        segment_path = root / name
        sidecar_path = segment_path.with_suffix(".json")
        segment_info = _regular_file(segment_path, "recording segment")
        sidecar_info = _regular_file(sidecar_path, "segment manifest")
        if segment_info.st_size != item.get("bytes"):
            raise RecordingSnapshotError(f"segment size differs from its manifest: {name}")
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RecordingSnapshotError(
                f"invalid segment manifest {sidecar_path}: {error}"
            ) from error
        if sidecar != item:
            raise RecordingSnapshotError(f"segment manifest changed during inventory: {name}")
        if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
            raise RecordingSnapshotError(f"segment manifest has no valid digest: {name}")
        files.append(
            {
                "path": f"segments/{name}",
                "kind": "segment",
                "bytes": segment_info.st_size,
                "sha256": item["sha256"],
                "source_mtime_ns": segment_info.st_mtime_ns,
            }
        )
        files.append(
            {
                "path": f"segments/{sidecar_path.name}",
                "kind": "segment_manifest",
                "bytes": sidecar_info.st_size,
                "sha256": _sha256_file(sidecar_path),
                "source_mtime_ns": sidecar_info.st_mtime_ns,
            }
        )
        total_bytes += segment_info.st_size + sidecar_info.st_size

    actual_names = {path.name for path in root.glob("*.seg")}
    if actual_names != expected_names:
        missing = sorted(actual_names - expected_names)
        absent = sorted(expected_names - actual_names)
        raise RecordingSnapshotError(
            f"recorded segments and manifests disagree (unmanifested={missing[:5]}, missing={absent[:5]})"
        )
    return value, files, total_bytes


def _copy_file(
    source: Path,
    destination: Path,
    expected: dict[str, Any],
    *,
    compare_source_mtime: bool = True,
) -> None:
    before = _regular_file(source, "snapshot source")
    if before.st_size != expected["bytes"] or (
        compare_source_mtime and before.st_mtime_ns != expected["source_mtime_ns"]
    ):
        raise RecordingSnapshotError(f"snapshot source changed before copy: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        os.fchmod(outgoing.fileno(), 0o600)
        while chunk := incoming.read(1024 * 1024):
            outgoing.write(chunk)
            digest.update(chunk)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    after = source.stat()
    if (after.st_ino, after.st_size, after.st_mtime_ns) != (
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        raise RecordingSnapshotError(f"snapshot source changed during copy: {source}")
    if digest.hexdigest() != expected["sha256"]:
        raise RecordingSnapshotError(f"snapshot source digest differs from its manifest: {source}")


def _read_snapshot_manifest(directory: Path) -> tuple[dict[str, Any], bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise RecordingSnapshotError("snapshot path must be an existing directory, not a symlink")
    path = directory / MANIFEST_NAME
    checksum_path = directory / MANIFEST_HASH_NAME
    _regular_file(path, "snapshot manifest")
    _regular_file(checksum_path, "snapshot manifest checksum")
    manifest_bytes = path.read_bytes()
    expected = checksum_path.read_text(encoding="ascii").strip()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected:
        raise RecordingSnapshotError("snapshot manifest checksum mismatch")
    try:
        value = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise RecordingSnapshotError(f"invalid snapshot manifest: {error}") from error
    if (
        value.get("format") != "midas-reality-recording-snapshot"
        or value.get("format_version") != FORMAT_VERSION
    ):
        raise RecordingSnapshotError("unsupported Reality recording snapshot format")
    _require_heavy_scope()
    return value, manifest_bytes


def _verify_snapshot(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = directory.expanduser().absolute()
    snapshot, manifest_bytes = _read_snapshot_manifest(directory)
    recording_path = directory / RECORDING_MANIFEST_NAME
    _regular_file(recording_path, "recording manifest")
    recording_bytes = recording_path.read_bytes()
    if hashlib.sha256(recording_bytes).hexdigest() != snapshot.get("recording_manifest_sha256"):
        raise RecordingSnapshotError("recording manifest checksum mismatch")
    try:
        value = json.loads(recording_bytes)
    except json.JSONDecodeError as error:
        raise RecordingSnapshotError(f"invalid recording manifest: {error}") from error

    files = snapshot.get("files")
    if not isinstance(files, list):
        raise RecordingSnapshotError("snapshot file inventory is missing")
    file_map: dict[str, dict[str, Any]] = {}
    for item in files:
        relative = item.get("path") if isinstance(item, dict) else None
        if not isinstance(relative, str) or Path(relative).parts[0:1] != ("segments",):
            raise RecordingSnapshotError("snapshot contains an unsafe file path")
        if Path(relative).name != relative.removeprefix("segments/") or relative in file_map:
            raise RecordingSnapshotError("snapshot contains an invalid or duplicate file path")
        file_map[relative] = item

    segments_path = directory / "segments"
    if segments_path.is_symlink() or not segments_path.is_dir():
        raise RecordingSnapshotError("snapshot segments directory is missing or unsafe")
    expected_files = {f"segments/{item['file']}" for item in value.get("segments", [])}
    expected_files |= {
        f"segments/{Path(item['file']).with_suffix('.json').name}"
        for item in value.get("segments", [])
    }
    if expected_files != set(file_map):
        raise RecordingSnapshotError("snapshot file inventory differs from its recording manifest")
    actual_files = {f"segments/{path.name}" for path in segments_path.iterdir()}
    if actual_files != expected_files:
        raise RecordingSnapshotError("snapshot contains missing or unexpected segment files")

    total_bytes = 0
    for info in value["segments"]:
        name = info["file"]
        segment_relative = f"segments/{name}"
        sidecar_relative = f"segments/{Path(name).with_suffix('.json').name}"
        segment = segments_path / name
        sidecar = segments_path / Path(name).with_suffix(".json")
        segment_stat = _regular_file(segment, "snapshot segment")
        sidecar_stat = _regular_file(sidecar, "snapshot segment manifest")
        segment_entry = file_map[segment_relative]
        sidecar_entry = file_map[sidecar_relative]
        if (
            segment_entry.get("kind") != "segment"
            or segment_entry.get("bytes") != segment_stat.st_size
            or segment_entry.get("sha256") != info.get("sha256")
        ):
            raise RecordingSnapshotError(f"snapshot segment metadata differs: {name}")
        if _sha256_file(sidecar) != sidecar_entry.get("sha256"):
            raise RecordingSnapshotError(f"snapshot sidecar checksum mismatch: {sidecar.name}")
        if (
            sidecar_entry.get("kind") != "segment_manifest"
            or sidecar_entry.get("bytes") != sidecar_stat.st_size
        ):
            raise RecordingSnapshotError(f"snapshot sidecar metadata differs: {sidecar.name}")
        if json.loads(sidecar.read_text(encoding="utf-8")) != info:
            raise RecordingSnapshotError(
                f"snapshot sidecar differs from recording manifest: {name}"
            )
        total_bytes += segment_stat.st_size + sidecar_stat.st_size

    record_count = sum(1 for _ in read_manifest(segments_path, value))
    if total_bytes != snapshot.get("recording_bytes"):
        raise RecordingSnapshotError("snapshot recording byte count differs from manifest")
    if len(value["segments"]) != snapshot.get("segment_count"):
        raise RecordingSnapshotError("snapshot segment count differs from manifest")
    return snapshot, {
        "decision": "VERIFIED",
        "snapshot_path": str(directory),
        "segment_count": len(value["segments"]),
        "record_count": record_count,
        "recording_bytes": total_bytes,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "recording_manifest_sha256": snapshot["recording_manifest_sha256"],
    }


def create_snapshot(
    source_root: Path,
    destination: Path,
    *,
    reserve_mib: int = 5120,
) -> dict[str, Any]:
    source_root = source_root.expanduser().absolute()
    destination = destination.expanduser().absolute()
    if source_root.is_symlink() or not source_root.is_dir():
        raise RecordingSnapshotError("recording source must be an existing real directory")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise RecordingSnapshotError(
            "snapshot destination parent must be an existing real directory"
        )
    if destination.exists() or destination.is_symlink():
        raise RecordingSnapshotError("snapshot destination already exists")
    source_resolved = source_root.resolve()
    destination_resolved = destination.resolve(strict=False)
    if (
        source_resolved == destination_resolved
        or source_resolved.is_relative_to(destination_resolved)
        or destination_resolved.is_relative_to(source_resolved)
    ):
        raise RecordingSnapshotError("snapshot destination overlaps the recording source")
    if reserve_mib < 0:
        raise RecordingSnapshotError("reserve_mib must be nonnegative")
    admission = _require_heavy_scope()
    lock_fd = _source_lock(source_root)
    staging = (
        destination.parent / f".{destination.name}.partial.{os.getpid()}.{uuid.uuid4().hex[:10]}"
    )
    try:
        value, files, total_bytes = _inventory(source_root)
        required = total_bytes + reserve_mib * 1024 * 1024
        filesystem = os.statvfs(destination.parent)
        available = filesystem.f_bavail * filesystem.f_frsize
        if available < required:
            raise RecordingSnapshotError(
                f"insufficient snapshot capacity: available={available} required={required}"
            )
        staging.mkdir(mode=0o700)
        segments_dir = staging / "segments"
        segments_dir.mkdir(mode=0o700)
        for item in files:
            name = Path(item["path"]).name
            _copy_file(source_root / name, segments_dir / name, item)

        recording_bytes = _write_json(staging / RECORDING_MANIFEST_NAME, value)
        snapshot = {
            "format": "midas-reality-recording-snapshot",
            "format_version": FORMAT_VERSION,
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_root": str(source_root),
            "destination": str(destination),
            "recording_manifest": RECORDING_MANIFEST_NAME,
            "recording_manifest_sha256": hashlib.sha256(recording_bytes).hexdigest(),
            "segment_count": len(value["segments"]),
            "recording_bytes": total_bytes,
            "files": files,
            "admission": admission,
            "included_scope": "finalized .seg files and their original .json sidecars",
            "excluded_scope": ["writer.lock", "open .open segments", "other runtime files"],
        }
        manifest_bytes = _write_json(staging / MANIFEST_NAME, snapshot)
        hash_path = staging / MANIFEST_HASH_NAME
        with hash_path.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(hashlib.sha256(manifest_bytes).hexdigest().encode("ascii") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        _verify_snapshot(staging)
        for directory in (segments_dir, staging):
            fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        _rename_noreplace(staging, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return {
            "decision": "CREATED",
            "snapshot_path": str(destination),
            "segment_count": len(value["segments"]),
            "file_count": len(files),
            "recording_bytes": total_bytes,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "recording_manifest_sha256": hashlib.sha256(recording_bytes).hexdigest(),
            "admission": admission,
        }
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def verify_snapshot(directory: Path) -> dict[str, Any]:
    return _verify_snapshot(directory)[1]


def restore_snapshot(directory: Path, destination: Path) -> dict[str, Any]:
    directory = directory.expanduser().absolute()
    snapshot, verified = _verify_snapshot(directory)
    destination = destination.expanduser().absolute()
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise RecordingSnapshotError("restore parent must be an existing real directory")
    if destination.exists() or destination.is_symlink():
        raise RecordingSnapshotError("restore destination must not already exist")
    staging = (
        destination.parent
        / f".{destination.name}.restore.partial.{os.getpid()}.{uuid.uuid4().hex[:10]}"
    )
    try:
        staging.mkdir(mode=0o700)
        for item in snapshot["files"]:
            source = directory / item["path"]
            _copy_file(
                source,
                staging / Path(item["path"]).name,
                item,
                compare_source_mtime=False,
            )
        record_manifest = json.loads(
            (directory / RECORDING_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        record_count = sum(1 for _ in read_manifest(staging, record_manifest))
        _rename_noreplace(staging, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return {
            "decision": "RESTORED",
            "destination": str(destination),
            "segment_count": verified["segment_count"],
            "record_count": record_count,
            "recording_bytes": verified["recording_bytes"],
            "manifest_sha256": verified["manifest_sha256"],
        }
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "decision",
        "snapshot_path",
        "destination",
        "segment_count",
        "file_count",
        "record_count",
        "recording_bytes",
        "manifest_sha256",
        "recording_manifest_sha256",
        "admission",
    )
    return {key: result[key] for key in keys if key in result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    backup = commands.add_parser(
        "backup", help="snapshot finalized segments from a stopped recorder"
    )
    backup.add_argument("--source-root", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--reserve-mib", type=int, default=5120)
    backup.add_argument("--receipt", type=Path, help="new durable JSON run receipt")

    verify = commands.add_parser("verify", help="verify checksums and replay every segment")
    verify.add_argument("--snapshot", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, help="new durable JSON run receipt")

    restore = commands.add_parser("restore", help="restore recordings to a new directory")
    restore.add_argument("--snapshot", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--receipt", type=Path, help="new durable JSON run receipt")
    return parser


def _handle_sigterm(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    args = build_parser().parse_args(argv)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    receipt_path: Path | None = None
    try:
        if args.receipt is not None:
            receipt_path = validate_receipt_path(args.receipt)
        if args.action == "backup":
            result = create_snapshot(
                args.source_root, args.destination, reserve_mib=args.reserve_mib
            )
            source = str(args.source_root)
            destination = str(args.destination)
            snapshot_path = None
        elif args.action == "verify":
            result = verify_snapshot(args.snapshot)
            source = None
            destination = None
            snapshot_path = str(args.snapshot)
        else:
            result = restore_snapshot(args.snapshot, args.destination)
            source = None
            destination = str(args.destination)
            snapshot_path = str(args.snapshot)
        if receipt_path is not None:
            write_receipt(
                receipt_path,
                {
                    "operation": args.action,
                    "decision": result["decision"],
                    "started_at_utc": started,
                    "finished_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source": source,
                    "destination": destination,
                    "snapshot": snapshot_path,
                    "result": _receipt_summary(result),
                },
            )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        failure = {"decision": "FAILED", "error_type": type(error).__name__, "error": str(error)}
        if receipt_path is not None:
            try:
                write_receipt(
                    receipt_path,
                    {
                        "operation": args.action,
                        "decision": "FAILED",
                        "started_at_utc": started,
                        "finished_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "source": str(getattr(args, "source_root", "")) or None,
                        "destination": str(getattr(args, "destination", "")) or None,
                        "snapshot": str(getattr(args, "snapshot", "")) or None,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    },
                )
            except (OSError, ValueError) as receipt_error:
                failure["receipt_error"] = str(receipt_error)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
