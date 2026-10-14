"""Reexecute completed plan policies with their worker's captured package source."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from midas.arena.artifacts import artifact_path, sha256


def verify(root: Path, identity: str) -> dict:
    root = root.absolute()
    plan = json.loads((artifact_path(root, "plans", identity) / "manifest.json").read_text())
    if plan["state"] != "COMPLETED" or not plan.get("owner_job_id"):
        raise ValueError("A completed native plan with captured owner is required")
    job_path = artifact_path(root, "jobs", plan["owner_job_id"])
    job = json.loads((job_path / "job.json").read_text())
    source = json.loads((job_path / "source-manifest.json").read_text())
    expected = plan["frozen"]["source_hash"]
    if (
        job["state"] != "COMPLETED"
        or job["exit_status"] != 0
        or job["configuration"]["plan_id"] != identity
        or source["source_hash"] != expected
        or job["submitted_source_hash"] != expected
        or not source["files"]
    ):
        raise ValueError("Completed native owner/source differs from plan")
    for relative, checksum in source["files"].items():
        name = Path(relative)
        if (
            name.is_absolute()
            or ".." in name.parts
            or sha256(job_path / "source" / name) != checksum
        ):
            raise ValueError("Captured package source changed")
    director = json.loads(
        (artifact_path(root, "directors", plan["director_id"]) / "manifest.json").read_text()
    )
    if director["state"] != "COMPLETED" or director["source_hash"] != expected:
        raise ValueError("Completed Director source differs")
    requests = []
    for step in director["steps"][1:]:
        tournament = step["artifact"]["identity"]
        directory = artifact_path(root, "tournaments", tournament)
        manifest = json.loads((directory / "manifest.json").read_text())
        if (
            manifest["source_hash"] != expected
            or sha256(directory / "rows.json") != manifest["rows_sha256"]
        ):
            raise ValueError("Tournament source or rows changed")
        rows = json.loads((directory / "rows.json").read_text())
        for policy in sorted({r["policy"] for r in rows}):
            executions = (
                ("optimistic", "standard", "conservative")
                if policy.startswith("model-")
                else ("standard",)
            )
            for execution in executions:
                eligible = [
                    r for r in rows if r["policy"] == policy and r["execution_model"] == execution
                ]
                # Prefer a nonzero outcome to inspect active behavior; retain zero
                # outcomes when the frozen policy abstains throughout this slice.
                row = min(
                    eligible,
                    key=lambda r: (-abs(float(r["metrics"]["net_simulated_pnl"])), r["id"]),
                )
                requests.append(
                    {
                        "tournament_id": tournament,
                        "row_id": row["id"],
                        "policy": policy,
                        "execution_model": execution,
                    }
                )
    with tempfile.TemporaryDirectory(prefix="midas-planning-inference-") as temporary:
        workspace = Path(temporary)
        tools = workspace / "scripts"
        tools.mkdir()
        producer = Path(__file__).parent / "reproduce_policy_inference.py"
        (tools / producer.name).write_bytes(producer.read_bytes())
        request_path = workspace / "requests.json"
        request_path.write_text(json.dumps(requests))
        output = workspace / "result.json"
        code = """
import json,sys
from pathlib import Path
from scripts.reproduce_policy_inference import reproduce
requests=json.loads(Path(sys.argv[2]).read_text())
reports=[dict(request, proof=reproduce(Path(sys.argv[1]),request['tournament_id'],request['row_id'])) for request in requests]
Path(sys.argv[3]).write_text(json.dumps(reports))
"""
        environment = dict(
            os.environ,
            PYTHONPATH=str(job_path / "source/packages"),
            PYTHONDONTWRITEBYTECODE="1",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            CUDA_VISIBLE_DEVICES="",
        )
        subprocess.run(
            [sys.executable, "-B", "-c", code, str(root), str(request_path), str(output)],
            cwd=workspace,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
        reports = json.loads(output.read_text())
    if not reports or any(
        not r["proof"]["verified"] or r["proof"]["source_hash"] != expected for r in reports
    ):
        raise ValueError("Captured inference did not reproduce")
    return {
        "plan_id": identity,
        "owner_job_id": plan["owner_job_id"],
        "source_hash": expected,
        "captured_package_files_verified": len(source["files"]),
        "inference_rows_verified": len(reports),
        "reports": reports,
        "orchestrator_sha256": sha256(Path(__file__)),
        "inference_producer_sha256": sha256(producer),
        "scope": "Selected archived decisions and accounting reproduced under captured worker packages; no new evaluation cohort, fitting, promotion or profitability evidence.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"plan_id": args.identity, "inference_rows_verified": report["inference_rows_verified"]}
        )
    )
