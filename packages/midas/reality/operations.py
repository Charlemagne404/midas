"""Read-only capacity inspection and bounded, non-destructive raw archival.

These jobs never acquire the recorder writer lock or read an active segment.
Forecasts describe observed compressed growth, not guaranteed future capacity.
"""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import logging
import math
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import Config
from .replay import replay
from .storage import (
    _HashingReader,
    _record_stream,
    atomic_json,
    canonical,
    describe,
    file_hash,
    manifest,
    records,
)

CAPACITY_WARNING_SECONDS = 30 * 86400
CAPACITY_CRITICAL_SECONDS = 14 * 86400
CAPACITY_ACTION_SECONDS = 7 * 86400
CAPACITY_GROWTH_WINDOWS_SECONDS = (6 * 3600, 24 * 3600)
ARCHIVE_IO_FULL_AVG10_MAX = 2.0
ARCHIVE_IO_FULL_AVG60_MAX = 2.0
ARCHIVE_IO_SAMPLE_SECONDS = 5.0
ARCHIVE_IO_STABLE_SECONDS = 60.0
ARCHIVE_REQUIRED_PROTECTED_SERVICES = {"midas-reality.service"}
ARCHIVE_HOST_IO_FULL_AVG10_MAX = 2.0
ARCHIVE_HOST_IO_FULL_AVG60_MAX = 2.0
ARCHIVE_SYNC_BATCH_BYTES = 32 * 1024**2
ARCHIVE_ADVISORY_LOG_INTERVAL_SECONDS = 60.0
_ARCHIVE_LAST_HOST_ADVISORY_NOTICE = 0.0


def _host_io_full_pressure() -> tuple[float, float]:
    values = {}
    for line in Path("/proc/pressure/io").read_text().splitlines():
        label, _, fields_text = line.partition(" ")
        fields = dict(part.split("=", 1) for part in fields_text.split() if "=" in part)
        if label in {"some", "full"}:
            values[label] = fields
    if not {"some", "full"}.issubset(values):
        raise RuntimeError("Host I/O pressure telemetry is unavailable")
    avg10 = float(values["full"]["avg10"])
    avg60 = float(values["full"]["avg60"])
    if not math.isfinite(avg10) or not math.isfinite(avg60):
        raise RuntimeError("Host I/O pressure telemetry is invalid")
    return avg10, avg60


def _current_cgroup_directory() -> Path:
    for line in Path("/proc/self/cgroup").read_text().splitlines():
        hierarchy, controllers, relative_path = line.split(":", 2)
        if hierarchy == "0" and not controllers:
            directory = Path("/sys/fs/cgroup") / relative_path.lstrip("/")
            if not directory.is_dir():
                raise RuntimeError("Current cgroup telemetry is unavailable")
            return directory
    raise RuntimeError("Unified cgroup telemetry is unavailable")


def _read_cgroup_io_full_pressure(path: Path) -> tuple[float, float]:
    values = {}
    for line in path.read_text().splitlines():
        label, _, fields_text = line.partition(" ")
        fields = dict(part.split("=", 1) for part in fields_text.split() if "=" in part)
        if label in {"some", "full"}:
            values[label] = fields
    if not {"some", "full"}.issubset(values):
        raise RuntimeError(f"I/O pressure telemetry is unavailable: {path}")
    avg10 = float(values["full"]["avg10"])
    avg60 = float(values["full"]["avg60"])
    if not math.isfinite(avg10) or not math.isfinite(avg60):
        raise RuntimeError(f"I/O pressure telemetry is invalid: {path}")
    return avg10, avg60


