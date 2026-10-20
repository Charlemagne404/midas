"""Read-only inventory and guarded, sequential recovery validation of Reality.

Run with candidate packages on PYTHONPATH. `inventory` reads only sidecars/stat;
it DOES NOT certify segment bytes. `run` requires sustained production headroom,
then places each worker in its own sandbox/cgroup. No production service actions.
Workers read immutable finalized source files through Landlock and write only to
independent staging state.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import shutil
import signal
import struct
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midas.reality import recovery
from midas.reality.reconstruction import _canonical_chunks
from midas.reality.resources import snapshot
from midas.reality.storage import (
    Store,
    _validate_manifest_metadata,
    canonical,
    manifest,
    records,
    sync_dir,
)
from midas.reality.storage import atomic_json as atomic_storage_json
from reality_readonly_sandbox import apply_readonly_source_policy, verify_source_write_denied
from reality_staging_admission import (
    CRITICAL_CPU_SOME_AVG10_MAX,
    CRITICAL_CPU_SOME_AVG60_MAX,
    HOST_CPU_LOAD_AVG1_PER_CPU_MAX,
    PROTECTED_DISK_RESERVE_BYTES,
    STAGING_EXTRA_BYTES,
    validate_staging_admission,
)

STAGING_OUTPUT_ROOT = Path("/mnt/continental-cloud/data/midas-reality-staging")
STAGING_VOLUME_RESERVE_BYTES = 400 * 1024**3
STAGING_CPU_QUOTA_PERCENT = 15
STAGING_CPU_WEIGHT = 10
ADMISSION_SAMPLE_SECONDS = 5
START_STABLE_SECONDS = 60
RESUME_STABLE_SAMPLES = 3
MAX_STAGE_PRESSURE_PAUSE_SECONDS = 30 * 60
COLD_CHUNK_SEGMENTS = 256


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def allowed_staging_path(path):
    return path.is_relative_to(Path("/tmp")) or path.is_relative_to(STAGING_OUTPUT_ROOT)


def inventory(source):
    """Pin exactly the sidecars listed at entry; fail on any broken boundary."""
    started = datetime.now(UTC).isoformat()
    sidecars = sorted(p for p in source.glob("*.json") if p.name[0].isdigit())
    segments, identities, kinds = [], [], Counter()
    previous = 0
    for sidecar in sidecars:
        raw = sidecar.read_bytes()
        info = json.loads(raw)
        if Path(info["file"]).name != info["file"] or not info["file"].endswith(".seg"):
            raise ValueError("Unsafe segment identity")
        path = source / info["file"]
        if sidecar != path.with_suffix(".json") or path.is_symlink() or sidecar.is_symlink():
            raise ValueError("Source must contain regular finalized files and sidecars")
        _validate_manifest_metadata(path, info)
        if info["count"]:
            if info["first"] != previous + 1:
                raise ValueError("Non-contiguous catalog")
            previous = info["last"]
        stat = path.stat()
        identities.append(
            dict(
                file=path.name,
                device=stat.st_dev,
                inode=stat.st_ino,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sidecar_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
        segments.append(info)
        kinds.update(info["kinds"])
    if not segments:
        raise ValueError("Empty snapshot")
    catalog = dict(
        schema_version=1,
        format="midas-reality-framed-zlib-v1",
        ordering="durable ordinal then frame array index",
        segments=segments,
    )
    known = {i["file"] for i in segments}
    unmatched = sorted(p.name for p in source.glob("*.seg") if p.name not in known)
    # A rename can precede sidecar publication. Do not silently omit an interior file.
    if any(int(n.split("-", 1)[0]) <= previous for n in unmatched):
        raise ValueError("Finalized segment without sidecar inside pinned prefix")
    summary = dict(
        started_at=started,
        completed_at=datetime.now(UTC).isoformat(),
        source=str(source),
        segment_count=len(segments),
        last_ordinal=previous,
        archive_bytes=sum(i["bytes"] for i in segments),
        kinds=dict(kinds),
        empty_segments=sum(i["count"] == 0 for i in segments),
        catalog_sha256=hashlib.sha256(canonical(catalog)).hexdigest(),
        identities_sha256=hashlib.sha256(canonical(identities)).hexdigest(),
        last_segment=segments[-1],
        unmatched_finalized=unmatched,
        excluded_open=[
            dict(file=p.name, observed_bytes=p.stat().st_size)
            for p in sorted(source.glob("*.open"))
        ],
        checkpoint_present=(source / recovery.CHECKPOINT_NAME).exists(),
        scope="metadata only; content checksums NOT yet verified",
    )
    return catalog, identities, summary


def admission(baseline_events=None):
    unit = subprocess.check_output(
        [
            "systemctl",
            "--user",
            "show",
            "midas-reality.service",
            "-p",
            "MainPID",
            "-p",
            "ControlGroup",
        ],
        text=True,
    )
    values = dict(line.split("=", 1) for line in unit.splitlines())
    if int(values["MainPID"]) <= 0:
        raise ValueError("Protected recorder is unavailable")
    control_group = values["ControlGroup"]
    group = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    sample = snapshot(control_group)
    max_text = (group / "memory.max").read_text().strip()
    memory_max = int(max_text) if max_text != "max" else None
    sample["memory_max_bytes"] = memory_max
    sample["memory_max_margin_bytes"] = (
        memory_max - sample["memory_current_bytes"] if memory_max is not None else None
    )
    sample["protected_cpu_stat"] = (group / "cpu.stat").read_text()
    sample["available_cpu_count"] = (
        len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    )
    sample["host_load_avg1"] = os.getloadavg()[0]
    sample["critical_service_cpu_pressure"] = {}
    for service in ("midas-reality.service", "midas-api.service", "midas-reality-api.service"):
        details = subprocess.check_output(
            ["systemctl", "--user", "show", service, "-p", "ActiveState", "-p", "ControlGroup"],
            text=True,
        )
        service_values = dict(line.split("=", 1) for line in details.splitlines())
        control_group_path = service_values.get("ControlGroup", "")
        pressure_path = Path("/sys/fs/cgroup") / control_group_path.lstrip("/") / "cpu.pressure"
        pressure_values = {}
        if (
            service_values.get("ActiveState") == "active"
            and control_group_path
            and pressure_path.is_file()
        ):
            for line in pressure_path.read_text().splitlines():
                label, _, rest = line.partition(" ")
                fields = dict(part.split("=", 1) for part in rest.split() if "=" in part)
                pressure_values[label] = {
                    key: float(value) for key, value in fields.items() if key.startswith("avg")
                }
        sample["critical_service_cpu_pressure"][service] = {
            "available": bool(pressure_values),
            "active_state": service_values.get("ActiveState", "unknown"),
            "pressure": pressure_values,
        }
    io_stat = group / "io.stat"
    sample["protected_io_stat"] = io_stat.read_text() if io_stat.exists() else None
    validate_staging_admission(sample, baseline_events)
    return dict(pid=values["MainPID"], control_group=control_group, **sample)


def is_transient_pressure_rejection(error):
    """Only transient admission-pressure thresholds may pause a staging worker for retry."""
    prefix = "Isolated staging admission rejected: "
    message = str(error)
    if not message.startswith(prefix):
        return False
    reasons = message.removeprefix(prefix).split("; ")
    allowed = (
        "host 1-minute load reached available CPU capacity ",
        "critical service cpu some PSI ",
        "critical service telemetry unavailable during unit transition: ",
        "host memory some PSI ",
        "host memory full PSI ",
        "host io full PSI ",
    )
    return bool(reasons) and all(reason.startswith(allowed) for reason in reasons)


def wait_for_sustained_admission(initial=None):
    """Wait for 60 continuous safe seconds; transient PSI resets the window."""
    first = initial
    stable_seconds = 0
    while True:
        if first is None:
            try:
                first = admission()
            except ValueError as error:
                if not is_transient_pressure_rejection(error):
                    raise
                print(
                    f"Admission window waiting for host pressure to clear: {error}",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(ADMISSION_SAMPLE_SECONDS)
                continue
        time.sleep(ADMISSION_SAMPLE_SECONDS)
        try:
            current = admission(first["memory_events"])
        except ValueError as error:
            if not is_transient_pressure_rejection(error):
                raise
            stable_seconds = 0
            print(
                f"Admission window reset after transient pressure: {error}",
                file=sys.stderr,
                flush=True,
            )
            continue
        if current["pid"] != first["pid"]:
            raise ValueError("Protected recorder identity changed during admission window")
        stable_seconds += ADMISSION_SAMPLE_SECONDS
        if stable_seconds >= START_STABLE_SECONDS:
            return first


def wait_for_admission_sample(baseline_events):
    """Delay a phase start through short PSI spikes without relaxing limits."""
    while True:
        try:
            return admission(baseline_events)
        except ValueError as error:
            if not is_transient_pressure_rejection(error):
                raise
            print(
                f"Worker start delayed by transient pressure: {error}", file=sys.stderr, flush=True
            )
            time.sleep(ADMISSION_SAMPLE_SECONDS)


def ensure_no_active_validation_units():
    active = subprocess.check_output(
        ["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-legend"],
        text=True,
    )
    names = [line.split()[0] for line in active.splitlines() if line.split()]
    conflicts = [name for name in names if name.startswith("midas-validation-")]
    if conflicts:
        raise ValueError(
            "Another isolated Reality validation unit is active: " + ", ".join(conflicts)
        )


def validate_staged_output(source, output):
    """Validate immutable staged boundary and all source-view symlinks for resume."""
    source = source.resolve()
    if output.is_symlink():
        raise ValueError("Resume output must not be a symbolic link")
    output = output.resolve()
    if (
        not allowed_staging_path(output)
        or output.is_relative_to(source)
        or source.is_relative_to(output)
    ):
        raise ValueError("Use an independent approved staging root for resume")
    if not output.is_dir() or output.is_symlink():
        raise ValueError("Resume output must be an existing ordinary directory")
    required = ("catalog.json", "identities.json", "boundary.json", "admission.json")
    documents = {}
    for name in required:
        path = output / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or unsafe staged receipt: {name}")
        documents[name] = json.loads(path.read_text())
    catalog = documents["catalog.json"]
    identities = documents["identities.json"]
    boundary = documents["boundary.json"]
    initial = documents["admission.json"]
    if boundary.get("source") != str(source):
        raise ValueError("Staged source identity changed")
    if hashlib.sha256(canonical(catalog)).hexdigest() != boundary.get("catalog_sha256"):
        raise ValueError("Staged catalog receipt hash mismatch")
    if hashlib.sha256(canonical(identities)).hexdigest() != boundary.get("identities_sha256"):
        raise ValueError("Staged identity receipt hash mismatch")
    segments = catalog.get("segments")
    if not isinstance(segments, list) or not segments or len(segments) != len(identities):
        raise ValueError("Staged catalog and identities have invalid lengths")
    if initial.get("pid") is None or not isinstance(initial.get("memory_events"), dict):
        raise ValueError("Staged admission baseline is incomplete")

    current_catalog, current_identities, _ = inventory(source)
    if current_catalog["segments"][: len(segments)] != segments:
        raise ValueError("Pinned source catalog prefix changed")
    if current_identities[: len(identities)] != identities:
        raise ValueError("Pinned source file identity changed")

    root = output / "view"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Staged source view is missing or unsafe")
    expected_names = set()
    for info in segments:
        name = info["file"]
        if Path(name).name != name or not name.endswith(".seg"):
            raise ValueError("Unsafe staged segment identity")
        target = source / name
        link = root / name
        sidecar = root / Path(name).with_suffix(".json")
        if not link.is_symlink() or link.resolve() != target:
            raise ValueError(f"Staged source link changed: {name}")
        if sidecar.is_symlink() or not sidecar.is_file() or json.loads(sidecar.read_text()) != info:
            raise ValueError(f"Staged segment sidecar changed: {name}")
        expected_names.update((name, sidecar.name))
    allowed_recovery_files = {recovery.CHECKPOINT_NAME, recovery.CHECKPOINT_NAME + ".tmp"}
    for name in allowed_recovery_files:
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"Unsafe recovery state in staged view: {name}")
    unexpected = {entry.name for entry in root.iterdir()} - expected_names - allowed_recovery_files
    if unexpected:
        raise ValueError(
            "Unexpected files in staged source view: " + ", ".join(sorted(unexpected)[:10])
        )
    return catalog, identities, boundary, initial


def validate_readonly_probe(output, catalog, boundary):
    probe_path = output / "readonly_probe.json"
    policy_path = output / "readonly_probe-landlock.json"
    if (
        not probe_path.is_file()
        or probe_path.is_symlink()
        or not policy_path.is_file()
        or policy_path.is_symlink()
    ):
        raise ValueError("Read-only source probe has not completed")
    probe = json.loads(probe_path.read_text())
    policy = probe.get("policy", {})
    expected_file = output / "view" / catalog["segments"][0]["file"]
    if probe.get("denied_source_file") != str(expected_file):
        raise ValueError("Read-only probe source path does not match the pinned view")
    if (
        probe.get("catalog_segment_sha256", probe.get("source_sha256"))
        != catalog["segments"][0]["sha256"]
    ):
        raise ValueError("Read-only probe's expected segment checksum does not match the catalog")
    if (
        policy.get("source_root") != boundary["source"]
        or policy.get("staging_root") != str(output)
        or policy.get("source_reads") != "allowed"
        or policy.get("filesystem_mutation") != "denied except below staging_root"
    ):
        raise ValueError("Read-only probe policy receipt does not match the staged roots")
    if json.loads(policy_path.read_text()) != policy:
        raise ValueError("Standalone Landlock receipt differs from the probe receipt")
    if probe.get("source_write_denied") is not True:
        # Earlier probe format recorded this only in systemd's successful worker
        # result. Preserve that evidence without treating the catalog hash as a
        # fresh content checksum.
        log = output / "readonly_probe.log"
        if (
            log.is_symlink()
            or not log.is_file()
            or "Finished with result: success" not in log.read_text()
        ):
            raise ValueError("Read-only probe did not prove source write denial")


def phase_attempt_paths(output, phase):
    log = output / f"{phase}.log"
    monitor = output / f"{phase}-monitor.jsonl"
    if not log.exists() and not monitor.exists():
        return log, monitor
    attempt = 1
    while True:
        log = output / f"{phase}-attempt-{attempt}.log"
        monitor = output / f"{phase}-attempt-{attempt}-monitor.jsonl"
        if not log.exists() and not monitor.exists():
            return log, monitor
        attempt += 1


def validate_phase_result(output, phase, catalog, boundary, expected=None):
    path = output / f"{phase}.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Completed phase receipt is missing or unsafe: {phase}")
    result = json.loads(path.read_text())
    if result.get("phase") != phase:
        raise ValueError(f"Phase receipt identity mismatch: {phase}")
    if (
        result.get("boundary_catalog_sha256") != boundary["catalog_sha256"]
        or result.get("boundary_identities_sha256") != boundary["identities_sha256"]
    ):
        raise ValueError(f"Phase receipt source boundary mismatch: {phase}")
    identity = [result.get(key) for key in ("state_sha256", "internal_sha256", "ordinal", "gaps")]
    if (
        result.get("ordinal") != boundary["last_ordinal"]
        or result.get("gaps") != boundary["kinds"].get("gap", 0)
        or not isinstance(identity[0], str)
        or not isinstance(identity[1], str)
    ):
        raise ValueError(f"Phase receipt accounting mismatch: {phase}")
    if expected is not None and identity != expected:
        raise ValueError(f"Phase receipt reconstruction mismatch: {phase}")
    recovery_result = result.get("recovery", {})
    fast = phase in ("fast", "restart", "after_interrupt_save")
    if fast and (
        recovery_result.get("segments_reconstructed") != 0
        or recovery_result.get("prefix_bytes_hashed") != boundary["archive_bytes"]
    ):
        raise ValueError(f"Checkpoint receipt failed full-prefix verification: {phase}")
    if phase == "cold":
        if (
            recovery_result.get("mode") not in ("full_replay", "resumable_full_replay")
            or recovery_result.get("segments_reconstructed") != boundary["segment_count"]
            or recovery_result.get("archive_bytes") != boundary["archive_bytes"]
        ):
            raise ValueError("Cold receipt does not cover the complete pinned archive")
    if phase in ("corrupt", "stale", "after_interrupt"):
        if recovery_result.get("mode") not in ("full_replay", "resumable_full_replay"):
            raise ValueError(f"Expected complete replay for recovery fallback: {phase}")
    return result, identity


def checkpoint_details(path, catalog):
    """Read a checksummed checkpoint and verify its pinned catalog prefix."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Recovery checkpoint is missing or unsafe")
    if path.stat().st_size > recovery.MAX_CHECKPOINT_BYTES:
        raise ValueError("Recovery checkpoint exceeds the format bound")
    with path.open("rb") as source:
        magic, expected_checksum = recovery.HEADER.unpack(source.read(recovery.HEADER.size))
        payload = source.read()
    if magic != recovery.MAGIC or hashlib.sha256(payload).digest() != expected_checksum:
        raise ValueError("Recovery checkpoint framing or checksum is invalid")
    saved = json.loads(payload)
    prefix = saved.get("catalog", {}).get("segments")
    if (
        saved.get("schema_version") != 1
        or saved.get("implementation") != recovery.implementation_identity()
        or not isinstance(prefix, list)
        or not prefix
        or len(prefix) > len(catalog.get("segments", []))
        or prefix != catalog["segments"][: len(prefix)]
    ):
        raise ValueError(
            "Recovery checkpoint does not match the pinned implementation/catalog prefix"
        )
    prefix_catalog = dict(catalog, segments=prefix)
    if saved.get("catalog") != prefix_catalog:
        raise ValueError("Recovery checkpoint manifest identity differs from the pinned prefix")
    engine = recovery._restore(saved["engine"])
    prefix_gaps = sum(item.get("kinds", {}).get("gap", 0) for item in prefix)
    prefix_ordinal = sum(item.get("count", 0) for item in prefix)
    if (
        engine.digest() != saved.get("state_sha256")
        or engine.last_ordinal != prefix_ordinal
        or engine.gaps != prefix_gaps
    ):
        raise ValueError("Recovery checkpoint state differs from its pinned manifest prefix")
    return dict(
        saved=saved,
        engine=engine,
        segment_count=len(prefix),
        ordinal=engine.last_ordinal,
        gaps=engine.gaps,
        state_sha256=engine.digest(),
        checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
        prefix_bytes=sum(item["bytes"] for item in prefix),
    )


