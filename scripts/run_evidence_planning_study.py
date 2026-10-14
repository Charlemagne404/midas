"""Execute one frozen evidence-selected plan after the exact successful gate."""

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, create, inspect
from midas.economics.attestation import digest

from scripts.arena_bundle import export_plan
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.run_generator_audit import gate_result
from scripts.verify_evidence_planning_study import verify


def run(root: Path, production_path: Path, output: Path):
    specification = json.loads(production_path.read_text())
    directory = root / "planned-studies/capacity-603071"
    state_path = directory / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing planned study requires inspection; no duplicate execution")
    identity = specification["plan_id"]
    plan_path = artifact_path(root, "plans", identity) / "manifest.json"
    plan = json.loads(plan_path.read_text())
    if plan["state"] != "PROPOSED" or sha256(plan_path) != specification["plan_sha256"]:
        raise ValueError("Original proposed research plan differs")
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "specification_sha256": sha256(production_path),
        "frozen_sha256": digest(plan["frozen"]),
        "tool_hashes": specification["tool_hashes"],
    }
    for name, expected in state["tool_hashes"].items():
        path = Path(__file__).parent / name
        if sha256(path) != expected:
            raise ValueError("Declared producer differs")
        atomic_bytes(directory / "source" / name, path.read_bytes())
    atomic_bytes(directory / "preregistration.json", production_path.read_bytes())
    began = time.monotonic()

    def publish(phase, **details):
        state.update(phase=phase, updated_at=time.time(), **details)
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    def unchanged():
        if (
            research_hash() != specification["source_hash"]
            or sha256(production_path) != state["specification_sha256"]
            or digest(json.loads(plan_path.read_text())["frozen"]) != state["frozen_sha256"]
        ):
            raise ValueError("Frozen study source/plan changed")
        for name, expected in state["tool_hashes"].items():
            if (
                sha256(Path(__file__).parent / name) != expected
                or sha256(directory / "source" / name) != expected
            ):
                raise ValueError("Captured study producer changed")

    try:
        unchanged()
        publish("WAITING_GATE")
        while (
            gate_result(specification["full_gate_unit"], Path(specification["full_gate_log"]))
            is None
        ):
            unchanged()
            if time.monotonic() - began > 2100:
                raise TimeoutError("Exact gate observation budget reached")
            time.sleep(5)
        publish("DEPLOYING_API")
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=45
        )
        for _ in range(30):
            try:
                response = json.load(
                    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
                )
                if response["status"] == "READY":
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise ValueError("API readiness not established")
        unchanged()
        spec = JobSpec(kind="plan", plan_id=identity, max_wall_seconds=7200)
        job = create(root, spec)
        publish("RESEARCHING", job_id=job["job_id"], unit=job["unit"])
        deadline = time.monotonic() + 7260
        while True:
            job = inspect(root, job["job_id"])
            if job["state"] == "COMPLETED":
                break
            if job["state"] not in {"RUNNING", "QUEUED"}:
                raise ValueError("Native research plan failed: " + str(job.get("error")))
            if time.monotonic() > deadline:
                raise TimeoutError("Native plan observation deadline reached; inspect original job")
            time.sleep(5)
        unchanged()
        if (
            job["configuration"] != spec.model_dump(mode="json")
            or job["submitted_source_hash"] != specification["source_hash"]
            or job["exit_status"] != 0
        ):
            raise ValueError("Native plan differs from bounded specification")
        source = json.loads((root / "jobs" / job["job_id"] / "source-manifest.json").read_text())
        if source["source_hash"] != specification["source_hash"] or not source["files"]:
            raise ValueError("Native source identity differs")
        for relative, expected in source["files"].items():
            name = Path(relative)
            if (
                name.is_absolute()
                or ".." in name.parts
                or sha256(root / "jobs" / job["job_id"] / "source" / name) != expected
            ):
                raise ValueError("Native source payload differs")
        publish("VERIFYING", plan_id=identity)
        report = verify(root, identity)
        report["native_job_id"] = job["job_id"]
        atomic_json(directory / "verification.json", report)
        finding = {
            "finding_id": "finding-capacity-planning-603071",
            "created_at": time.time(),
            "director_id": report["director_id"],
            "research_question": plan["frozen"]["question"],
            "title": "Evidence-selected multi-seed capacity comparison completed",
            "outcome": report,
            "interpretation": "Four preregistered fits selected using validation only; matched fresh support comparisons and uncertainty are preserved. No model promoted or retuned from challenge outcomes.",
            "caveats": report["limitations"],
            "next_experiment": "Inspect independent downside and conservative execution before proposing another question; retain this opened cohort outside further selection.",
        }
        atomic_json(
            artifact_path(root, "findings", finding["finding_id"]) / "manifest.json", finding
        )
        bundle = Path("data/exports/evidence-planning-603071") / (identity + ".tar.gz")
        report["export"] = export_plan(root, identity, bundle)
        report["export_payloads_verified"] = verify_bundle(bundle)
        atomic_json(output, report)
        publish("VERIFIED", report=str(output))
        return report
    except BaseException as error:
        publish("FAILED", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--specification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.specification, args.output)
