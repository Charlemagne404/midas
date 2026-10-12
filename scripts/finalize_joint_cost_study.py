"""Bounded post-study verification, findings publication and evidence export."""

import argparse
import hashlib
import json
import signal
import tarfile
import time
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.jobs import artifact_usage
from midas.economics.attestation import digest

from scripts.arena_bundle import export_tournament
from scripts.capture_public_series import publish_exclusive
from scripts.verify_joint_cost_study import analyze_study


def verify_bundle(path: Path) -> int:
    with tarfile.open(path, "r:gz") as archive:
        manifest = json.load(archive.extractfile("BUNDLE_MANIFEST.json"))
        seen = set()
        for member in archive:
            if member.name == "BUNDLE_MANIFEST.json":
                continue
            if member.name in seen or member.name not in manifest["files"]:
                raise ValueError("Unexpected or duplicate bundle payload")
            seen.add(member.name)
            payload = archive.extractfile(member)
            if (
                payload is None
                or hashlib.sha256(payload.read()).hexdigest() != manifest["files"][member.name]
            ):
                raise ValueError("Bundle payload checksum differs")
        if seen != set(manifest["files"]):
            raise ValueError("Missing bundle payload")
        return len(seen)


def finalize(root: Path, plan_path: Path, job_id: str, output: Path, wall_seconds: int) -> dict:
    job_directory = artifact_path(root, "jobs", job_id)
    state_path = job_directory / "post-study-state.json"
    if state_path.exists():
        raise ValueError(
            "Existing finalization state requires inspection; no blind duplicate execution"
        )
    plan = json.loads(plan_path.read_text())
    began = time.monotonic()
    state = {
        "job_id": job_id,
        "phase": "WAITING",
        "created_at": time.time(),
        "producer_sha256": sha256(Path(__file__)),
        "plan_sha256": sha256(plan_path),
        "wall_seconds": wall_seconds,
    }
    tool_directory = Path(__file__).resolve().parent
    state["tool_hashes"] = {}
    for name in (
        "finalize_joint_cost_study.py",
        "verify_joint_cost_study.py",
        "verify_cost_policy.py",
        "attribute_arena_losses.py",
        "compare_policies.py",
        "arena_bundle.py",
        "capture_public_series.py",
    ):
        payload = (tool_directory / name).read_bytes()
        state["tool_hashes"][name] = hashlib.sha256(payload).hexdigest()
        atomic_bytes(job_directory / "post-study-source" / name, payload)

    def publish(phase, **details):
        state.update(phase=phase, updated_at=time.time(), **details)
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    try:
        publish("WAITING")
        while True:
            job = json.loads((job_directory / "job.json").read_text())
            if job["state"] == "COMPLETED":
                break
            if job["state"] not in {"QUEUED", "RUNNING"}:
                raise ValueError("Research job did not complete: " + job["state"])
            if time.monotonic() - began > wall_seconds:
                raise TimeoutError("Post-study wall budget reached")
            time.sleep(3)
        if artifact_usage(root)[0] >= 1024**3 - 16 * 1024**2:
            raise RuntimeError("Insufficient artifact headroom for final reports")
        for name, expected in state["tool_hashes"].items():
            if (
                sha256(tool_directory / name) != expected
                or sha256(job_directory / "post-study-source" / name) != expected
            ):
                raise ValueError("Finalization tool source changed during the wait")
        available = next(
            int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemAvailable:")
        )
        if available < 2048 * 1024:
            raise RuntimeError("Insufficient host memory for evidence finalization")
        publish("VERIFYING")
        report = analyze_study(root, plan, job_id)
        identity = report["tournament_id"]
        directory = artifact_path(root, "tournaments", identity)
        analysis = directory / "analyses" / "joint-cost-study.json"
        publish_exclusive(analysis, json.dumps(report, indent=2, allow_nan=False).encode())
        finding_id = "finding-joint-cost-" + digest([identity, "preregistered-joint-cost-1"])[:24]
        finding = {
            "finding_id": finding_id,
            "created_at": time.time(),
            "title": "Joint completion and friction comparison completed",
            "tournament_id": identity,
            "research_question": plan["hypothesis"],
            "outcome": {
                "primary_comparisons": report["primary_comparisons"],
                "verification": report["verification"],
            },
            "interpretation": f"Fixed policies evaluated on {plan['source_groups']} fresh synthetic source groups. Mean-difference intervals and sampled downside metrics are preserved separately. No model selection, threshold retuning or promotion occurred.",
            "caveats": report["limitations"],
            "next_experiment": "Use the verified loss attribution to design a fresh robustness or recovery experiment.",
        }
        publish_exclusive(
            artifact_path(root, "findings", finding_id) / "manifest.json",
            json.dumps(finding, indent=2, allow_nan=False).encode(),
        )
        if artifact_usage(root)[0] > 1024**3:
            raise RuntimeError("Artifact cap exceeded; completed evidence retained")
        publish("EXPORTING", tournament_id=identity, finding_id=finding_id)
        bundle = export_tournament(root, identity, output)
        payloads = verify_bundle(output)
        publish(
            "VERIFIED",
            bundle=bundle,
            payloads_verified=payloads,
            elapsed_seconds=time.monotonic() - began,
        )
        return state
    except Exception as error:
        publish("FAILED", error=str(error))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=2100)
    args = parser.parse_args()
    if not 60 <= args.wall_seconds <= 2400:
        parser.error("--wall-seconds must be between 60 and 2400")

    def stopped(signum, frame):
        raise InterruptedError("Finalization supervisor stopped the process")

    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)
    finalize(args.root, args.plan, args.job_id, args.output, args.wall_seconds)
