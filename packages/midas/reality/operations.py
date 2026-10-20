"""Read-only capacity inspection and bounded, non-destructive raw archival.

These jobs never acquire the recorder writer lock or read an active segment.
Forecasts describe observed compressed growth, not guaranteed future capacity.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from .config import Config
from .replay import replay
from .storage import atomic_json, canonical, describe, file_hash, manifest, records, sync_dir

CAPACITY_WARNING_SECONDS = 30 * 86400
CAPACITY_CRITICAL_SECONDS = 14 * 86400
CAPACITY_ACTION_SECONDS = 7 * 86400


def _last_started_budget(
    root: Path, configured_budget: int, status: dict[str, Any]
) -> tuple[int, str]:
    """Use the last-started writer configuration until runtime status confirms a change."""
    observed: list[tuple[str, int]] = []
    status_config = status.get("config")
    if isinstance(status_config, dict):
        value = status_config.get("budget_bytes")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            observed.append(("collector_status", value))
    startup_path = root / "config.json"
    if startup_path.is_file():
        try:
            startup_config = json.loads(startup_path.read_text())
        except (OSError, json.JSONDecodeError):
            startup_config = {}
        if isinstance(startup_config, dict):
            value = startup_config.get("budget_bytes")
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                observed.append(("startup_config", value))
    if not observed:
        return configured_budget, "configured_fallback"
    # If status and its startup receipt disagree, use the lower known limit until reconciled.
    effective = min(value for _, value in observed)
    source = "+".join(name for name, value in observed if value == effective)
    return effective, source


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
    headroom = min(runtime_budget - used, free - config.reserve_bytes)
    storage_seconds = max(0, headroom) / rate if rate else None
    retention_seconds = (
        max(0, config.retention_days * 86400 - (now - oldest) / 1e9) if oldest is not None else None
    )
    horizons = [x for x in (storage_seconds, retention_seconds) if x is not None]
    deadline = min(horizons) if horizons else None
    alerts = []
    if budget_pending:
        alerts.append("BUDGET_CHANGE_PENDING_RESTART")
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
        if any(
            value is None
            for value in (archive_path, archive_budget, archive_reserve, archive_mountpoint)
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
        filesystem_free_bytes=free,
        free_disk_reserve_bytes=config.reserve_bytes,
        available_headroom_bytes=max(0, headroom),
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


def archive(root: Path, destination: Path, *, budget: int, reserve: int) -> dict[str, Any]:
    """Incrementally copy finalized segments; publish only after full validation.

    Interrupted copies may be resumed. Every existing segment is verified, never
    overwritten. Original bytes and catalogs remain owned by the collector.
    """
    root, destination = root.resolve(), destination.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Archive must be separate from raw recorder root")
    if budget <= 0 or reserve <= 0:
        raise ValueError("Archive budget and reserve must be positive")
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
        used = sum(p.stat().st_size for p in destination.iterdir() if p.is_file())
        for info in value["segments"]:
            if Path(info["file"]).name != info["file"]:
                raise ValueError("Unsafe segment path")
            source, target = root / info["file"], destination / info["file"]
            if describe(source) != info:
                raise ValueError(f"Source segment integrity mismatch: {source}")
            if target.exists():
                if describe(target) != info:
                    raise ValueError(f"Archived segment integrity mismatch: {target}")
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
            with source.open("rb") as incoming, partial.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            if describe(partial) != dict(info, file=partial.name):
                raise ValueError("Copied archive segment failed validation")
            os.replace(partial, target)
            sync_dir(destination)
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
        replay(destination, value)  # Verify global ordering and online checkpoints too.
        if used + len(canonical(published)) > budget:
            raise OSError("Archive publication exceeds budget; originals preserved")
        if shutil.disk_usage(destination).free < reserve + len(canonical(published)):
            raise OSError("Archive publication reaches disk reserve; originals preserved")
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
            Path(config.root), args.output, budget=args.budget_bytes, reserve=args.reserve_bytes
        )
        print(
            json.dumps(
                dict(segments=len(result["segments"]), provenance=result["archival_provenance"]),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
