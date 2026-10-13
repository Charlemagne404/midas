"""Wait for a successful full gate, then run and export one fixed revision pair."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, artifact_usage, create

from scripts.arena_bundle import export_tournament
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.verify_generator_pair import verify


def gate_result(unit: str, log: Path) -> dict | None:
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "ExecMainStatus"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if fields.get("ActiveState") in {"active", "activating"}:
        return None
    if fields.get("ExecMainStatus") != "0":
        raise ValueError("Full gate failed; no research admission")
    matches = re.findall(r"^(\d+) passed, (\d+) skipped[^\n]* in ([\d.]+)s", log.read_text(), re.M)
    if len(matches) != 1 or int(matches[0][0]) < 480:
        raise ValueError("Missing complete successful full-gate evidence")
    return {
        "unit": unit,
        "passed": int(matches[0][0]),
        "skipped": int(matches[0][1]),
        "seconds": float(matches[0][2]),
        "log_sha256": sha256(log),
    }


def run(root: Path, plan_path: Path, output: Path, gate_unit: str, gate_log: Path) -> dict:
    plan = json.loads(plan_path.read_text())
    specs = [JobSpec.model_validate(c) for c in plan["configurations"]]
    if len(specs) != 2 or any(s.kind != "tournament" or s.tournament is None for s in specs):
        raise ValueError("Require exactly two tournament configurations")
    a, b = [s.tournament.model_dump(mode="json") for s in specs]
    if (
        a.pop("generator_revision") is not None
        or b.pop("generator_revision") != {"version": "hashed-settlement-1"}
        or a != b
    ):
        raise ValueError("Only declared settlement revision may differ")
    if plan["models_trained"] or plan["promotion"] or plan["retuning"]:
        raise ValueError("Audit must use frozen models without selection")
    if plan["source_hash"] != research_hash():
        raise ValueError("Preregistered package source changed")
    directory = root / "generator-audits" / "audit-483071"
    state_path = directory / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing audit requires inspection; refuse duplicate admission")
    tools = Path(__file__).resolve().parent
    names = (
        "run_generator_audit.py",
        "verify_generator_pair.py",
        "arena_bundle.py",
        "finalize_joint_cost_study.py",
        "capture_public_series.py",
    )
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "jobs": [],
        "source_hash": plan["source_hash"],
        "plan_sha256": sha256(plan_path),
        "tool_hashes": {},
    }
    for name in names:
        atomic_bytes(directory / "source" / name, (tools / name).read_bytes())
        state["tool_hashes"][name] = sha256(tools / name)
    atomic_bytes(directory / "preregistration.json", plan_path.read_bytes())
    began = time.monotonic()

    def publish(phase: str, **details):
        state.update(
            phase=phase, updated_at=time.time(), elapsed_seconds=time.monotonic() - began, **details
        )
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    def unchanged():
        if research_hash() != plan["source_hash"] or sha256(plan_path) != state["plan_sha256"]:
            raise ValueError("Preregistered source or plan changed")
        for name, expected in state["tool_hashes"].items():
            if sha256(tools / name) != expected or sha256(directory / "source" / name) != expected:
                raise ValueError("Captured producer or verifier changed")
        for identity, expected in plan["weights"].items():
            model_dir = artifact_path(root, "models", identity)
            model = json.loads((model_dir / "manifest.json").read_text())
            weights = model_dir / ("policy.zip" if model["family"] == "ppo" else "parameters.json")
            if sha256(weights) != expected or model["artifact_sha256"] != expected:
                raise ValueError("Fixed model weights changed")

    try:
        publish("WAITING_GATE", gate_unit=gate_unit)
        while True:
            unchanged()
            gate = gate_result(gate_unit, gate_log)
            if gate is not None:
                break
            if time.monotonic() - began > 1200:
                raise TimeoutError("Gate observation budget reached; inspect original unit")
            time.sleep(5)
        publish("GATE_PASSED", gate=gate)
        for index, spec in enumerate(specs):
            unchanged()
            if artifact_usage(root)[0] >= 1024**3 - 64 * 1024**2:
                raise RuntimeError("Insufficient Arena headroom under unchanged cap")
            publish("ADMITTING", revision=index)
            job = create(root, spec)
            state["jobs"].append({"job_id": job["job_id"], "unit": job["unit"], "revision": index})
            publish("RESEARCHING", job_id=job["job_id"])
            deadline = time.monotonic() + spec.max_wall_seconds + 60
            while True:
                job = json.loads((root / "jobs" / job["job_id"] / "job.json").read_text())
                if job["state"] == "COMPLETED":
                    break
                if job["state"] not in {"QUEUED", "RUNNING"}:
                    raise RuntimeError("Research failed: " + str(job.get("error")))
                if time.monotonic() > deadline:
                    raise TimeoutError("Research observation budget reached; inspect native job")
                time.sleep(3)
            if (
                job["configuration"] != plan["configurations"][index]
                or job["submitted_source_hash"] != plan["source_hash"]
            ):
                raise ValueError("Worker differs from preregistration")
            source = json.loads(
                (root / "jobs" / job["job_id"] / "source-manifest.json").read_text()
            )
            if source["source_hash"] != plan["source_hash"] or not source["files"]:
                raise ValueError("Captured package identity changed")
            for relative, expected in source["files"].items():
                path = Path(relative)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or sha256(root / "jobs" / job["job_id"] / "source" / path) != expected
                ):
                    raise ValueError("Captured package payload changed")
            state["jobs"][-1]["tournament_id"] = job["result"]["tournament_id"]
            publish("STUDY_COMPLETED", tournament_id=job["result"]["tournament_id"])
        unchanged()
        identities = [j["tournament_id"] for j in state["jobs"]]
        publish("VERIFYING", tournaments=identities)
        report = verify(root, plan, identities)
        finding_id = "finding-generator-483071"
        finding = {
            "finding_id": finding_id,
            "created_at": time.time(),
            "title": "Fixed-policy sensitivity to hashed synthetic settlement",
            "tournament_id": identities[1],
            "research_question": plan["question"],
            "outcome": report,
            "interpretation": "Matched fixed policies evaluated before and after a terminal payout revision. Report per-policy mean differences and intervals; no retraining, selection or promotion.",
            "caveats": plan["limitations"],
            "next_experiment": "Audit broader generator and market-path diversity on a separately preregistered cohort.",
        }
        atomic_json(artifact_path(root, "findings", finding_id) / "manifest.json", finding)
        for identity in identities:
            study = artifact_path(root, "tournaments", identity)
            atomic_json(study / "analyses" / "generator-pair.json", report)
            atomic_bytes(study / "analyses" / "preregistration.json", plan_path.read_bytes())
            for name in names:
                atomic_bytes(
                    study / "analyses" / "source" / name, (directory / "source" / name).read_bytes()
                )
            publish("EXPORTING", tournament_id=identity)
            path = output.parent / (identity + ".tar.gz")
            exported = export_tournament(root, identity, path)
            next(j for j in state["jobs"] if j["tournament_id"] == identity).update(
                bundle=exported, payloads_verified=verify_bundle(path)
            )
        unchanged()
        atomic_json(output, {"analysis": report, "campaign": state})
        publish("VERIFIED", finding_id=finding_id, output=str(output))
        return state
    except Exception as error:
        publish("FAILED", error=str(error))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gate-unit", required=True)
    parser.add_argument("--gate-log", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.plan, args.output, args.gate_unit, args.gate_log)
