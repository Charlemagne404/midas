#!/usr/bin/env python3
"""Capture and verify a coherent Veritas source-analysis checkpoint and ledger."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FORMAT_VERSION = 1
MAX_CHECKPOINT_BYTES = 24 * 1024**2
MAX_EVENT_BYTES = 256 * 1024
MAX_LEDGER_BYTES = 256 * 1024**2
MAX_EVENT_COUNT = 100_000
MAX_SMALL_FILE_BYTES = 4 * 1024**2
SENSITIVE_ENVIRONMENT = re.compile(r"(?i)(password|token|secret|api[_-]?key)")


class SnapshotError(RuntimeError):
    """A Veritas capture is incomplete, inconsistent, or unsafe."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_file(path: Path, *, maximum: int, label: str) -> tuple[bytes, os.stat_result]:
    if path.is_symlink():
        raise SnapshotError(f"{label} must not be a symlink: {path}")
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise SnapshotError(f"{label} is not a bounded regular file: {path}")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            os.close(descriptor)
            raise SnapshotError(f"{label} identity changed before it could be read: {path}")
        with os.fdopen(descriptor, "rb") as stream:
            data = stream.read(maximum + 1)
        after = path.stat()
    except OSError as error:
        raise SnapshotError(f"cannot read {label} {path}: {error}") from error
    if len(data) > maximum or len(data) != before.st_size:
        raise SnapshotError(f"{label} changed size while being read: {path}")
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise SnapshotError(f"{label} changed while being read: {path}")
    return data, after


