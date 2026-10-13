"""Compare captured old/current workers on an already-opened financial workload."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from midas.arena.datasets import research_hash
from midas.arena.jobs import artifact_usage

CHILD = """
import json,sys
from pathlib import Path
from midas.arena.jobs import JobSpec,create,run
from midas.arena.unwind import UnwindStudySpec
root=Path(sys.argv[1])
spec=JobSpec(kind='unwind',unwind=UnwindStudySpec.model_validate(json.loads(sys.argv[2])),max_wall_seconds=1200)
job=create(root,spec,launch=False)
run(root,job['job_id'])
record=json.loads((root/'jobs'/job['job_id']/'job.json').read_text())
(root/'BENCHMARK_JOB.json').write_text(json.dumps(record))
raise SystemExit(record['exit_status'])
"""


def benchmark(root: Path, baseline_job: str, reference_id: str, output: Path) -> dict:
    if output.exists():
        raise ValueError("Refuse to overwrite a worker benchmark")
    source = root / "jobs" / baseline_job / "source" / "packages"
    if not (source / "midas/arena/jobs.py").is_file():
        raise ValueError("Captured baseline source is missing")
    baseline = json.loads((source.parent.parent / "job.json").read_text())
    capture = json.loads((source.parent.parent / "source-manifest.json").read_text())
    if baseline["state"] != "COMPLETED" or baseline["exit_status"] != 0:
        raise ValueError("Baseline worker did not complete")
    if capture["source_hash"] != baseline["submitted_source_hash"]:
        raise ValueError("Captured baseline identity differs from its job")
    for relative, digest in capture["files"].items():
        path = source.parent / relative
        if not path.resolve().is_relative_to(source.parent.resolve()):
            raise ValueError("Captured path escapes source root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Captured baseline source changed")
    original = root / "unwinds" / reference_id
    manifest = json.loads((original / "manifest.json").read_text())
    reference = json.loads((original / "rows.json").read_text())
    expected = {row["id"]: (row["result_hash"], row["journal_hash"]) for row in reference}
    results = []
    initial = artifact_usage(root)
    for label, packages in (
        ("captured_full_scan", source),
        ("event_index", Path.cwd() / "packages"),
    ):
        with tempfile.TemporaryDirectory(prefix="midas-guard-benchmark-") as temporary:
            working = Path(temporary)
            # Copies prevent benchmark writes, chmod or inode sharing from
            # changing any original artifact. Ballast is outside study catalogs.
            shutil.copytree(root, working / "ballast", symlinks=True)
            if artifact_usage(working / "ballast") != initial:
                raise ValueError("Archive changed while preparing matched ballast")
            environment = {
                **os.environ,
                "PYTHONPATH": str(packages),
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "CUDA_VISIBLE_DEVICES": "",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            began = time.monotonic()
            with (working / "worker.log").open("w") as stream:
                process = subprocess.run(
                    [
                        "nice",
                        "-n",
                        "10",
                        "taskset",
                        "-c",
                        "0",
                        sys.executable,
                        "-B",
                        "-c",
                        CHILD,
                        str(working),
                        json.dumps(manifest["configuration"]),
                    ],
                    env=environment,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=1250,
                )
            if process.returncode:
                raise RuntimeError((working / "worker.log").read_text()[-3000:])
            job = json.loads((working / "BENCHMARK_JOB.json").read_text())
            expected_source = (
                capture["source_hash"] if label == "captured_full_scan" else research_hash()
            )
            if job["submitted_source_hash"] != expected_source:
                raise ValueError("Worker imported an unexpected source tree")
            identity = job["result"]["unwind_id"]
            actual = json.loads((working / "unwinds" / identity / "rows.json").read_text())
            if {row["id"]: (row["result_hash"], row["journal_hash"]) for row in actual} != expected:
                raise ValueError("Worker optimization changed financial or journal results")
            results.append(
                {
                    "worker": label,
                    "wall_seconds": time.monotonic() - began,
                    "worker_elapsed_seconds": job["elapsed_seconds"],
                    "runtime_profile": job["runtime_profile"],
                    "artifact_guard": job.get("artifact_guard"),
                    "source_hash": job["submitted_source_hash"],
                    "identical_variants": len(actual),
                }
            )
    if artifact_usage(root) != initial:
        raise ValueError("Original archive changed during the benchmark")
    report = {
        "purpose": "PERFORMANCE_REPLAY_OF_OPENED_WORKLOAD",
        "reference_unwind": reference_id,
        "ballast_bytes": initial[0],
        "ballast_files": initial[1],
        "results": results,
        "limitations": [
            "One sequential old/new pair on this host; cache/order and load effects remain.",
            "No new independent economic evidence, training, selection or promotion.",
            "All financial/journal hashes match the original opened cohort.",
            "Temporary copied workspaces removed; original research artifacts untouched.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--baseline-job", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(benchmark(args.root, args.baseline_job, args.reference, args.output), indent=2)
    )
