"""Finite gate-bound native migration and independently verified portable evidence."""

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, create, inspect

from scripts.arena_bundle import dataset_paths, write_bundle
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.run_generator_audit import gate_result
from scripts.verify_dataset_migration import canonical, verify


def run(root: Path, plan_path: Path, output: Path):
    plan = json.loads(plan_path.read_text())
    directory = root / "migration-pilots/schema-pilot-1"
    state_path = directory / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing migration pilot requires inspection; no duplicate admission")
    spec = JobSpec.model_validate(plan["configuration"])
    if spec.kind != "migration" or plan["scientific_samples_added"] or plan["models_trained"]:
        raise ValueError("Pilot must only migrate stored observations")
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "plan_sha256": sha256(plan_path),
        "tool_hashes": plan["tool_hashes"],
    }
    for name, expected in state["tool_hashes"].items():
        source = Path(__file__).parent / name
        if sha256(source) != expected:
            raise ValueError("Pilot producer differs")
        atomic_bytes(directory / "source" / name, source.read_bytes())
    atomic_bytes(directory / "preregistration.json", plan_path.read_bytes())
    started = time.monotonic()

    def publish(phase, **details):
        state.update(phase=phase, updated_at=time.time(), **details)
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    def unchanged():
        if research_hash() != plan["source_hash"] or sha256(plan_path) != state["plan_sha256"]:
            raise ValueError("Frozen migration source or plan changed")
        for name, expected in state["tool_hashes"].items():
            if (
                sha256(Path(__file__).parent / name) != expected
                or sha256(directory / "source" / name) != expected
            ):
                raise ValueError("Captured migration producer changed")
        source = root / "datasets" / spec.migration.source_dataset_id
        for name, expected in plan["source_file_hashes"].items():
            if sha256(source / name) != expected:
                raise ValueError("Frozen original dataset changed")

    try:
        unchanged()
        publish("WAITING_GATE")
        while gate_result(plan["full_gate_unit"], Path(plan["full_gate_log"])) is None:
            unchanged()
            if time.monotonic() - started > 1800:
                raise TimeoutError("Migration gate wait budget reached")
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
        unchanged()
        source = root / "datasets" / spec.migration.source_dataset_id
        before = {str(p.relative_to(source)): sha256(p) for p in source.rglob("*") if p.is_file()}
        atomic_json(directory / "source-files-before.json", before)
        job = create(root, spec, admission_key="dataset-migration-schema-pilot-1")
        publish("MIGRATING", job_id=job["job_id"], unit=job["unit"])
        deadline = time.monotonic() + spec.max_wall_seconds + 60
        while True:
            job = inspect(root, job["job_id"])
            if job["state"] == "COMPLETED":
                break
            if job["state"] not in {"QUEUED", "RUNNING"}:
                raise ValueError("Native migration failed: " + str(job.get("error")))
            if time.monotonic() > deadline:
                raise TimeoutError("Native migration observation deadline reached")
            time.sleep(2)
        unchanged()
        if (
            job["submitted_source_hash"] != plan["source_hash"]
            or job["configuration"] != spec.model_dump(mode="json")
            or job["exit_status"] != 0
        ):
            raise ValueError("Native migration worker differs")
        captured = json.loads((root / "jobs" / job["job_id"] / "source-manifest.json").read_text())
        if captured["source_hash"] != plan["source_hash"] or not captured["files"]:
            raise ValueError("Native migration captured source identity differs")
        for relative, expected in captured["files"].items():
            name = Path(relative)
            if (
                name.is_absolute()
                or ".." in name.parts
                or sha256(root / "jobs" / job["job_id"] / "source" / name) != expected
            ):
                raise ValueError("Native migration captured source payload differs")
        after = {str(p.relative_to(source)): sha256(p) for p in source.rglob("*") if p.is_file()}
        if before != after:
            raise ValueError("Original dataset files changed")
        atomic_json(directory / "source-files-after.json", after)
        identity = job["result"]["dataset_id"]
        publish("VERIFYING", dataset_id=identity)
        report = verify(root, identity, plan)
        report["all_source_files_unchanged"] = True
        report["job_id"] = job["job_id"]
        api_rows = json.load(
            urllib.request.urlopen(
                f"http://127.0.0.1:8000/api/arena/datasets/{identity}/rows?limit=25", timeout=15
            )
        )
        target = root / "datasets" / identity
        target_manifest = json.loads((target / "manifest.json").read_text())
        expected_rows = canonical(target / "rows.json", target_manifest)[:25]
        if api_rows["storage_version"] != "decision-storage-2" or api_rows["rows"] != expected_rows:
            raise ValueError("Actual API canonical rows differ")
        atomic_json(directory / "verification.json", report)
        paths = dataset_paths(root, identity)
        for model_id in plan["model_parameters"]:
            paths.update((root / "models" / model_id).glob("*.json"))
        paths.update((root / "jobs" / job["job_id"]).rglob("*"))
        paths.update(directory.rglob("*"))
        extras = {
            "TOOLS/verify_dataset_migration.py": Path(__file__).parent
            / "verify_dataset_migration.py"
        }
        export = write_bundle(
            root.resolve(),
            [p.resolve() for p in paths if p.is_file() and not p.is_symlink()],
            extras,
            "dataset_id",
            identity,
            Path("data/exports/dataset-migration-pilot") / (identity + ".tar.gz"),
        )
        report["export"] = export
        report["export_payloads_verified"] = verify_bundle(Path(export["path"]))
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
