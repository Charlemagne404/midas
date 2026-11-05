#!/usr/bin/env python3
"""Compare Reality v5/v6 on synthetic full stores in service-sized containers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

COUNTS = (1_000, 10_000, 58_367)
MEMORY_MAX = 192 * 1024**2
MEMORY_HIGH = 160 * 1024**2


def run_one(
    *,
    implementation: str,
    count: int,
    image: str,
    source: Path,
    baseline: Path,
    data: Path,
    run_key: str,
) -> dict[str, Any]:
    name = f"midas-reality-capacity-{run_key}-{implementation}-{count}"
    python_path = "/source/packages" if implementation == "v6" else "/reality-v5-baseline/packages"
    command = [
        "docker",
        "run",
        "--name",
        name,
        "--network=none",
        f"--memory={MEMORY_MAX}",
        f"--memory-reservation={MEMORY_HIGH}",
        f"--memory-swap={MEMORY_MAX}",
        "--cpus=1",
        "--pids-limit=64",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777",
        "--mount",
        f"type=bind,src={source},dst=/source,readonly",
        "--mount",
        f"type=bind,src={baseline},dst=/reality-v5-baseline,readonly",
        "--mount",
        f"type=bind,src={data},dst=/reality-test-data,readonly",
        "--env",
        f"PYTHONPATH={python_path}",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "HOME=/home/midas",
        "--env",
        "TMPDIR=/tmp",
        image,
        "/opt/venv/bin/python",
        "/source/.github/ci-test-support/measure-reality-capacity.py",
        "--implementation",
        implementation,
        "--source-root",
        "/source",
        "--baseline-root",
        "/reality-v5-baseline",
        "--data-root",
        f"/reality-test-data/reality-{count}",
        "--catalog-count",
        str(count),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=65, check=False)
        status = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as error:
        status = 124
        stdout = (
            error.stdout.decode(errors="replace")
            if isinstance(error.stdout, bytes)
            else error.stdout or ""
        )
        stderr = (
            error.stderr.decode(errors="replace")
            if isinstance(error.stderr, bytes)
            else error.stderr or ""
        )
        timed_out = True
    try:
        inspect = subprocess.run(
            ["docker", "inspect", name], capture_output=True, text=True, check=False
        )
        if inspect.returncode == 0:
            details = json.loads(inspect.stdout)[0]
            state = details["State"]
            host_config = details["HostConfig"]
            actual = {
                "memory_max": host_config["Memory"],
                "memory_high": host_config["MemoryReservation"],
                "memory_swap": host_config["MemorySwap"],
                "cpu_quota_nano": host_config["NanoCpus"],
                "oom_killed": bool(state["OOMKilled"]),
                "exit_code": int(state["ExitCode"]),
            }
        else:
            actual = {"inspect_error": inspect.stderr.strip()}
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False)

    report: dict[str, Any] = {
        "implementation": implementation,
        "catalog_count": count,
        "exit_status": status,
        "timed_out": timed_out,
        "container": actual,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }
    if status == 0:
        try:
            measured = json.loads(stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as error:
            raise RuntimeError(f"benchmark output was not valid JSON: {stdout!r}") from error
        report["measurement"] = measured
    print(json.dumps(report, sort_keys=True), flush=True)
    if actual.get("memory_max") != MEMORY_MAX or actual.get("memory_high") != MEMORY_HIGH:
        raise RuntimeError(f"Docker did not apply Reality service memory limits: {actual}")
    if actual.get("memory_swap") != MEMORY_MAX or actual.get("cpu_quota_nano") != 1_000_000_000:
        raise RuntimeError(f"Docker did not apply no-swap / one-CPU benchmark limits: {actual}")
    if implementation == "v6" and (status != 0 or actual.get("oom_killed") or timed_out):
        raise RuntimeError(f"bounded Reality v6 failed its existing service limits: {report}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--runner-temp", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--run-key", required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    baseline = args.baseline_root.resolve()
    runner_temp = args.runner_temp.resolve()
    if not (source / ".github/ci-test-support/measure-reality-capacity.py").is_file():
        raise SystemExit("candidate capacity benchmark entry point is missing")
    if not (baseline / "packages/midas/reality/operations.py").is_file():
        raise SystemExit("pinned Reality v5 source is missing")
    if not runner_temp.is_dir():
        raise SystemExit("runner temporary directory is unavailable")

    temp_name: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="midas-reality-capacity-", dir=runner_temp) as name:
            temp_name = name
            data_root = Path(name) / "stores"
            subprocess.run(
                [
                    sys.executable,
                    str(source / ".github/ci-test-support/prepare-reality-capacity-fixture.py"),
                    "--root",
                    str(data_root),
                    "--counts",
                    *(str(count) for count in COUNTS),
                ],
                check=True,
            )
            os.chmod(name, 0o755)
            for count in COUNTS:
                data = data_root / f"reality-{count}"
                os.chmod(data, 0o755)
                baseline_result = run_one(
                    implementation="v5",
                    count=count,
                    image=args.image,
                    source=source,
                    baseline=baseline,
                    data=data,
                    run_key=args.run_key,
                )
                candidate_result = run_one(
                    implementation="v6",
                    count=count,
                    image=args.image,
                    source=source,
                    baseline=baseline,
                    data=data,
                    run_key=args.run_key,
                )
                if baseline_result.get("measurement") and candidate_result.get("measurement"):
                    baseline_data = baseline_result["measurement"]["result"]
                    candidate_data = candidate_result["measurement"]["result"]
                    if baseline_data != candidate_data:
                        raise RuntimeError(
                            f"Reality v5/v6 capacity reports differ at {count} catalogs"
                        )
    finally:
        if temp_name is not None and Path(temp_name).exists():
            shutil.rmtree(temp_name)


if __name__ == "__main__":
    main()
