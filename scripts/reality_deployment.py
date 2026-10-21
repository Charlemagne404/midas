"""Guarded recorder deployment with a one-start, no-automatic-rollback policy.

Run verify, then preflight, then apply. Apply installs Restart=no before its single
stop/start and waits for full-store replay plus a stable fresh-book window. Failure
leaves automatic restarts disabled and requires a separately authorized decision;
it never starts a rollback. Raw recording roots remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from midas.reality import recovery
from midas.reality.config import Config
from midas.reality.replay import replay
from midas.reality.resources import require_restart_safe
from midas.reality.storage import (
    atomic_json,
    canonical,
    file_hash,
    manifest,
    read_manifest,
    sync_dir,
)

WORKSPACE = Path(__file__).resolve().parents[1]
PRODUCTION_WORKSPACE = Path.home() / "midas-reality"
PRODUCTION_PYTHON = PRODUCTION_WORKSPACE / ".venv/bin/python"
PRODUCTION_CONFIG = PRODUCTION_WORKSPACE / "deploy/reality.json"
SERVICE_UNIT_SOURCE = WORKSPACE / "deploy/systemd/user/midas-reality.service"
SERVICE_UNIT_TARGET = Path.home() / ".config/systemd/user/midas-reality.service"
RUNTIME_RELEASES = Path.home() / ".local/share/midas-reality/releases"
RUNTIME_DROPIN_TARGET = (
    Path.home() / ".config/systemd/user/midas-reality.service.d/60-candidate-runtime.conf"
)
RUNTIME_SITE_PACKAGES = PRODUCTION_WORKSPACE / ".venv/lib/python3.12/site-packages"
EXPECTED_EFFECTIVE_LIMITS = {
    "MemoryHigh": str(1152 * 1024**2),
    "MemoryMax": str(1280 * 1024**2),
    "MemorySwapMax": "0",
    "CPUQuotaPerSecUSec": "250ms",
    "TasksMax": "32",
}


def source_hash(workspace: Path = WORKSPACE) -> str:
    return hashlib.sha256(
        b"".join(
            p.name.encode() + p.read_bytes()
            for p in sorted((workspace / "packages/midas/reality").glob("*.py"))
        )
    ).hexdigest()


def deployment_tool_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def recovery_monitor_paths(root: Path) -> list[Path]:
    """Return every safe cold-replay monitor receipt, independent of attempt number."""
    candidates = sorted(root.glob("cold-attempt-*-monitor.jsonl"))
    if any(path.is_symlink() or not path.is_file() for path in candidates):
        raise ValueError("Cold replay monitor receipt is unsafe")
    paths = candidates
    if not paths:
        raise ValueError("Full-scale recovery evidence has no cold replay monitor receipt")
    return paths


def service_unit_hash() -> str:
    if SERVICE_UNIT_SOURCE.is_symlink() or not SERVICE_UNIT_SOURCE.is_file():
        raise ValueError("Verified Reality service unit is missing or unsafe")
    return hashlib.sha256(SERVICE_UNIT_SOURCE.read_bytes()).hexdigest()


def production_source_hash() -> str:
    return source_hash(PRODUCTION_WORKSPACE)


def runtime_dropin_text(identity: str) -> str:
    return (
        "[Service]\n"
        f"Environment=PYTHONPATH=%h/.local/share/midas-reality/releases/{identity}/packages:"
        "%h/midas-reality/.venv/lib/python3.12/site-packages\n"
        "Environment=PYTHONDONTWRITEBYTECODE=1\n"
        "ExecStart=\n"
        "ExecStart=%h/midas-reality/.venv/bin/python -S -m midas.reality record "
        "--config %h/midas-reality/deploy/reality.json\n"
    )


def runtime_release_evidence() -> dict[str, Any]:
    """Validate the isolated, read-only code release used by the future service unit."""
    identity = source_hash()
    root = RUNTIME_RELEASES / identity
    package_root = root / "packages/midas/reality"
    receipt_path = root / "release.json"
    dropin_path = root / "midas-reality-candidate-runtime.conf"
    for path in (root, package_root, receipt_path, dropin_path, RUNTIME_SITE_PACKAGES):
        if path.is_symlink() or not path.exists():
            raise ValueError(f"Candidate runtime release input is missing or unsafe: {path}")
    if not root.is_dir() or not package_root.is_dir() or not RUNTIME_SITE_PACKAGES.is_dir():
        raise ValueError("Candidate runtime release or production dependencies are not directories")
    release_identity = source_hash(root)
    receipt = json.loads(receipt_path.read_text())
    expected_dropin = runtime_dropin_text(identity)
    if (
        release_identity != identity
        or receipt.get("candidate_source_sha256") != identity
        or receipt.get("release_path") != str(root)
        or receipt.get("package_path") != str(package_root)
        or receipt.get("runtime_python") != str(PRODUCTION_PYTHON)
        or receipt.get("runtime_site_packages") != str(RUNTIME_SITE_PACKAGES)
        or dropin_path.read_text() != expected_dropin
        or hashlib.sha256(expected_dropin.encode()).hexdigest() != receipt.get("drop_in_sha256")
        or receipt.get("drop_in") != expected_dropin
    ):
        raise ValueError("Candidate runtime release receipt or code identity is inconsistent")
    for path in (root, *root.rglob("*")):
        if path.stat().st_mode & 0o222:
            raise ValueError(f"Candidate runtime release is writable: {path}")
    return dict(
        source_sha256=identity,
        release_path=str(root),
        package_path=str(package_root),
        dropin_path=str(dropin_path),
        dropin_sha256=receipt["drop_in_sha256"],
        site_packages=str(RUNTIME_SITE_PACKAGES),
        release_receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    )


def verification_environment() -> dict[str, str]:
    environment = os.environ.copy()
    paths = [str(WORKSPACE), str(WORKSPACE / "packages")]
    inherited = environment.get("PYTHONPATH")
    if inherited:
        paths.extend(inherited.split(os.pathsep))
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def verification_tool(name: str) -> str:
    if Path(name).name != name:
        raise ValueError("Verification tool name must be a single executable name")
    sibling = Path(sys.executable).parent / name
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)
    fallback = shutil.which(name)
    if fallback is None:
        raise ValueError(f"Required verification tool is unavailable: {name}")
    return fallback


def _unit_configuration_identity(unit: dict[str, str]) -> dict[str, Any]:
    fragment = Path(unit.get("FragmentPath", ""))
    if not fragment.is_absolute() or fragment.is_symlink() or not fragment.is_file():
        raise ValueError("Active Reality service fragment is missing or unsafe")
    drop_ins = []
    for value in unit.get("DropInPaths", "").split():
        path = Path(value)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Active Reality service drop-in is missing or unsafe")
        drop_ins.append(
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    return {
        "fragment_path": str(fragment),
        "fragment_sha256": hashlib.sha256(fragment.read_bytes()).hexdigest(),
        "drop_ins": drop_ins,
        "exec_start": unit.get("ExecStart", ""),
        "working_directory": unit.get("WorkingDirectory", ""),
        "environment_sha256": unit.get(
            "EnvironmentSHA256",
            hashlib.sha256(unit.get("Environment", "").encode()).hexdigest(),
        ),
        "environment_files": unit.get("EnvironmentFiles", ""),
        "user": unit.get("User", ""),
        "effective_limits": {name: unit.get(name) for name in EXPECTED_EFFECTIVE_LIMITS},
        "restart": unit.get("Restart"),
    }


def _validate_service_configuration(unit: dict[str, str]) -> dict[str, Any]:
    identity = _unit_configuration_identity(unit)
    if SERVICE_UNIT_TARGET.is_symlink() or not SERVICE_UNIT_TARGET.is_file():
        raise ValueError("Installed Reality service unit is missing or unsafe")
    if identity["fragment_path"] != str(SERVICE_UNIT_TARGET):
        raise ValueError("Active Reality service fragment is not the configured user unit")
    if identity["fragment_sha256"] != service_unit_hash():
        raise ValueError(
            "Installed Reality service unit differs from verified source; install it and daemon-reload before preflight"
        )
    expected_start = (
        f"path={PRODUCTION_PYTHON} ; argv[]={PRODUCTION_PYTHON} -m midas.reality "
        f"record --config {PRODUCTION_CONFIG} ;"
    )
    if expected_start not in identity["exec_start"]:
        raise ValueError(
            "Reality service executable or module arguments differ from the verified target"
        )
    if identity["working_directory"] != str(PRODUCTION_WORKSPACE):
        raise ValueError("Reality service working directory differs from the verified target")
    expected_environment_hash = hashlib.sha256(b"PYTHONUNBUFFERED=1").hexdigest()
    if identity["environment_sha256"] != expected_environment_hash:
        raise ValueError("Reality service environment differs from the verified target")
    if identity["environment_files"] or identity["user"]:
        raise ValueError("Reality service has an unverified environment file or user override")
    if identity["effective_limits"] != EXPECTED_EFFECTIVE_LIMITS:
        raise ValueError(
            "Effective Reality service resource limits differ from the verified contract"
        )
    if identity["restart"] != "on-failure":
        raise ValueError("Reality service restart policy is not the expected bounded policy")
    return identity


def _validate_candidate_runtime_configuration(
    unit: dict[str, str], release: dict[str, Any], *, restart_policies: set[str]
) -> dict[str, Any]:
    identity = _unit_configuration_identity(unit)
    if identity["fragment_path"] != str(SERVICE_UNIT_TARGET):
        raise ValueError("Active Reality service fragment is not the configured user unit")
    if identity["fragment_sha256"] != service_unit_hash():
        raise ValueError("Installed Reality service unit differs from the verified source")
    expected_start = (
        f"path={PRODUCTION_PYTHON} ; argv[]={PRODUCTION_PYTHON} -S -m midas.reality "
        f"record --config {PRODUCTION_CONFIG} ;"
    )
    if expected_start not in identity["exec_start"]:
        raise ValueError("Reality service executable does not use the verified candidate runtime")
    if identity["working_directory"] != str(PRODUCTION_WORKSPACE):
        raise ValueError("Reality service working directory differs from the verified target")
    environment = dict(
        value.split("=", 1) for value in unit.get("Environment", "").split() if "=" in value
    )
    expected_pythonpath = f"{release['package_path']}:{release['site_packages']}"
    if (
        environment.get("PYTHONPATH") != expected_pythonpath
        or environment.get("PYTHONDONTWRITEBYTECODE") != "1"
        or environment.get("PYTHONUNBUFFERED") != "1"
    ):
        raise ValueError("Reality service environment does not pin the candidate release")
    if identity["environment_files"] or identity["user"]:
        raise ValueError("Reality service has an unverified environment file or user override")
    if identity["effective_limits"] != EXPECTED_EFFECTIVE_LIMITS:
        raise ValueError(
            "Effective Reality service resource limits differ from the verified contract"
        )
    if identity["restart"] not in restart_policies:
        raise ValueError("Reality service restart policy differs from the transition phase")
    dropins = {item["path"]: item["sha256"] for item in identity["drop_ins"]}
    if dropins.get(str(RUNTIME_DROPIN_TARGET)) != release["dropin_sha256"]:
        raise ValueError("Installed candidate runtime drop-in differs from its verified release")
    return identity


def service() -> dict[str, str]:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            "midas-reality.service",
            "-p",
            "ActiveState",
            "-p",
            "MainPID",
            "-p",
            "NRestarts",
            "-p",
            "Restart",
            "-p",
            "ExecStart",
            "-p",
            "WorkingDirectory",
            "-p",
            "Environment",
            "-p",
            "EnvironmentFiles",
            "-p",
            "User",
            "-p",
            "ControlGroup",
            "-p",
            "FragmentPath",
            "-p",
            "DropInPaths",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
            "-p",
            "MemorySwapMax",
            "-p",
            "CPUQuotaPerSecUSec",
            "-p",
            "TasksMax",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines())
    environment = values.get("Environment", "")
    values["EnvironmentSHA256"] = hashlib.sha256(environment.encode()).hexdigest()
    return values


def _restart_guard_path() -> Path:
    return Path.home() / ".config/systemd/user/midas-reality.service.d/99-midas-one-shot.conf"


def _install_restart_guard() -> Path:
    path = _restart_guard_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"One-shot restart guard already exists: {path}")
    path.write_text("[Service]\nRestart=no\n", encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    if service().get("Restart") != "no":
        raise ValueError("systemd did not activate the one-shot Restart=no guard")
    return path


def _install_candidate_runtime_dropin(release: dict[str, Any]) -> Path:
    path = RUNTIME_DROPIN_TARGET
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Candidate service drop-in directory is missing or unsafe")
    if path.exists() or path.is_symlink():
        raise ValueError(f"Candidate runtime drop-in already exists: {path}")
    source = Path(release["dropin_path"])
    if source.is_symlink() or not source.is_file():
        raise ValueError("Candidate runtime drop-in source is missing or unsafe")
    content = source.read_bytes()
    if hashlib.sha256(content).hexdigest() != release["dropin_sha256"]:
        raise ValueError("Candidate runtime drop-in changed after preflight")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    return path


def _remove_restart_guard(path: Path, expected_restart: str) -> None:
    path.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    if service().get("Restart") != expected_restart:
        raise ValueError("systemd did not restore the prior restart policy")


def _memory_events(unit: dict[str, str]) -> dict[str, int]:
    control_group = unit.get("ControlGroup")
    if not control_group:
        return {}
    path = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "memory.events"
    try:
        return {
            key: int(value)
            for key, value in (line.split() for line in path.read_text().splitlines())
        }
    except (FileNotFoundError, PermissionError):
        return {}


def _load_runtime_status(root: str) -> dict[str, Any]:
    value = json.loads((Path(root) / "status.json").read_text())
    if not isinstance(value, dict):
        raise ValueError("Production Reality status is not an object")
    return value


def _install_recovery_checkpoint(evidence: dict[str, Any], recording_root: Path) -> Path:
    if recording_root.is_symlink() or not recording_root.is_dir():
        raise ValueError("Protected Reality recording root is missing or unsafe")
    source = Path(evidence["checkpoint_path"])
    target: Path = recording_root / str(recovery.CHECKPOINT_NAME)
    temporary = target.with_suffix(target.suffix + ".mission-tmp")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Prepared recovery checkpoint is missing or unsafe")
    if target.exists() or target.is_symlink() or temporary.exists() or temporary.is_symlink():
        raise ValueError("Refusing to replace an existing Reality recovery checkpoint")
    try:
        with source.open("rb") as src, temporary.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        if file_hash(temporary) != evidence["checkpoint_sha256"]:
            raise ValueError("Staged recovery checkpoint hash changed during installation")
        os.replace(temporary, target)
        sync_dir(recording_root)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def storage_capacity(
    raw_root: Path,
    archive_root: Path,
    archive_mountpoint: Path,
    *,
    raw_budget_bytes: int,
    raw_reserve_bytes: int,
    archive_budget_bytes: int,
    archive_reserve_bytes: int,
) -> dict[str, int | str]:
    """Check raw and archive commitments against their actual separate filesystems."""
    if raw_root.is_symlink():
        raise ValueError("Reality raw recording root must not be a symlink")
    if archive_root.is_symlink() or archive_mountpoint.is_symlink():
        raise ValueError("Reality archive destination must not be a symlink")
    raw_root = raw_root.resolve(strict=True)
    archive_root = archive_root.resolve(strict=True)
    archive_mountpoint = archive_mountpoint.resolve(strict=True)
    if not raw_root.is_dir():
        raise ValueError("Reality raw recording root is missing or unsafe")
    if not os.path.ismount(archive_mountpoint) or not archive_root.is_relative_to(
        archive_mountpoint
    ):
        raise ValueError("Reality archive path is not on the declared mounted archive volume")
    if not archive_root.is_dir():
        raise ValueError("Reality archive destination is missing or unsafe")
    raw_used = sum(path.stat().st_size for path in raw_root.iterdir() if path.is_file())
    raw_free = shutil.disk_usage(raw_root).free
    archive_free = shutil.disk_usage(archive_mountpoint).free
    raw_remaining = max(0, raw_budget_bytes - raw_used)
    if raw_free < raw_remaining + raw_reserve_bytes:
        raise ValueError("Raw Reality storage commitment breaches its filesystem reserve")
    if archive_free < archive_budget_bytes + archive_reserve_bytes:
        raise ValueError("Reality archive commitment breaches its filesystem reserve")
    return dict(
        raw_root=str(raw_root),
        raw_used_bytes=raw_used,
        raw_free_bytes=raw_free,
        raw_budget_bytes=raw_budget_bytes,
        raw_remaining_budget_bytes=raw_remaining,
        raw_reserve_bytes=raw_reserve_bytes,
        archive_root=str(archive_root),
        archive_mountpoint=str(archive_mountpoint),
        archive_free_bytes=archive_free,
        archive_budget_bytes=archive_budget_bytes,
        archive_reserve_bytes=archive_reserve_bytes,
    )


def recovery_resource_evidence(root: Path) -> dict[str, Any]:
    """Validate the complete archive-recovery matrix and measured cgroup peak."""
    root = root.resolve(strict=True)
    names = (
        "result.json",
        "boundary.json",
        "catalog.json",
        "identities.json",
        "admission.json",
        "valid.checkpoint",
        "readonly_probe.json",
        "readonly_probe-landlock.json",
        "cold.json",
        "fast.json",
        "corrupt.json",
        "after_interrupt.json",
        "after_interrupt_save.json",
        "interrupt-termination.json",
        "interrupt_save-termination.json",
    )
    documents: dict[str, bytes] = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Full-scale recovery evidence is missing or unsafe: {name}")
        documents[name] = path.read_bytes()
    for path in recovery_monitor_paths(root):
        documents[path.name] = path.read_bytes()
    result = json.loads(documents["result.json"])
    catalog = json.loads(documents["catalog.json"])
    identities = json.loads(documents["identities.json"])
    recorded_boundary = json.loads(documents["boundary.json"])
    admission = json.loads(documents["admission.json"])
    required_phases = {
        "cold",
        "fast",
        "corrupt",
        "after_interrupt",
        "after_interrupt_save",
        "interrupt",
        "interrupt_save",
        "readonly_probe",
    }
    if result.get("recovery_matrix") != "PASSED" or not required_phases.issubset(
        set(result.get("completed_phases", []))
    ):
        raise ValueError("Full-scale recovery matrix is incomplete")
    boundary = result.get("boundary", {})
    expected_source_hash = source_hash(WORKSPACE)
    expected_recovery_hash = recovery.implementation_identity()
    if (
        result.get("implementation_source_sha256") != expected_source_hash
        or result.get("recovery_implementation_sha256") != expected_recovery_hash
        or boundary.get("implementation_packages") != str(WORKSPACE / "packages")
        or boundary.get("implementation_source_sha256") != expected_source_hash
        or boundary.get("recovery_implementation_sha256") != expected_recovery_hash
    ):
        raise ValueError("Full-scale recovery evidence uses a different Reality implementation")
    if recorded_boundary != boundary or not isinstance(admission.get("memory_events"), dict):
        raise ValueError("Full-scale recovery boundary or admission receipt is inconsistent")
    segment_count = int(boundary.get("segment_count", 0))
    if (
        segment_count <= 0
        or int(boundary.get("archive_bytes", 0)) <= 0
        or boundary.get("unmatched_finalized")
        or not boundary.get("catalog_sha256")
        or not boundary.get("identities_sha256")
        or hashlib.sha256(canonical(catalog)).hexdigest() != boundary["catalog_sha256"]
        or hashlib.sha256(canonical(identities)).hexdigest() != boundary["identities_sha256"]
        or len(catalog.get("segments", [])) != segment_count
    ):
        raise ValueError("Full-scale recovery boundary is incomplete")
    phase_names = (
        "cold.json",
        "fast.json",
        "corrupt.json",
        "after_interrupt.json",
        "after_interrupt_save.json",
    )
    phases = {name.removesuffix(".json"): json.loads(documents[name]) for name in phase_names}
    if any(
        phase.get("implementation_source_sha256") != expected_source_hash
        or phase.get("recovery_implementation_sha256") != expected_recovery_hash
        for phase in phases.values()
    ):
        raise ValueError("Recovery phase receipts use a different Reality implementation")
    probe = json.loads(documents["readonly_probe.json"])
    probe_policy = json.loads(documents["readonly_probe-landlock.json"])
    if (
        probe.get("source_write_denied") is not True
        or probe.get("implementation_source_sha256") != expected_source_hash
        or probe.get("recovery_implementation_sha256") != expected_recovery_hash
        or probe.get("policy") != probe_policy
        or probe_policy.get("source_root") != boundary.get("source")
        or probe_policy.get("staging_root") != str(root)
        or probe_policy.get("source_reads") != "allowed"
        or probe_policy.get("filesystem_mutation") != "denied except below staging_root"
    ):
        raise ValueError("Full-scale source read-only probe is incomplete or unbound")
    for phase in ("interrupt", "interrupt_save"):
        termination = json.loads(documents[f"{phase}-termination.json"])
        systemd = termination.get("systemd", "")
        if (
            termination.get("boundary_catalog_sha256") != boundary.get("catalog_sha256")
            or termination.get("boundary_identities_sha256") != boundary.get("identities_sha256")
            or termination.get("implementation_source_sha256") != expected_source_hash
            or termination.get("recovery_implementation_sha256") != expected_recovery_hash
            or "ExecMainCode=2\n" not in systemd
            or "ExecMainStatus=9\n" not in systemd
        ):
            raise ValueError(f"Expected isolated interruption receipt is incomplete: {phase}")
    baseline = phases["cold"]
    state_sha = baseline.get("state_sha256")
    internal_sha = baseline.get("internal_sha256")
    if not state_sha or not internal_sha:
        raise ValueError("Full-scale replay digest evidence is missing")
    if any(
        phase.get("state_sha256") != state_sha or phase.get("internal_sha256") != internal_sha
        for phase in phases.values()
    ):
        raise ValueError("Recovery matrix phases do not reconstruct matching states")
    cold_recovery = baseline.get("recovery", {})
    fast_recovery = phases["fast"].get("recovery", {})
    corrupt_recovery = phases["corrupt"].get("recovery", {})
    interrupted_recovery = phases["after_interrupt"].get("recovery", {})
    checkpoint_recovery = phases["after_interrupt_save"].get("recovery", {})
    if (
        cold_recovery.get("segments_reconstructed") != segment_count
        or fast_recovery.get("source_integrity") != "verified"
        or fast_recovery.get("prefix_segments_hashed") != segment_count
        or not corrupt_recovery.get("fallback_reason")
        or corrupt_recovery.get("segments_reconstructed") != segment_count
        or interrupted_recovery.get("segments_reconstructed") != segment_count
        or checkpoint_recovery.get("source_integrity") != "verified"
    ):
        raise ValueError(
            "Cold, checkpoint, corrupt, or interruption recovery evidence is incomplete"
        )
    checkpoint_path = root / "valid.checkpoint"
    checkpoint_digest = hashlib.sha256(documents["valid.checkpoint"]).hexdigest()
    if checkpoint_digest != cold_recovery.get(
        "checkpoint_sha256"
    ) or checkpoint_path.stat().st_size != cold_recovery.get("checkpoint_bytes"):
        raise ValueError(
            "Prepared recovery capsule differs from the verified full-scale checkpoint"
        )
    with checkpoint_path.open("rb") as stream:
        magic, expected = recovery.HEADER.unpack(stream.read(recovery.HEADER.size))
        if magic != recovery.MAGIC or hashlib.file_digest(stream, "sha256").digest() != expected:
            raise ValueError("Prepared recovery capsule checksum is invalid")
        stream.seek(recovery.HEADER.size)
        saved = json.load(stream)
    if (
        saved.get("schema_version") != 1
        or saved.get("implementation") != recovery.implementation_identity()
        or saved.get("catalog") != catalog
        or saved.get("state_sha256") != state_sha
        or saved.get("engine", {}).get("last_ordinal") != boundary.get("last_ordinal")
    ):
        raise ValueError("Prepared recovery capsule does not match the validated source boundary")
    monitor_rows = [
        json.loads(line)
        for name, contents in documents.items()
        if name.startswith("cold-attempt-") and name.endswith("-monitor.jsonl")
        for line in contents.splitlines()
        if line.strip()
    ]
    if not monitor_rows:
        raise ValueError("Recovery cgroup monitor evidence is empty")
    protected_pid = str(admission.get("pid", ""))
    observed_pids = {
        str(row["protected"].get("pid"))
        for row in monitor_rows
        if isinstance(row.get("protected"), dict) and row["protected"].get("pid") is not None
    }
    if not protected_pid.isdigit() or observed_pids != {protected_pid}:
        raise ValueError("Protected Reality process identity changed during cold recovery")
    peak = 0
    monitor_events: Counter[str] = Counter()
    cgroup_samples = 0
    for row in monitor_rows:
        event = str(row.get("event", "sample"))
        monitor_events[event] += 1
        if event not in {
            "sample",
            "pressure_clear_sample",
            "worker_frozen_for_host_pressure",
            "worker_resumed_after_host_pressure",
        }:
            raise ValueError(f"Unknown recovery monitor event: {event}")
        cgroup = row.get("cgroup", {})
        if not cgroup:
            continue
        cgroup_samples += 1
        peak = max(peak, int(cgroup.get("memory.peak", "0").strip() or 0))
        events = dict(line.split() for line in cgroup.get("memory.events", "").splitlines())
        if any(int(events.get(key, 0)) for key in ("max", "oom", "oom_kill", "oom_group_kill")):
            raise ValueError("Recovery worker recorded a memory max or OOM event")
        pressure = dict(
            line.split(maxsplit=1) for line in cgroup.get("memory.pressure", "").splitlines()
        )
        if not {"some", "full"}.issubset(pressure):
            raise ValueError("Recovery worker memory PSI evidence is missing")
        if any(
            float(dict(item.split("=") for item in pressure[kind].split())["avg10"]) > 0.01
            for kind in ("some", "full")
        ):
            raise ValueError("Recovery worker recorded sustained memory pressure")
    if peak <= 0 or cgroup_samples == 0:
        raise ValueError("Recovery worker peak memory evidence is missing")
    evidence_hash = hashlib.sha256(
        canonical({name: hashlib.sha256(data).hexdigest() for name, data in documents.items()})
    ).hexdigest()
    return dict(
        root=str(root),
        source_root=str(boundary.get("source", "")),
        evidence_sha256=evidence_hash,
        segment_count=segment_count,
        last_ordinal=int(boundary["last_ordinal"]),
        archive_bytes=int(boundary["archive_bytes"]),
        catalog_sha256=boundary["catalog_sha256"],
        identities_sha256=boundary["identities_sha256"],
        state_sha256=state_sha,
        internal_sha256=internal_sha,
        measured_startup_peak_bytes=peak,
        cold_wall_seconds=baseline["wall_seconds"],
        cold_cpu_seconds=baseline["cpu_seconds"],
        checkpoint_wall_seconds=fast_recovery["seconds"],
        checkpoint_bytes=cold_recovery.get("checkpoint_bytes"),
        checkpoint_path=str(checkpoint_path),
        checkpoint_sha256=checkpoint_digest,
        monitor_samples=cgroup_samples,
        monitor_events=dict(monitor_events),
    )


def validate_recovery_prefix(
    source_root: Path, current_catalog: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    """Prove the measured recovery boundary is the unchanged prefix of production."""
    if source_root.is_symlink() or source_root.absolute() != source_root.resolve(strict=True):
        raise ValueError("Recovery prefix source root is a symlink or noncanonical path")
    source_root = source_root.resolve(strict=True)
    evidence_source = Path(str(evidence.get("source_root", "")))
    if not evidence_source.is_absolute() or evidence_source.resolve(strict=True) != source_root:
        raise ValueError("Full-scale recovery evidence came from a different recording root")
    count = evidence.get("segment_count")
    segments = current_catalog.get("segments")
    if (
        type(count) is not int
        or count <= 0
        or not isinstance(segments, list)
        or len(segments) < count
    ):
        raise ValueError(
            "Full-scale recovery evidence exceeds the current finalized source boundary"
        )
    prefix_segments = segments[:count]
    prefix = {
        "schema_version": current_catalog["schema_version"],
        "format": current_catalog["format"],
        "ordering": current_catalog["ordering"],
        "segments": prefix_segments,
    }
    prefix_sha256 = hashlib.sha256(canonical(prefix)).hexdigest()
    if prefix_sha256 != evidence.get("catalog_sha256"):
        raise ValueError("Full-scale recovery evidence does not match the production source prefix")
    if sum(info["bytes"] for info in prefix_segments) != evidence.get("archive_bytes"):
        raise ValueError("Full-scale recovery source-prefix byte count changed")
    last_ordinal = max(
        (int(info["last"]) for info in prefix_segments if int(info["count"]) > 0),
        default=0,
    )
    if last_ordinal != evidence.get("last_ordinal"):
        raise ValueError("Full-scale recovery source-prefix ordinal changed")

    identities = []
    for info in prefix_segments:
        name = info.get("file")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".seg"):
            raise ValueError("Unsafe finalized segment identity in recovery prefix")
        segment = source_root / name
        sidecar = segment.with_suffix(".json")
        if (
            segment.is_symlink()
            or sidecar.is_symlink()
            or not segment.is_file()
            or not sidecar.is_file()
        ):
            raise ValueError("Recovery prefix source file or sidecar is missing or unsafe")
        sidecar_bytes = sidecar.read_bytes()
        if json.loads(sidecar_bytes) != info:
            raise ValueError("Recovery prefix sidecar differs from the verified catalog")
        stat = segment.stat()
        identities.append(
            dict(
                file=name,
                device=stat.st_dev,
                inode=stat.st_ino,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sidecar_sha256=hashlib.sha256(sidecar_bytes).hexdigest(),
            )
        )
    identities_sha256 = hashlib.sha256(canonical(identities)).hexdigest()
    if identities_sha256 != evidence.get("identities_sha256"):
        raise ValueError("Verified recovery prefix files changed since full-scale measurement")
    return dict(
        segment_count=count,
        last_ordinal=last_ordinal,
        archive_bytes=int(evidence["archive_bytes"]),
        catalog_sha256=prefix_sha256,
        identities_sha256=identities_sha256,
        appended_finalized_segments=len(segments) - count,
    )


def verify(output: Path) -> dict[str, Any]:
    if output.is_symlink():
        raise ValueError("Verification receipt path cannot be a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    began = time.time_ns()
    identity = source_hash()
    tool_identity = deployment_tool_hash()
    unit_identity = service_unit_hash()
    workspace = repr(str(WORKSPACE.resolve()))
    import_check = (
        "from pathlib import Path; import midas.reality, scripts.reality_deployment; "
        f"root=Path({workspace}); "
        "package=Path(midas.reality.__file__).resolve(); "
        "script=Path(scripts.reality_deployment.__file__).resolve(); "
        "assert package.is_relative_to(root/'packages'), package; "
        "assert script.is_relative_to(root/'scripts'), script; "
        "print(f'package={package} script={script}')"
    )
    checks = [
        [sys.executable, "-c", import_check],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_reality.py",
            "tests/test_reality_operations.py",
            "tests/test_reality_panel.py",
            "tests/test_reality_deployment.py",
            "tests/test_reality_recovery.py",
            "tests/test_reality_fixture_canary.py",
            "-q",
        ],
        [
            verification_tool("ruff"),
            "check",
            "packages/midas/reality",
            "scripts/reality_deployment.py",
            "scripts/reality_fixture_canary.py",
            "tests/test_reality_panel.py",
            "tests/test_reality_deployment.py",
            "tests/test_reality_fixture_canary.py",
        ],
        [
            verification_tool("mypy"),
            "packages/midas/reality",
            "scripts/reality_deployment.py",
            "scripts/reality_fixture_canary.py",
        ],
    ]
    results = []
    environment = verification_environment()
    for command in checks:
        result = subprocess.run(
            command,
            cwd=WORKSPACE,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        results.append(
            dict(
                command=command, returncode=result.returncode, output=result.stdout + result.stderr
            )
        )
    passed = (
        all(r["returncode"] == 0 for r in results)
        and source_hash() == identity
        and deployment_tool_hash() == tool_identity
        and service_unit_hash() == unit_identity
    )
    receipt = dict(
        schema_version=1,
        began_ns=began,
        completed_ns=time.time_ns(),
        source_sha256=identity,
        deployment_tool_sha256=tool_identity,
        systemd_unit_sha256=unit_identity,
        passed=passed,
        checks=results,
    )
    atomic_json(output, receipt)
    if not passed:
        raise ValueError("Recorder verification failed; inspect receipt")
    return receipt


def preflight(
    candidate: Config,
    canary: Config,
    receipt: dict[str, Any],
    archive_budget: int,
    disk_reserve: int,
    *,
    recovery_evidence_root: Path | None = None,
    archive_root: Path = Path("/mnt/continental-cloud/data/midas-reality-staging/archive-mission3"),
    archive_mountpoint: Path = Path("/mnt/continental-cloud"),
    archive_reserve: int = 400 * 1024**3,
    repair_cached_snapshots: bool = False,
) -> dict[str, Any]:
    if (
        not receipt.get("passed")
        or receipt.get("source_sha256") != source_hash()
        or receipt.get("deployment_tool_sha256") != deployment_tool_hash()
        or receipt.get("systemd_unit_sha256") != service_unit_hash()
    ):
        raise ValueError("Checks missing, failed or source changed since verification")
    if time.time_ns() - receipt["completed_ns"] > 24 * 3600 * 10**9:
        raise ValueError("Verification receipt expired")
    if Path(candidate.root).resolve() == Path(canary.root).resolve():
        raise ValueError("Canary must be isolated from production root")
    ignored = {"root", "budget_bytes", "reserve_bytes", "retention_days"}
    if any(candidate.dump()[k] != canary.dump()[k] for k in candidate.dump() if k not in ignored):
        raise ValueError("Canary did not exercise candidate network/reconstruction settings")
    production_service = service()
    production_unit_config = _validate_service_configuration(production_service)
    deployed_source_identity = production_source_hash()
    candidate_runtime = runtime_release_evidence()
    if candidate_runtime["source_sha256"] != source_hash():
        raise ValueError("Immutable candidate runtime differs from the verified candidate")
    if recovery_evidence_root is None:
        raise ValueError("Full-scale recovery evidence is required for restart preflight")
    recovery_evidence = recovery_resource_evidence(recovery_evidence_root)
    production_catalog = manifest(Path(candidate.root))
    production_catalog_sha256 = hashlib.sha256(canonical(production_catalog)).hexdigest()
    recovery_prefix = validate_recovery_prefix(
        Path(candidate.root), production_catalog, recovery_evidence
    )
    resources = require_restart_safe(
        production_service.get("ControlGroup", ""),
        measured_startup_peak_bytes=recovery_evidence["measured_startup_peak_bytes"],
        target_memory_high_bytes=int(EXPECTED_EFFECTIVE_LIMITS["MemoryHigh"]),
        target_memory_max_bytes=int(EXPECTED_EFFECTIVE_LIMITS["MemoryMax"]),
        current_memory_max_bytes=int(production_service["MemoryMax"]),
    )
    root = Path(canary.root)
    status = json.loads((root / "status.json").read_text())
    if status["state"] != "STOPPED" or status["failures"] or status["frames"] < 20:
        raise ValueError("Canary must finish successfully with sufficient feed frames")
    value = manifest(root)
    engine, checkpoints = replay(root, value)
    if checkpoints < 3:
        raise ValueError("Canary needs at least three verified checkpoints")
    gaps: Counter[str] = Counter()
    comparison_counts: Counter[str] = Counter()
    last_checkpoint = None
    start = end = None
    for r in read_manifest(root, value):
        if r["kind"] == "gap":
            gaps[r["payload"]["reason"]] += 1
            if r["payload"]["reason"] == "process_start":
                if r["payload"]["implementation_sha256"] != source_hash():
                    raise ValueError("Canary implementation differs from verified source")
                start = r["received_ns"]
        elif r["kind"] == "checkpoint":
            last_checkpoint = r["ordinal"]
            end = r["received_ns"]
        elif r["kind"] == "book_comparison":
            comparison_counts[r["payload"]["assessment"]] += 1
    if start is None or end is None or last_checkpoint is None or end - start < 60 * 10**9:
        raise ValueError("Canary duration insufficient")
    elapsed = (end - start) / 1e9
    permitted_resync = max(3, math.ceil(elapsed / 120 * 3))
    if gaps["book_resynchronization"] + gaps["unconfirmed_top_advertisement"] > permitted_resync:
        raise ValueError(
            "Canary repeatedly lost book consistency (more than 1.5 resynchronizations/minute)"
        )
    if (
        comparison_counts["stable_local_lineage_divergence"]
        or comparison_counts["invalid_public_comparison"]
    ):
        raise ValueError("Canary independent book verification failed")
    if (
        candidate.comparison_seconds
        and comparison_counts["stable_local_lineage_match_unsequenced"] < 2
    ):
        raise ValueError("Independent comparison path not exercised")
    before_stop, _ = replay(root, value, through=last_checkpoint - 1)
    state = before_stop.state()
    fresh = sum(
        b["internally_consistent"] and b["age_ns"] < candidate.stale_seconds * 1e9
        for b in state["books"].values()
    )
    if status["markets"] != candidate.markets or fresh != candidate.markets * 2:
        raise ValueError("Canary failed complete fresh outcome coverage")
    # Worst-case allocated local raw and archive growth must fit while protecting other services.
    if archive_budget <= 0 or disk_reserve < candidate.reserve_bytes:
        raise ValueError("Unsafe archive budget or global disk reserve")
    capacity = storage_capacity(
        Path(candidate.root),
        archive_root,
        archive_mountpoint,
        raw_budget_bytes=candidate.budget_bytes,
        raw_reserve_bytes=disk_reserve,
        archive_budget_bytes=archive_budget,
        archive_reserve_bytes=archive_reserve,
    )
    used = int(capacity["raw_used_bytes"])
    free = int(capacity["raw_free_bytes"])
    elapsed = (end - start) / 1e9
    sample_bytes = sum(s["bytes"] for s in value["segments"])
    rate = sample_bytes / elapsed
    runway = max(0, candidate.budget_bytes - used) / rate
    if runway < 14 * 86400:
        raise ValueError("Pilot growth offers less than fourteen days storage runway")
    production_status = json.loads((Path(candidate.root) / "status.json").read_text())
    current = production_service
    fresh_production = (
        production_status["state"] == "RECORDING_UNSEQUENCED"
        and production_status["fresh_books"] == production_status["expected_books"]
    )
    bad_books = {
        t: b
        for t, b in production_status.get("books", {}).items()
        if not b["internally_consistent"]
    }
    repair_confirmed = (
        repair_cached_snapshots
        and not fresh_production
        and "Initial snapshots incomplete" in production_status.get("error", "")
        and bool(bad_books)
        and all(b["issue"] in {"stale", "timestamp_regression"} for b in bad_books.values())
        and engine.counts["snapshot_source_time_regression_after_gap"] >= 1
        and production_status["config"] == candidate.dump()
    )
    if (
        current["ActiveState"] != "active"
        or time.time_ns() - production_status["updated_ns"] > 10 * 10**9
        or not (fresh_production or repair_confirmed)
    ):
        raise ValueError(
            "Production is not healthy before deployment, and a cached-snapshot repair is not confirmed"
        )
    return dict(
        schema_version=1,
        checked_ns=time.time_ns(),
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=deployed_source_identity,
        candidate_runtime=candidate_runtime,
        production_unit_config=production_unit_config,
        candidate=candidate.dump(),
        canary=canary.dump(),
        canary_replay_sha256=engine.digest(),
        canary_manifest_sha256=hashlib.sha256(canonical(value)).hexdigest(),
        canary_checkpoints=checkpoints,
        canary_fresh_books=fresh,
        canary_frames=status["frames"],
        canary_duration_seconds=elapsed,
        maximum_resynchronizations_for_duration=permitted_resync,
        gaps=dict(gaps),
        comparisons=dict(comparison_counts),
        canary_bytes_per_second=rate,
        conservative_pilot_runway_days=runway / 86400,
        allocated_raw_and_archive_bytes=candidate.budget_bytes + archive_budget,
        free_disk_bytes=free,
        protected_disk_reserve_bytes=disk_reserve,
        storage_capacity=capacity,
        production_before=current,
        production_runtime_config=production_status["config"],
        production_catalog_sha256=production_catalog_sha256,
        recovery_prefix=recovery_prefix,
        recovery_evidence=recovery_evidence,
        resources=resources,
        cached_snapshot_repair=dict(
            requested=repair_cached_snapshots,
            confirmed=repair_confirmed,
            prior_error=production_status.get("error"),
            affected_assets=list(bad_books),
        ),
        passed=True,
        limitations=[
            "Pilot includes startup/discovery overhead, not a stable long-term rate estimate.",
            "Bounded canary is an engineering gate, not scientific validation.",
            "A rollback requires a separately authorized stop/start; no raw bytes are removed.",
        ],
    )


def apply(
    candidate: Config,
    gate: dict[str, Any],
    config_path: Path,
    output: Path,
    *,
    protected_restart_approved: bool = False,
    health_timeout_seconds: int = 3600,
    stability_seconds: int = 300,
) -> dict[str, Any]:
    if not 2400 <= health_timeout_seconds <= 3600:
        raise ValueError("Full-store readiness window must be 2400..3600 seconds")
    if not 300 <= stability_seconds <= 600:
        raise ValueError("Post-readiness stability window must be 300..600 seconds")
    if not protected_restart_approved:
        raise ValueError("Protected Reality restart requires explicit approval")
    if (
        not gate.get("passed")
        or gate["source_sha256"] != source_hash()
        or gate.get("deployment_tool_sha256") != deployment_tool_hash()
        or gate.get("systemd_unit_sha256") != service_unit_hash()
        or gate.get("production_source_sha256") != production_source_hash()
        or gate["candidate"] != candidate.dump()
        or gate.get("candidate_runtime") != runtime_release_evidence()
        or not isinstance(gate.get("production_unit_config"), dict)
        or not isinstance(gate.get("recovery_prefix"), dict)
        or not isinstance(gate.get("recovery_evidence"), dict)
        or time.time_ns() - gate["checked_ns"] > 60 * 10**9
    ):
        raise ValueError("Deployment gate changed or expired; rerun preflight")
    before = service()
    if before["MainPID"] != gate["production_before"]["MainPID"]:
        raise ValueError("Production process changed after preflight")
    if _validate_service_configuration(before) != gate["production_unit_config"]:
        raise ValueError("Production service unit or drop-ins changed after preflight")
    if before.get("Restart") != "on-failure":
        raise ValueError("Production restart policy is not the expected bounded policy")
    recovery_evidence = recovery_resource_evidence(Path(gate["recovery_evidence"]["root"]))
    if recovery_evidence != gate["recovery_evidence"]:
        raise ValueError("Full-scale recovery evidence changed after preflight")
    current_prefix = validate_recovery_prefix(
        Path(candidate.root), manifest(Path(candidate.root)), recovery_evidence
    )
    if any(
        current_prefix.get(key) != gate["recovery_prefix"].get(key)
        for key in (
            "segment_count",
            "last_ordinal",
            "archive_bytes",
            "catalog_sha256",
            "identities_sha256",
        )
    ):
        raise ValueError("Verified recovery prefix changed after preflight")
    require_restart_safe(
        before.get("ControlGroup", ""),
        measured_startup_peak_bytes=recovery_evidence["measured_startup_peak_bytes"],
        target_memory_high_bytes=int(EXPECTED_EFFECTIVE_LIMITS["MemoryHigh"]),
        target_memory_max_bytes=int(EXPECTED_EFFECTIVE_LIMITS["MemoryMax"]),
        current_memory_max_bytes=int(before["MemoryMax"]),
    )
    planned_capacity = gate.get("storage_capacity", {})
    current_capacity = storage_capacity(
        Path(candidate.root),
        Path(planned_capacity["archive_root"]),
        Path(planned_capacity["archive_mountpoint"]),
        raw_budget_bytes=candidate.budget_bytes,
        raw_reserve_bytes=int(gate["protected_disk_reserve_bytes"]),
        archive_budget_bytes=int(planned_capacity["archive_budget_bytes"]),
        archive_reserve_bytes=int(planned_capacity["archive_reserve_bytes"]),
    )
    if any(
        current_capacity[key] != planned_capacity[key]
        for key in (
            "raw_root",
            "archive_root",
            "archive_mountpoint",
            "raw_budget_bytes",
            "raw_reserve_bytes",
            "archive_budget_bytes",
            "archive_reserve_bytes",
        )
    ):
        raise ValueError("Storage capacity contract changed after preflight")
    runtime_status = _load_runtime_status(candidate.root)
    if runtime_status.get("config") != gate.get("production_runtime_config"):
        raise ValueError("Loaded production config changed after preflight")
    previous = Config(**gate["production_runtime_config"])
    backup = Path(candidate.root).parent / f"config-before-deployment-{time.time_ns()}.json"
    atomic_json(backup, previous.dump())
    result = dict(
        gate,
        prior_config=previous.dump(),
        prior_config_backup=str(backup),
        restart_intent_ns=time.time_ns(),
        health_timeout_seconds=health_timeout_seconds,
        stability_seconds=stability_seconds,
    )
    atomic_json(output, result)  # Record intent before mutating the service.
    restart_guard = _install_restart_guard()
    result["restart_guard"] = str(restart_guard)
    result["automatic_restarts_disabled"] = True
    atomic_json(output, result)
    try:
        subprocess.run(["systemctl", "--user", "stop", "midas-reality.service"], check=True)
        stopped = service()
        if stopped.get("ActiveState") != "inactive" or stopped.get("MainPID") not in {None, "0"}:
            raise RuntimeError("Reality did not stop cleanly before the single candidate start")
        result["stop_completed_ns"] = time.time_ns()
        runtime_dropin = _install_candidate_runtime_dropin(gate["candidate_runtime"])
        result["installed_candidate_runtime_dropin"] = str(runtime_dropin)
        atomic_json(config_path, candidate.dump())
        checkpoint_target = _install_recovery_checkpoint(recovery_evidence, Path(candidate.root))
        result["installed_recovery_checkpoint"] = str(checkpoint_target)
        result["installed_recovery_checkpoint_sha256"] = recovery_evidence["checkpoint_sha256"]
        atomic_json(output, result)
        candidate_unit = _validate_candidate_runtime_configuration(
            service(), gate["candidate_runtime"], restart_policies={"no"}
        )
        result["candidate_service_configuration"] = candidate_unit
        atomic_json(output, result)
        subprocess.run(["systemctl", "--user", "start", "midas-reality.service"], check=True)
    except Exception as exc:
        result.update(
            deployed=False,
            operator_action_required=True,
            reason=f"One-shot stop, checkpoint installation or start failed: {exc}",
            no_automatic_retry_or_rollback=True,
        )
        atomic_json(output, result)
        raise ValueError(
            "One-shot recorder transition failed; no retry or rollback was attempted"
        ) from exc

    deadline = time.monotonic() + health_timeout_seconds
    baseline_events = _memory_events(before)
    ready_since: float | None = None
    ready_pid: str | None = None
    ready_restarts: str | None = None
    first_ready_status: dict[str, Any] | None = None
    last_status: dict[str, Any] | None = None
    failure_reason: str | None = None
    while time.monotonic() < deadline:
        current = service()
        if current.get("ActiveState") != "active" or current.get("MainPID") in {None, "0"}:
            failure_reason = "Recorder exited during the one-shot start"
            break
        events = _memory_events(current)
        if any(
            events.get(key, 0) > baseline_events.get(key, 0)
            for key in ("max", "oom", "oom_kill", "oom_group_kill")
        ):
            failure_reason = "Recorder cgroup recorded a memory-limit or OOM event"
            break
        try:
            status = json.loads((Path(candidate.root) / "status.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            status = None
        healthy = bool(
            status
            and status.get("started_ns", 0) > result["restart_intent_ns"]
            and status.get("state") == "RECORDING_UNSEQUENCED"
            and status.get("fresh_books") == candidate.markets * 2
            and status.get("config") == candidate.dump()
        )
        if ready_since is None:
            if healthy:
                ready_since = time.monotonic()
                ready_pid = current["MainPID"]
                ready_restarts = current.get("NRestarts", "0")
                first_ready_status = status
                last_status = status
        else:
            if not healthy:
                failure_reason = "Recorder lost fresh-book health during the stability window"
                break
            assert status is not None and first_ready_status is not None and last_status is not None
            if current["MainPID"] != ready_pid or current.get("NRestarts", "0") != ready_restarts:
                failure_reason = "Recorder process ownership changed during the stability window"
                break
            status_age_ns = time.time_ns() - status.get("updated_ns", 0)
            if status_age_ns > 30 * 10**9:
                failure_reason = "Recorder status became stale during the stability window"
                break
            if status.get("ordinal", 0) < last_status.get("ordinal", 0) or status.get(
                "frames", 0
            ) < last_status.get("frames", 0):
                failure_reason = "Recorder counters regressed during the stability window"
                break
            last_status = status
            if time.monotonic() - ready_since >= stability_seconds:
                if (
                    status.get("updated_ns", 0) <= first_ready_status.get("updated_ns", 0)
                    or status.get("ordinal", 0) <= first_ready_status.get("ordinal", 0)
                    or status.get("frames", 0) <= first_ready_status.get("frames", 0)
                ):
                    failure_reason = (
                        "Recorder did not advance observations during the stability window"
                    )
                    break
                try:
                    _remove_restart_guard(restart_guard, before["Restart"])
                except Exception as exc:
                    result.update(
                        deployed=False,
                        operator_action_required=True,
                        health_passed=True,
                        restart_policy_restored=False,
                        reason=f"Recorder healthy but restart policy restore failed: {exc}",
                        no_automatic_retry_or_rollback=True,
                    )
                    atomic_json(output, result)
                    raise ValueError(
                        "Recorder is healthy but Restart=no remains; operator action is required"
                    ) from exc
                result.update(
                    deployed_ns=time.time_ns(),
                    production_after=service(),
                    deployed=True,
                    restart_policy_restored=True,
                    automatic_restarts_disabled=False,
                    health=dict(
                        state=status["state"],
                        fresh_books=status["fresh_books"],
                        ordinal=status["ordinal"],
                        frames=status["frames"],
                        stable_seconds=stability_seconds,
                    ),
                )
                atomic_json(output, result)
                return result
        time.sleep(5)

    result.update(
        deployed=False,
        operator_action_required=True,
        automatic_restarts_disabled=True,
        no_automatic_retry_or_rollback=True,
        production_after=service(),
        memory_events_after=_memory_events(service()),
        reason=failure_reason or "Fresh-book readiness timeout",
    )
    atomic_json(output, result)
    raise ValueError(
        "One-shot recorder deployment did not pass health; Restart=no is retained and no retry or rollback was attempted"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "preflight", "apply"])
    parser.add_argument(
        "--candidate", type=Path, default=WORKSPACE / "deploy/reality-candidate.json"
    )
    parser.add_argument(
        "--canary-config",
        type=Path,
        default=WORKSPACE / "data/recordings/gate-a-canary-r2-config.json",
    )
    parser.add_argument(
        "--receipt", type=Path, default=WORKSPACE / "docs/reliability/REALITY_FRONTIER_CHECKS.json"
    )
    parser.add_argument(
        "--gate", type=Path, default=WORKSPACE / "docs/reliability/REALITY_FRONTIER_PREFLIGHT.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=WORKSPACE / "docs/reliability/REALITY_FRONTIER_DEPLOYMENT.json",
    )
    parser.add_argument("--archive-budget", type=int, default=112 * 1024**3)
    parser.add_argument("--archive-reserve", type=int, default=400 * 1024**3)
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=Path("/mnt/continental-cloud/data/midas-reality-staging/archive-mission3"),
    )
    parser.add_argument("--archive-mountpoint", type=Path, default=Path("/mnt/continental-cloud"))
    parser.add_argument("--health-timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--approve-protected-restart",
        action="store_true",
        help="explicitly authorize the protected Reality stop/start transition",
    )
    parser.add_argument("--recovery-evidence", type=Path)
    parser.add_argument("--stability-seconds", type=int, default=300)
    parser.add_argument("--repair-cached-snapshots", action="store_true")
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.receipt)
    elif args.command == "preflight":
        if args.recovery_evidence is None:
            parser.error("preflight requires --recovery-evidence from a complete full-scale run")
        gate = preflight(
            Config.load(args.candidate),
            Config.load(args.canary_config),
            json.loads(args.receipt.read_text()),
            args.archive_budget,
            20 * 1024**3,
            recovery_evidence_root=args.recovery_evidence,
            archive_root=args.archive_root,
            archive_mountpoint=args.archive_mountpoint,
            archive_reserve=args.archive_reserve,
            repair_cached_snapshots=args.repair_cached_snapshots,
        )
        atomic_json(args.gate, gate)
        print(json.dumps(gate, indent=2))
    else:
        if not args.approve_protected_restart:
            parser.error("apply requires --approve-protected-restart")
        result = apply(
            Config.load(args.candidate),
            json.loads(args.gate.read_text()),
            PRODUCTION_CONFIG,
            args.output,
            protected_restart_approved=True,
            health_timeout_seconds=args.health_timeout_seconds,
            stability_seconds=args.stability_seconds,
        )
        print(json.dumps(result["health"], indent=2))


if __name__ == "__main__":
    main()