def validate_checkpoint_file(path, catalog, expected_identity):
    """Validate the full cold checkpoint before it seeds another phase."""
    details = checkpoint_details(path, catalog)
    if (
        details["segment_count"] != len(catalog["segments"])
        or details["state_sha256"] != expected_identity[0]
        or details["ordinal"] != expected_identity[2]
        or details["gaps"] != expected_identity[3]
    ):
        raise ValueError("Saved cold checkpoint state differs from the cold receipt")
    return dict(size_bytes=details["size_bytes"], state_sha256=details["state_sha256"])


def completed_phases(output, phases, catalog, boundary):
    """Trust only receipts bound to the pinned prefix; leave partial logs intact."""
    completed = set()
    expected = None
    source_quality = None
    incomplete_seen = False
    if (output / "result.json").exists():
        raise ValueError("Validation already has a final result receipt")
    if (output / "readonly_probe.json").exists():
        validate_readonly_probe(output, catalog, boundary)
        completed.add("readonly_probe")
    else:
        incomplete_seen = True
    for phase in phases:
        if phase == "readonly_probe":
            continue
        result_path = output / f"{phase}.json"
        termination_path = output / f"{phase}-termination.json"
        has_receipt = result_path.exists() or termination_path.exists()
        if incomplete_seen and has_receipt:
            raise ValueError(f"Later phase receipt exists after an incomplete phase: {phase}")
        if termination_path.exists() and phase not in ("interrupt", "interrupt_save"):
            raise ValueError(f"Unexpected termination receipt for phase: {phase}")
        if phase in ("interrupt", "interrupt_save") and termination_path.exists():
            if result_path.exists():
                raise ValueError(f"Interrupted phase also has a normal result receipt: {phase}")
            termination = json.loads(termination_path.read_text())
            systemd = termination.get("systemd", "")
            if (
                termination.get("boundary_catalog_sha256") != boundary["catalog_sha256"]
                or termination.get("boundary_identities_sha256") != boundary["identities_sha256"]
                or "ExecMainCode=2" not in systemd
                or "ExecMainStatus=9" not in systemd
            ):
                raise ValueError(f"Interrupted phase receipt is invalid: {phase}")
            completed.add(phase)
            continue
        if phase in ("interrupt", "interrupt_save") and result_path.exists():
            raise ValueError(f"Interrupted phase has a normal result receipt: {phase}")
        if phase == "endurance":
            endurance_path = output / "endurance.json"
            if endurance_path.exists():
                endurance = json.loads(endurance_path.read_text())
                if (
                    endurance.get("seconds", 0) < 3600
                    or endurance.get("boundary_catalog_sha256") != boundary["catalog_sha256"]
                    or endurance.get("boundary_identities_sha256") != boundary["identities_sha256"]
                ):
                    raise ValueError("Existing endurance receipt is incomplete")
                completed.add(phase)
            else:
                incomplete_seen = True
            continue
        if not result_path.exists():
            incomplete_seen = True
            continue
        result, identity = validate_phase_result(output, phase, catalog, boundary, expected)
        if expected is None:
            if phase != "cold":
                raise ValueError("Later phase exists without a cold-recovery receipt")
            expected = identity
            source_quality = result.get("source_quality_audit")
        elif identity != expected:
            raise ValueError(f"Completed phases disagree at {phase}")
        completed.add(phase)
    return completed, expected, source_quality


