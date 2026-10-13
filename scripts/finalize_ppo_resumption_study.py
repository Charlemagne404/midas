"""Finish evidence export after a terminal study; never admit or retrain jobs."""

import argparse
import json
import time
from pathlib import Path

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256

from scripts.arena_bundle import export_tournament
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.verify_ppo_resumption_study import verify


def finalize(root: Path, plan_path: Path, output: Path) -> dict:
    directory = root / "ppo-resumption-studies/study-573071"
    state_path = directory / "post-study-state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing finalization requires inspection; no duplicate export")
    plan = json.loads(plan_path.read_text())
    original = json.loads((directory / "state.json").read_text())
    if original["phase"] not in {"FAILED", "VERIFIED"} or len(original["jobs"]) != 3:
        raise ValueError("Original study must be terminal with exactly three stages")
    jobs = []
    for item in original["jobs"]:
        record = json.loads((root / "jobs" / item["job_id"] / "job.json").read_text())
        if (
            record["state"] != "COMPLETED"
            or record["exit_status"] != 0
            or record["submitted_source_hash"] != plan["source_hash"]
        ):
            raise ValueError("Original native stage is incomplete or differs")
        jobs.append(record)
    parent, child, tournament = (
        jobs[0]["result"]["model_id"],
        jobs[1]["result"]["model_id"],
        jobs[2]["result"]["tournament_id"],
    )
    state = {
        "state": "VERIFYING",
        "created_at": time.time(),
        "original_coordinator_phase": original["phase"],
        "original_error": original.get("error"),
        "tool_hashes": {},
    }
    for name in (
        "finalize_ppo_resumption_study.py",
        "arena_bundle.py",
        "verify_ppo_resumption_study.py",
    ):
        path = Path(__file__).parent / name
        state["tool_hashes"][name] = sha256(path)
        atomic_bytes(directory / "post-study-source" / name, path.read_bytes())
    atomic_json(state_path, state)
    try:
        report = verify(root, plan, parent, child, tournament)
        before = json.loads((directory / "parent-files-before-continuation.json").read_text())
        after = json.loads((directory / "parent-files-after-continuation.json").read_text())
        if before != after:
            raise ValueError("Original parent preservation evidence differs")
        report["parent_file_hashes_unchanged_during_continuation"] = True
        report["native_jobs"] = original["jobs"]
        analysis = root / "tournaments" / tournament / "analyses/ppo-resumption"
        for path in directory.rglob("*"):
            if path.is_file() and path.name != "post-study-state.json":
                atomic_bytes(analysis / path.relative_to(directory), path.read_bytes())
        atomic_json(analysis / "independent-verification.json", report)
        exported = export_tournament(
            root, tournament, Path("data/exports/ppo-resumption-573071") / (tournament + ".tar.gz")
        )
        report["export"] = exported
        report["export_payloads_verified"] = verify_bundle(Path(exported["path"]))
        report["finalization"] = {
            "original_coordinator_phase": original["phase"],
            "original_error": original.get("error"),
            "corrected_export_tool_sha256": state["tool_hashes"]["arena_bundle.py"],
            "new_training_or_evaluation_jobs": 0,
        }
        atomic_json(output, report)
        state.update(state="VERIFIED", completed_at=time.time(), report=str(output))
        atomic_json(state_path, state)
        print(
            json.dumps(
                {
                    "state": "VERIFIED",
                    "report": str(output),
                    "payloads": report["export_payloads_verified"],
                }
            ),
            flush=True,
        )
        return report
    except BaseException as error:
        state.update(state="FAILED", error=f"{type(error).__name__}: {error}")
        atomic_json(state_path, state)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.root, args.plan, args.output)
