"""Read-only capacity inspection and bounded, non-destructive raw archival.

These jobs never acquire the recorder writer lock or read an active segment.
Forecasts describe observed compressed growth, not guaranteed future capacity.
"""

from __future__ import annotations

import argparse
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
from .storage import atomic_json, canonical, describe, file_hash, manifest, records

CAPACITY_WARNING_SECONDS = 30 * 86400
CAPACITY_CRITICAL_SECONDS = 14 * 86400
CAPACITY_ACTION_SECONDS = 7 * 86400
ARCHIVE_IO_FULL_AVG10_MAX = 2.0
ARCHIVE_IO_FULL_AVG60_MAX = 2.0
ARCHIVE_IO_SAMPLE_SECONDS = 5.0
ARCHIVE_IO_STABLE_SECONDS = 60.0
ARCHIVE_REQUIRED_PROTECTED_SERVICES = {"midas-reality.service"}


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
    """Wait for active MIDAS service cgroups to clear the I/O pressure gate.

    Host-wide PSI is retained as an advisory signal. Admission follows the
    protected service cgroups because unrelated host services can dominate the
    global value while the recorder and MIDAS APIs remain healthy.
    """
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
        except (OSError, RuntimeError, ValueError, KeyError):
            host_pressure = None
        if not pressured:
            stable_samples += 1
            if stable_samples >= required_samples:
                return
        else:
            stable_samples = 0
        now = time.monotonic()
        if now >= deadline:
            raise TimeoutError(
                "Archive I/O admission window did not clear before its configured deadline"
            )
        if now - last_notice >= 60:
            logging.warning(
                "Archive waiting for MIDAS service I/O headroom: pressured=%s; "
                "host full PSI advisory=%s",
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
    used = (
        sum(p.stat().st_size for p in destination.iterdir() if p.is_file())
        if destination.is_dir()
        else 0
    )
    manifest_present = (destination / "manifest.json").is_file()
    state = "MANIFEST_PRESENT" if manifest_present else "NOT_YET_VERIFIED"
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
        raw_archive_bytes=used,
        budget_bytes=budget,
        filesystem_free_bytes=free,
        filesystem_reserve_bytes=reserve,
        available_headroom_bytes=max(0, headroom),
        estimated_storage_seconds_remaining=seconds,
        alerts=alerts,
    )


def capacity(
    config: Config,
    *,
    window_segments: int = 120,
    now_ns: int | None = None,
    archive_path: Path | None = None,
    archive_budget: int | None = None,
    archive_reserve: int | None = None,
    archive_mountpoint: Path | None = None,
) -> dict[str, Any]:
    if not 2 <= window_segments <= 2000:
        raise ValueError("Sample must contain 2..2000 finalized segments")
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
    status_path = root / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    # Collection continues during sampling; measure status and capacity at the end.
    now = time.time_ns() if now_ns is None else now_ns
    used = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
    free = shutil.disk_usage(root).free
    runtime_budget, budget_source = _last_started_budget(root, config.budget_bytes, status)
    budget_pending = runtime_budget != config.budget_bytes
    runtime_retention_days, retention_source = _last_started_setting(
        root, config.retention_days, status, "retention_days"
    )
    retention_pending = runtime_retention_days != config.retention_days
    headroom = min(runtime_budget - used, free - config.reserve_bytes)
    storage_seconds = max(0, headroom) / rate if rate else None
    configured_headroom = min(
        config.budget_bytes - used,
        free - config.reserve_bytes,
    )
    configured_storage_seconds = max(0, configured_headroom) / rate if rate else None
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
            bytes_per_second=rate,
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
        compressed_bytes_per_second=rate,
        estimated_bytes_per_day=rate * 86400 if rate else None,
        estimated_storage_seconds_remaining=storage_seconds,
        retention_seconds_remaining=retention_seconds,
        configured_estimated_storage_seconds_remaining=configured_storage_seconds,
        configured_retention_seconds_remaining=configured_retention_seconds,
        effective_capacity_runway_seconds=deadline,
        effective_capacity_runway_days=deadline / 86400 if deadline is not None else None,
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


def archive(
    root: Path,
    destination: Path,
    *,
    budget: int,
    reserve: int,
    resource_admission_timeout_seconds: float = 0,
    operation_timeout_seconds: float = 0,
) -> dict[str, Any]:
    """Incrementally copy finalized segments; publish only after full validation.

    Interrupted copies may be resumed. The source and completed destination are
    each fully replay-verified; copied files are checked against the source
    manifest while streaming. Original bytes and catalogs remain collector-owned.
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
            if json.loads(identity.read_text())["recording_root"] != str(root):
                raise ValueError("Archive destination belongs to a different recording root")
        else:
            if any(p.name != "archive.lock" for p in destination.iterdir()):
                raise ValueError("Unidentified nonempty archive destination")
            atomic_json(identity, dict(schema_version=1, recording_root=str(root)))
        value = manifest(root)
        # Validate all source bytes and durable checkpoints once, with admission
        # checks between segments. The copy loop hashes each copied source stream,
        # so it does not need to re-read the source or the temporary destination.
        replay(root, value, before_segment=before_segment)
        used = sum(p.stat().st_size for p in destination.iterdir() if p.is_file())
        for info in value["segments"]:
            if before_segment is not None:
                before_segment()
            if Path(info["file"]).name != info["file"]:
                raise ValueError("Unsafe segment path")
            source, target = root / info["file"], destination / info["file"]
            if target.exists():
                # The complete destination replay below verifies existing and
                # newly copied segments together before manifest publication.
                continue
            partial = target.with_suffix(".copying")
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
                os.fsync(outgoing.fileno())
            if copied_bytes != info["bytes"] or digest.hexdigest() != info["sha256"]:
                raise ValueError("Source segment changed or copied bytes failed validation")
            os.replace(partial, target)
            used += info["bytes"]
        published = dict(
            value,
            archival_provenance=dict(
                recording_root=str(root),
                verified_ns=time.time_ns(),
                source_manifest_sha256=file_hash_list(value["segments"]),
                originals_deleted=False,
                active_segment_included=False,
            ),
        )
        replay(destination, value, before_segment=before_segment)
        if used + len(canonical(published)) > budget:
            raise OSError("Archive publication exceeds budget; originals preserved")
        if shutil.disk_usage(destination).free < reserve + len(canonical(published)):
            raise OSError("Archive publication reaches disk reserve; originals preserved")
        # The atomic manifest publication syncs this directory after all
        # segment files have been fsynced and replay-verified. Deferring this
        # directory sync avoids one HDD journal commit for every segment; an
        # interruption before publication remains resumable from source data.
        atomic_json(destination / "manifest.json", published)
        return published


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capacity", "archive"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-bytes", type=int)
    parser.add_argument("--reserve-bytes", type=int)
    parser.add_argument("--archive-path", type=Path)
    parser.add_argument("--archive-budget-bytes", type=int)
    parser.add_argument("--archive-reserve-bytes", type=int)
    parser.add_argument("--archive-mountpoint", type=Path)
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
        result = capacity(
            config,
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
        )
        print(
            json.dumps(
                dict(segments=len(result["segments"]), provenance=result["archival_provenance"]),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