def cgroup_metrics():
    relative = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
    group = Path("/sys/fs/cgroup") / relative.lstrip("/")
    return {
        name: (group / name).read_text() if (group / name).exists() else None
        for name in (
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
    }


def source_quality_observation(engine, record):
    """Summarize persisted gap/comparison evidence without inferring source truth."""
    kind = record.get("kind")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    if kind == "gap":
        assets = payload.get("assets")
        observed = dict(
            kind="gap",
            ordinal=record.get("ordinal"),
            reason=payload.get("reason", "unknown"),
        )
        for key in ("source", "issue", "error", "reconstruction_version", "stale_ns"):
            if key in payload:
                value = payload[key]
                observed[key] = value[:500] if isinstance(value, str) else value
        if isinstance(assets, list):
            observed["assets_sample"] = assets[:8]
            observed["assets_count"] = len(assets)
        return observed
    if kind != "book_comparison":
        return None

    assessment = payload.get("assessment", "unknown")
    observed = dict(kind="book_comparison", assessment=assessment)
    if assessment != "stable_local_lineage_divergence":
        return observed

    from midas.reality.quality import depth_state

    asset = payload.get("asset_id")
    local = depth_state(engine.books.get(asset)) if isinstance(asset, str) else None
    local_depth = {side: local[side] for side in ("bids", "asks")} if local is not None else None
    local_hash = (
        hashlib.sha256(canonical(local_depth)).hexdigest() if local_depth is not None else None
    )
    lineage_agrees = local is not None and local["last"] == payload.get("after_lineage")
    external_hash = payload.get("independent_depth_sha256")
    if not lineage_agrees:
        classification = "LOCAL_LINEAGE_MISMATCH_AT_COMPARISON_RECORD"
    elif local_hash == external_hash:
        classification = "AUDIT_HASH_MATCHES_BUT_RECORDED_DIVERGENCE"
    elif local_hash is None or external_hash is None:
        classification = "COMPARISON_HASH_UNAVAILABLE"
    else:
        classification = "CONFIRMED_DEPTH_HASH_MISMATCH_DIRECTION_UNKNOWN"
    received_ns = local.get("received_ns") if local is not None else None
    response_ns = payload.get("response_ns")
    observed.update(
        classification=classification,
        record_ordinal=record.get("ordinal"),
        raw_ordinal=payload.get("raw_ordinal"),
        asset_id=asset,
        condition=payload.get("condition"),
        before_lineage=payload.get("before_lineage"),
        after_lineage=payload.get("after_lineage"),
        local_lineage=local.get("last") if local is not None else None,
        local_lineage_agrees_with_after=lineage_agrees,
        local_depth_sha256=local_hash,
        independent_depth_sha256=external_hash,
        local_hash_matches_independent=local_hash == external_hash,
        local_level_counts=(
            {side: len(local[side]) for side in ("bids", "asks")} if local is not None else None
        ),
        local_received_ns=received_ns,
        response_ns=response_ns,
        local_age_at_response_ns=(
            response_ns - received_ns
            if isinstance(response_ns, int) and isinstance(received_ns, int)
            else None
        ),
        request_ns=payload.get("request_ns"),
        round_trip_ns=payload.get("round_trip_ns"),
        source_timestamp_ms=payload.get("source_timestamp_ms"),
        source_native_hash=payload.get("source_native_hash"),
        limitation=(
            "The historical REST depth body was not persisted. Hash mismatch confirms unequal "
            "views at stable local lineage but cannot identify which view was incomplete."
        ),
    )
    return observed


def new_source_quality_audit():
    return dict(
        gap_records=0,
        gap_reasons=Counter(),
        gap_examples={},
        comparison_records=0,
        comparison_assessments=Counter(),
        stable_lineage_divergences=[],
    )


def source_quality_document(audit):
    if audit is None:
        return None
    return dict(
        gap_records=audit["gap_records"],
        gap_reasons=dict(audit["gap_reasons"]),
        gap_examples=audit["gap_examples"],
        comparison_records=audit["comparison_records"],
        comparison_assessments=dict(audit["comparison_assessments"]),
        stable_lineage_divergences=audit["stable_lineage_divergences"],
    )


def restore_source_quality_audit(target, document, prefix_catalog):
    if target is None:
        if document is not None:
            raise ValueError("Unexpected source-quality audit in this recovery phase")
        return
    if not isinstance(document, dict):
        raise ValueError("Cold replay progress lacks its source-quality audit")
    gaps = int(document.get("gap_records", -1))
    comparisons = int(document.get("comparison_records", -1))
    gap_reasons = document.get("gap_reasons")
    assessments = document.get("comparison_assessments")
    divergences = document.get("stable_lineage_divergences")
    examples = document.get("gap_examples")
    expected_gaps = sum(item.get("kinds", {}).get("gap", 0) for item in prefix_catalog["segments"])
    expected_comparisons = sum(
        item.get("kinds", {}).get("book_comparison", 0) for item in prefix_catalog["segments"]
    )
    if (
        not isinstance(gap_reasons, dict)
        or not isinstance(assessments, dict)
        or not isinstance(examples, dict)
        or not isinstance(divergences, list)
        or gaps != expected_gaps
        or comparisons != expected_comparisons
        or sum(gap_reasons.values()) != gaps
        or sum(assessments.values()) != comparisons
        or len(divergences) != assessments.get("stable_local_lineage_divergence", 0)
    ):
        raise ValueError("Cold replay quality audit does not reconcile with the pinned prefix")
    target.clear()
    target.update(
        gap_records=gaps,
        gap_reasons=Counter(gap_reasons),
        gap_examples=examples,
        comparison_records=comparisons,
        comparison_assessments=Counter(assessments),
        stable_lineage_divergences=divergences,
    )


def validate_progress_document(path, phase, boundary, catalog):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Recovery progress receipt is missing or unsafe: {path.name}")
    document = json.loads(path.read_text())
    index = document.get("next_segment_index")
    if (
        document.get("schema_version") != 1
        or document.get("phase") != phase
        or document.get("boundary_catalog_sha256") != boundary["catalog_sha256"]
        or document.get("boundary_identities_sha256") != boundary["identities_sha256"]
        or type(index) is not int
        or not 0 < index <= len(catalog["segments"])
    ):
        raise ValueError("Recovery progress receipt is not bound to this phase and boundary")
    prefix = dict(catalog, segments=catalog["segments"][:index])
    if (
        document.get("segment_count") != len(catalog["segments"])
        or document.get("ordinal") != sum(item["count"] for item in prefix["segments"])
        or document.get("gaps")
        != sum(item.get("kinds", {}).get("gap", 0) for item in prefix["segments"])
        or not isinstance(document.get("state_sha256"), str)
    ):
        raise ValueError("Recovery progress receipt has inconsistent prefix accounting")
    return document, prefix


def progress_matches_checkpoint(document, details):
    if (
        document["next_segment_index"] != details["segment_count"]
        or document["ordinal"] != details["ordinal"]
        or document["gaps"] != details["gaps"]
        or document["state_sha256"] != details["state_sha256"]
    ):
        return False
    saved_checksum = document.get("checkpoint_sha256")
    return saved_checksum is None or saved_checksum == details["checkpoint_sha256"]


def write_progress_summary(output, phase, document):
    atomic_storage_json(
        output / f"{phase}-progress-summary.json",
        dict(
            phase=phase,
            updated_at=document.get("updated_at"),
            next_segment_index=document["next_segment_index"],
            segment_count=document.get("segment_count"),
            ordinal=document["ordinal"],
            gaps=document["gaps"],
            state_sha256=document["state_sha256"],
            boundary_catalog_sha256=document["boundary_catalog_sha256"],
            boundary_identities_sha256=document["boundary_identities_sha256"],
        ),
    )


def quarantine_staging_checkpoint(path, output, phase):
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        path.unlink(missing_ok=True)
        return "unsafe_checkpoint_removed_from_isolated_stage"
    retained = output / f"{phase}-rejected-checkpoint-{uuid.uuid4().hex[:8]}.bin"
    shutil.copyfile(path, retained)
    path.unlink()
    return retained.name


def resumable_reconstruction(root, catalog, boundary, phase, quality_audit, audit_enabled):
    """Replay verified segment chunks, committing checkpoint and audit together."""
    output = root.parent
    checkpoint = root / recovery.CHECKPOINT_NAME
    progress_path = output / f"{phase}-progress.json"
    pending_path = output / f"{phase}-progress.pending.json"
    progress = None
    pending = None
    if progress_path.exists():
        progress, _ = validate_progress_document(progress_path, phase, boundary, catalog)
    if pending_path.exists():
        pending, _ = validate_progress_document(pending_path, phase, boundary, catalog)

    checkpoint_state = None
    if checkpoint.exists() or checkpoint.is_symlink():
        try:
            checkpoint_state = checkpoint_details(checkpoint, catalog)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, struct.error):
            checkpoint_state = None

    selected = None
    for document in (pending, progress):
        if (
            document is not None
            and checkpoint_state is not None
            and progress_matches_checkpoint(document, checkpoint_state)
        ):
            selected = document
            break
    if selected is None and progress is not None:
        # A crash or damaged checkpoint must not discard a committed replay
        # prefix. Recovery below will reconstruct that prefix from raw records.
        selected = progress

    start_index = 0
    prefix_hash_verified = 0
    chunks_this_invocation = 0
    fallback_reason = None
    engine = None
    if selected is not None:
        start_index = selected["next_segment_index"]
        prefix_catalog = dict(catalog, segments=catalog["segments"][:start_index])
        restore_source_quality_audit(
            quality_audit, selected.get("source_quality_audit"), prefix_catalog
        )
        if not (checkpoint_state and progress_matches_checkpoint(selected, checkpoint_state)):
            quarantine_staging_checkpoint(checkpoint, output, phase)
        audit_enabled["value"] = False
        engine, restore_status = recovery.recover(root, prefix_catalog)
        audit_enabled["value"] = True
        if (
            engine.digest() != selected["state_sha256"]
            or engine.last_ordinal != selected["ordinal"]
            or engine.gaps != selected["gaps"]
        ):
            raise ValueError("Verified source prefix differs from its committed progress receipt")
        prefix_hash_verified = restore_status.get("prefix_bytes_hashed", 0)
        fallback_reason = restore_status.get("fallback_reason")
        if restore_status.get("mode") == "full_replay":
            # A damaged accelerator is disposable; the raw prefix and progress
            # state remain authoritative. Re-publish only after the replay agrees.
            recovery.save(root, engine, prefix_catalog)
            document = dict(
                selected, checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            )
            atomic_storage_json(progress_path, document)
            selected = document
        if pending_path.exists():
            pending_path.unlink()
            sync_dir(output)
        write_progress_summary(output, phase, selected)
    else:
        if phase == "cold" and (checkpoint.exists() or checkpoint.is_symlink()):
            quarantine_staging_checkpoint(checkpoint, output, phase)
        engine = None
        if pending_path.exists():
            pending_path.unlink()
            sync_dir(output)

    segments = catalog["segments"]
    while start_index < len(segments):
        end_index = min(len(segments), start_index + COLD_CHUNK_SEGMENTS)
        prefix_catalog = dict(catalog, segments=segments[:end_index])
        chunk_catalog = dict(catalog, segments=segments[start_index:end_index])
        if start_index == 0:
            # This first bounded fallback proves an absent, corrupt, or stale
            # checkpoint is rejected before ordinary source replay continues.
            engine, chunk_status = recovery.recover(root, chunk_catalog)
            fallback_reason = chunk_status.get("fallback_reason")
        else:
            engine, _ = recovery.replay(root, chunk_catalog, _engine=engine)
        if engine.last_ordinal != sum(
            item["count"] for item in prefix_catalog["segments"]
        ) or engine.gaps != sum(
            item.get("kinds", {}).get("gap", 0) for item in prefix_catalog["segments"]
        ):
            raise ValueError("Chunked recovery prefix accounting mismatch")

        document = dict(
            schema_version=1,
            phase=phase,
            boundary_catalog_sha256=boundary["catalog_sha256"],
            boundary_identities_sha256=boundary["identities_sha256"],
            next_segment_index=end_index,
            ordinal=engine.last_ordinal,
            gaps=engine.gaps,
            state_sha256=engine.digest(),
            source_quality_audit=source_quality_document(quality_audit),
            fallback_reason=fallback_reason,
            checkpoint_sha256=None,
            segment_count=len(segments),
            updated_at=datetime.now(UTC).isoformat(),
        )
        atomic_storage_json(pending_path, document)
        recovery.save(root, engine, prefix_catalog)
        document["checkpoint_sha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        atomic_storage_json(pending_path, document)
        atomic_storage_json(progress_path, document)
        pending_path.unlink(missing_ok=True)
        sync_dir(output)
        write_progress_summary(output, phase, document)
        start_index = end_index
        chunks_this_invocation += 1

    if engine is None:
        raise ValueError("Chunked recovery did not produce an engine")
    final_checkpoint = checkpoint_details(checkpoint, catalog)
    if (
        final_checkpoint["segment_count"] != len(segments)
        or final_checkpoint["state_sha256"] != engine.digest()
    ):
        raise ValueError("Final chunk checkpoint does not cover the complete pinned archive")
    return engine, dict(
        mode="resumable_full_replay"
        if progress is not None or pending is not None
        else "full_replay",
        fallback_reason=fallback_reason,
        segments_reconstructed=len(segments),
        segments_reconstructed_this_invocation=(
            len(segments) - (selected["next_segment_index"] if selected is not None else 0)
        ),
        chunks_completed_this_invocation=chunks_this_invocation,
        chunk_size_segments=COLD_CHUNK_SEGMENTS,
        prefix_segments_restored=(selected["next_segment_index"] if selected is not None else 0),
        prefix_bytes_hashed_on_resume=prefix_hash_verified,
        archive_bytes=sum(item["bytes"] for item in segments),
        checkpoint_bytes=final_checkpoint["size_bytes"],
        checkpoint_sha256=final_checkpoint["checkpoint_sha256"],
        progress_receipt=str(progress_path),
        recovery_scope=(
            "Every pinned segment was checksum-verified and reconstructed from raw records; "
            "segment-boundary checkpoints make interrupted cold replay resumable."
        ),
    )


def endurance(root, engine, catalog, seconds):
    """Two captured frames/second, isolated durable writes; no source subscriptions."""
    if seconds != 3600:
        raise ValueError("Endurance duration must be 3600 seconds")
    payloads = []
    for info in reversed(catalog["segments"]):
        for record, _ in records(root / info["file"]):
            if record["kind"] == "frame":
                payloads.append(record["payload"])
                if len(payloads) == 16:
                    break
        if len(payloads) == 16:
            break
    if not payloads:
        raise ValueError("No captured frames for replay")
    budget = sum(s["bytes"] for s in catalog["segments"]) + 128 * 1024**2
    store = Store(
        root,
        budget=budget,
        reserve=20 * 1024**3,
        segment_bytes=8 * 1024**2,
        segment_seconds=3600,
        verify_existing=False,
        defer_open=True,
    )
    store.activate()
    engine.consume(store.append("gap", dict(reason="isolated_controlled_replay_start")))
    started, last_checkpoint, last_report = time.monotonic(), 0, 0
    frames, maximum_latency = 0, 0.0
    try:
        while time.monotonic() - started < seconds:
            before = time.monotonic()
            engine.consume(store.append("frame", payloads[frames % len(payloads)]))
            maximum_latency = max(maximum_latency, time.monotonic() - before)
            frames += 1
            elapsed = time.monotonic() - started
            if elapsed - last_checkpoint >= 60:
                engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
                store.rotate()
                recovery.save(root, engine, manifest(root))
                last_checkpoint = elapsed
            if elapsed - last_report >= 300:
                with (root.parent / "endurance-samples.jsonl").open("a") as out:
                    out.write(
                        json.dumps(
                            dict(
                                at=datetime.now(UTC).isoformat(),
                                elapsed=elapsed,
                                frames=frames,
                                max_append_seconds=maximum_latency,
                                gc_counts=gc.get_count(),
                                gc_stats=gc.get_stats(),
                                cgroup=cgroup_metrics(),
                            )
                        )
                        + "\n"
                    )
                last_report = elapsed
            time.sleep(max(0, 0.5 - (time.monotonic() - before)))
        engine.consume(store.append("gap", dict(reason="isolated_controlled_replay_stop")))
        engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
    finally:
        store.close()
    complete = manifest(root)
    recovery.save(root, engine, complete)
    again, restored = recovery.recover(root, complete)
    if again.__dict__ != engine.__dict__:
        raise ValueError("Endurance clean restart changed internal state")
    boundary = json.loads((root.parent / "boundary.json").read_text())
    write(
        root.parent / "endurance.json",
        dict(
            seconds=time.monotonic() - started,
            frames=frames,
            max_append_seconds=maximum_latency,
            restart=restored,
            ordinal=engine.last_ordinal,
            state_sha256=engine.digest(),
            cgroup=cgroup_metrics(),
            boundary_catalog_sha256=boundary["catalog_sha256"],
            boundary_identities_sha256=boundary["identities_sha256"],
            scope="captured raw payload replay; synchronous persistence; no network/reconnection test",
        ),
    )


def worker(root, phase):
    """Only called inside the staging unit; artifacts are under disposable root."""
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    catalog = json.loads((root.parent / "catalog.json").read_text())
    boundary = json.loads((root.parent / "boundary.json").read_text())
    sandbox = apply_readonly_source_policy(Path(boundary["source"]), root.parent)
    source_file = root / catalog["segments"][0]["file"]
    verify_source_write_denied(source_file)
    write(root.parent / f"{phase}-landlock.json", sandbox)
    if phase == "readonly_probe":
        write(
            root.parent / "readonly_probe.json",
            dict(
                denied_source_file=str(source_file),
                catalog_segment_sha256=catalog["segments"][0]["sha256"],
                source_write_denied=True,
                policy=sandbox,
            ),
        )
        return
    checkpoint = root / recovery.CHECKPOINT_NAME
    if checkpoint.is_symlink():
        raise ValueError("Checkpoint must be independent writable staging state")
    phase_progress = root.parent / f"{phase}-progress.json"
    phase_pending = root.parent / f"{phase}-progress.pending.json"
    phase_is_resumable = phase in {"cold", "corrupt", "stale", "after_interrupt"}
    has_phase_progress = phase_progress.exists() or phase_pending.exists()
    if phase in ("cold", "interrupt", "after_interrupt") and not has_phase_progress:
        checkpoint.unlink(missing_ok=True)
        checkpoint.with_suffix(".tmp").unlink(missing_ok=True)
    elif phase == "corrupt" and not has_phase_progress:
        checkpoint.write_bytes(b"intentionally invalid isolated checkpoint")
    elif phase == "stale" and not has_phase_progress:
        # Valid framing/checksum, incompatible reconstruction identity.
        data = json.loads((root.parent / "valid.checkpoint").read_bytes()[recovery.HEADER.size :])
        data["implementation"] = "stale-isolated-implementation"
        payload = canonical(data)
        checkpoint.write_bytes(
            recovery.HEADER.pack(recovery.MAGIC, hashlib.sha256(payload).digest()) + payload
        )
    elif phase == "after_interrupt_save":
        if checkpoint.read_bytes() != (root.parent / "valid.checkpoint").read_bytes():
            raise ValueError("Interrupted save changed previously durable checkpoint")
    if phase == "interrupt":
        from midas.reality.reconstruction import Engine

        consume = Engine.consume

        def interrupted(self, record):
            consume(self, record)
            if self.last_ordinal >= 2:
                os.kill(os.getpid(), signal.SIGKILL)

        Engine.consume = interrupted
    started = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    base_memory = Path("/proc/self/smaps_rollup").read_text()
    base_gc = gc.get_stats()
    quality_audit = new_source_quality_audit() if phase == "cold" else None
    original_consume = None
    audit_enabled = {"value": True}
    if quality_audit is not None:
        from midas.reality.reconstruction import Engine

        original_consume = Engine.consume

        def audited_consume(current_engine, record):
            if audit_enabled["value"]:
                observed = source_quality_observation(current_engine, record)
                if observed is not None and observed["kind"] == "gap":
                    quality_audit["gap_records"] += 1
                    reason = observed["reason"]
                    quality_audit["gap_reasons"][reason] += 1
                    examples = quality_audit["gap_examples"].setdefault(reason, [])
                    if len(examples) < 3:
                        examples.append(observed)
                elif observed is not None and observed["kind"] == "book_comparison":
                    quality_audit["comparison_records"] += 1
                    quality_audit["comparison_assessments"][observed["assessment"]] += 1
                    if observed["assessment"] == "stable_local_lineage_divergence":
                        quality_audit["stable_lineage_divergences"].append(observed)
            original_consume(current_engine, record)

        Engine.consume = audited_consume
    if phase_is_resumable:
        engine, status = resumable_reconstruction(
            root, catalog, boundary, phase, quality_audit, audit_enabled
        )
    else:
        engine, status = recovery.recover(root, catalog)
    if original_consume is not None:
        Engine.consume = original_consume
    recovered_seconds = time.monotonic() - started
    if phase == "endurance":
        endurance(root, engine, catalog, 3600)
        return
    if engine.last_ordinal != sum(s["count"] for s in catalog["segments"]):
        raise ValueError("Record accounting mismatch")
    if engine.gaps != sum(s["kinds"].get("gap", 0) for s in catalog["segments"]):
        raise ValueError("Gap accounting mismatch")
    internal = hashlib.sha256()
    for chunk in _canonical_chunks(recovery._snapshot(engine)):
        internal.update(chunk)
    if phase == "interrupt_save":
        # Kill at atomic publication after tmp fsync. Existing checkpoint must survive.
        recovery.os.replace = lambda *a: os.kill(os.getpid(), signal.SIGKILL)
    save_started = time.monotonic()
    size = (
        status["checkpoint_bytes"] if phase_is_resumable else recovery.save(root, engine, catalog)
    )
    after = resource.getrusage(resource.RUSAGE_SELF)
    audit_result = None
    if quality_audit is not None:
        audit_result = dict(
            quality_audit,
            gap_reasons=dict(quality_audit["gap_reasons"]),
            comparison_assessments=dict(quality_audit["comparison_assessments"]),
            interpretation=(
                "Counts and local-state identities are replay-derived. Stable REST/WS hash "
                "differences do not prove which source view is incomplete."
            ),
        )
    result = dict(
        phase=phase,
        recovery=status,
        recovery_seconds=recovered_seconds,
        save_seconds=time.monotonic() - save_started,
        checkpoint_bytes=size,
        wall_seconds=time.monotonic() - started,
        cpu_seconds=after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
        peak_rss_kib=after.ru_maxrss,
        ordinal=engine.last_ordinal,
        gaps=engine.gaps,
        counts=dict(engine.counts),
        state_sha256=engine.digest(),
        internal_sha256=internal.hexdigest(),
        sequence_verified=False,
        readiness_scope=(
            "complete archive reconstruction with durable segment-boundary progress; "
            "no collector/network start"
            if phase_is_resumable
            else "reconstruction and checkpoint save; no collector/network start"
        ),
        base_memory=base_memory,
        final_memory=Path("/proc/self/smaps_rollup").read_text(),
        cgroup=cgroup_metrics(),
        gc_before=base_gc,
        gc_after=gc.get_stats(),
        process_io=Path("/proc/self/io").read_text(),
        boundary_catalog_sha256=boundary["catalog_sha256"],
        boundary_identities_sha256=boundary["identities_sha256"],
        source_quality_audit=audit_result,
    )
    write(root.parent / f"{phase}.json", result)


def run(source, output, with_endurance=False, resume=False):
    ensure_no_active_validation_units()
    phases = ("readonly_probe", "cold", "fast", "corrupt", "interrupt_save", "after_interrupt_save")
    if with_endurance:
        phases += ("endurance",)
    reserve = (
        STAGING_VOLUME_RESERVE_BYTES
        if output.is_relative_to(STAGING_OUTPUT_ROOT)
        else PROTECTED_DISK_RESERVE_BYTES
    )
    if shutil.disk_usage(output.parent).free < reserve + STAGING_EXTRA_BYTES:
        raise ValueError("Need the staging-volume reserve and 1 GiB staging allowance")

    if resume:
        catalog, identities, summary, initial = validate_staged_output(source, output)
        validate_readonly_probe(output, catalog, summary) if (
            output / "readonly_probe.json"
        ).exists() else None
        completed, expected, source_quality = completed_phases(output, phases, catalog, summary)
        if with_endurance != json.loads((output / "staging-policy.json").read_text()).get(
            "with_endurance", False
        ):
            raise ValueError("Resume endurance setting differs from the original run")
        root = output / "view"
        policy = dict(
            resumed_at=datetime.now(UTC).isoformat(),
            boundary_catalog_sha256=summary["catalog_sha256"],
            boundary_identities_sha256=summary["identities_sha256"],
            runtime_max_seconds=7200,
            maximum_total_pressure_pause_seconds=MAX_STAGE_PRESSURE_PAUSE_SECONDS,
            cpu_quota_percent=STAGING_CPU_QUOTA_PERCENT,
            memory_high_bytes=640 * 1024**2,
            memory_max_bytes=768 * 1024**2,
            memory_swap_max_bytes=0,
            output_max_bytes=256 * 1024**2,
            recovery_chunk_segments=COLD_CHUNK_SEGMENTS,
            cpu_admission_policy=(
                f"Host cpu PSI is recorded as telemetry; 1-minute load per available CPU gates "
                f"at {HOST_CPU_LOAD_AVG1_PER_CPU_MAX}; each critical "
                f"service cgroup gates at cpu.some avg10 >= {CRITICAL_CPU_SOME_AVG10_MAX}% "
                f"or avg60 >= {CRITICAL_CPU_SOME_AVG60_MAX}%"
            ),
            source_policy="Landlock read-only across /; writes allowed only below this output root",
            completed_phases=sorted(completed),
        )
        write(output / f"resume-policy-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.json", policy)
    else:
        if output.exists() or output.is_symlink():
            raise ValueError(
                "New validation output must not already exist; use resume for a saved run"
            )
        # Mandatory gate is evaluated before staging setup or expensive I/O.
        initial = wait_for_sustained_admission()
        catalog, identities, summary = inventory(source)
        output.mkdir(mode=0o700, exist_ok=False)
        write(output / "catalog.json", catalog)
        write(output / "identities.json", identities)
        write(output / "boundary.json", summary)
        root = output / "view"
        root.mkdir()
        # Reuse finalized source bytes without copying. Worker Landlock rules allow
        # reads across the filesystem and mutations only below this run-owned root.
        for info in catalog["segments"]:
            (root / info["file"]).symlink_to(source / info["file"])
            write((root / info["file"]).with_suffix(".json"), info)
        write(output / "admission.json", initial)
        write(
            output / "staging-policy.json",
            dict(
                memory_high_bytes=640 * 1024**2,
                memory_max_bytes=768 * 1024**2,
                memory_swap_max_bytes=0,
                cpu_quota_percent=STAGING_CPU_QUOTA_PERCENT,
                cpu_weight=STAGING_CPU_WEIGHT,
                nice=19,
                io_scheduling_class="idle",
                runtime_max_seconds=7200,
                maximum_total_pressure_pause_seconds=MAX_STAGE_PRESSURE_PAUSE_SECONDS,
                output_max_bytes=256 * 1024**2,
                recovery_chunk_segments=COLD_CHUNK_SEGMENTS,
                cpu_admission_policy=(
                    f"Host cpu PSI is recorded as telemetry; 1-minute load per available CPU gates "
                    f"at {HOST_CPU_LOAD_AVG1_PER_CPU_MAX}; each critical "
                    f"service cgroup gates at cpu.some avg10 >= {CRITICAL_CPU_SOME_AVG10_MAX}% "
                    f"or avg60 >= {CRITICAL_CPU_SOME_AVG60_MAX}%"
                ),
                with_endurance=with_endurance,
                source_policy="Landlock read-only across /; writes allowed only below this output root",
            ),
        )
        completed, expected, source_quality = set(), None, None

    if "cold" in completed:
        checkpoint = root / recovery.CHECKPOINT_NAME
        saved_checkpoint = output / "valid.checkpoint"
        if saved_checkpoint.exists():
            validate_checkpoint_file(saved_checkpoint, catalog, expected)
        else:
            # A parent crash immediately after the cold worker can leave only
            # its newly published checkpoint. Validate it against the cold
            # receipt before promoting it into the immutable resume baseline.
            validate_checkpoint_file(checkpoint, catalog, expected)
            shutil.copyfile(checkpoint, saved_checkpoint)

    executed = []
    for phase in phases:
        if phase in completed:
            continue
        if phase in ("fast", "restart", "interrupt_save", "after_interrupt_save"):
            saved_checkpoint = output / "valid.checkpoint"
            validate_checkpoint_file(saved_checkpoint, catalog, expected)
            current_checkpoint = root / recovery.CHECKPOINT_NAME
            if current_checkpoint.is_symlink():
                raise ValueError("Worker checkpoint path became a symbolic link")
            shutil.copyfile(saved_checkpoint, current_checkpoint)
        # Each new phase receives its own continuous safe window. The thresholds
        # and protected-recorder reserve are unchanged across retries.
        phase_admission = wait_for_sustained_admission(initial)
        if phase_admission["pid"] != initial["pid"]:
            raise ValueError("Protected recorder identity changed before a phase")
        name = "midas-validation-" + uuid.uuid4().hex[:12]
        command = [
            "systemd-run",
            "--user",
            "--wait",
            "--pipe",
            "--unit=" + name,
            "-p",
            "MemoryHigh=640M",
            "-p",
            "MemoryMax=768M",
            "-p",
            "MemorySwapMax=0",
            "-p",
            f"CPUQuota={STAGING_CPU_QUOTA_PERCENT}%",
            "-p",
            f"CPUWeight={STAGING_CPU_WEIGHT}",
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
            "ReadWritePaths=" + str(output),
            "-p",
            "PrivateNetwork=yes",
            "-p",
            "NoNewPrivileges=yes",
            "-p",
            "LimitCORE=0",
            "-p",
            "IOAccounting=yes",
            "-p",
            "RestrictAddressFamilies=AF_UNIX",
            "--setenv=PYTHONDONTWRITEBYTECODE=1",
            "--setenv=PYTHONPATH=" + os.environ["PYTHONPATH"],
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            "--source",
            str(root),
            "--phase",
            phase,
        ]
        log_path, monitor_path = phase_attempt_paths(output, phase)
        with log_path.open("w") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            paused_at = None
            pressure_pause_seconds = 0.0
            safe_samples_after_pause = 0
            try:
                with monitor_path.open("w") as monitor:
                    while child.poll() is None:
                        try:
                            sample = admission(initial["memory_events"])
                        except ValueError as error:
                            if not is_transient_pressure_rejection(error):
                                raise
                            if paused_at is None:
                                subprocess.run(["systemctl", "--user", "freeze", name], check=True)
                                paused_at = time.monotonic()
                                safe_samples_after_pause = 0
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
                                pressure_pause_seconds + time.monotonic() - paused_at
                                > MAX_STAGE_PRESSURE_PAUSE_SECONDS
                            ):
                                raise ValueError(
                                    "Staging worker exceeded its pressure-pause budget; "
                                    "preserved output and source"
                                ) from error
                            time.sleep(ADMISSION_SAMPLE_SECONDS)
                            continue
                        if sample["pid"] != initial["pid"]:
                            raise ValueError("Protected recorder changed")
                        if paused_at is not None:
                            safe_samples_after_pause += 1
                            if safe_samples_after_pause < RESUME_STABLE_SAMPLES:
                                monitor.write(
                                    json.dumps(
                                        dict(
                                            event="pressure_clear_sample",
                                            at=datetime.now(UTC).isoformat(),
                                            consecutive_safe_samples=safe_samples_after_pause,
                                        )
                                    )
                                    + "\n"
                                )
                                monitor.flush()
                                time.sleep(ADMISSION_SAMPLE_SECONDS)
                                continue
                            elapsed = time.monotonic() - paused_at
                            subprocess.run(["systemctl", "--user", "thaw", name], check=True)
                            pressure_pause_seconds += elapsed
                            monitor.write(
                                json.dumps(
                                    dict(
                                        event="worker_resumed_after_host_pressure",
                                        at=datetime.now(UTC).isoformat(),
                                        pause_seconds=elapsed,
                                        total_pressure_pause_seconds=pressure_pause_seconds,
                                    )
                                )
                                + "\n"
                            )
                            monitor.flush()
                            paused_at = None
                            safe_samples_after_pause = 0
                        owned = subprocess.check_output(
                            [
                                "systemctl",
                                "--user",
                                "show",
                                name,
                                "-p",
                                "ControlGroup",
                                "-p",
                                "MemoryPeak",
                                "-p",
                                "CPUUsageNSec",
                                "-p",
                                "IOReadBytes",
                                "-p",
                                "IOWriteBytes",
                            ],
                            text=True,
                        )
                        cg = dict(line.split("=", 1) for line in owned.splitlines())["ControlGroup"]
                        details = {}
                        if cg:
                            for filename in (
                                "memory.current",
                                "memory.peak",
                                "memory.stat",
                                "memory.events",
                                "cpu.stat",
                                "io.stat",
                                "cpu.pressure",
                                "memory.pressure",
                                "io.pressure",
                            ):
                                path = Path("/sys/fs/cgroup") / cg.lstrip("/") / filename
                                if path.exists():
                                    details[filename] = path.read_text()
                        progress_path = output / f"{phase}-progress-summary.json"
                        phase_progress = (
                            json.loads(progress_path.read_text())
                            if progress_path.is_file() and not progress_path.is_symlink()
                            else None
                        )
                        monitor.write(
                            json.dumps(
                                dict(
                                    at=datetime.now(UTC).isoformat(),
                                    protected=sample,
                                    worker=owned,
                                    cgroup=details,
                                    phase_progress=phase_progress,
                                )
                            )
                            + "\n"
                        )
                        monitor.flush()
                        if shutil.disk_usage(output).free < reserve:
                            raise ValueError(
                                "Staging filesystem fell below its reserved free space"
                            )
                        time.sleep(5)
                child.wait()
            except BaseException:
                # The random owned unit is the ONLY unit this tool may stop.
                if paused_at is not None:
                    subprocess.run(["systemctl", "--user", "thaw", name], check=False)
                subprocess.run(["systemctl", "--user", "stop", name], check=False)
                child.wait(timeout=15)
                raise
        killed = phase in ("interrupt", "interrupt_save")
        if killed:
            status = subprocess.check_output(
                ["systemctl", "--user", "show", name, "-p", "ExecMainCode", "-p", "ExecMainStatus"],
                text=True,
            )
            write(
                output / f"{phase}-termination.json",
                dict(
                    systemd=status,
                    boundary_catalog_sha256=summary["catalog_sha256"],
                    boundary_identities_sha256=summary["identities_sha256"],
                ),
            )
            if "ExecMainCode=2\n" not in status or "ExecMainStatus=9\n" not in status:
                raise ValueError("Expected isolated SIGKILL did not occur")
            executed.append(phase)
            continue
        if child.returncode:
            raise ValueError(f"Worker failed: {phase}; inspect retained log")
        executed.append(phase)
        if phase == "readonly_probe":
            validate_readonly_probe(output, catalog, summary)
            continue
        if phase == "endurance":
            continue
        result, identity = validate_phase_result(output, phase, catalog, summary, expected)
        if phase == "cold":
            source_quality = result.get("source_quality_audit")
            expected = identity
            shutil.copyfile(root / recovery.CHECKPOINT_NAME, output / "valid.checkpoint")
        if identity != expected:
            raise ValueError(f"Reconstruction differs: {phase}")
        fast = phase in ("fast", "restart", "after_interrupt_save")
        if fast and result["recovery"]["segments_reconstructed"] != 0:
            raise ValueError("Checkpoint did not eliminate prefix reconstruction")
        if fast and result["recovery"]["prefix_bytes_hashed"] != summary["archive_bytes"]:
            raise ValueError("Checkpoint did not verify all source bytes")
        if (
            phase in ("corrupt", "stale", "after_interrupt")
            and result["recovery"]["mode"] != "full_replay"
        ):
            raise ValueError("Expected verified full replay fallback")

    staged_bytes = sum(
        p.stat().st_size for p in output.rglob("*") if p.is_file() and not p.is_symlink()
    )
    if staged_bytes > 256 * 1024**2:
        raise ValueError("Independent staging exceeds the 256 MiB bound")
    final_catalog, final_identities, _ = inventory(source)
    if (
        final_catalog["segments"][: len(catalog["segments"])] != catalog["segments"]
        or final_identities[: len(identities)] != identities
    ):
        raise ValueError("Source prefix changed")
    completed_now = completed_phases(output, phases, catalog, summary)[0]
    if completed_now != set(phases):
        raise ValueError("Recovery matrix is incomplete; staged output is resumable")
    write(
        output / "result.json",
        dict(
            recovery_matrix="PASSED",
            boundary=summary,
            collector_readiness="UNTESTED",
            endurance="PASSED" if with_endurance else "UNTESTED",
            deployment="NOT PERFORMED",
            resumed=resume,
            executed_phases=executed,
            source_quality_audit=source_quality,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "run", "resume", "worker"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--with-endurance", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    if args.command == "inventory":
        _, _, summary = inventory(source)
        write(args.output, summary)
    elif args.command == "worker":
        if not allowed_staging_path(source) or source.name != "view":
            raise ValueError("Worker view must be under an approved disposable staging root")
        worker(source, args.phase)
    else:
        if args.output is None:
            parser.error("--output is required for run and resume")
        output = Path(os.path.abspath(args.output))
        if output.is_symlink():
            raise ValueError("Validation output must not be a symbolic link")
        if (
            not allowed_staging_path(output)
            or output.is_relative_to(source)
            or source.is_relative_to(output)
        ):
            raise ValueError("Use a new output root under an approved staging location")
        run(source, output, args.with_endurance, resume=args.command == "resume")


if __name__ == "__main__":
    main()
