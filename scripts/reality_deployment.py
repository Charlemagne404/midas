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

from midas.reality.config import Config
from midas.reality.replay import replay
from midas.reality.storage import atomic_json, canonical, manifest, read_manifest

WORKSPACE = Path(__file__).resolve().parents[1]
PRODUCTION_WORKSPACE = Path.home() / "midas-reality"
PRODUCTION_PYTHON = PRODUCTION_WORKSPACE / ".venv/bin/python"
PRODUCTION_CONFIG = PRODUCTION_WORKSPACE / "deploy/reality.json"
SERVICE_UNIT_SOURCE = WORKSPACE / "deploy/systemd/user/midas-reality.service"
SERVICE_UNIT_TARGET = Path.home() / ".config/systemd/user/midas-reality.service"
EXPECTED_EFFECTIVE_LIMITS = {
    "MemoryHigh": str(704 * 1024**2),
    "MemoryMax": str(768 * 1024**2),
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


def service_unit_hash() -> str:
    if SERVICE_UNIT_SOURCE.is_symlink() or not SERVICE_UNIT_SOURCE.is_file():
        raise ValueError("Verified Reality service unit is missing or unsafe")
    return hashlib.sha256(SERVICE_UNIT_SOURCE.read_bytes()).hexdigest()


def production_source_hash() -> str:
    return source_hash(PRODUCTION_WORKSPACE)


def verification_environment() -> dict[str, str]:
    environment = os.environ.copy()
    paths = [str(WORKSPACE), str(WORKSPACE / "packages")]
    inherited = environment.get("PYTHONPATH")
    if inherited:
        paths.extend(inherited.split(os.pathsep))
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


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
        "effective_limits": {
            name: unit.get(name) for name in EXPECTED_EFFECTIVE_LIMITS
        },
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
        raise ValueError("Reality service executable or module arguments differ from the verified target")
    if identity["working_directory"] != str(PRODUCTION_WORKSPACE):
        raise ValueError("Reality service working directory differs from the verified target")
    expected_environment_hash = hashlib.sha256(b"PYTHONUNBUFFERED=1").hexdigest()
    if identity["environment_sha256"] != expected_environment_hash:
        raise ValueError("Reality service environment differs from the verified target")
    if identity["environment_files"] or identity["user"]:
        raise ValueError("Reality service has an unverified environment file or user override")
    if identity["effective_limits"] != EXPECTED_EFFECTIVE_LIMITS:
        raise ValueError("Effective Reality service resource limits differ from the verified contract")
    if identity["restart"] != "on-failure":
        raise ValueError("Reality service restart policy is not the expected bounded policy")
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
    environment = values.pop("Environment", "")
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


def verify(output: Path) -> dict[str, Any]:
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
            "-q",
        ],
        [
            str(WORKSPACE / ".venv/bin/ruff"),
            "check",
            "packages/midas/reality",
            "scripts/reality_deployment.py",
            "tests/test_reality_panel.py",
            "tests/test_reality_deployment.py",
        ],
        [
            str(WORKSPACE / ".venv/bin/mypy"),
            "packages/midas/reality",
            "scripts/reality_deployment.py",
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
    if deployed_source_identity != source_hash():
        raise ValueError("Production Reality package source differs from the verified candidate")
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
    free = shutil.disk_usage(Path(candidate.root)).free
    used = sum(p.stat().st_size for p in Path(candidate.root).iterdir() if p.is_file())
    additional = max(0, candidate.budget_bytes - used) + archive_budget
    if free < disk_reserve + additional:
        raise ValueError("Configured storage commitments consume protected host headroom")
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
        production_before=current,
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
    health_timeout_seconds: int = 2700,
    stability_seconds: int = 300,
) -> dict[str, Any]:
    if not 2400 <= health_timeout_seconds <= 3600:
        raise ValueError("Full-store readiness window must be 2400..3600 seconds")
    if not 300 <= stability_seconds <= 600:
        raise ValueError("Post-readiness stability window must be 300..600 seconds")
    if (
        not gate.get("passed")
        or gate["source_sha256"] != source_hash()
        or gate.get("deployment_tool_sha256") != deployment_tool_hash()
        or gate.get("systemd_unit_sha256") != service_unit_hash()
        or gate.get("production_source_sha256") != production_source_hash()
        or gate.get("production_source_sha256") != source_hash()
        or gate["candidate"] != candidate.dump()
        or not isinstance(gate.get("production_unit_config"), dict)
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
    previous = Config.load(config_path)
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
    try:
        atomic_json(config_path, candidate.dump())
    except Exception:
        # No process start has been attempted; it is safe to restore policy now.
        _remove_restart_guard(restart_guard, before["Restart"])
        raise
    result["restart_guard"] = str(restart_guard)
    result["automatic_restarts_disabled"] = True
    atomic_json(output, result)
    try:
        subprocess.run(["systemctl", "--user", "restart", "midas-reality.service"], check=True)
    except Exception as exc:
        result.update(
            deployed=False,
            operator_action_required=True,
            reason=f"One start command failed: {exc}",
            no_automatic_retry_or_rollback=True,
        )
        atomic_json(output, result)
        raise ValueError("One-shot recorder start failed; automatic retry and rollback are disabled") from exc

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
            if status.get("ordinal", 0) < last_status.get("ordinal", 0) or status.get("frames", 0) < last_status.get("frames", 0):
                failure_reason = "Recorder counters regressed during the stability window"
                break
            last_status = status
            if time.monotonic() - ready_since >= stability_seconds:
                if (
                    status.get("updated_ns", 0) <= first_ready_status.get("updated_ns", 0)
                    or status.get("ordinal", 0) <= first_ready_status.get("ordinal", 0)
                    or status.get("frames", 0) <= first_ready_status.get("frames", 0)
                ):
                    failure_reason = "Recorder did not advance observations during the stability window"
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
        "--receipt", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_CHECKS.json"
    )
    parser.add_argument(
        "--gate", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_PREFLIGHT.json"
    )
    parser.add_argument(
        "--output", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_DEPLOYMENT.json"
    )
    parser.add_argument("--archive-budget", type=int, default=112 * 1024**3)
    parser.add_argument("--health-timeout-seconds", type=int, default=2700)
    parser.add_argument("--stability-seconds", type=int, default=300)
    parser.add_argument("--repair-cached-snapshots", action="store_true")
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.receipt)
    elif args.command == "preflight":
        gate = preflight(
            Config.load(args.candidate),
            Config.load(args.canary_config),
            json.loads(args.receipt.read_text()),
            args.archive_budget,
            20 * 1024**3,
            repair_cached_snapshots=args.repair_cached_snapshots,
        )
        atomic_json(args.gate, gate)
        print(json.dumps(gate, indent=2))
    else:
        result = apply(
            Config.load(args.candidate),
            json.loads(args.gate.read_text()),
            WORKSPACE / "deploy/reality.json",
            args.output,
            health_timeout_seconds=args.health_timeout_seconds,
            stability_seconds=args.stability_seconds,
        )
        print(json.dumps(result["health"], indent=2))


if __name__ == "__main__":
    main()
