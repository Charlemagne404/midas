"""Intentional recorder deployment: frozen checks, isolated canary, capacity guard.

Run `verify`, then `preflight`, then `apply`. Only apply changes production config
and restarts the recorder. A failed health gate restores the previous configuration
under the same tested implementation. All raw roots remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from midas.reality.config import Config
from midas.reality.replay import replay
from midas.reality.resources import require_restart_safe
from midas.reality.storage import atomic_json, canonical, manifest, read_manifest

WORKSPACE = Path(__file__).resolve().parents[1]


def source_hash() -> str:
    return hashlib.sha256(
        b"".join(
            p.name.encode() + p.read_bytes()
            for p in sorted((WORKSPACE / "packages/midas/reality").glob("*.py"))
        )
    ).hexdigest()


def deployment_guard_hash() -> str:
    """Bind verification and preflight receipts to this deployment procedure."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def config_hash(config: Config) -> str:
    return hashlib.sha256(canonical(config.dump())).hexdigest()


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
            "ControlGroup",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def verify(output: Path) -> dict[str, Any]:
    began = time.time_ns()
    identity = source_hash()
    guard_identity = deployment_guard_hash()
    checks = [
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
    for command in checks:
        result = subprocess.run(command, cwd=WORKSPACE, capture_output=True, text=True, check=False)
        results.append(
            dict(
                command=command, returncode=result.returncode, output=result.stdout + result.stderr
            )
        )
    passed = (
        all(r["returncode"] == 0 for r in results)
        and source_hash() == identity
        and deployment_guard_hash() == guard_identity
    )
    receipt = dict(
        schema_version=1,
        began_ns=began,
        completed_ns=time.time_ns(),
        source_sha256=identity,
        deployment_guard_sha256=guard_identity,
        passed=passed,
        checks=results,
    )
    atomic_json(output, receipt)
    if not passed:
        raise ValueError("Recorder verification failed; inspect receipt")
    return receipt


def storage_commitment(
    raw_root: Path,
    *,
    raw_budget: int,
    archive_budget: int,
    raw_reserve: int,
    archive_destination: Path | None = None,
    archive_reserve: int | None = None,
) -> dict[str, int | bool | str]:
    """Check raw and archive budgets against the filesystems that hold them.

    With no archive destination, retain the legacy conservative assumption that
    the full archive budget shares the raw filesystem. An explicit destination
    is accounted on its own mount, including any already-written archive bytes.
    """
    raw_root = raw_root.resolve()
    archive_reserve = raw_reserve if archive_reserve is None else archive_reserve
    raw_used = sum(p.stat().st_size for p in raw_root.iterdir() if p.is_file())
    raw_remaining = max(0, raw_budget - raw_used)
    raw_free = shutil.disk_usage(raw_root).free

    if archive_destination is None:
        archive_used = 0
        archive_remaining = archive_budget
        required_raw = raw_remaining + archive_remaining + max(raw_reserve, archive_reserve)
        if raw_free < required_raw:
            raise ValueError("Configured storage commitments consume protected host headroom")
        return dict(
            separate_filesystems=False,
            raw_used_bytes=raw_used,
            raw_remaining_bytes=raw_remaining,
            raw_free_bytes=raw_free,
            raw_reserve_bytes=raw_reserve,
            archive_used_bytes=archive_used,
            archive_remaining_bytes=archive_remaining,
            archive_free_bytes=raw_free,
            archive_reserve_bytes=archive_reserve,
        )

    archive_root = archive_destination.resolve()
    if (
        archive_root == raw_root
        or archive_root.is_relative_to(raw_root)
        or raw_root.is_relative_to(archive_root)
    ):
        raise ValueError("Archive destination must be separate from the raw recording root")
    archive_mount = archive_root
    while not archive_mount.exists() and archive_mount != archive_mount.parent:
        archive_mount = archive_mount.parent
    if not archive_mount.is_dir():
        raise ValueError("Archive destination has no existing directory or mount")
    archive_dev = archive_mount.stat().st_dev
    raw_dev = raw_root.stat().st_dev
    archive_used = (
        sum(p.stat().st_size for p in archive_root.iterdir() if p.is_file())
        if archive_root.is_dir()
        else 0
    )
    archive_remaining = max(0, archive_budget - archive_used)
    archive_free = shutil.disk_usage(archive_mount).free

    if archive_dev == raw_dev:
        required = raw_remaining + archive_remaining + max(raw_reserve, archive_reserve)
        if raw_free < required:
            raise ValueError("Configured storage commitments consume protected host headroom")
    else:
        if raw_free < raw_remaining + raw_reserve:
            raise ValueError("Raw storage commitment consumes protected host headroom")
        if archive_free < archive_remaining + archive_reserve:
            raise ValueError("Archive storage commitment consumes its protected filesystem reserve")
    return dict(
        separate_filesystems=archive_dev != raw_dev,
        raw_used_bytes=raw_used,
        raw_remaining_bytes=raw_remaining,
        raw_free_bytes=raw_free,
        raw_reserve_bytes=raw_reserve,
        archive_used_bytes=archive_used,
        archive_remaining_bytes=archive_remaining,
        archive_free_bytes=archive_free,
        archive_reserve_bytes=archive_reserve,
    )


def archive_inventory(destination: Path) -> dict[str, Any]:
    """Read archive identities and inventory without changing staging files."""
    if destination.is_symlink():
        raise ValueError("Archive destination cannot be a symlink")
    root = destination.resolve()
    manifest_path = root / "manifest.json"
    source_path = root / "source.json"
    if any(path.is_symlink() or not path.is_file() for path in (manifest_path, source_path)):
        raise ValueError("Archive manifest or source identity is missing or unsafe")
    try:
        value = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Archive manifest is unreadable") from error
    segments = value.get("segments") if isinstance(value, dict) else None
    if not isinstance(segments, list):
        raise ValueError("Archive manifest has no segment inventory")
    expected: list[str] = []
    for item in segments:
        if not isinstance(item, dict):
            raise ValueError("Archive manifest entry is malformed")
        name, digest = item.get("file"), item.get("sha256")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".seg")
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError("Archive manifest entry identity is malformed")
        expected.append(name)
    actual = {path.name for path in root.glob("*.seg") if path.is_file() and not path.is_symlink()}
    expected_set = set(expected)
    return {
        "archive_root": str(root),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "source_json_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "segment_count": len(actual),
        "manifest_entry_count": len(segments),
        "duplicate_manifest_entries": len(expected) - len(expected_set),
        "copying_file_count": sum(1 for path in root.glob("*.copying") if path.is_file()),
        "unmanifested_segment_count": len(actual - expected_set),
        "missing_segment_count": len(expected_set - actual),
    }


