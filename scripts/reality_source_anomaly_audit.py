#!/usr/bin/env python3
"""Locate Reality replay anomalies in a pinned finalized archive boundary.

The audit wraps the existing reconstruction engine without changing its state
updates, then verifies that the wrapper reproduces the pinned cold receipt.
It reads only finalized segments named by the pinned catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

STAGING_ROOT = Path("/mnt/continental-cloud/data/midas-reality-staging").resolve()
ANOMALIES = (
    "duplicate",
    "timestamp_regression",
    "snapshot_source_time_regression_after_gap",
    "crossed",
)
EXAMPLES_PER_ANOMALY = 12
PROGRESS_CHECKPOINTS = 500


def read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected regular non-symlink JSON input: {path}")
    return json.loads(path.read_text())


def atomic_json(path: Path, value: Any) -> None:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cgroup_metrics() -> dict[str, Any]:
    relative = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
    group = Path("/sys/fs/cgroup") / relative.lstrip("/")
    names = (
        "memory.current",
        "memory.peak",
        "memory.stat",
        "memory.events",
        "cpu.stat",
        "io.stat",
        "cpu.pressure",
        "memory.pressure",
        "io.pressure",
    )
    return {name: (group / name).read_text() if (group / name).exists() else None for name in names}


def _decimal(value: Any) -> str | None:
    return None if value is None else str(value)


def _top(engine: Any, book: dict[str, Any] | None) -> dict[str, Any] | None:
    if book is None:
        return None
    bid, ask = engine.top(book)
    return {"bid": _decimal(bid), "ask": _decimal(ask)}


class ReplayAnomalyAudit:
    """Observe anomaly events while preserving the original engine behavior."""

    def __init__(self) -> None:
        self.examples: dict[str, list[dict[str, Any]]] = {name: [] for name in ANOMALIES}
        self.by_event_type: dict[str, Counter[str]] = {name: Counter() for name in ANOMALIES}
        self.gap_count = 0
        self.first_seen: dict[str, dict[str, Any]] = {}
        self.checkpoint_count = 0
        self.record_count = 0
        self.frame_count = 0
        self.event_count = 0
        self._last_progress_monotonic = 0.0
        self.progress_path: Path | None = None
        self.boundary: dict[str, Any] | None = None

    def reset_window(self) -> None:
        self.first_seen.clear()

    def _add_example(
        self,
        category: str,
        event_type: str,
        example: dict[str, Any],
        *,
        count: int = 1,
    ) -> None:
        self.by_event_type[category][event_type] += count
        if len(self.examples[category]) < EXAMPLES_PER_ANOMALY:
            self.examples[category].append(example)

    def wrap_event(
        self, engine: Any, raw: dict[str, Any], record: dict[str, Any], index: int, original
    ):
        event_type = raw.get("event_type", "unknown") if isinstance(raw, dict) else "invalid"
        event_type = event_type if isinstance(event_type, str) else "invalid"
        changes = raw.get("price_changes") if event_type == "price_change" else [raw]
        changes = changes if isinstance(changes, list) else []
        stamp: int | None = None
        try:
            stamp = int(raw["timestamp"])
        except (KeyError, TypeError, ValueError):
            pass

        touched: list[str] = []
        before_books: dict[str, dict[str, Any] | None] = {}
        regressed: list[dict[str, Any]] = []
        snapshots_after_gap: list[dict[str, Any]] = []
        market = raw.get("market") if isinstance(raw, dict) else None
        for change in changes:
            if not isinstance(change, dict):
                continue
            asset = change.get("asset_id")
            if not isinstance(asset, str):
                continue
            touched.append(asset)
            prior = engine.books.get(asset)
            if asset not in before_books:
                before_books[asset] = (
                    {
                        "exchange_ms": prior.get("exchange_ms"),
                        "snapshot": list(prior.get("snapshot", [])),
                        "last": list(prior.get("last", [])),
                        "issue": prior.get("issue"),
                        "top": _top(engine, prior),
                    }
                    if prior
                    else None
                )
            if (
                prior is None
                or stamp is None
                or asset not in engine.tokens
                or market != engine.tokens[asset]
                or stamp >= prior["exchange_ms"]
            ):
                continue
            after_gap_snapshot = bool(
                event_type == "book"
                and engine.reconstruction_version >= 4
                and prior["snapshot"][0] < engine.last_gap_ordinal
            )
            item = dict(
                asset_id=asset,
                previous_source_timestamp_ms=prior["exchange_ms"],
                incoming_source_timestamp_ms=stamp,
                previous_snapshot=list(prior["snapshot"]),
                previous_event=list(prior["last"]),
                last_gap_ordinal=engine.last_gap_ordinal,
                previous_issue=prior.get("issue"),
            )
            (snapshots_after_gap if after_gap_snapshot else regressed).append(item)

        before = {name: engine.counts.get(name, 0) for name in ANOMALIES}
        oldest_digest = engine.recent[0] if len(engine.recent) == engine.recent.maxlen else None
        oldest_location = self.first_seen.get(oldest_digest) if oldest_digest is not None else None
        ordinal = record.get("ordinal")
        location = dict(ordinal=ordinal, event_index=index, event_type=event_type)
        try:
            result = original(engine, raw, record, index)
        except BaseException:
            raise

        self.event_count += 1
        digest = engine.recent[-1] if engine.recent else None
        deltas = {name: engine.counts.get(name, 0) - before[name] for name in ANOMALIES}

        if deltas["duplicate"] and digest is not None:
            previous = self.first_seen.get(digest)
            if previous is None and digest == oldest_digest:
                previous = oldest_location
            self._add_example(
                "duplicate",
                event_type,
                dict(
                    **location,
                    digest=digest,
                    duplicate_of=previous,
                    source_timestamp=raw.get("timestamp") if isinstance(raw, dict) else None,
                    source_native_hash=raw.get("hash") if isinstance(raw, dict) else None,
                    last_gap_ordinal=engine.last_gap_ordinal,
                ),
                count=deltas["duplicate"],
            )

        if deltas["timestamp_regression"]:
            self._add_example(
                "timestamp_regression",
                event_type,
                dict(
                    **location,
                    market=market,
                    received_ns=record.get("received_ns"),
                    source_native_hash=raw.get("hash") if isinstance(raw, dict) else None,
                    count_delta=deltas["timestamp_regression"],
                    assets=regressed[:16],
                ),
                count=deltas["timestamp_regression"],
            )

        if deltas["snapshot_source_time_regression_after_gap"]:
            self._add_example(
                "snapshot_source_time_regression_after_gap",
                event_type,
                dict(
                    **location,
                    market=market,
                    received_ns=record.get("received_ns"),
                    source_native_hash=raw.get("hash") if isinstance(raw, dict) else None,
                    count_delta=deltas["snapshot_source_time_regression_after_gap"],
                    assets=snapshots_after_gap[:16],
                    reconstruction_version=engine.reconstruction_version,
                ),
                count=deltas["snapshot_source_time_regression_after_gap"],
            )

        if deltas["crossed"]:
            crossed_assets = []
            for asset in dict.fromkeys(touched):
                book = engine.books.get(asset)
                if book is None:
                    continue
                top = _top(engine, book)
                if top and top["bid"] is not None and top["ask"] is not None:
                    if Decimal(top["bid"]) >= Decimal(top["ask"]):
                        crossed_assets.append(
                            dict(
                                asset_id=asset,
                                previous=before_books.get(asset),
                                current=dict(
                                    top=top,
                                    issue=book.get("issue"),
                                    snapshot=list(book.get("snapshot", [])),
                                    last=list(book.get("last", [])),
                                    exchange_ms=book.get("exchange_ms"),
                                ),
                            )
                        )
            self._add_example(
                "crossed",
                event_type,
                dict(
                    **location,
                    market=market,
                    received_ns=record.get("received_ns"),
                    source_timestamp=raw.get("timestamp") if isinstance(raw, dict) else None,
                    source_native_hash=raw.get("hash") if isinstance(raw, dict) else None,
                    count_delta=deltas["crossed"],
                    assets=crossed_assets[:16],
                ),
                count=deltas["crossed"],
            )

        if oldest_digest is not None:
            self.first_seen.pop(oldest_digest, None)
        if digest is not None:
            self.first_seen.setdefault(digest, location)
        return result

    def wrap_consume(self, engine: Any, record: dict[str, Any], original):
        self.record_count += 1
        if record.get("kind") == "gap":
            self.gap_count += 1
            self.reset_window()
        if record.get("kind") == "frame":
            self.frame_count += 1
        if record.get("kind") == "checkpoint":
            self.checkpoint_count += 1
            if (
                self.progress_path is not None
                and self.checkpoint_count % PROGRESS_CHECKPOINTS == 0
                and time.monotonic() - self._last_progress_monotonic >= 30
            ):
                self._last_progress_monotonic = time.monotonic()
                atomic_json(
                    self.progress_path,
                    dict(
                        phase="full_source_anomaly_audit",
                        updated_at=datetime.now(UTC).isoformat(),
                        checkpoint_records=self.checkpoint_count,
                        record_ordinal=record.get("ordinal"),
                        durable_records=self.record_count,
                        frames=self.frame_count,
                        websocket_events=self.event_count,
                        anomalies={
                            name: sum(self.by_event_type[name].values()) for name in ANOMALIES
                        },
                    ),
                )
        return original(engine, record)

    def document(self) -> dict[str, Any]:
        return dict(
            counts={name: sum(self.by_event_type[name].values()) for name in ANOMALIES},
            by_event_type={name: dict(self.by_event_type[name]) for name in ANOMALIES},
            examples=self.examples,
            example_limit_per_category=EXAMPLES_PER_ANOMALY,
            duplicate_window="same as Engine recent hash window (4096 events), reset at every durable gap",
            source_timestamp_interpretation=(
                "Timestamps are provider source timestamps. Regressions are local ordered observations; "
                "without upstream sequence they do not prove reordering or message loss."
            ),
            crossed_interpretation=(
                "Counted when the reconstructed local top bid is >= the local top ask after an event. "
                "This is a local reconstructed-state condition, not proof that the provider published "
                "an atomic crossed snapshot."
            ),
        )


def worker(
    *,
    source: Path,
    catalog_path: Path,
    identities_path: Path,
    boundary_path: Path,
    cold_path: Path,
    matrix_path: Path,
    packages: Path,
    output: Path,
) -> dict[str, Any]:
    if source.is_symlink() or output.is_symlink() or not output.is_dir():
        raise ValueError("Source/output roots must be ordinary directories")
    source = source.resolve(strict=True)
    packages = packages.resolve(strict=True)
    output = output.resolve(strict=True)
    if not output.is_relative_to(STAGING_ROOT):
        raise ValueError("Audit output must remain under independent staging")

    sys.path.insert(0, str(packages))
    from midas.reality import recovery
    from midas.reality.reconstruction import Engine
    from midas.reality.replay import replay
    from midas.reality.storage import canonical
    from reality_full_scale_validation import reality_source_sha256
    from reality_readonly_sandbox import apply_readonly_source_policy, verify_source_write_denied

    catalog = read_json(catalog_path)
    identities = read_json(identities_path)
    boundary = read_json(boundary_path)
    cold = read_json(cold_path)
    matrix = read_json(matrix_path)
    actual_source_hash = reality_source_sha256(packages)
    catalog_hash = hashlib.sha256(canonical(catalog)).hexdigest()
    identity_hash = hashlib.sha256(canonical(identities)).hexdigest()
    if (
        matrix.get("recovery_matrix") != "PASSED"
        or boundary.get("source") != str(source)
        or boundary.get("implementation_packages") != str(packages)
        or boundary.get("implementation_source_sha256") != actual_source_hash
        or actual_source_hash != cold.get("implementation_source_sha256")
        or boundary.get("recovery_implementation_sha256") != recovery.implementation_identity()
        or boundary.get("catalog_sha256") != catalog_hash
        or boundary.get("identities_sha256") != identity_hash
        or cold.get("boundary_catalog_sha256") != catalog_hash
        or cold.get("boundary_identities_sha256") != identity_hash
        or matrix.get("boundary", {}).get("catalog_sha256") != catalog_hash
        or matrix.get("boundary", {}).get("identities_sha256") != identity_hash
    ):
        raise ValueError("Anomaly audit inputs do not match the full-scale recovery receipt")

    policy = apply_readonly_source_policy(source, output)
    first_segment = source / catalog["segments"][0]["file"]
    verify_source_write_denied(first_segment)
    atomic_json(output / "source-readonly-policy.json", policy)

    audit = ReplayAnomalyAudit()
    original_event = Engine.event
    original_consume = Engine.consume

    def audited_event(engine, raw, record, index):
        return audit.wrap_event(engine, raw, record, index, original_event)

    def audited_consume(engine, record):
        return audit.wrap_consume(engine, record, original_consume)

    Engine.event = audited_event
    Engine.consume = audited_consume
    started = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    audit.progress_path = output / "progress.json"
    try:
        engine, checkpoints = replay(source, catalog, _engine=Engine())
    finally:
        Engine.event = original_event
        Engine.consume = original_consume

    elapsed = time.monotonic() - started
    cold_phase = read_json(cold_path)
    expected_counts = cold_phase.get("counts", {})
    actual_counts = dict(engine.counts)
    anomaly_counts = audit.document()["counts"]
    internal_digest = hashlib.sha256()
    for chunk in recovery._canonical_chunks(recovery._snapshot(engine)):
        internal_digest.update(chunk)
    if (
        engine.last_ordinal != boundary["last_ordinal"]
        or engine.gaps != boundary["kinds"].get("gap", 0)
        or engine.digest() != cold_phase["state_sha256"]
        or internal_digest.hexdigest() != cold_phase["internal_sha256"]
        or checkpoints != boundary["kinds"].get("checkpoint", 0)
        or actual_counts != expected_counts
        or any(anomaly_counts[name] != actual_counts.get(name, 0) for name in ANOMALIES)
    ):
        raise ValueError("Anomaly-instrumented replay differs from the pinned cold reconstruction")

    after = resource.getrusage(resource.RUSAGE_SELF)
    receipt = dict(
        schema_version=1,
        status="FULL_ARCHIVE_REPLAY_VERIFIED",
        created_at=datetime.now(UTC).isoformat(),
        source=str(source),
        source_read_policy="pinned finalized segments opened read-only; .open excluded by catalog",
        candidate_packages=str(packages),
        implementation_source_sha256=actual_source_hash,
        recovery_implementation_sha256=boundary["recovery_implementation_sha256"],
        boundary_catalog_sha256=catalog_hash,
        boundary_identities_sha256=identity_hash,
        source_boundary=dict(
            segment_count=boundary["segment_count"],
            archive_bytes=boundary["archive_bytes"],
            last_ordinal=boundary["last_ordinal"],
            gap_records=boundary["kinds"].get("gap", 0),
            checkpoint_records=checkpoints,
            excluded_open=boundary.get("excluded_open", []),
        ),
        replay=dict(
            wall_seconds=elapsed,
            cpu_seconds=after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
            peak_rss_kib=after.ru_maxrss,
            records_consumed=audit.record_count,
            websocket_frames=audit.frame_count,
            websocket_events=audit.event_count,
            checkpoint_records=checkpoints,
            state_sha256=engine.digest(),
            internal_sha256=internal_digest.hexdigest(),
            sequence_verified=False,
            process_io=Path("/proc/self/io").read_text(),
            cgroup=cgroup_metrics(),
        ),
        engine_anomaly_counts={name: actual_counts.get(name, 0) for name in ANOMALIES},
        anomaly_audit=audit.document(),
        interpretation=(
            "The audit localizes reconstruction signals in durable records. It does not establish "
            "which unsequenced upstream view was complete or prove provider message loss."
        ),
    )
    atomic_json(output / "anomaly-audit.json", receipt)
    (output / "progress.json").unlink(missing_ok=True)
    return receipt


def _validate_inputs(args) -> dict[str, Any]:
    source = args.source.resolve(strict=True)
    output = args.output
    if output.is_symlink() or output.exists():
        raise ValueError("Audit output directory must be new and non-symlink")
    output_parent = output.parent.resolve(strict=True)
    if not output_parent.is_relative_to(STAGING_ROOT) or output.parent.is_symlink():
        raise ValueError("Audit output must be under the independent staging mount")
    matrix = read_json(args.matrix)
    boundary = read_json(args.boundary)
    catalog = read_json(args.catalog)
    identities = read_json(args.identities)
    if (
        matrix.get("recovery_matrix") != "PASSED"
        or boundary.get("source") != str(source)
        or matrix.get("boundary", {}).get("catalog_sha256") != boundary.get("catalog_sha256")
        or matrix.get("boundary", {}).get("identities_sha256") != boundary.get("identities_sha256")
    ):
        raise ValueError("Full-scale matrix or source boundary does not match the requested inputs")
    packages = args.packages.resolve(strict=True)
    sys.path.insert(0, str(packages))
    from midas.reality import recovery
    from reality_full_scale_validation import reality_source_sha256

    source_hash = reality_source_sha256(packages)
    if source_hash != boundary.get(
        "implementation_source_sha256"
    ) or recovery.implementation_identity() != boundary.get("recovery_implementation_sha256"):
        raise ValueError("Candidate package or recovery code differs from the pinned matrix")
    return dict(
        source=source,
        packages=packages,
        source_hash=source_hash,
        boundary=boundary,
        catalog=catalog,
        identities=identities,
        matrix=matrix,
    )


def run(args) -> dict[str, Any]:
    inputs = _validate_inputs(args)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from reality_full_scale_validation import (
        ADMISSION_SAMPLE_SECONDS,
        MAX_STAGE_PRESSURE_PAUSE_SECONDS,
        RESUME_STABLE_SAMPLES,
        STAGING_VOLUME_RESERVE_BYTES,
        admission,
        ensure_no_active_validation_units,
        is_transient_pressure_rejection,
        wait_for_sustained_admission,
    )

    ensure_no_active_validation_units()
    initial = wait_for_sustained_admission()
    if initial.get("pid") != "863193":
        raise ValueError("Protected Reality process identity changed before audit")
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    atomic_json(args.output / "admission.json", initial)
    unit = "midas-validation-anomaly-" + uuid.uuid4().hex[:12]
    command = [
        "systemd-run",
        "--user",
        "--wait",
        "--pipe",
        "--unit=" + unit,
        "-p",
        "MemoryHigh=640M",
        "-p",
        "MemoryMax=768M",
        "-p",
        "MemorySwapMax=0",
        "-p",
        "CPUQuota=20%",
        "-p",
        "CPUWeight=10",
        "-p",
        "Nice=19",
        "-p",
        "IOSchedulingClass=idle",
        "-p",
        "TasksMax=16",
        "-p",
        "RuntimeMaxSec=7200",
        "-p",
        "TimeoutStopSec=5",
        "-p",
        "ProtectSystem=strict",
        "-p",
        "ProtectHome=read-only",
        "-p",
        "ReadWritePaths=" + str(args.output.resolve()),
        "-p",
        "PrivateNetwork=yes",
        "-p",
        "NoNewPrivileges=yes",
        "-p",
        "LimitCORE=0",
        "-p",
        "LimitFSIZE=64M",
        "-p",
        "IOAccounting=yes",
        "-p",
        "RestrictAddressFamilies=AF_UNIX",
        "--setenv=PYTHONDONTWRITEBYTECODE=1",
        "--setenv=PYTHONPATH=" + os.environ["PYTHONPATH"],
        "--setenv=MIDAS_REALITY_VALIDATION_PACKAGES=" + str(inputs["packages"]),
        "--setenv=MIDAS_REALITY_VALIDATION_SOURCE_SHA256=" + inputs["source_hash"],
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--source",
        str(inputs["source"]),
        "--packages",
        str(inputs["packages"]),
        "--catalog",
        str(args.catalog.resolve(strict=True)),
        "--identities",
        str(args.identities.resolve(strict=True)),
        "--boundary",
        str(args.boundary.resolve(strict=True)),
        "--cold",
        str(args.cold.resolve(strict=True)),
        "--matrix",
        str(args.matrix.resolve(strict=True)),
        "--output",
        str(args.output.resolve()),
    ]
    log_path = args.output / "worker.log"
    monitor_path = args.output / "monitor.jsonl"
    reserve = STAGING_VOLUME_RESERVE_BYTES
    with log_path.open("w") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        paused_at = None
        pause_total = 0.0
        safe_samples = 0
        try:
            with monitor_path.open("w") as monitor:
                while child.poll() is None:
                    try:
                        sample = admission(initial["memory_events"])
                    except ValueError as error:
                        if not is_transient_pressure_rejection(error):
                            raise
                        if paused_at is None:
                            subprocess.run(["systemctl", "--user", "freeze", unit], check=True)
                            paused_at = time.monotonic()
                            safe_samples = 0
                            monitor.write(
                                json.dumps(
                                    dict(
                                        event="worker_frozen_for_host_pressure",
                                        at=datetime.now(UTC).isoformat(),
                                        reason=str(error),
                                    )
                                )
                                + "\n"
                            )
                            monitor.flush()
                        elif (
                            pause_total + time.monotonic() - paused_at
                            > MAX_STAGE_PRESSURE_PAUSE_SECONDS
                        ):
                            raise ValueError(
                                "Anomaly audit exceeded its pressure-pause budget"
                            ) from error
                        time.sleep(ADMISSION_SAMPLE_SECONDS)
                        continue
                    if sample["pid"] != initial["pid"]:
                        raise ValueError("Protected Reality process identity changed during audit")
                    if paused_at is not None:
                        safe_samples += 1
                        if safe_samples < RESUME_STABLE_SAMPLES:
                            time.sleep(ADMISSION_SAMPLE_SECONDS)
                            continue
                        duration = time.monotonic() - paused_at
                        subprocess.run(["systemctl", "--user", "thaw", unit], check=True)
                        pause_total += duration
                        monitor.write(
                            json.dumps(
                                dict(
                                    event="worker_resumed_after_host_pressure",
                                    at=datetime.now(UTC).isoformat(),
                                    pause_seconds=duration,
                                    total_pressure_pause_seconds=pause_total,
                                )
                            )
                            + "\n"
                        )
                        monitor.flush()
                        paused_at = None
                        safe_samples = 0
                    owned = subprocess.check_output(
                        [
                            "systemctl",
                            "--user",
                            "show",
                            unit,
                            "-p",
                            "ControlGroup",
                            "-p",
                            "MemoryPeak",
                            "-p",
                            "CPUUsageNSec",
                        ],
                        text=True,
                    )
                    control_group = dict(
                        line.split("=", 1) for line in owned.splitlines() if "=" in line
                    ).get("ControlGroup", "")
                    cgroup = Path("/sys/fs/cgroup") / control_group.lstrip("/")
                    details = {
                        name: (cgroup / name).read_text()
                        for name in (
                            "memory.current",
                            "memory.peak",
                            "memory.events",
                            "cpu.stat",
                            "io.stat",
                            "cpu.pressure",
                            "memory.pressure",
                            "io.pressure",
                        )
                        if control_group and (cgroup / name).exists()
                    }
                    progress = args.output / "progress.json"
                    monitor.write(
                        json.dumps(
                            dict(
                                at=datetime.now(UTC).isoformat(),
                                protected=sample,
                                worker=owned,
                                cgroup=details,
                                progress=read_json(progress) if progress.is_file() else None,
                            )
                        )
                        + "\n"
                    )
                    monitor.flush()
                    if shutil_disk_free(args.output) < reserve:
                        raise ValueError("Staging filesystem fell below its protected reserve")
                    time.sleep(ADMISSION_SAMPLE_SECONDS)
            child.wait()
        except BaseException:
            if paused_at is not None:
                subprocess.run(["systemctl", "--user", "thaw", unit], check=False)
            subprocess.run(["systemctl", "--user", "stop", unit], check=False)
            child.wait(timeout=15)
            raise

    if child.returncode:
        raise ValueError(f"Anomaly audit worker failed; inspect {log_path}")
    receipt = read_json(args.output / "anomaly-audit.json")
    if (
        receipt.get("status") != "FULL_ARCHIVE_REPLAY_VERIFIED"
        or receipt.get("boundary_catalog_sha256") != inputs["boundary"]["catalog_sha256"]
        or receipt.get("boundary_identities_sha256") != inputs["boundary"]["identities_sha256"]
        or receipt.get("implementation_source_sha256") != inputs["source_hash"]
        or receipt.get("replay", {}).get("state_sha256") != read_json(args.cold)["state_sha256"]
    ):
        raise ValueError("Completed anomaly audit receipt does not match its pinned cold result")
    atomic_json(
        args.output / "runner-receipt.json",
        dict(
            schema_version=1,
            unit=unit,
            exit_code=child.returncode,
            total_pressure_pause_seconds=pause_total,
            worker_receipt_sha256=sha256(args.output / "anomaly-audit.json"),
            boundary_catalog_sha256=receipt["boundary_catalog_sha256"],
            boundary_identities_sha256=receipt["boundary_identities_sha256"],
            created_at=datetime.now(UTC).isoformat(),
        ),
    )
    return receipt


def shutil_disk_free(path: Path) -> int:
    details = os.statvfs(path)
    return details.f_bavail * details.f_frsize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "worker"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--identities", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--cold", type=Path, required=True)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "worker":
        if args.matrix is None:
            parser.error("worker requires --matrix")
        expected = os.environ.get("MIDAS_REALITY_VALIDATION_SOURCE_SHA256")
        if expected is None:
            parser.error("worker requires the pinned candidate source hash")
        from reality_full_scale_validation import require_reality_source_sha256

        require_reality_source_sha256(args.packages, expected)
        worker(
            source=args.source,
            packages=args.packages,
            catalog_path=args.catalog,
            identities_path=args.identities,
            boundary_path=args.boundary,
            cold_path=args.cold,
            matrix_path=args.matrix,
            output=args.output,
        )
    else:
        if args.matrix is None:
            parser.error("run requires --matrix")
        run(args)


if __name__ == "__main__":
    main()
