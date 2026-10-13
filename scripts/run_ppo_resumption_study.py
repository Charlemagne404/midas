"""Finite source-bound native PPO training, continuation and independent challenge."""

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import DatasetSpec, research_hash
from midas.arena.jobs import JobSpec, artifact_usage, create, inspect
from midas.arena.rl import RLSpec
from midas.arena.tournaments import TournamentSpec

from scripts.arena_bundle import export_tournament
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.run_generator_audit import gate_result
from scripts.verify_ppo_resumption_study import verify


def run(root: Path, plan_path: Path, output: Path):
    plan = json.loads(plan_path.read_text())
    directory = root / "ppo-resumption-studies" / "study-573071"
    state_path = directory / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing PPO study requires inspection; no duplicate execution")
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "jobs": [],
        "plan_sha256": sha256(plan_path),
        "tool_hashes": plan["tool_hashes"],
    }
    for name, expected in plan["tool_hashes"].items():
        source = Path(__file__).parent / name
        if sha256(source) != expected:
            raise ValueError("Declared producer source changed")
        atomic_bytes(directory / "source" / name, source.read_bytes())
    atomic_bytes(directory / "preregistration.json", plan_path.read_bytes())
    began = time.monotonic()

    def publish(phase, **details):
        state.update(phase=phase, updated_at=time.time(), **details)
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    def unchanged():
        if research_hash() != plan["source_hash"] or sha256(plan_path) != state["plan_sha256"]:
            raise ValueError("Frozen PPO study source or plan changed")
        for name, expected in state["tool_hashes"].items():
            if (
                sha256(Path(__file__).parent / name) != expected
                or sha256(directory / "source" / name) != expected
            ):
                raise ValueError("Captured PPO study producer changed")
        old = root / "models" / plan["old_ppo_control"] / "policy.zip"
        if sha256(old) != plan["old_ppo_sha256"]:
            raise ValueError("Frozen old PPO control changed")

    def execute(spec, index):
        unchanged()
        if artifact_usage(root)[0] >= 1024**3 - 64 * 1024**2:
            raise ValueError("Insufficient Arena headroom for declared study")
        publish("ADMITTING", stage=index)
        job = create(root, spec, admission_key=f"ppo-resumption-573071-{index}")
        state["jobs"].append({"job_id": job["job_id"], "unit": job["unit"], "stage": index})
        publish("RESEARCHING", job_id=job["job_id"])
        deadline = time.monotonic() + spec.max_wall_seconds + 60
        while True:
            job = inspect(root, job["job_id"])
            if job["state"] == "COMPLETED":
                break
            if job["state"] not in {"RUNNING", "QUEUED"}:
                raise ValueError("PPO research failed: " + str(job.get("error")))
            if time.monotonic() > deadline:
                raise TimeoutError("Native job observation budget reached; inspect original job")
            time.sleep(3)
        unchanged()
        if (
            job["configuration"] != spec.model_dump(mode="json")
            or job["submitted_source_hash"] != plan["source_hash"]
            or job["exit_status"] != 0
        ):
            raise ValueError("Native worker differs from declared stage")
        source = json.loads((root / "jobs" / job["job_id"] / "source-manifest.json").read_text())
        if source["source_hash"] != plan["source_hash"] or not source["files"]:
            raise ValueError("Native captured source identity differs")
        for relative, expected in source["files"].items():
            name = Path(relative)
            if (
                name.is_absolute()
                or ".." in name.parts
                or sha256(root / "jobs" / job["job_id"] / "source" / name) != expected
            ):
                raise ValueError("Native captured package bytes differ")
        state["jobs"][-1]["result"] = job["result"]
        publish("STAGE_COMPLETED", stage=index, result=job["result"])
        return job["result"]

    try:
        unchanged()
        publish("WAITING_GATE")
        while gate_result(plan["full_gate_unit"], Path(plan["full_gate_log"])) is None:
            unchanged()
            if time.monotonic() - began > 1800:
                raise TimeoutError("Full-gate wait budget exhausted")
            time.sleep(5)
        publish("DEPLOYING_API")
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=45
        )
        for _ in range(30):
            try:
                health = json.load(
                    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
                )
                if health["status"] == "READY":
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise ValueError("API readiness not established")
        parent_spec = RLSpec.model_validate(plan["parent_training"])
        parent_id = execute(JobSpec(kind="rl", rl=parent_spec, max_wall_seconds=1800), "parent")[
            "model_id"
        ]
        parent_directory = root / "models" / parent_id
        before = {p.name: sha256(p) for p in parent_directory.iterdir() if p.is_file()}
        atomic_json(directory / "parent-files-before-continuation.json", before)
        child_spec = parent_spec.model_copy(
            update={"resume_from": parent_id, "timesteps": plan["child_total_timesteps"]}
        )
        child_id = execute(JobSpec(kind="rl", rl=child_spec, max_wall_seconds=1800), "child")[
            "model_id"
        ]
        after = {p.name: sha256(p) for p in parent_directory.iterdir() if p.is_file()}
        if before != after:
            raise ValueError("Continuation changed parent evidence")
        atomic_json(directory / "parent-files-after-continuation.json", after)
        spec = TournamentSpec(
            dataset_id=parent_spec.dataset_id,
            model_ids=(parent_id, child_id, plan["old_ppo_control"]),
            challenge=DatasetSpec.model_validate(plan["challenge"]),
            max_episodes=plan["evaluation_source_groups"],
            minimum_champion_episodes=plan["minimum_champion_episodes"],
        )
        tournament_id = execute(
            JobSpec(kind="tournament", tournament=spec, max_wall_seconds=1800), "challenge"
        )["tournament_id"]
        unchanged()
        publish("VERIFYING", tournament_id=tournament_id)
        report = verify(root, plan, parent_id, child_id, tournament_id)
        report["parent_file_hashes_unchanged_during_continuation"] = before == after
        atomic_json(directory / "verification.json", report)
        finding = {
            "finding_id": "finding-ppo-resumption-573071",
            "title": "PPO continuation and fresh matched policy comparison",
            "created_at": time.time(),
            "tournament_id": tournament_id,
            "research_question": plan["purpose"],
            "outcome": report,
            "interpretation": "Optimizer-preserving continuation completed. Fresh paired results and uncertainty determine policy evidence; no model promoted or retuned.",
            "caveats": report["limitations"],
            "next_experiment": "Preregister repeated RL seeds and wider generator shifts; keep these opened challenge groups out of selection.",
        }
        atomic_json(
            artifact_path(root, "findings", finding["finding_id"]) / "manifest.json", finding
        )
        export_path = Path("data/exports/ppo-resumption-573071") / (tournament_id + ".tar.gz")
        exported = export_tournament(root, tournament_id, export_path)
        report["export"] = exported
        report["export_payloads_verified"] = verify_bundle(export_path)
        report["native_jobs"] = state["jobs"]
        atomic_json(output, report)
        publish("VERIFIED", report=str(output))
        return report
    except BaseException as error:
        publish("FAILED", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.plan, args.output)
