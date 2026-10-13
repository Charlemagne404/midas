"""Execute and verify two fixed fresh cohorts after the worker equivalence gate."""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, artifact_usage, create

from scripts.arena_bundle import export_unwind
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.verify_unwind import verify


def validate(plan: dict, benchmark: dict) -> list[JobSpec]:
    specs = [JobSpec.model_validate(c) for c in plan["cohorts"]]
    if len(specs) != 2 or any(s.kind != "unwind" or s.unwind is None for s in specs):
        raise ValueError("Require exactly two fixed unwind cohorts")
    if plan["source_hash"] != research_hash():
        raise ValueError("Preregistered source changed")
    if plan["selection_or_retuning"] or plan["promotion"] or plan["models_trained"]:
        raise ValueError("Robustness campaign must not train, retune or promote")
    if specs[0].unwind is None or specs[1].unwind is None:
        raise ValueError("Missing unwind configuration")
    a, b = specs[0].unwind, specs[1].unwind
    if a.unwind != b.unwind or not (a.seed + a.episodes <= b.seed or b.seed + b.episodes <= a.seed):
        raise ValueError("Cohorts overlap or use different policies")
    results = benchmark["results"]
    if (
        benchmark["purpose"] != "PERFORMANCE_REPLAY_OF_OPENED_WORKLOAD"
        or benchmark["reference_unwind"] != plan["prior_unwind"]
        or [r["worker"] for r in results] != ["captured_full_scan", "event_index"]
        or any(r["identical_variants"] != 720 for r in results)
        or results[1]["source_hash"] != plan["source_hash"]
    ):
        raise ValueError("Worker equivalence gate differs from this campaign")
    return specs


def coverage(rows: list[dict]) -> dict:
    counts = defaultdict(lambda: {"requests": 0, "filled_variants": 0, "filled_groups": set()})
    for row in rows:
        entry = counts[row["policy"] + "/" + row["execution_model"]]
        entry["requests"] += row["intervention_requests"]
        if float(row["intervention_filled_shares"]) > 0:
            entry["filled_variants"] += 1
            entry["filled_groups"].add(row["base_episode_id"])
    return {k: {**v, "filled_groups": len(v["filled_groups"])} for k, v in counts.items()}


def run(root: Path, plan_path: Path, benchmark_path: Path, output: Path) -> dict:
    plan = json.loads(plan_path.read_text())
    specs = validate(plan, json.loads(benchmark_path.read_text()))
    directory = root / "unwind-campaigns" / "robustness-423071-453071"
    state_path = directory / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing campaign requires inspection; refuse duplicate admission")
    tools = Path(__file__).resolve().parent
    names = (
        "run_unwind_robustness.py",
        "verify_unwind.py",
        "arena_bundle.py",
        "finalize_joint_cost_study.py",
        "capture_public_series.py",
    )
    state = {
        "phase": "PREFLIGHT",
        "created_at": time.time(),
        "cohorts": [],
        "source_hash": plan["source_hash"],
        "plan_sha256": sha256(plan_path),
        "benchmark_sha256": sha256(benchmark_path),
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
            raise ValueError("Preregistered package or plan changed")
        for name, expected in state["tool_hashes"].items():
            if sha256(tools / name) != expected or sha256(directory / "source" / name) != expected:
                raise ValueError("Captured verification tool changed")

    try:
        for spec in specs:
            unchanged()
            if artifact_usage(root)[0] >= 1024**3 - 64 * 1024**2:
                raise RuntimeError("Insufficient headroom under unchanged Arena budget")
            publish("ADMITTING", seed=spec.unwind.seed)
            job = create(root, spec)
            entry = {"seed": spec.unwind.seed, "job_id": job["job_id"], "unit": job["unit"]}
            state["cohorts"].append(entry)
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
            unchanged()
            identity = job["result"]["unwind_id"]
            study = root / "unwinds" / identity
            manifest = json.loads((study / "manifest.json").read_text())
            if (
                manifest["configuration"] != spec.unwind.model_dump(mode="json")
                or manifest["source_hash"] != plan["source_hash"]
            ):
                raise ValueError("Produced study differs from preregistration")
            publish("VERIFYING", unwind_id=identity)
            checked = verify(root, identity)
            atomic_json(study / "verification.json", checked)
            atomic_bytes(study / "robustness-preregistration.json", plan_path.read_bytes())
            bundle_path = output.parent / (identity + ".tar.gz")
            publish("EXPORTING", unwind_id=identity)
            exported = export_unwind(root, identity, bundle_path)
            entry.update(
                unwind_id=identity,
                verification=checked,
                bundle=exported,
                payloads_verified=verify_bundle(bundle_path),
                coverage=coverage(json.loads((study / "rows.json").read_text())),
                paired_comparisons=manifest["paired_comparisons"],
                leaderboard=manifest["leaderboard"],
            )
            publish("COHORT_VERIFIED", unwind_id=identity)
        unchanged()
        atomic_json(output, {**state, "phase": "VERIFIED", "limitations": plan["limitations"]})
        publish("VERIFIED", output=str(output))
        return state
    except Exception as error:
        publish("FAILED", error=str(error))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.plan, args.benchmark, args.output)
