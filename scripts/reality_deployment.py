"""Intentional recorder deployment: frozen checks, isolated canary, capacity guard.

Run `verify`, then `preflight`, then `apply`. Only apply changes production config
and restarts the recorder. A failed health gate restores the previous configuration
under the same tested implementation. All raw roots remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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


def source_hash() -> str:
    return hashlib.sha256(
        b"".join(
            p.name.encode() + p.read_bytes()
            for p in sorted((WORKSPACE / "packages/midas/reality").glob("*.py"))
        )
    ).hexdigest()


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
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def verify(output: Path) -> dict[str, Any]:
    began = time.time_ns()
    identity = source_hash()
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
    passed = all(r["returncode"] == 0 for r in results) and source_hash() == identity
    receipt = dict(
        schema_version=1,
        began_ns=began,
        completed_ns=time.time_ns(),
        source_sha256=identity,
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
) -> dict[str, Any]:
    if not receipt.get("passed") or receipt.get("source_sha256") != source_hash():
        raise ValueError("Checks missing, failed or source changed since verification")
    if time.time_ns() - receipt["completed_ns"] > 24 * 3600 * 10**9:
        raise ValueError("Verification receipt expired")
    if Path(candidate.root).resolve() == Path(canary.root).resolve():
        raise ValueError("Canary must be isolated from production root")
    ignored = {"root", "budget_bytes", "reserve_bytes", "retention_days"}
    if any(candidate.dump()[k] != canary.dump()[k] for k in candidate.dump() if k not in ignored):
        raise ValueError("Canary did not exercise candidate network/reconstruction settings")
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
    if gaps["book_resynchronization"] + gaps["unconfirmed_top_advertisement"] > 3:
        raise ValueError("Canary repeatedly lost book consistency")
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
    current = service()
    if (
        current["ActiveState"] != "active"
        or production_status["state"] != "RECORDING_UNSEQUENCED"
        or time.time_ns() - production_status["updated_ns"] > 10 * 10**9
        or production_status["fresh_books"] != production_status["expected_books"]
    ):
        raise ValueError("Production is not healthy before planned deployment")
    return dict(
        schema_version=1,
        checked_ns=time.time_ns(),
        source_sha256=source_hash(),
        candidate=candidate.dump(),
        canary=canary.dump(),
        canary_replay_sha256=engine.digest(),
        canary_manifest_sha256=hashlib.sha256(canonical(value)).hexdigest(),
        canary_checkpoints=checkpoints,
        canary_fresh_books=fresh,
        canary_frames=status["frames"],
        gaps=dict(gaps),
        comparisons=dict(comparison_counts),
        canary_bytes_per_second=rate,
        conservative_pilot_runway_days=runway / 86400,
        allocated_raw_and_archive_bytes=candidate.budget_bytes + archive_budget,
        free_disk_bytes=free,
        protected_disk_reserve_bytes=disk_reserve,
        production_before=current,
        passed=True,
        limitations=[
            "Pilot includes startup/discovery overhead, not a stable long-term rate estimate.",
            "Two-minute canary is an engineering gate, not scientific validation.",
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
        or gate["candidate"] != candidate.dump()
        or time.time_ns() - gate["checked_ns"] > 60 * 10**9
    ):
        raise ValueError("Deployment gate changed or expired; rerun preflight")
    if service()["MainPID"] != gate["production_before"]["MainPID"]:
        raise ValueError("Production process changed after preflight")
    previous = Config.load(config_path)
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
    parser.add_argument(
        "--gate", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_PREFLIGHT.json"
    )
    parser.add_argument(
        "--output", type=Path, default=WORKSPACE / "docs/REALITY_GATE_A_DEPLOYMENT.json"
    )
    parser.add_argument("--archive-budget", type=int, default=24 * 1024**3)
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
        )
        atomic_json(args.gate, gate)
        print(json.dumps(gate, indent=2))
    else:
        result = apply(
            Config.load(args.candidate),
            json.loads(args.gate.read_text()),
            WORKSPACE / "deploy/reality.json",
            args.output,
        )
        print(json.dumps(result["health"], indent=2))


if __name__ == "__main__":
    main()