def preflight(
    candidate: Config,
    canary: Config,
    receipt: dict[str, Any],
    archive_budget: int,
    disk_reserve: int,
    *,
    archive_destination: Path | None = None,
    archive_reserve: int | None = None,
    repair_cached_snapshots: bool = False,
    active_config: Config | None = None,
    active_config_path: Path | None = None,
    canary_receipt: dict[str, Any] | None = None,
    recovery_receipt: dict[str, Any] | None = None,
    archive_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guard_identity = deployment_guard_hash()
    if (
        not receipt.get("passed")
        or receipt.get("source_sha256") != source_hash()
        or receipt.get("deployment_guard_sha256") != guard_identity
    ):
        raise ValueError("Checks missing, failed or source changed since verification")
    if time.time_ns() - receipt["completed_ns"] > 24 * 3600 * 10**9:
        raise ValueError("Verification receipt expired")
    if Path(candidate.root).resolve() == Path(canary.root).resolve():
        raise ValueError("Canary must be isolated from production root")
    ignored = {"root", "budget_bytes", "reserve_bytes", "retention_days"}
    if any(candidate.dump()[k] != canary.dump()[k] for k in candidate.dump() if k not in ignored):
        raise ValueError("Canary did not exercise candidate network/reconstruction settings")
    if canary_receipt is None or recovery_receipt is None or archive_receipt is None:
        raise ValueError(
            "Preflight requires a seeded candidate canary, latest-boundary recovery receipt, and verified archive receipt"
        )
    for evidence in (canary_receipt, recovery_receipt, archive_receipt):
        completed_ns = evidence.get("completed_ns")
        if type(completed_ns) is not int or time.time_ns() - completed_ns > 24 * 3600 * 10**9:
            raise ValueError("Latest-boundary preflight evidence is missing or expired")
        if evidence.get("candidate_source_sha256") != source_hash():
            raise ValueError("Latest-boundary evidence was produced by another candidate source")
    if (
        canary_receipt.get("status") != "PASSED"
        or canary_receipt.get("config") != canary.dump()
        or not canary_receipt.get("seed_manifest_sha256")
        or recovery_receipt.get("status") != "COMPLETE"
        or recovery_receipt.get("verification_complete") is not True
    ):
        raise ValueError("Preflight evidence does not prove seeded startup and completed recovery")
    if (
        archive_receipt.get("status") != "VERIFIED"
        or archive_receipt.get("checksums_verified") is not True
        or archive_receipt.get("ownership_provenance_verified") is not True
    ):
        raise ValueError("Archive receipt lacks checksum and ownership/provenance verification")
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
    if archive_budget <= 0 or disk_reserve < candidate.reserve_bytes:
        raise ValueError("Unsafe archive budget or global disk reserve")
    commitments = storage_commitment(
        Path(candidate.root),
        raw_budget=candidate.budget_bytes,
        archive_budget=archive_budget,
        raw_reserve=disk_reserve,
        archive_destination=archive_destination,
        archive_reserve=archive_reserve,
    )
    inventory = archive_inventory(archive_destination)
    if (
        archive_receipt.get("archive_root") != inventory["archive_root"]
        or archive_receipt.get("manifest_sha256") != inventory["manifest_sha256"]
        or archive_receipt.get("source_json_sha256") != inventory["source_json_sha256"]
        or archive_receipt.get("segment_count") != inventory["segment_count"]
        or archive_receipt.get("manifest_entry_count") != inventory["manifest_entry_count"]
        or archive_receipt.get("copying_file_count") != 0
        or archive_receipt.get("unmanifested_segment_count") != 0
        or archive_receipt.get("missing_segment_count") != 0
        or archive_receipt.get("duplicate_manifest_entries") != 0
        or inventory["copying_file_count"]
        or inventory["unmanifested_segment_count"]
        or inventory["missing_segment_count"]
        or inventory["duplicate_manifest_entries"]
    ):
        raise ValueError("Archive inventory does not match the verified provenance receipt")
    free = int(commitments["raw_free_bytes"])
    used = int(commitments["raw_used_bytes"])
    elapsed = (end - start) / 1e9
    sample_bytes = sum(s["bytes"] for s in value["segments"])
    rate = sample_bytes / elapsed
    runway = max(0, candidate.budget_bytes - used) / rate
    if runway < 14 * 86400:
        raise ValueError("Pilot growth offers less than fourteen days storage runway")
    production_status = json.loads((Path(candidate.root) / "status.json").read_text())
    current = service()
    if active_config is None or active_config_path is None:
        raise ValueError("Preflight requires the explicit active rollback configuration")
    if active_config_path.is_symlink() or not active_config_path.is_file():
        raise ValueError("Active rollback configuration is missing or unsafe")
    if production_status.get("config") != active_config.dump():
        raise ValueError("Active rollback configuration does not match the live recorder state")
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
    boundary = manifest(Path(candidate.root))
    boundary_sha256 = hashlib.sha256(canonical(boundary)).hexdigest()
    boundary_bytes = sum(segment["bytes"] for segment in boundary["segments"])
    boundary_count = len(boundary["segments"])
    if (
        canary_receipt["seed_manifest_sha256"] != boundary_sha256
        or canary_receipt.get("seed_segment_count") != boundary_count
        or canary_receipt.get("seed_archive_bytes") != boundary_bytes
        or recovery_receipt.get("manifest_sha256") != boundary_sha256
        or recovery_receipt.get("segment_count") != boundary_count
        or recovery_receipt.get("archive_bytes") != boundary_bytes
        or not isinstance(recovery_receipt.get("recovery"), dict)
        or recovery_receipt["recovery"].get("source_integrity") != "verified"
    ):
        raise ValueError(
            "Canary or recovery evidence does not match the exact current finalized boundary"
        )
    measured_startup_peak = canary_receipt.get("canary_process_peak_rss_bytes")
    if type(measured_startup_peak) is not int or measured_startup_peak <= 0:
        raise ValueError("Seeded canary lacks a measured candidate-process startup peak")
    if (
        not current.get("ControlGroup")
        or not current.get("MemoryHigh", "").isdigit()
        or not current.get("MemoryMax", "").isdigit()
    ):
        raise ValueError("Production service memory limits or cgroup identity are unavailable")
    restart_resources = require_restart_safe(
        current["ControlGroup"],
        measured_startup_peak_bytes=measured_startup_peak,
        target_memory_high_bytes=int(current["MemoryHigh"]),
        target_memory_max_bytes=int(current["MemoryMax"]),
        current_memory_max_bytes=int(current["MemoryMax"]),
    )
    return dict(
        schema_version=1,
        checked_ns=time.time_ns(),
        source_sha256=source_hash(),
        candidate=candidate.dump(),
        canary=canary.dump(),
        canary_replay_sha256=engine.digest(),
        canary_manifest_sha256=hashlib.sha256(canonical(value)).hexdigest(),
        production_boundary_manifest_sha256=boundary_sha256,
        production_boundary_segment_count=boundary_count,
        production_boundary_archive_bytes=boundary_bytes,
        canary_seed_manifest_sha256=canary_receipt["seed_manifest_sha256"],
        recovery_receipt_sha256=hashlib.sha256(canonical(recovery_receipt)).hexdigest(),
        restart_resources=restart_resources,
        archive_inventory=inventory,
        archive_receipt_sha256=hashlib.sha256(canonical(archive_receipt)).hexdigest(),
        archive_budget_bytes=archive_budget,
        archive_reserve_bytes=commitments["archive_reserve_bytes"],
        archive_destination=inventory["archive_root"],
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
        storage_commitments=commitments,
        free_disk_bytes=free,
        protected_disk_reserve_bytes=disk_reserve,
        production_before=current,
        production_before_config=active_config.dump(),
        production_before_config_sha256=config_hash(active_config),
        active_config_path=str(active_config_path.resolve()),
        deployment_guard_sha256=guard_identity,
        cached_snapshot_repair=dict(
            requested=repair_cached_snapshots,
            confirmed=repair_confirmed,
            prior_error=production_status.get("error"),
            affected_assets=list(bad_books),
        ),
        passed=True,
        limitations=[
            "Canary includes startup/discovery overhead, not a stable long-term rate estimate.",
            "Bounded canary is an engineering gate, not scientific validation.",
            "Rollback restores previous network configuration under tested revision; no raw bytes are removed.",
        ],
    )


def apply(
    candidate: Config,
    gate: dict[str, Any],
    config_path: Path,
    output: Path,
    *,
    health_timeout_seconds: int = 180,
) -> dict[str, Any]:
    if not 60 <= health_timeout_seconds <= 300:
        raise ValueError("Deployment health window must be 60..300 seconds")
    if (
        not gate.get("passed")
        or gate["source_sha256"] != source_hash()
        or gate.get("deployment_guard_sha256") != deployment_guard_hash()
        or gate["candidate"] != candidate.dump()
        or time.time_ns() - gate["checked_ns"] > 60 * 10**9
    ):
        raise ValueError("Deployment gate changed or expired; rerun preflight")
    current_service = service()
    if current_service["MainPID"] != gate["production_before"]["MainPID"]:
        raise ValueError("Production process changed after preflight")
    if config_path.is_symlink() or not config_path.is_file():
        raise ValueError("Active rollback configuration is missing or unsafe")
    previous = Config.load(config_path)
    if (
        str(config_path.resolve()) != gate.get("active_config_path")
        or previous.dump() != gate.get("production_before_config")
        or config_hash(previous) != gate.get("production_before_config_sha256")
    ):
        raise ValueError("Active rollback configuration changed after preflight")
    current_boundary = manifest(Path(candidate.root))
    current_boundary_sha256 = hashlib.sha256(canonical(current_boundary)).hexdigest()
    if current_boundary_sha256 != gate.get("production_boundary_manifest_sha256"):
        raise ValueError("Finalized production boundary changed after preflight")
    inventory = archive_inventory(Path(gate["archive_destination"]))
    verified_inventory = gate.get("archive_inventory", {})
    if inventory != verified_inventory:
        raise ValueError("Archive inventory changed after preflight")
    storage_commitment(
        Path(candidate.root),
        raw_budget=candidate.budget_bytes,
        archive_budget=gate["archive_budget_bytes"],
        raw_reserve=gate["protected_disk_reserve_bytes"],
        archive_destination=Path(gate["archive_destination"]),
        archive_reserve=gate["archive_reserve_bytes"],
    )
    recovery_resources = gate.get("restart_resources", {})
    require_restart_safe(
        current_service["ControlGroup"],
        measured_startup_peak_bytes=recovery_resources["measured_startup_peak_bytes"],
        target_memory_high_bytes=recovery_resources["target_memory_high_bytes"],
        target_memory_max_bytes=recovery_resources["target_memory_max_bytes"],
        current_memory_max_bytes=int(current_service["MemoryMax"]),
    )
    latest_status = json.loads((Path(candidate.root) / "status.json").read_text())
    if time.time_ns() - latest_status.get("updated_ns", 0) > 10 * 10**9 or latest_status.get(
        "fresh_books"
    ) != latest_status.get("expected_books"):
        raise ValueError("Production source health changed after preflight")
    backup = Path(candidate.root).parent / f"config-before-deployment-{time.time_ns()}.json"
    atomic_json(backup, previous.dump())
    result = dict(
        gate,
        prior_config=previous.dump(),
        prior_config_backup=str(backup),
        restart_intent_ns=time.time_ns(),
        health_timeout_seconds=health_timeout_seconds,
    )
    atomic_json(output, result)  # Record intent before mutating the service.
    atomic_json(config_path, candidate.dump())
    subprocess.run(["systemctl", "--user", "restart", "midas-reality.service"], check=True)
    deadline = time.monotonic() + health_timeout_seconds
    while time.monotonic() < deadline:
        status = json.loads((Path(candidate.root) / "status.json").read_text())
        if (
            status["started_ns"] > result["restart_intent_ns"]
            and status["state"] == "RECORDING_UNSEQUENCED"
            and status["fresh_books"] == candidate.markets * 2
            and status["config"] == candidate.dump()
        ):
            result.update(
                deployed_ns=time.time_ns(),
                production_after=service(),
                deployed=True,
                health=dict(
                    state=status["state"],
                    fresh_books=status["fresh_books"],
                    ordinal=status["ordinal"],
                    frames=status["frames"],
                ),
            )
            atomic_json(output, result)
            return result
        time.sleep(1)
    atomic_json(config_path, previous.dump())
    subprocess.run(["systemctl", "--user", "restart", "midas-reality.service"], check=True)
    result.update(deployed=False, rolled_back_ns=time.time_ns(), reason="Fresh-book health timeout")
    atomic_json(output, result)
    raise ValueError("Fresh-book deployment health gate failed; prior configuration restored")


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
    parser.add_argument("--active-config", type=Path, default=WORKSPACE / "deploy/reality.json")
    parser.add_argument("--canary-receipt", type=Path)
    parser.add_argument("--recovery-receipt", type=Path)
    parser.add_argument("--archive-receipt", type=Path)
    parser.add_argument(
        "--gate", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_PREFLIGHT.json"
    )
    parser.add_argument(
        "--output", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_DEPLOYMENT.json"
    )
    parser.add_argument("--archive-budget", type=int, default=112 * 1024**3)
    parser.add_argument(
        "--archive-destination",
        type=Path,
        default=Path("/mnt/continental-cloud/data/midas-reality-staging/archive-mission3"),
    )
    parser.add_argument("--archive-reserve", type=int, default=400 * 1024**3)
    parser.add_argument("--repair-cached-snapshots", action="store_true")
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.receipt)
    elif args.command == "preflight":
        if args.active_config.is_symlink() or not args.active_config.is_file():
            raise ValueError("Active rollback configuration is missing or unsafe")
        if (
            args.canary_receipt is None
            or args.recovery_receipt is None
            or args.archive_receipt is None
            or args.canary_receipt.is_symlink()
            or args.recovery_receipt.is_symlink()
            or args.archive_receipt.is_symlink()
        ):
            raise ValueError(
                "Preflight requires regular seeded-canary, recovery, and verified-archive receipts"
            )
        gate = preflight(
            Config.load(args.candidate),
            Config.load(args.canary_config),
            json.loads(args.receipt.read_text()),
            args.archive_budget,
            20 * 1024**3,
            archive_destination=args.archive_destination,
            archive_reserve=args.archive_reserve,
            repair_cached_snapshots=args.repair_cached_snapshots,
            active_config=Config.load(args.active_config),
            active_config_path=args.active_config,
            canary_receipt=json.loads(args.canary_receipt.read_text()),
            recovery_receipt=json.loads(args.recovery_receipt.read_text()),
            archive_receipt=json.loads(args.archive_receipt.read_text()),
        )
        atomic_json(args.gate, gate)
        print(json.dumps(gate, indent=2))
    else:
        result = apply(
            Config.load(args.candidate),
            json.loads(args.gate.read_text()),
            args.active_config,
            args.output,
        )
        print(json.dumps(result["health"], indent=2))


if __name__ == "__main__":
    main()
