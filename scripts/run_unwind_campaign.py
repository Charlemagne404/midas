"""Run one bounded full gate, fixed unwind study, independent verification and export."""

import argparse
import json
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, artifact_usage, create

from scripts.arena_bundle import export_unwind
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.verify_unwind import verify


def run(root: Path, plan_path: Path, output: Path, test_log: Path) -> dict:
    plan = json.loads(plan_path.read_text())
    specification = JobSpec.model_validate(plan["configuration"])
    if specification.kind != "unwind":
        raise ValueError("Campaign requires one fixed unwind job")
    assert specification.unwind is not None
    directory = root / "unwind-campaigns" / ("campaign-" + str(specification.unwind.seed))
    state_path = directory / "state.json"
    if state_path.exists() or output.exists() or test_log.exists():
        raise ValueError("Existing campaign artifacts require inspection; no blind duplicate run")
    if research_hash() != plan["source_hash"]:
        raise ValueError("Preregistered package source changed")
    state = {
        "phase": "PREFLIGHT",
        "created_at": time.time(),
        "source_hash": plan["source_hash"],
        "plan_sha256": sha256(plan_path),
        "tool_hashes": {},
        "configuration": plan["configuration"],
    }
    tools = Path(__file__).resolve().parent
    for name in (
        "run_unwind_campaign.py",
        "verify_unwind.py",
        "arena_bundle.py",
        "finalize_joint_cost_study.py",
        "capture_public_series.py",
    ):
        payload = (tools / name).read_bytes()
        atomic_bytes(directory / "source" / name, payload)
        state["tool_hashes"][name] = sha256(directory / "source" / name)
    began = time.monotonic()

    def publish(phase, **fields):
        state.update(
            phase=phase, updated_at=time.time(), elapsed_seconds=time.monotonic() - began, **fields
        )
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **fields}), flush=True)

    def unchanged():
        if research_hash() != plan["source_hash"]:
            raise ValueError("Package source changed during the campaign")
        for name, expected in state["tool_hashes"].items():
            if sha256(tools / name) != expected or sha256(directory / "source" / name) != expected:
                raise ValueError("Campaign tool source changed")

    try:
        if artifact_usage(root)[0] > 1024**3 - 32 * 1024**2:
            raise RuntimeError("Insufficient Arena artifact headroom")
        publish("FULL_GATE", test_log=str(test_log))
        test_log.parent.mkdir(parents=True, exist_ok=True)
        with test_log.open("x") as stream:
            result = subprocess.run(
                ["nice", "-n", "10", "taskset", "-c", "0", sys.executable, "-m", "pytest", "-q"],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=1200,
            )
        publish("GATE_RESULT", test_exit_code=result.returncode)
        if result.returncode:
            raise RuntimeError("Full source regression failed; study not admitted")
        unchanged()
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=90
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8000/api/health", timeout=3
                ) as response:
                    health = json.load(response)
                if health["status"] == "READY":
                    break
            except (urllib.error.URLError, TimeoutError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("Original API did not return READY")
            time.sleep(1)
        publish("ADMITTING", health=health)
        job = create(root, specification)
        publish("RESEARCHING", job_id=job["job_id"], unit=job["unit"])
        deadline = time.monotonic() + specification.max_wall_seconds + 60
        while True:
            job = json.loads((root / "jobs" / job["job_id"] / "job.json").read_text())
            if job["state"] == "COMPLETED":
                break
            if job["state"] not in {"QUEUED", "RUNNING"}:
                raise RuntimeError("Study did not complete: " + str(job.get("error")))
            if time.monotonic() > deadline:
                raise TimeoutError("Bounded study observation deadline reached")
            time.sleep(3)
        unchanged()
        identity = job["result"]["unwind_id"]
        manifest = json.loads((root / "unwinds" / identity / "manifest.json").read_text())
        if (
            manifest["configuration"] != plan["configuration"]["unwind"]
            or manifest["source_hash"] != plan["source_hash"]
        ):
            raise ValueError("Study differs from preregistration")
        publish("VERIFYING", unwind_id=identity)
        verified = verify(root, identity)
        atomic_json(root / "unwinds" / identity / "verification.json", verified)
        publish("EXPORTING", verification=verified)
        bundle = export_unwind(root, identity, output)
        payloads = verify_bundle(output)
        if artifact_usage(root)[0] > 1024**3:
            raise RuntimeError("Arena artifact cap exceeded; evidence retained")
        publish("COMPLETED", bundle=bundle, payloads_verified=payloads)
        return state
    except Exception as error:
        publish("FAILED", error=str(error))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-log", type=Path, required=True)
    args = parser.parse_args()

    def stopped(signum, frame):
        raise InterruptedError("Campaign supervisor stopped the process")

    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)
    run(args.root, args.plan, args.output, args.test_log)