def _sealed(data: bytes, *, key: str, maximum: int, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SnapshotError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise SnapshotError(f"{label} is not a JSON object")
    stored = value.pop(key, None)
    if not isinstance(stored, str) or stored != _sha256(_canonical(value)):
        raise SnapshotError(f"{label} {key} digest does not verify")
    value[key] = stored
    if len(data) > maximum:
        raise SnapshotError(f"{label} exceeds its size bound")
    return value


def _read_checkpoint(path: Path) -> tuple[dict[str, Any], bytes, os.stat_result]:
    data, info = _read_file(path, maximum=MAX_CHECKPOINT_BYTES, label="Veritas checkpoint")
    value = _sealed(data, key="state_sha256", maximum=MAX_CHECKPOINT_BYTES, label=path.name)
    version = value.get("schema_version")
    expected = 1 if path.name == "source-analysis-state-v1.json" else 2
    if version != expected:
        raise SnapshotError(f"{path.name} has unsupported checkpoint schema {version!r}")
    count = value.get("processed_segment_count")
    if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= MAX_EVENT_COUNT:
        raise SnapshotError(f"{path.name} has an invalid processed event count")
    if not isinstance(value.get("analysis_code_files"), dict):
        raise SnapshotError(f"{path.name} omits its analysis source digests")
    for name, digest in value["analysis_code_files"].items():
        if (
            not isinstance(name, str)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise SnapshotError(f"{path.name} contains malformed source digest metadata")
    for key in ("campaign_sha256", "analysis_code_sha256"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise SnapshotError(f"{path.name} omits valid {key} provenance")
    if _sha256(_canonical(value["analysis_code_files"])) != value["analysis_code_sha256"]:
        raise SnapshotError(f"{path.name} source digests do not match analysis_code_sha256")
    for key in ("campaign_id", "analysis_version"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise SnapshotError(f"{path.name} omits valid {key} provenance")
    migration = value.get("migration")
    if migration is not None and path.name == "source-analysis-state-v2.json":
        if (
            not isinstance(migration, dict)
            or migration.get("from_state_schema_version") != 1
            or not isinstance(migration.get("from_state_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", migration["from_state_sha256"])
            or not isinstance(migration.get("from_processed_segment_count"), int)
            or isinstance(migration.get("from_processed_segment_count"), bool)
            or not isinstance(migration.get("from_analysis_code_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", migration["from_analysis_code_sha256"])
        ):
            raise SnapshotError(f"{path.name} has invalid migration lineage")
    return value, data, info


def _event_value(data: bytes, *, index: int) -> dict[str, Any]:
    value = _sealed(
        data,
        key="analysis_event_sha256",
        maximum=MAX_EVENT_BYTES,
        label=f"Veritas event {index}",
    )
    if (
        not isinstance(value.get("segment_index"), int)
        or isinstance(value.get("segment_index"), bool)
        or value["segment_index"] != index
    ):
        raise SnapshotError(f"Veritas event {index} has an inconsistent segment index")
    return value


def _write_new(path: Path, data: bytes, *, sync: bool = True) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        if sync:
            os.fsync(stream.fileno())


def _unit_properties(units: list[str]) -> dict[str, dict[str, str]]:
    properties = (
        "Id",
        "LoadState",
        "ActiveState",
        "SubState",
        "UnitFileState",
        "Result",
        "ExecMainStartTimestampMonotonic",
        "ExecMainStartTimestamp",
        "ExecMainExitTimestamp",
        "ExecMainStatus",
        "FragmentPath",
        "DropInPaths",
        "ExecStart",
        "WorkingDirectory",
        "User",
        "Group",
        "MemoryHigh",
        "MemoryMax",
        "MemorySwapMax",
        "CPUQuotaPerSecUSec",
        "IOWeight",
        "Nice",
        "IOSchedulingClass",
        "TimeoutStartUSec",
        "Restart",
        "OnCalendar",
        "OnBootUSec",
        "OnUnitActiveUSec",
        "Persistent",
        "NextElapseUSecRealtime",
        "LastTriggerUSec",
    )
    result: dict[str, dict[str, str]] = {}
    for unit in units:
        try:
            completed = subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    *[item for p in properties for item in ("-p", p)],
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SnapshotError(f"cannot inspect systemd unit {unit}: {error}") from error
        if completed.returncode != 0:
            raise SnapshotError(f"systemd could not inspect required unit {unit}")
        values: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value
        if not values.get("Id"):
            raise SnapshotError(f"systemd returned incomplete metadata for {unit}")
        # Only allowlisted, non-Environment properties are collected. Also redact
        # secret-like command arguments in case a local unit was configured unusually.
        for key, value in list(values.items()):
            if key == "ExecStart" and SENSITIVE_ENVIRONMENT.search(value):
                values[key] = "<redacted>"
        result[unit] = values
    return result


def _timer_epoch(value: str) -> float:
    try:
        return int(value) / 1_000_000
    except ValueError:
        pass
    fields = value.split()
    if len(fields) < 3:
        raise SnapshotError("active Veritas timer has no measurable next trigger")
    try:
        zone_name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        zone = ZoneInfo(zone_name)
    except (OSError, ZoneInfoNotFoundError):
        zone = datetime.now().astimezone().tzinfo
    try:
        parsed = datetime.strptime(f"{fields[1]} {fields[2]}", "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise SnapshotError("active Veritas timer returned an invalid trigger time") from error
    if fields[-1] in {"UTC", "GMT"}:
        zone = UTC
    return parsed.replace(tzinfo=zone).timestamp()


def _capture_systemd_config(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    records: list[dict[str, Any]] = []
    contents: dict[str, bytes] = {}
    for index, path in enumerate(paths):
        if "credential" in {part.lower() for part in path.parts} or "password" in path.name.lower():
            raise SnapshotError("credential files cannot be included in MIDAS backup archives")
        data, info = _read_file(path, maximum=MAX_SMALL_FILE_BYTES, label="MIDAS systemd config")
        text = data.decode("utf-8", errors="replace")
        redacted = False
        safe_lines: list[str] = []
        for line in text.splitlines(keepends=True):
            if SENSITIVE_ENVIRONMENT.search(line):
                key, separator, _value = line.partition("=")
                replacement = f"{key}=<redacted>\n" if separator else "<redacted>\n"
                safe_lines.append(replacement)
                redacted = True
            else:
                safe_lines.append(line)
        safe_data = "".join(safe_lines).encode("utf-8")
        key = f"{index:03d}-{path.name}"
        contents[key] = safe_data
        records.append(
            {
                "path": str(path),
                "archive_path": f"host/systemd/{key}",
                "source_sha256": _sha256(data),
                "archived_sha256": _sha256(safe_data),
                "redacted_secret_material": redacted,
                "mode": stat.S_IMODE(info.st_mode),
            }
        )
        after, _ = _read_file(path, maximum=MAX_SMALL_FILE_BYTES, label="MIDAS systemd config")
        if after != data:
            raise SnapshotError(f"MIDAS systemd config changed during capture: {path}")
    return records, contents


def _runtime_code_files(
    state: dict[str, Any], *, module_root: Path, script_root: Path
) -> dict[str, tuple[Path, bytes]]:
    files: dict[str, tuple[Path, bytes]] = {}
    for relative, expected in sorted(state["analysis_code_files"].items()):
        path_part = Path(relative)
        if path_part.is_absolute() or ".." in path_part.parts:
            raise SnapshotError(f"unsafe runtime code identity path: {relative}")
        if relative == "scripts/veritas_source_analysis.py":
            source = script_root / "veritas_source_analysis.py"
            archive = _code_archive_path(relative)
        elif relative in {"finalized_source_analysis.py", "economics.py"}:
            source = module_root / "veritas" / relative
            archive = _code_archive_path(relative)
        elif relative.startswith("reality/"):
            source = module_root / relative
            archive = _code_archive_path(relative)
        else:
            raise SnapshotError(f"unrecognized runtime code identity path: {relative}")
        data, _ = _read_file(source, maximum=MAX_SMALL_FILE_BYTES, label="Veritas runtime code")
        if _sha256(data) != expected:
            raise SnapshotError(f"runtime code digest differs from checkpoint: {relative}")
        files[archive.as_posix()] = (source, data)
    if not files:
        raise SnapshotError("checkpoint contains no runtime source identities")
    return files


def _code_archive_path(relative: str) -> Path:
    if relative == "scripts/veritas_source_analysis.py":
        return Path("provenance/runtime-code/scripts/veritas_source_analysis.py")
    if relative in {"finalized_source_analysis.py", "economics.py"}:
        return Path("provenance/runtime-code/veritas") / relative
    if relative.startswith("reality/"):
        return Path("provenance/runtime-code") / relative
    raise SnapshotError(f"unrecognized runtime code identity path: {relative}")


def _source_lock_is_free(root: Path) -> None:
    lock_path = root / "source-analysis.lock"
    if lock_path.is_symlink() or not lock_path.exists():
        raise SnapshotError("Veritas source-analysis lock is missing or unsafe")
    try:
        descriptor = os.open(lock_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise SnapshotError(f"cannot inspect Veritas analysis lock: {error}") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise SnapshotError("Veritas source-analysis lock is not a regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SnapshotError("Veritas source-analysis writer currently owns its lock") from error
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _publish_directory(source: Path, destination: Path) -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise SnapshotError("atomic no-replace snapshot publication is unavailable") from error
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def create_snapshot(
    *,
    source_root: Path,
    destination: Path,
    module_root: Path,
    script_root: Path,
    campaign_path: Path,
    systemd_units: list[str],
    systemd_config_paths: list[Path],
    minimum_timer_gap_seconds: int = 900,
) -> dict[str, Any]:
    source_root = source_root.absolute()
    destination = destination.absolute()
    if source_root.is_symlink() or not source_root.is_dir():
        raise SnapshotError("Veritas source-analysis root is missing or unsafe")
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        raise SnapshotError("snapshot destination must not exist and its parent must exist")
    if destination.is_relative_to(source_root) or source_root.is_relative_to(destination):
        raise SnapshotError("snapshot destination overlaps the live Veritas source")
    if minimum_timer_gap_seconds < 0:
        raise SnapshotError("minimum timer gap cannot be negative")

    root = source_root
    states: dict[str, dict[str, Any]] = {}
    state_bytes: dict[str, bytes] = {}
    state_stats: dict[str, os.stat_result] = {}
    for filename in ("source-analysis-state-v1.json", "source-analysis-state-v2.json"):
        path = root / filename
        if path.exists() or path.is_symlink():
            value, data, info = _read_checkpoint(path)
            states[filename] = value
            state_bytes[filename] = data
            state_stats[filename] = info
    if not states:
        raise SnapshotError("no supported Veritas source-analysis checkpoint exists")
    if (
        len(
            {
                (item.get("campaign_id"), item.get("campaign_sha256"), item.get("analysis_version"))
                for item in states.values()
            }
        )
        != 1
    ):
        raise SnapshotError("Veritas checkpoint files disagree about campaign provenance")
    prior_chains: dict[int, str | None] = {}
    for item in states.values():
        count = int(item["processed_segment_count"])
        current = item.get("last_event_sha256")
        if count == 0 and current not in (None, ""):
            raise SnapshotError("empty Veritas checkpoint has a nonempty event chain")
        if count > 0 and (
            not isinstance(current, str) or not re.fullmatch(r"[0-9a-f]{64}", current)
        ):
            raise SnapshotError("Veritas checkpoint has an invalid event chain")
        if count in prior_chains and prior_chains[count] != current:
            raise SnapshotError("Veritas checkpoints disagree about the same event prefix")
        prior_chains[count] = current
    migrated = states.get("source-analysis-state-v2.json", {}).get("migration")
    legacy = states.get("source-analysis-state-v1.json")
    if migrated is not None and legacy is not None:
        if (
            not isinstance(migrated, dict)
            or migrated.get("from_state_schema_version") != 1
            or migrated.get("from_state_sha256") != legacy.get("state_sha256")
            or migrated.get("from_processed_segment_count") != legacy.get("processed_segment_count")
            or migrated.get("from_analysis_code_sha256") != legacy.get("analysis_code_sha256")
        ):
            raise SnapshotError(
                "v2 checkpoint migration lineage differs from the preserved v1 state"
            )
    authoritative = (
        "source-analysis-state-v2.json"
        if "source-analysis-state-v2.json" in states
        else "source-analysis-state-v1.json"
    )
    latest = states[authoritative]
    _source_lock_is_free(root)

    units_before = _unit_properties(systemd_units)
    service_states = [
        values.get("ActiveState", "")
        for unit, values in units_before.items()
        if unit.endswith(".service") and "source-analysis" in unit
    ]
    if any(value in {"active", "activating", "reloading"} for value in service_states):
        raise SnapshotError("Veritas source-analysis service is active")
    timer_values = [
        values
        for unit, values in units_before.items()
        if unit.endswith(".timer") and "source-analysis" in unit
    ]
    gap_seconds: int | None = None
    if timer_values and timer_values[0].get("ActiveState") == "active":
        next_us = timer_values[0].get("NextElapseUSecRealtime", "")
        next_epoch = _timer_epoch(next_us)
        gap_seconds = int(next_epoch - time.time())
        if gap_seconds < minimum_timer_gap_seconds:
            raise SnapshotError("next Veritas timer trigger is too near for a bounded capture")

    max_count = max(int(state["processed_segment_count"]) for state in states.values())
    temp = destination.parent / f".{destination.name}.partial.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    temp.mkdir(mode=0o700, exist_ok=False)
    try:
        file_records: list[dict[str, Any]] = []
        for filename, data in state_bytes.items():
            archive_path = f"checkpoints/{filename}"
            _write_new(temp / archive_path, data)
            file_records.append(
                {"path": archive_path, "bytes": len(data), "sha256": _sha256(data), "mode": 0o600}
            )

        ledger = temp / "source-analysis-events" / "v1"
        ledger.mkdir(mode=0o700, parents=True, exist_ok=False)
        event_base = root / "source-analysis-events"
        event_root = event_base / "v1"
        if event_base.is_symlink() or event_root.is_symlink() or not event_root.is_dir():
            raise SnapshotError("Veritas v1 event ledger is missing or unsafe")
        total_event_bytes = 0
        chain = "0" * 64
        checks_at_count = {
            int(state["processed_segment_count"]): (name, state.get("last_event_sha256"))
            for name, state in states.items()
        }
        for index in range(1, max_count + 1):
            source = event_root / f"{index:020d}.json"
            data, info = _read_file(source, maximum=MAX_EVENT_BYTES, label="Veritas event")
            event = _event_value(data, index=index)
            for key in ("campaign_id", "campaign_sha256", "analysis_version"):
                if event.get(key) != latest.get(key):
                    raise SnapshotError(f"Veritas event {index} differs from checkpoint {key}")
            event_digest = event["analysis_event_sha256"]
            chain = _sha256(bytes.fromhex(chain) + bytes.fromhex(event_digest))
            expected_at_count = checks_at_count.get(index)
            if expected_at_count and expected_at_count[1] != chain:
                raise SnapshotError(
                    f"checkpoint {expected_at_count[0]} does not match event {index}"
                )
            target = ledger / source.name
            # The ledger can contain tens of thousands of small events.
            # Fsyncing each temporary file serially turns a bounded copy into
            # tens of thousands of disk barriers, especially on the backup HDD.
            # The complete staged tree is hashed before Restic reads it; Restic
            # handles durability of the repository snapshot itself.
            _write_new(target, data, sync=False)
            file_records.append(
                {
                    "path": f"source-analysis-events/v1/{source.name}",
                    "bytes": len(data),
                    "sha256": _sha256(data),
                    "mode": 0o600,
                }
            )
            total_event_bytes += len(data)
            if total_event_bytes > MAX_LEDGER_BYTES:
                raise SnapshotError("Veritas event ledger exceeds its 256 MiB capture bound")
        provenance_files: dict[str, bytes] = {}
        code_files = _runtime_code_files(latest, module_root=module_root, script_root=script_root)
        for archive_path, (_source, data) in code_files.items():
            provenance_files[archive_path] = data
        campaign_data, _ = _read_file(
            campaign_path, maximum=MAX_SMALL_FILE_BYTES, label="pinned Veritas campaign"
        )
        if _sha256(campaign_data) != latest.get("campaign_sha256"):
            raise SnapshotError("pinned campaign file differs from checkpoint provenance")
        provenance_files["provenance/campaign.json"] = campaign_data
        summary_path = root / "source-research-summary.json"
        summary_data: bytes | None = None
        summary_info: dict[str, Any] = {"included": False}
        if summary_path.exists() or summary_path.is_symlink():
            summary_data, _ = _read_file(
                summary_path, maximum=MAX_SMALL_FILE_BYTES, label="Veritas research summary"
            )
            provenance_files["provenance/source-research-summary.json"] = summary_data
            try:
                summary = _sealed(
                    summary_data,
                    key="summary_sha256",
                    maximum=MAX_SMALL_FILE_BYTES,
                    label="Veritas research summary",
                )
                current_summary = all(
                    summary.get(summary_key) == latest.get(state_key)
                    for summary_key, state_key in (
                        ("processed_segment_count", "processed_segment_count"),
                        ("analysis_code_sha256", "analysis_code_sha256"),
                        ("campaign_sha256", "campaign_sha256"),
                        ("last_processed_ordinal", "last_ordinal"),
                        ("prefix_catalog_sha256", "prefix_catalog_sha256"),
                    )
                )
                summary_info = {
                    "included": True,
                    "seal_valid": True,
                    "consistent_with_authoritative_checkpoint": current_summary,
                    "summary_sha256": summary["summary_sha256"],
                }
            except SnapshotError:
                summary_info = {
                    "included": True,
                    "seal_valid": False,
                    "consistent_with_authoritative_checkpoint": False,
                    "summary_sha256": _sha256(summary_data),
                }

        config_records, config_contents = _capture_systemd_config(systemd_config_paths)
        for archive_path, data in provenance_files.items():
            _write_new(temp / archive_path, data)
            file_records.append(
                {"path": archive_path, "bytes": len(data), "sha256": _sha256(data), "mode": 0o600}
            )
        for name, data in config_contents.items():
            archive_path = f"host/systemd/{name}"
            _write_new(temp / archive_path, data)
            file_records.append(
                {"path": archive_path, "bytes": len(data), "sha256": _sha256(data), "mode": 0o600}
            )

        effective_data = (json.dumps(units_before, sort_keys=True, indent=2) + "\n").encode()
        _write_new(temp / "host" / "systemd-effective.json", effective_data)
        file_records.append(
            {
                "path": "host/systemd-effective.json",
                "bytes": len(effective_data),
                "sha256": _sha256(effective_data),
                "mode": 0o600,
            }
        )
        checkpoint_names = ("source-analysis-state-v1.json", "source-analysis-state-v2.json")
        for filename in checkpoint_names:
            present = (root / filename).exists() or (root / filename).is_symlink()
            if present != (filename in state_bytes):
                raise SnapshotError("Veritas checkpoint set changed during capture")
        for filename in state_bytes:
            data, info = _read_file(
                root / filename,
                maximum=MAX_CHECKPOINT_BYTES,
                label="Veritas checkpoint consistency check",
            )
            if data != state_bytes[filename]:
                raise SnapshotError("Veritas checkpoint changed during capture")
            before = state_stats[filename]
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
                info.st_dev,
                info.st_ino,
                info.st_mtime_ns,
            ):
                raise SnapshotError("Veritas checkpoint identity changed during capture")
        if summary_data is not None:
            summary_after, _ = _read_file(
                summary_path,
                maximum=MAX_SMALL_FILE_BYTES,
                label="Veritas summary consistency check",
            )
            if summary_after != summary_data:
                raise SnapshotError("Veritas research summary changed during capture")
        _source_lock_is_free(root)
        units_after = _unit_properties(systemd_units)
        for unit, values in units_before.items():
            if values.get("ExecMainStartTimestampMonotonic") != units_after.get(unit, {}).get(
                "ExecMainStartTimestampMonotonic"
            ):
                raise SnapshotError("Veritas analysis service ran during checkpoint capture")
            if (
                unit.endswith(".service")
                and "source-analysis" in unit
                and units_after.get(unit, {}).get("ActiveState")
                in {"active", "activating", "reloading"}
            ):
                raise SnapshotError("Veritas source-analysis service became active during capture")

        ledger_info = {
            "event_count": max_count,
            "event_bytes": total_event_bytes,
            "last_chain_sha256": None if not max_count else chain,
        }
        files = sorted(file_records, key=lambda item: item["path"])
        manifest = {
            "format": "midas-veritas-analysis-snapshot",
            "format_version": FORMAT_VERSION,
            "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_root": str(root),
            "authoritative_checkpoint": authoritative,
            "checkpoints": {
                name: {
                    "schema_version": state["schema_version"],
                    "state_sha256": state["state_sha256"],
                    "processed_segment_count": state["processed_segment_count"],
                    "last_ordinal": state.get("last_ordinal"),
                    "last_event_sha256": state.get("last_event_sha256"),
                    "campaign_id": state["campaign_id"],
                    "campaign_sha256": state["campaign_sha256"],
                    "analysis_code_sha256": state["analysis_code_sha256"],
                    "analysis_code_files": state["analysis_code_files"],
                }
                for name, state in states.items()
            },
            "ledger": ledger_info,
            "research_summary": summary_info,
            "timer_gap_seconds_at_start": gap_seconds,
            "systemd_units": units_before,
            "systemd_config": config_records,
            "credentials_included": False,
            "files": files,
        }
        manifest_data = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        _write_new(temp / "manifest.json", manifest_data)
        _write_new(temp / "manifest.sha256", (_sha256(manifest_data) + "\n").encode())
        for path in (temp, temp / "checkpoints", ledger, temp / "source-analysis-events"):
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        verify_snapshot(temp)
        _publish_directory(temp, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return manifest
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def verify_snapshot(directory: Path) -> dict[str, Any]:
    directory = directory.absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise SnapshotError("Veritas snapshot directory is missing or unsafe")
    manifest_data, _ = _read_file(
        directory / "manifest.json", maximum=MAX_SMALL_FILE_BYTES, label="Veritas manifest"
    )
    checksum_data, _ = _read_file(
        directory / "manifest.sha256", maximum=256, label="Veritas manifest checksum"
    )
    try:
        manifest = json.loads(manifest_data)
    except json.JSONDecodeError as error:
        raise SnapshotError("Veritas manifest is malformed") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "midas-veritas-analysis-snapshot"
        or manifest.get("format_version") != FORMAT_VERSION
        or checksum_data.decode("ascii", errors="replace").strip() != _sha256(manifest_data)
    ):
        raise SnapshotError("Veritas manifest format or checksum is invalid")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise SnapshotError("Veritas manifest file inventory is malformed")
    expected: dict[str, dict[str, Any]] = {}
    for item in raw_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise SnapshotError("Veritas manifest file inventory is malformed")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in expected:
            raise SnapshotError("Veritas manifest contains an unsafe or duplicate path")
        expected[relative.as_posix()] = item
    states: dict[str, dict[str, Any]] = {}
    for filename in ("source-analysis-state-v1.json", "source-analysis-state-v2.json"):
        path = directory / "checkpoints" / filename
        if path.exists():
            states[filename] = _read_checkpoint(path)[0]
    recorded_states = manifest.get("checkpoints")
    if not states or not isinstance(recorded_states, dict) or set(recorded_states) != set(states):
        raise SnapshotError("Veritas manifest checkpoint inventory does not match the snapshot")
    for filename, state in states.items():
        record = recorded_states[filename]
        if (
            not isinstance(record, dict)
            or record.get("state_sha256") != state.get("state_sha256")
            or record.get("processed_segment_count") != state.get("processed_segment_count")
            or record.get("analysis_code_sha256") != state.get("analysis_code_sha256")
        ):
            raise SnapshotError(f"Veritas manifest checkpoint lineage differs: {filename}")
    authoritative = manifest.get("authoritative_checkpoint")
    if authoritative not in states:
        raise SnapshotError("Veritas manifest authoritative checkpoint is missing")
    state = states[authoritative]
    if (
        len(
            {
                (item.get("campaign_id"), item.get("campaign_sha256"), item.get("analysis_version"))
                for item in states.values()
            }
        )
        != 1
    ):
        raise SnapshotError("Veritas checkpoint files disagree about campaign provenance")

    maximum_count = max(int(item["processed_segment_count"]) for item in states.values())
    checkpoint_counts: dict[int, dict[str, Any]] = {}
    for item in states.values():
        count = int(item["processed_segment_count"])
        if count in checkpoint_counts and checkpoint_counts[count].get(
            "last_event_sha256"
        ) != item.get("last_event_sha256"):
            raise SnapshotError("Veritas checkpoint files disagree about the same event prefix")
        checkpoint_counts[count] = item
    migrated = states.get("source-analysis-state-v2.json", {}).get("migration")
    legacy = states.get("source-analysis-state-v1.json")
    if (
        migrated is not None
        and legacy is not None
        and (
            not isinstance(migrated, dict)
            or migrated.get("from_state_schema_version") != 1
            or migrated.get("from_state_sha256") != legacy.get("state_sha256")
            or migrated.get("from_processed_segment_count") != legacy.get("processed_segment_count")
            or migrated.get("from_analysis_code_sha256") != legacy.get("analysis_code_sha256")
        )
    ):
        raise SnapshotError("v2 checkpoint migration lineage differs from the preserved v1 state")
    observed: set[str] = set()
    ledger_seen = False
    event_count = 0
    event_bytes = 0
    event_chain = "0" * 64
    for current, directories, filenames in os.walk(directory, followlinks=False):
        parent = Path(current)
        directories.sort()
        filenames.sort()
        relative_directory = parent.relative_to(directory).as_posix()
        if relative_directory == "source-analysis-events/v1":
            ledger_seen = True
        for dirname in directories:
            if (parent / dirname).is_symlink():
                raise SnapshotError("Veritas snapshot contains a symlink directory")
        for filename in filenames:
            path = parent / filename
            rel = path.relative_to(directory).as_posix()
            if rel in {"manifest.json", "manifest.sha256"}:
                continue
            if path.is_symlink() or not path.is_file() or rel not in expected:
                raise SnapshotError("Veritas snapshot contains an unmanifested or unsafe file")
            data, info = _read_file(path, maximum=MAX_LEDGER_BYTES, label="Veritas snapshot file")
            item = expected[rel]
            if info.st_size != item.get("bytes") or _sha256(data) != item.get("sha256"):
                raise SnapshotError(f"Veritas snapshot file checksum mismatch: {rel}")
            if relative_directory == "source-analysis-events/v1":
                match = re.fullmatch(r"([0-9]{20})\.json", filename)
                if match is None:
                    raise SnapshotError("Veritas snapshot contains a noncanonical event filename")
                event_count += 1
                if int(match.group(1)) != event_count:
                    raise SnapshotError("Veritas event filenames are missing or out of sequence")
                event = _event_value(data, index=event_count)
                for key in ("campaign_id", "campaign_sha256", "analysis_version"):
                    if event.get(key) != state.get(key):
                        raise SnapshotError(
                            f"Veritas event {event_count} differs from checkpoint {key}"
                        )
                event_bytes += len(data)
                if event_bytes > MAX_LEDGER_BYTES:
                    raise SnapshotError("Veritas snapshot event ledger exceeds its size bound")
                event_chain = _sha256(
                    bytes.fromhex(event_chain) + bytes.fromhex(event["analysis_event_sha256"])
                )
                checkpoint = checkpoint_counts.get(event_count)
                if checkpoint and checkpoint.get("last_event_sha256") != event_chain:
                    raise SnapshotError("Veritas checkpoint does not match its event chain")
            observed.add(rel)
    if observed != set(expected):
        raise SnapshotError("Veritas snapshot is missing one or more manifest files")
    if not ledger_seen or event_count != maximum_count:
        raise SnapshotError("Veritas snapshot event count differs from its checkpoint")
    if any(
        (count == 0 and item.get("last_event_sha256") not in (None, ""))
        or (count > 0 and count == maximum_count and item.get("last_event_sha256") != event_chain)
        for count, item in (
            (int(value["processed_segment_count"]), value) for value in states.values()
        )
    ):
        raise SnapshotError("Veritas snapshot checkpoint chain is inconsistent")
    ledger = {
        "event_count": event_count,
        "event_bytes": event_bytes,
        "last_chain_sha256": None if not event_count else event_chain,
    }
    if ledger != manifest.get("ledger"):
        raise SnapshotError("Veritas snapshot ledger summary differs from its manifest")
    campaign, _ = _read_file(
        directory / "provenance" / "campaign.json",
        maximum=MAX_SMALL_FILE_BYTES,
        label="archived Veritas campaign",
    )
    if _sha256(campaign) != state.get("campaign_sha256"):
        raise SnapshotError("archived campaign does not match checkpoint provenance")
    for code_name, digest in state["analysis_code_files"].items():
        code_data, _ = _read_file(
            directory / _code_archive_path(code_name),
            maximum=MAX_SMALL_FILE_BYTES,
            label="archived Veritas runtime code",
        )
        if _sha256(code_data) != digest:
            raise SnapshotError(f"archived runtime code digest does not match: {code_name}")
    if manifest.get("credentials_included") is not False:
        raise SnapshotError("Veritas snapshot does not confirm credential exclusion")
    summary_info = manifest.get("research_summary", {})
    if summary_info.get("included") and summary_info.get("seal_valid"):
        summary_data, _ = _read_file(
            directory / "provenance" / "source-research-summary.json",
            maximum=MAX_SMALL_FILE_BYTES,
            label="archived Veritas research summary",
        )
        summary = _sealed(
            summary_data,
            key="summary_sha256",
            maximum=MAX_SMALL_FILE_BYTES,
            label="archived Veritas research summary",
        )
        if summary.get("summary_sha256") != summary_info.get("summary_sha256"):
            raise SnapshotError("archived summary digest differs from capture manifest")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--source-root", type=Path, required=True)
    capture.add_argument("--destination", type=Path, required=True)
    capture.add_argument("--module-root", type=Path, required=True)
    capture.add_argument("--script-root", type=Path, required=True)
    capture.add_argument("--campaign", type=Path, required=True)
    capture.add_argument("--unit", action="append", default=[])
    capture.add_argument("--unit-config", type=Path, action="append", default=[])
    capture.add_argument("--minimum-timer-gap-seconds", type=int, default=900)
    verify = commands.add_parser("verify")
    verify.add_argument("--snapshot", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "verify":
            result = verify_snapshot(args.snapshot)
        else:
            result = create_snapshot(
                source_root=args.source_root,
                destination=args.destination,
                module_root=args.module_root,
                script_root=args.script_root,
                campaign_path=args.campaign,
                systemd_units=args.unit,
                systemd_config_paths=args.unit_config,
                minimum_timer_gap_seconds=args.minimum_timer_gap_seconds,
            )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (SnapshotError, OSError, ValueError, KeyError) as error:
        print(f"midas-veritas-snapshot: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