def sync_filesystem(path: Path) -> None:
    """Durably flush one destination filesystem without syncing unrelated mounts."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        syncfs = getattr(libc, "syncfs", None)
        if syncfs is None:
            raise OSError("syncfs is unavailable on this platform")
        syncfs.argtypes = [ctypes.c_int]
        syncfs.restype = ctypes.c_int
        if syncfs(descriptor) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(path))
    finally:
        os.close(descriptor)


def _active_midas_service_io_pressure() -> dict[str, tuple[float, float]]:
    """Return I/O pressure for active MIDAS services beside the archive unit."""
    archive_cgroup = _current_cgroup_directory()
    if archive_cgroup.name != "midas-reality-archive.service":
        raise RuntimeError("Archive must run in its dedicated systemd service cgroup")
    service_parent = archive_cgroup.parent
    protected: dict[str, tuple[float, float]] = {}
    discovered: set[str] = set()
    for service_cgroup in service_parent.glob("midas-*.service"):
        if not service_cgroup.is_dir() or service_cgroup.name == archive_cgroup.name:
            continue
        name = service_cgroup.name
        discovered.add(name)
        events = dict(
            line.split(maxsplit=1)
            for line in (service_cgroup / "cgroup.events").read_text().splitlines()
            if " " in line
        )
        if events.get("populated") != "1":
            continue
        protected[name] = _read_cgroup_io_full_pressure(service_cgroup / "io.pressure")
    missing = ARCHIVE_REQUIRED_PROTECTED_SERVICES - discovered
    if missing:
        raise RuntimeError(
            "Required protected service cgroup is unavailable: " + ", ".join(sorted(missing))
        )
    if any(name not in protected for name in ARCHIVE_REQUIRED_PROTECTED_SERVICES):
        raise RuntimeError("Protected Reality recorder cgroup is not populated")
    return protected


def wait_for_archive_io_window(deadline: float, *, stable_seconds: float = 0) -> None:
    """Wait for active MIDAS service pressure to clear; report host PSI as advisory."""
    global _ARCHIVE_LAST_HOST_ADVISORY_NOTICE
    required_samples = max(1, math.ceil(stable_seconds / ARCHIVE_IO_SAMPLE_SECONDS))
    stable_samples = 0
    last_notice = 0.0
    while True:
        service_pressure = _active_midas_service_io_pressure()
        pressured = {
            name: values
            for name, values in service_pressure.items()
            if values[0] >= ARCHIVE_IO_FULL_AVG10_MAX or values[1] >= ARCHIVE_IO_FULL_AVG60_MAX
        }
        try:
            host_pressure: tuple[float, float] | None = _host_io_full_pressure()
        except (OSError, RuntimeError, ValueError):
            host_pressure = None
        host_advisory = host_pressure is not None and (
            host_pressure[0] >= ARCHIVE_HOST_IO_FULL_AVG10_MAX
            or host_pressure[1] >= ARCHIVE_HOST_IO_FULL_AVG60_MAX
        )
        now = time.monotonic()
        if not pressured:
            stable_samples += 1
            if stable_samples >= required_samples:
                if host_advisory and now - _ARCHIVE_LAST_HOST_ADVISORY_NOTICE >= (
                    ARCHIVE_ADVISORY_LOG_INTERVAL_SECONDS
                ):
                    logging.warning(
                        "Archive admitted with host-wide I/O PSI above advisory threshold: %s",
                        host_pressure,
                    )
                    _ARCHIVE_LAST_HOST_ADVISORY_NOTICE = now
                return
        else:
            stable_samples = 0
        if now >= deadline:
            raise TimeoutError(
                "Archive I/O admission window did not clear before its configured deadline"
            )
        if now - last_notice >= 60:
            logging.warning(
                "Archive waiting for MIDAS service I/O headroom: "
                "pressured=%s; host full PSI is advisory=%s",
                pressured,
                host_pressure,
            )
            last_notice = now
        time.sleep(ARCHIVE_IO_SAMPLE_SECONDS)


def _last_started_setting(
    root: Path, configured_value: int, status: dict[str, Any], key: str
) -> tuple[int, str]:
    """Use the last-started collector setting until status confirms a change."""
    observed: list[tuple[str, int]] = []
    status_config = status.get("config")
    if isinstance(status_config, dict):
        value = status_config.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            observed.append(("collector_status", value))
    startup_path = root / "config.json"
    if startup_path.is_file():
        try:
            startup_config = json.loads(startup_path.read_text())
        except (OSError, json.JSONDecodeError):
            startup_config = {}
        if isinstance(startup_config, dict):
            value = startup_config.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                observed.append(("startup_config", value))
    if not observed:
        return configured_value, "configured_fallback"
    # If status and its startup receipt disagree, use the lower known limit until reconciled.
    effective = min(value for _, value in observed)
    source = "+".join(name for name, value in observed if value == effective)
    return effective, source


def _last_started_budget(
    root: Path, configured_budget: int, status: dict[str, Any]
) -> tuple[int, str]:
    return _last_started_setting(root, configured_budget, status, "budget_bytes")


def _archive_directory_usage(
    destination: Path, segments: list[dict[str, Any]] | None
) -> tuple[int, bool]:
    """Count a verified archive from catalog sizes without statting every HDD segment."""
    if not destination.is_dir():
        return 0, True
    entries = {entry.name: entry for entry in os.scandir(destination)}
    segment_map = (
        {info["file"]: info for info in segments if isinstance(info, dict)}
        if segments is not None
        else {}
    )
    inventory_valid = segments is not None and len(segment_map) == len(segments)
    used = 0
    if segments is not None:
        for name, info in segment_map.items():
            entry = entries.get(name)
            size = info.get("bytes")
            if (
                entry is None
                or entry.is_symlink()
                or not entry.is_file(follow_symlinks=False)
                or type(size) is not int
                or size < 0
            ):
                inventory_valid = False
                continue
            used += size
    for name, entry in entries.items():
        if name in segment_map:
            continue
        if name.endswith(".seg") and segments is not None:
            inventory_valid = False
        if entry.is_symlink():
            inventory_valid = False
        elif entry.is_file(follow_symlinks=False):
            used += entry.stat(follow_symlinks=False).st_size
        elif segments is not None:
            inventory_valid = False
    return used, inventory_valid


def archive_capacity(
    root: Path,
    destination: Path,
    mountpoint: Path,
    *,
    budget: int,
    reserve: int,
    bytes_per_second: float | None,
    segment_bytes: int,
) -> dict[str, Any]:
    """Report archive-volume capacity without treating a manifest as an integrity audit."""
    if budget <= 0 or reserve <= 0 or segment_bytes <= 0:
        raise ValueError("Archive budget, reserve, and segment size must be positive")
    root, destination, mountpoint = root.resolve(), destination.resolve(), mountpoint.resolve()
    alerts: list[str] = []
    mounted = mountpoint.is_mount()
    same_as_raw = root.stat().st_dev == mountpoint.stat().st_dev if mountpoint.exists() else False
    destination_on_mount = (
        destination.exists() and destination.stat().st_dev == mountpoint.stat().st_dev
        if mountpoint.exists()
        else False
    )
    manifest_path = destination / "manifest.json"
    manifest_exists = manifest_path.exists() or manifest_path.is_symlink()
    manifest_present = manifest_path.is_file() and not manifest_path.is_symlink()
    manifest_value: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    manifest_provenance_valid: bool | None = False if manifest_exists else None
    if manifest_present:
        try:
            parsed = json.loads(manifest_path.read_text())
            if isinstance(parsed, dict):
                manifest_value = parsed
                candidate = parsed.get("archival_provenance")
                if isinstance(candidate, dict):
                    provenance = candidate
                segments = parsed.get("segments")
                manifest_provenance_valid = bool(
                    isinstance(segments, list)
                    and provenance.get("recording_root") == str(root)
                    and provenance.get("source_manifest_sha256") == file_hash_list(segments)
                    and provenance.get("originals_deleted") is False
                    and provenance.get("active_segment_included") is False
                )
        except (OSError, ValueError, TypeError):
            manifest_provenance_valid = False
    catalog = manifest_value.get("segments")
    used, archive_inventory_valid = _archive_directory_usage(
        destination,
        catalog if manifest_provenance_valid and isinstance(catalog, list) else None,
    )
    if manifest_provenance_valid and not archive_inventory_valid:
        manifest_provenance_valid = False
        alerts.append("ARCHIVE_SEGMENT_INVENTORY_INVALID")
    if not manifest_exists:
        state = "NOT_YET_VERIFIED"
    elif manifest_provenance_valid:
        state = "MANIFEST_PRESENT"
    else:
        state = "INVALID_MANIFEST"
        alerts.append("ARCHIVE_MANIFEST_PROVENANCE_INVALID")
    if manifest_path.is_symlink():
        state = "INVALID_MANIFEST"
        manifest_provenance_valid = False
        alerts.append("ARCHIVE_MANIFEST_UNSAFE")
    verification_mode = provenance.get("verification_mode")
    if verification_mode is None and manifest_provenance_valid:
        verification_mode = "legacy_full_replay_receipt"
    archive_manifest_fields = dict(
        archive_manifest_provenance_valid=manifest_provenance_valid,
        archive_verification_mode=verification_mode,
        archive_full_verified_ns=provenance.get("full_verified_ns", provenance.get("verified_ns")),
        archive_full_verified_manifest_sha256=provenance.get(
            "full_verified_manifest_sha256",
            provenance.get("source_manifest_sha256")
            if verification_mode == "legacy_full_replay_receipt"
            else None,
        ),
        archive_full_verified_segment_count=provenance.get(
            "full_verified_segment_count",
            len(catalog)
            if verification_mode == "legacy_full_replay_receipt" and isinstance(catalog, list)
            else None,
        ),
        archive_full_verified_bytes=provenance.get(
            "full_verified_bytes",
            sum(info.get("bytes", 0) for info in catalog if isinstance(info, dict))
            if verification_mode == "legacy_full_replay_receipt" and isinstance(catalog, list)
            else None,
        ),
        archive_incremental_verified_ns=provenance.get("incremental_verified_ns"),
        archive_incremental_verified_segments=provenance.get("incremental_verified_segments"),
        archive_source_manifest_sha256=provenance.get("source_manifest_sha256"),
        archive_segment_count=len(catalog) if isinstance(catalog, list) else None,
    )
    if not mounted:
        alerts.append("ARCHIVE_MOUNT_UNAVAILABLE")
    elif not destination_on_mount:
        alerts.append("ARCHIVE_DESTINATION_OFF_EXPECTED_MOUNT")
    if same_as_raw:
        alerts.append("ARCHIVE_SHARES_RAW_FILESYSTEM")
    if not destination_on_mount or not mounted or same_as_raw:
        return dict(
            destination=str(destination),
            mountpoint=str(mountpoint),
            mounted=mounted,
            destination_on_expected_mount=destination_on_mount,
            separate_from_raw_filesystem=mounted and not same_as_raw,
            destination_state=state,
            **archive_manifest_fields,
            raw_archive_bytes=used,
            budget_bytes=budget,
            filesystem_free_bytes=None,
            filesystem_reserve_bytes=reserve,
            available_headroom_bytes=0,
            estimated_storage_seconds_remaining=None,
            alerts=alerts,
        )
    free = shutil.disk_usage(mountpoint).free
    headroom = min(budget - used, free - reserve)
    seconds = max(0, headroom) / bytes_per_second if bytes_per_second else None
    if headroom <= 0:
        alerts.append("ARCHIVE_CAPACITY_EXHAUSTED")
    elif budget - used < max(segment_bytes * 2, budget * 0.1):
        alerts.append("ARCHIVE_BUDGET_LOW")
    if free - reserve < segment_bytes * 2:
        alerts.append("ARCHIVE_DISK_RESERVE_LOW")
    if seconds is not None:
        if seconds <= CAPACITY_WARNING_SECONDS:
            alerts.append("ARCHIVE_CAPACITY_WARNING_WITHIN_THIRTY_DAYS")
        if seconds <= CAPACITY_CRITICAL_SECONDS:
            alerts.append("ARCHIVE_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS")
        if seconds <= CAPACITY_ACTION_SECONDS:
            alerts.append("ARCHIVE_CAPACITY_ACTION_WITHIN_SEVEN_DAYS")
    return dict(
        destination=str(destination),
        mountpoint=str(mountpoint),
        mounted=mounted,
        destination_on_expected_mount=destination_on_mount,
        separate_from_raw_filesystem=True,
        destination_state=state,
        **archive_manifest_fields,
        raw_archive_bytes=used,
        budget_bytes=budget,
        filesystem_free_bytes=free,
        filesystem_reserve_bytes=reserve,
        available_headroom_bytes=max(0, headroom),
        estimated_storage_seconds_remaining=seconds,
        alerts=alerts,
    )


def _trailing_segment_growth(
    root: Path, segments: list[dict[str, Any]], now_ns: int
) -> dict[str, dict[str, Any]]:
    """Estimate calendar-time growth from finalized files in rolling windows.

    Use filesystem timestamps only to select the window; never read old segment
    contents for the capacity trend. A short finalized-segment sample remains a
    separate burst signal. If the source clock is inconsistent, callers can fall
    back to that conservative sample.
    """
    oldest_mtime_ns: int | None = None
    timestamp_mismatch = False
    bytes_by_window = {seconds: 0 for seconds in CAPACITY_GROWTH_WINDOWS_SECONDS}
    segments_by_window = {seconds: 0 for seconds in CAPACITY_GROWTH_WINDOWS_SECONDS}

    for info in segments:
        name = str(info.get("file", ""))
        if Path(name).name != name:
            raise ValueError("Unsafe segment path in capacity growth window")
        segment = root / name
        catalog = segment.with_suffix(".json")
        if segment.is_symlink() or catalog.is_symlink():
            raise ValueError("Capacity growth window contains a symlink")
        segment_stat = segment.stat()
        catalog_stat = catalog.stat()
        if segment_stat.st_size != int(info["bytes"]):
            raise ValueError(f"Capacity growth size differs from catalog: {segment}")
        finalized_ns = max(segment_stat.st_mtime_ns, catalog_stat.st_mtime_ns)
        oldest_mtime_ns = (
            finalized_ns if oldest_mtime_ns is None else min(oldest_mtime_ns, finalized_ns)
        )
        if finalized_ns > now_ns + 60 * 10**9:
            timestamp_mismatch = True
        amount = segment_stat.st_size + catalog_stat.st_size
        for window_seconds in CAPACITY_GROWTH_WINDOWS_SECONDS:
            if finalized_ns >= now_ns - window_seconds * 10**9:
                bytes_by_window[window_seconds] += amount
                segments_by_window[window_seconds] += 1

    root_age_seconds = (
        max(0.0, (now_ns - oldest_mtime_ns) / 1e9) if oldest_mtime_ns is not None else 0.0
    )
    result: dict[str, dict[str, Any]] = {}
    for window_seconds in CAPACITY_GROWTH_WINDOWS_SECONDS:
        coverage_seconds = min(float(window_seconds), root_age_seconds)
        valid = not timestamp_mismatch and coverage_seconds >= 60
        rate = bytes_by_window[window_seconds] / coverage_seconds if valid else None
        label = "trailing_six_hours" if window_seconds == 6 * 3600 else "trailing_twenty_four_hours"
        result[label] = dict(
            window_seconds=window_seconds,
            coverage_seconds=coverage_seconds,
            finalized_segments=segments_by_window[window_seconds],
            bytes=bytes_by_window[window_seconds],
            bytes_per_second=rate,
            bytes_per_day=rate * 86400 if rate is not None else None,
            timestamp_state="future_timestamp_detected" if timestamp_mismatch else "valid",
        )
    return result


def capacity(
    config: Config,
    *,
    window_segments: int = 120,
    now_ns: int | None = None,
    forecast_floor_bytes_per_day: int = 0,
    archive_path: Path | None = None,
    archive_budget: int | None = None,
    archive_reserve: int | None = None,
    archive_mountpoint: Path | None = None,
) -> dict[str, Any]:
    if not 2 <= window_segments <= 2000:
        raise ValueError("Sample must contain 2..2000 finalized segments")
    if forecast_floor_bytes_per_day < 0:
        raise ValueError("Forecast floor must be nonnegative")
    root = Path(config.root)
    source = manifest(root)
    sample = source["segments"][-window_segments:]
    first = last = previous_ns = previous_frame_ns = None
    raw_bytes = frames = sampled_bytes = 0
    clock_regressions = receipt_regressions = 0
    oldest = None
    if source["segments"]:
        name = source["segments"][0]["file"]
        if Path(name).name != name:
            raise ValueError("Unsafe segment path")
        first_record = next(records(root / name), None)
        if first_record:
            oldest = first_record[0]["received_ns"]
    for info in sample:
        if Path(info["file"]).name != info["file"]:
            raise ValueError("Unsafe segment path")
        path = root / info["file"]
        if describe(path) != info:
            raise ValueError(f"Capacity sample integrity mismatch: {path}")
        sampled_bytes += info["bytes"] + path.with_suffix(".json").stat().st_size
        for record, _ in records(path):
            received = record["received_ns"]
            first = received if first is None else min(first, received)
            last = received if last is None else max(last, received)
            if previous_ns is not None and received < previous_ns:
                receipt_regressions += 1
            previous_ns = received
            if record["kind"] == "frame":
                # WS dequeue frames are persisted synchronously and retain their arrival
                # order. Asynchronous independent HTTP results may be persisted later
                # than newer WS arrivals; that is not itself a UTC clock regression.
                if previous_frame_ns is not None and received < previous_frame_ns:
                    clock_regressions += 1
                previous_frame_ns = received
                frames += 1
                raw_bytes += len(record["payload"].encode())
    seconds = (last - first) / 1e9 if first is not None and last is not None else 0
    # Partial/very short or clock-regressing samples cannot support an exhaustion date.
    rate = sampled_bytes / seconds if seconds >= 60 and not clock_regressions else None
    forecast_floor = forecast_floor_bytes_per_day / 86400
    status_path = root / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    # Collection continues during sampling; measure status and capacity at the end.
    now = time.time_ns() if now_ns is None else now_ns
    growth_windows = _trailing_segment_growth(root, source["segments"], now)
    sustained_rates = [
        float(value["bytes_per_second"])
        for value in growth_windows.values()
        if value["bytes_per_second"] is not None
    ]
    if sustained_rates:
        forecast_rate = max(*sustained_rates, forecast_floor) or None
        forecast_basis = "maximum_of_trailing_six_hour_twenty_four_hour_and_configured_floor"
    else:
        # Keep a conservative fallback when filesystem timestamps cannot support
        # rolling windows (for example, a copied store with a mismatched clock).
        forecast_rate = max(rate or 0, forecast_floor) or None
        forecast_basis = (
            "maximum_of_recent_sample_and_configured_floor"
            if forecast_floor_bytes_per_day
            else "recent_sample_fallback_no_valid_growth_windows"
        )
    used = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
    free = shutil.disk_usage(root).free
    runtime_budget, budget_source = _last_started_budget(root, config.budget_bytes, status)
    budget_pending = runtime_budget != config.budget_bytes
    runtime_retention_days, retention_source = _last_started_setting(
        root, config.retention_days, status, "retention_days"
    )
    retention_pending = runtime_retention_days != config.retention_days
    headroom = min(runtime_budget - used, free - config.reserve_bytes)
    storage_seconds = max(0, headroom) / forecast_rate if forecast_rate else None
    measured_storage_seconds = max(0, headroom) / rate if rate else None
    configured_headroom = min(
        config.budget_bytes - used,
        free - config.reserve_bytes,
    )
    configured_storage_seconds = (
        max(0, configured_headroom) / forecast_rate if forecast_rate else None
    )
    data_age_seconds = (now - oldest) / 1e9 if oldest is not None else None
    retention_seconds = (
        max(0, runtime_retention_days * 86400 - data_age_seconds)
        if data_age_seconds is not None
        else None
    )
    configured_retention_seconds = (
        max(0, config.retention_days * 86400 - data_age_seconds)
        if data_age_seconds is not None
        else None
    )
    horizons = [x for x in (storage_seconds, retention_seconds) if x is not None]
    deadline = min(horizons) if horizons else None
    configured_horizons = [
        x for x in (configured_storage_seconds, configured_retention_seconds) if x is not None
    ]
    configured_deadline = min(configured_horizons) if configured_horizons else None
    burst_storage_seconds = max(0, headroom) / rate if rate else None
    burst_horizons = [
        value for value in (burst_storage_seconds, retention_seconds) if value is not None
    ]
    burst_deadline = min(burst_horizons) if burst_horizons else None
    alerts = []
    if budget_pending:
        alerts.append("BUDGET_CHANGE_PENDING_RESTART")
    if retention_pending:
        alerts.append("RETENTION_CHANGE_PENDING_RESTART")
    if headroom <= 0:
        alerts.append("CAPACITY_EXHAUSTED")
    elif runtime_budget - used < max(config.segment_bytes * 2, runtime_budget * 0.1):
        alerts.append("BUDGET_LOW")
    if free - config.reserve_bytes < config.segment_bytes * 2:
        alerts.append("DISK_RESERVE_LOW")
    if deadline is not None:
        if deadline <= CAPACITY_WARNING_SECONDS:
            alerts.append("CAPACITY_WARNING_WITHIN_THIRTY_DAYS")
        if deadline <= CAPACITY_CRITICAL_SECONDS:
            alerts.append("CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS")
        if deadline <= CAPACITY_ACTION_SECONDS:
            alerts.append("CAPACITY_ACTION_WITHIN_SEVEN_DAYS")
    if retention_seconds == 0:
        alerts.append("RETENTION_HORIZON_REACHED")
    if burst_deadline is not None:
        if burst_deadline <= CAPACITY_WARNING_SECONDS:
            alerts.append("SHORT_WINDOW_CAPACITY_WARNING_WITHIN_THIRTY_DAYS")
        if burst_deadline <= CAPACITY_CRITICAL_SECONDS:
            alerts.append("SHORT_WINDOW_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS")
        if burst_deadline <= CAPACITY_ACTION_SECONDS:
            alerts.append("SHORT_WINDOW_CAPACITY_ACTION_WITHIN_SEVEN_DAYS")
    if rate is None:
        alerts.append("RATE_INSUFFICIENT_EVIDENCE")
    archive_report = None
    if any(
        value is not None
        for value in (archive_path, archive_budget, archive_reserve, archive_mountpoint)
    ):
        if (
            archive_path is None
            or archive_budget is None
            or archive_reserve is None
            or archive_mountpoint is None
        ):
            raise ValueError("Archive monitoring requires path, budget, reserve, and mountpoint")
        archive_report = archive_capacity(
            root,
            archive_path,
            archive_mountpoint,
            budget=archive_budget,
            reserve=archive_reserve,
            bytes_per_second=forecast_rate,
            segment_bytes=config.segment_bytes,
        )
        alerts.extend(archive_report["alerts"])
    age = (now - status["updated_ns"]) / 1e9 if "updated_ns" in status else None
    if age is None or age < 0 or age > 10:
        alerts.append("COLLECTOR_STATUS_STALE")
    return dict(
        schema_version=1,
        capacity_builder_version="receipt-aware-capacity-v4-split-archive-volume",
        capacity_builder_sha256=file_hash(Path(__file__)),
        measured_ns=now,
        recording_root=str(root),
        raw_root_bytes=used,
        budget_bytes=runtime_budget,
        effective_budget_bytes=runtime_budget,
        configured_budget_bytes=config.budget_bytes,
        budget_source=budget_source,
        budget_change_pending_restart=budget_pending,
        retention_days=runtime_retention_days,
        effective_retention_days=runtime_retention_days,
        configured_retention_days=config.retention_days,
        retention_source=retention_source,
        retention_change_pending_restart=retention_pending,
        filesystem_free_bytes=free,
        free_disk_reserve_bytes=config.reserve_bytes,
        available_headroom_bytes=max(0, headroom),
        configured_available_headroom_bytes=max(0, configured_headroom),
        sample=dict(
            segments=len(sample),
            first_received_ns=first,
            last_received_ns=last,
            seconds=seconds,
            compressed_and_catalog_bytes=sampled_bytes,
            raw_frame_payload_bytes=raw_bytes,
            raw_frames=frames,
            clock_regressions=clock_regressions,
            record_receipt_regressions=receipt_regressions,
            clock_assessment_basis="sequential WebSocket dequeue frames; deferred HTTP timestamps remain separate",
            source_sha256=file_hash_list(sample),
        ),
        growth_windows=growth_windows,
        compressed_bytes_per_second=rate,
        estimated_bytes_per_day=rate * 86400 if rate else None,
        forecast_floor_bytes_per_day=forecast_floor_bytes_per_day,
        forecast_bytes_per_day=forecast_rate * 86400 if forecast_rate else None,
        forecast_basis=forecast_basis,
        estimated_storage_seconds_remaining=storage_seconds,
        measured_storage_seconds_remaining=measured_storage_seconds,
        retention_seconds_remaining=retention_seconds,
        configured_estimated_storage_seconds_remaining=configured_storage_seconds,
        configured_retention_seconds_remaining=configured_retention_seconds,
        effective_capacity_runway_seconds=deadline,
        effective_capacity_runway_days=deadline / 86400 if deadline is not None else None,
        short_window_capacity_runway_seconds=burst_deadline,
        short_window_capacity_runway_days=(
            burst_deadline / 86400 if burst_deadline is not None else None
        ),
        configured_capacity_runway_seconds=configured_deadline,
        configured_capacity_runway_days=(
            configured_deadline / 86400 if configured_deadline is not None else None
        ),
        estimated_action_deadline_ns=int(now + deadline * 1e9) if deadline is not None else None,
        collector_state=status.get("state", "UNKNOWN"),
        collector_status_age_seconds=age,
        archive_capacity=archive_report,
        alerts=alerts,
        limitations=[
            "Recent finalized-segment rate includes gaps and metadata; future rates vary.",
            "Active segment excluded from rate, included in root usage.",
            "Raw originals never pruned. Retention horizon stops collection.",
            "Capacity metadata does not perform full archive integrity verification.",
            "Local archive copies consume a separately accounted filesystem allocation; they are not off-host redundancy.",
        ],
    )


def file_hash_list(segments: list[dict[str, Any]]) -> str:
    import hashlib

    return hashlib.sha256(canonical(segments)).hexdigest()


def _inspect_segment(
    path: Path,
    expected: dict[str, Any],
    *,
    previous_ordinal: int,
    copy_to: Any | None = None,
) -> dict[str, Any]:
    """Validate framing, checksums, catalog metadata, and cross-segment ordinals."""
    first = last = count = 0
    kinds: dict[str, int] = {}
    digest = hashlib.sha256()
    with path.open("rb") as source:
        reader = _HashingReader(source, digest, copy_to)
        for record, _ in _record_stream(reader, path):
            ordinal = record.get("ordinal")
            if type(ordinal) is not int or ordinal != previous_ordinal + 1:
                raise ValueError(f"Non-contiguous archive segment ordinal: {path.name}")
            previous_ordinal = ordinal
            first = first or ordinal
            last = ordinal
            count += 1
            kind = record.get("kind")
            if not isinstance(kind, str):
                raise ValueError(f"Invalid archive record kind: {path.name}")
            kinds[kind] = kinds.get(kind, 0) + 1
    actual = dict(
        schema_version=1,
        file=expected["file"],
        sha256=digest.hexdigest(),
        bytes=path.stat().st_size,
        first=first,
        last=last,
        count=count,
        kinds=kinds,
    )
    if actual != expected:
        raise ValueError(f"Archive segment integrity mismatch: {path}")
    return actual


def _validate_catalog_ordinals(segments: list[dict[str, Any]]) -> None:
    previous = 0
    seen_names: set[str] = set()
    for info in segments:
        name = info.get("file") if isinstance(info, dict) else None
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Unsafe archive segment path")
        if name in seen_names:
            raise ValueError("Duplicate archive segment path")
        seen_names.add(name)
        count = info.get("count")
        first = info.get("first")
        last = info.get("last")
        if type(count) is not int or type(first) is not int or type(last) is not int:
            raise ValueError("Invalid archive segment ordinal metadata")
        if count == 0:
            if first != 0 or last != 0:
                raise ValueError("Invalid empty archive segment metadata")
            continue
        if count < 0 or first != previous + 1 or last != first + count - 1:
            raise ValueError("Non-contiguous archive catalog ordinals")
        previous = last


def _last_catalog_ordinal(segments: list[dict[str, Any]]) -> int:
    for info in reversed(segments):
        if info.get("count", 0):
            return int(info["last"])
    return 0


def _archive_incremental_suffix(
    root: Path,
    destination: Path,
    value: dict[str, Any],
    *,
    previous: dict[str, Any],
    budget: int,
    reserve: int,
    before_segment: Callable[[], None] | None,
) -> dict[str, Any]:
    """Extend a full-verified archive without random-reading its old segment files."""
    previous_segments = previous.get("segments")
    previous_provenance = previous.get("archival_provenance")
    current_segments = value.get("segments")
    if not isinstance(previous_segments, list) or not isinstance(previous_provenance, dict):
        raise ValueError("Existing archive has no verified provenance")
    if not isinstance(current_segments, list):
        raise ValueError("Current source catalog is malformed")
    previous_hash = file_hash_list(previous_segments)
    if previous_provenance.get("source_manifest_sha256") != previous_hash:
        raise ValueError("Existing archive source-manifest identity is invalid")
    if previous_provenance.get("recording_root") != str(root):
        raise ValueError("Existing archive belongs to a different recording root")
    if previous_provenance.get("originals_deleted") is not False:
        raise ValueError("Existing archive does not certify preserved originals")
    if previous_provenance.get("active_segment_included") is not False:
        raise ValueError("Existing archive includes an unsupported active segment")
    _validate_catalog_ordinals(previous_segments)
    _validate_catalog_ordinals(current_segments)
    previous_by_name = {info["file"]: info for info in previous_segments}
    current_by_name = {info["file"]: info for info in current_segments}
    if len(previous_by_name) != len(previous_segments):
        raise ValueError("Existing archive catalog contains duplicate segment paths")
    if len(current_by_name) != len(current_segments):
        raise ValueError("Current source catalog contains duplicate segment paths")
    if not previous_by_name.keys() <= current_by_name.keys():
        raise ValueError("Current source catalog lost previously archived segments")
    if any(current_by_name[name] != info for name, info in previous_by_name.items()):
        raise ValueError("Current source catalog changed a previously archived segment")

    source_names = {info["file"] for info in current_segments}
    destination_entries = {entry.name: entry for entry in os.scandir(destination)}
    destination_segment_names = {name for name in destination_entries if name.endswith(".seg")}
    for name in destination_segment_names:
        entry = destination_entries[name]
        if name not in source_names:
            raise ValueError(f"Archive contains an untracked segment: {name}")
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise ValueError(f"Archive segment is not a regular file: {name}")
    for name, entry in destination_entries.items():
        if name.endswith(".copying"):
            if Path(name).with_suffix(".seg").name not in source_names:
                raise ValueError(f"Archive contains an untracked partial segment: {name}")
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                raise ValueError(f"Unsafe interrupted archive segment: {name}")

    # Segment sizes come from the full-verified catalog. Stat only the handful of
    # non-segment files so daily runs avoid random inode reads across the archive HDD.
    used = sum(current_by_name[name]["bytes"] for name in destination_segment_names)
    for name, entry in destination_entries.items():
        if name in destination_segment_names:
            continue
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise ValueError(f"Unexpected non-file in archive directory: {name}")
        used += entry.stat(follow_symlinks=False).st_size
    pending: list[tuple[Path, Path]] = []
    pending_bytes = 0
    verified_segments = 0
    verified_bytes = 0

    def flush_pending() -> None:
        nonlocal pending_bytes
        if not pending:
            return
        if before_segment is not None:
            before_segment()
        sync_filesystem(destination)
        for partial_path, target_path in pending:
            if target_path.name in destination_segment_names:
                raise FileExistsError(f"Archive target appeared during publication: {target_path}")
            os.replace(partial_path, target_path)
            destination_entries.pop(partial_path.name, None)
            destination_segment_names.add(target_path.name)
        pending.clear()
        pending_bytes = 0

    def copy_missing(info: dict[str, Any], previous_ordinal: int) -> None:
        nonlocal used, pending_bytes, verified_segments, verified_bytes
        source = root / info["file"]
        target = destination / info["file"]
        partial = target.with_suffix(".copying")
        partial_entry = destination_entries.get(partial.name)
        if partial_entry is not None:
            if partial_entry.is_symlink() or not partial_entry.is_file(follow_symlinks=False):
                raise ValueError(f"Unsafe interrupted archive segment: {partial}")
            used -= partial_entry.stat(follow_symlinks=False).st_size
            partial.unlink()
            destination_entries.pop(partial.name, None)
        margin = len(canonical(value)) + 8192
        if used + info["bytes"] + margin > budget:
            raise OSError("Archive budget reached; originals preserved")
        if shutil.disk_usage(destination).free < reserve + info["bytes"] + margin:
            raise OSError("Archive free-disk reserve reached; originals preserved")
        with partial.open("xb") as outgoing:
            _inspect_segment(
                source,
                info,
                previous_ordinal=previous_ordinal,
                copy_to=outgoing,
            )
            outgoing.flush()
            os.fsync(outgoing.fileno())
        pending.append((partial, target))
        pending_bytes += info["bytes"]
        used += info["bytes"]
        verified_segments += 1
        verified_bytes += info["bytes"]

    for index, info in enumerate(previous_segments):
        if before_segment is not None and index % 128 == 0:
            before_segment()
        partial = (destination / info["file"]).with_suffix(".copying")
        partial_entry = destination_entries.get(partial.name)
        if partial_entry is not None and info["file"] in destination_segment_names:
            if partial_entry.is_symlink() or not partial_entry.is_file(follow_symlinks=False):
                raise ValueError(f"Unsafe interrupted archive segment: {partial}")
            used -= partial_entry.stat(follow_symlinks=False).st_size
            partial.unlink()
            destination_entries.pop(partial.name, None)
        prior_ordinal = (
            int(info["first"]) - 1
            if info["count"]
            else _last_catalog_ordinal(previous_segments[:index])
        )
        if info["file"] not in destination_segment_names:
            copy_missing(info, prior_ordinal)

    previous_ordinal = _last_catalog_ordinal(previous_segments)
    new_segments = [info for info in current_segments if info["file"] not in previous_by_name]
    for info in new_segments:
        if before_segment is not None:
            before_segment()
        if info["count"] and info["first"] != previous_ordinal + 1:
            raise ValueError("New archive segment does not continue the verified ordinal prefix")
        target = destination / info["file"]
        partial = target.with_suffix(".copying")
        if info["file"] in destination_segment_names:
            target_entry = destination_entries.get(target.name)
            if target_entry is not None and (
                target_entry.is_symlink() or not target_entry.is_file(follow_symlinks=False)
            ):
                raise ValueError(f"Unsafe new archive segment: {target}")
            partial_entry = destination_entries.get(partial.name)
            if partial_entry is not None:
                if partial_entry.is_symlink() or not partial_entry.is_file(follow_symlinks=False):
                    raise ValueError(f"Unsafe interrupted archive segment: {partial}")
                used -= partial_entry.stat(follow_symlinks=False).st_size
                partial.unlink()
                destination_entries.pop(partial.name, None)
            _inspect_segment(root / info["file"], info, previous_ordinal=previous_ordinal)
            _inspect_segment(target, info, previous_ordinal=previous_ordinal)
            verified_segments += 2
            verified_bytes += 2 * info["bytes"]
        else:
            copy_missing(info, previous_ordinal)
        if info["count"]:
            previous_ordinal = info["last"]
        if pending_bytes >= ARCHIVE_SYNC_BATCH_BYTES:
            flush_pending()
    flush_pending()

    verified_ns = time.time_ns()
    full_verified_ns = previous_provenance.get(
        "full_verified_ns", previous_provenance.get("verified_ns")
    )
    if type(full_verified_ns) is not int or full_verified_ns <= 0:
        raise ValueError("Existing archive lacks a full-verification timestamp")
    full_verified_manifest_sha256 = previous_provenance.get(
        "full_verified_manifest_sha256", previous_provenance.get("source_manifest_sha256")
    )
    if not isinstance(full_verified_manifest_sha256, str):
        raise ValueError("Existing archive lacks a full-verification source identity")
    published = dict(
        value,
        archival_provenance=dict(
            recording_root=str(root),
            verified_ns=verified_ns,
            full_verified_ns=full_verified_ns,
            full_verified_manifest_sha256=full_verified_manifest_sha256,
            full_verified_segment_count=previous_provenance.get(
                "full_verified_segment_count", len(previous_segments)
            ),
            full_verified_bytes=previous_provenance.get(
                "full_verified_bytes", sum(info["bytes"] for info in previous_segments)
            ),
            incremental_verified_ns=verified_ns,
            incremental_verified_segments=verified_segments,
            incremental_verified_bytes=verified_bytes,
            verification_mode="incremental_suffix",
            source_manifest_sha256=file_hash_list(current_segments),
            originals_deleted=False,
            active_segment_included=False,
        ),
    )
    prior_manifest_bytes = (destination / "manifest.json").stat().st_size
    manifest_bytes = len(canonical(published))
    manifest_tmp = destination / "manifest.json.tmp"
    if manifest_tmp.is_symlink() or (manifest_tmp.exists() and not manifest_tmp.is_file()):
        raise ValueError("Archive manifest temporary file is unsafe")
    prior_tmp_bytes = manifest_tmp.stat().st_size if manifest_tmp.exists() else 0
    if used - prior_manifest_bytes - prior_tmp_bytes + manifest_bytes > budget:
        raise OSError("Archive publication exceeds budget; originals preserved")
    if shutil.disk_usage(destination).free < reserve + manifest_bytes:
        raise OSError("Archive publication reaches disk reserve; originals preserved")
    atomic_json(destination / "manifest.json", published)
    return published


def archive(
    root: Path,
    destination: Path,
    *,
    budget: int,
    reserve: int,
    resource_admission_timeout_seconds: float = 0,
    operation_timeout_seconds: float = 0,
    full_verify: bool = False,
) -> dict[str, Any]:
    """Copy finalized segments and verify appended bytes against prior provenance.

    The first publication fully replay-verifies source and destination. Later
    daily runs validate prior catalog identity, repair missing archived segments,
    and verify appended bytes without random-reading the full HDD prefix.
    ``full_verify`` replays both entire trees again. Interrupted copies resume
    from finalized files; original bytes and catalogs remain collector-owned.
    """
    root, destination = root.resolve(), destination.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Archive must be separate from raw recorder root")
    if budget <= 0 or reserve <= 0:
        raise ValueError("Archive budget and reserve must be positive")
    if (
        not math.isfinite(resource_admission_timeout_seconds)
        or resource_admission_timeout_seconds < 0
    ):
        raise ValueError("Archive resource-admission timeout must be finite and nonnegative")
    if not math.isfinite(operation_timeout_seconds) or operation_timeout_seconds < 0:
        raise ValueError("Archive operation timeout must be finite and nonnegative")
    operation_deadline = (
        time.monotonic() + operation_timeout_seconds if operation_timeout_seconds else None
    )
    before_segment: Callable[[], None] | None = None
    if resource_admission_timeout_seconds:
        initial_deadline = time.monotonic() + resource_admission_timeout_seconds
        if operation_deadline is not None:
            initial_deadline = min(initial_deadline, operation_deadline)
        wait_for_archive_io_window(initial_deadline, stable_seconds=ARCHIVE_IO_STABLE_SECONDS)

    if resource_admission_timeout_seconds or operation_deadline is not None:

        def check_segment_admission() -> None:
            now = time.monotonic()
            if operation_deadline is not None and now >= operation_deadline:
                raise TimeoutError("Archive exceeded its configured operation runtime")
            if resource_admission_timeout_seconds:
                deadline = now + resource_admission_timeout_seconds
                if operation_deadline is not None:
                    deadline = min(deadline, operation_deadline)
                wait_for_archive_io_window(deadline)

        before_segment = check_segment_admission
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (destination / "archive.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another archive job owns destination") from None
        identity = destination / "source.json"
        if identity.exists():
            if identity.is_symlink() or not identity.is_file():
                raise ValueError("Archive source identity is unsafe")
            if json.loads(identity.read_text())["recording_root"] != str(root):
                raise ValueError("Archive destination belongs to a different recording root")
        else:
            if any(p.name != "archive.lock" for p in destination.iterdir()):
                raise ValueError("Unidentified nonempty archive destination")
            atomic_json(identity, dict(schema_version=1, recording_root=str(root)))
        value = manifest(root)
        _validate_catalog_ordinals(value["segments"])
        manifest_path = destination / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError("Archive manifest is unsafe")
        if manifest_path.exists() and not full_verify:
            if not manifest_path.is_file():
                raise ValueError("Archive manifest is not a regular file")
            previous = json.loads(manifest_path.read_text())
            if not isinstance(previous, dict):
                raise ValueError("Existing archive manifest is malformed")
            return _archive_incremental_suffix(
                root,
                destination,
                value,
                previous=previous,
                budget=budget,
                reserve=reserve,
                before_segment=before_segment,
            )
        # Validate all source bytes and durable checkpoints once, with admission
        # checks between segments. The copy loop hashes each copied source stream,
        # so it does not need to re-read the source or the temporary destination.
        replay(root, value, before_segment=before_segment)
        used = sum(p.stat().st_size for p in destination.iterdir() if p.is_file())
        pending: list[tuple[Path, Path]] = []
        pending_bytes = 0

        def flush_pending() -> None:
            nonlocal pending_bytes
            if not pending:
                return
            if before_segment is not None:
                before_segment()
            # Each temporary file was fully copied and checksummed before joining
            # this batch. syncfs makes the batch durable before any .seg name is
            # exposed; the final manifest directory sync commits all renames.
            sync_filesystem(destination)
            for partial_path, target_path in pending:
                os.replace(partial_path, target_path)
            pending.clear()
            pending_bytes = 0

        for info in value["segments"]:
            if before_segment is not None:
                before_segment()
            if Path(info["file"]).name != info["file"]:
                raise ValueError("Unsafe segment path")
            source, target = root / info["file"], destination / info["file"]
            partial = target.with_suffix(".copying")
            if target.exists():
                if partial.exists():
                    used -= partial.stat().st_size
                    partial.unlink()
                # The complete destination replay below verifies existing and
                # newly copied segments together before manifest publication.
                continue
            # Only an interrupted temporary copy in this exclusive archive is disposable.
            if partial.exists():
                used -= partial.stat().st_size
                partial.unlink()
            margin = len(canonical(value)) + 8192
            if used + info["bytes"] + margin > budget:
                raise OSError("Archive budget reached; originals preserved")
            if shutil.disk_usage(destination).free < reserve + info["bytes"] + margin:
                raise OSError("Archive free-disk reserve reached; originals preserved")
            digest = hashlib.sha256()
            copied_bytes = 0
            with source.open("rb") as incoming, partial.open("xb") as outgoing:
                while chunk := incoming.read(1024 * 1024):
                    outgoing.write(chunk)
                    digest.update(chunk)
                    copied_bytes += len(chunk)
                outgoing.flush()
            if copied_bytes != info["bytes"] or digest.hexdigest() != info["sha256"]:
                raise ValueError("Source segment changed or copied bytes failed validation")
            pending.append((partial, target))
            pending_bytes += copied_bytes
            used += info["bytes"]
            if pending_bytes >= ARCHIVE_SYNC_BATCH_BYTES:
                flush_pending()
        flush_pending()
        replay(destination, value, before_segment=before_segment)
        verified_ns = time.time_ns()
        source_manifest_sha256 = file_hash_list(value["segments"])
        segment_count = len(value["segments"])
        segment_bytes = sum(info["bytes"] for info in value["segments"])
        published = dict(
            value,
            archival_provenance=dict(
                recording_root=str(root),
                verified_ns=verified_ns,
                full_verified_ns=verified_ns,
                full_verified_manifest_sha256=source_manifest_sha256,
                full_verified_segment_count=segment_count,
                full_verified_bytes=segment_bytes,
                incremental_verified_ns=verified_ns,
                incremental_verified_segments=segment_count,
                incremental_verified_bytes=segment_bytes,
                verification_mode="full_replay",
                source_manifest_sha256=source_manifest_sha256,
                originals_deleted=False,
                active_segment_included=False,
            ),
        )
        if used + len(canonical(published)) > budget:
            raise OSError("Archive publication exceeds budget; originals preserved")
        if shutil.disk_usage(destination).free < reserve + len(canonical(published)):
            raise OSError("Archive publication reaches disk reserve; originals preserved")
        # The atomic manifest publication syncs this directory after all
        # bounded batches have been flushed and the complete destination replay
        # has passed. An interruption before publication remains resumable from
        # the untouched raw originals.
        atomic_json(destination / "manifest.json", published)
        return published


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capacity", "archive"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-bytes", type=int)
    parser.add_argument("--reserve-bytes", type=int)
    parser.add_argument(
        "--full-verify",
        action="store_true",
        help="Replay the complete existing source and archive instead of validating only the suffix",
    )
    parser.add_argument("--archive-path", type=Path)
    parser.add_argument("--archive-budget-bytes", type=int)
    parser.add_argument("--archive-reserve-bytes", type=int)
    parser.add_argument("--archive-mountpoint", type=Path)
    parser.add_argument(
        "--storage-policy",
        type=Path,
        help="Optional storage policy JSON containing forecast_floor_bytes_per_day.",
    )
    parser.add_argument(
        "--resource-admission-timeout-seconds",
        type=float,
        default=0,
        help="Maximum wait for each initial or per-segment MIDAS service I/O window.",
    )
    parser.add_argument(
        "--operation-timeout-seconds",
        type=float,
        default=6 * 60 * 60,
        help="Bound the complete archive operation; use a separate per-window admission timeout.",
    )
    args = parser.parse_args()
    config = Config.load(args.config)
    if args.command == "capacity":
        policy = json.loads(args.storage_policy.read_text()) if args.storage_policy else {}
        result = capacity(
            config,
            forecast_floor_bytes_per_day=int(policy.get("forecast_floor_bytes_per_day", 0)),
            archive_path=args.archive_path,
            archive_budget=args.archive_budget_bytes,
            archive_reserve=args.archive_reserve_bytes,
            archive_mountpoint=args.archive_mountpoint,
        )
        atomic_json(args.output, result)
        if result["alerts"]:
            logging.warning(
                json.dumps(dict(event="reality_capacity_alert", alerts=result["alerts"]))
            )
        print(json.dumps(result, indent=2))
    else:
        if args.budget_bytes is None or args.reserve_bytes is None:
            parser.error("archive requires explicit --budget-bytes and --reserve-bytes")
        result = archive(
            Path(config.root),
            args.output,
            budget=args.budget_bytes,
            reserve=args.reserve_bytes,
            resource_admission_timeout_seconds=args.resource_admission_timeout_seconds,
            operation_timeout_seconds=args.operation_timeout_seconds,
            full_verify=args.full_verify,
        )
        print(
            json.dumps(
                dict(segments=len(result["segments"]), provenance=result["archival_provenance"]),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
