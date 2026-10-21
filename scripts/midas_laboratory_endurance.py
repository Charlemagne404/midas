#!/usr/bin/env python3
"""Run one bounded Laboratory evaluation from a small spawn-safe entry point.

The parent endurance harness imports Arena and monitoring code.  Keeping this
entry point small prevents ProcessPoolExecutor's spawn workers from importing
that much larger module before their per-worker address-space limit is applied.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
import traceback
from typing import Any

from midas.laboratory.campaigns import Campaigns, CampaignSpec


def write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def campaign_result(
    lab: Campaigns, record: dict[str, Any], lab_root: pathlib.Path
) -> dict[str, Any]:
    expected_runs = (
        int(record["spec"]["runs"])
        * len(record["spec"]["strategies"])
        * len(record["spec"]["models"])
    )
    if record["status"] != "COMPLETED":
        raise RuntimeError(
            f"Laboratory campaign did not complete: {record['status']} {record.get('error')}"
        )
    if record["completed"] != expected_runs or record["episodes_completed"] != 32:
        raise RuntimeError("Laboratory campaign did not commit all 32 isolated episodes")
    runs = lab.runs(str(record["id"]), 0, expected_runs)
    if len(runs) != expected_runs or len({item["id"] for item in runs}) != expected_runs:
        raise RuntimeError("Laboratory run identities are incomplete or duplicated")
    verified = lab.artifact(runs[0]["id"])
    if verified["result"]["result_hash"] != runs[0]["result"]["result_hash"]:
        raise RuntimeError("Laboratory artifact replay differs from the durable run record")
    return {
        "campaign_id": record["id"],
        "status": record["status"],
        "runs": record["completed"],
        "episodes": record["episodes_completed"],
        "passed": record["passed"],
        "failed": record["failed"],
        "events": record["events"],
        "elapsed_seconds": record["elapsed_seconds"],
        "runs_per_second": record["runs_per_second"],
        "code_revision": record["code_revision"],
        "code_hash": record["code_hash"],
        "verified_run_id": verified["run_id"],
        "verified_result_hash": verified["result"]["result_hash"],
        "campaign_root": str(lab_root),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=pathlib.Path)
    parser.add_argument("--progress", required=True, type=pathlib.Path)
    parser.add_argument("--result", required=True, type=pathlib.Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=int, default=360)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.root.is_symlink() or args.progress.is_symlink() or args.result.is_symlink():
        raise ValueError("Laboratory evidence paths must not be symlinks")
    lab_root = args.root.resolve()
    lab_root.mkdir(parents=True, exist_ok=True)
    if any(lab_root.iterdir()):
        raise ValueError("Laboratory evidence root must be empty")

    lab = Campaigns(lab_root, lab_root / "datasets")
    campaign_id: str | None = None
    try:
        record = lab.create(
            CampaignSpec(
                preset="Quick",
                runs=32,
                seed=args.seed,
                families=("calm", "thin", "deep", "one_sided"),
                strategies=("arbitrage", "conservative"),
                models=("standard",),
                workers=1,
                memory_mb=args.memory_mb,
                max_wall_seconds=300,
                max_disk_mb=128,
                retain_successes=3,
            )
        )
        campaign_id = str(record["id"])
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            record = lab.get(campaign_id)
            write_json(
                args.progress,
                {
                    "campaign_id": campaign_id,
                    "status": record["status"],
                    "completed": record["completed"],
                    "total": record["total"],
                    "episodes_completed": record["episodes_completed"],
                    "events": record["events"],
                    "elapsed_seconds": record["elapsed_seconds"],
                    "error": record.get("error"),
                },
            )
            if record["status"] not in {"READY", "RUNNING"}:
                break
            time.sleep(1)
        else:
            raise TimeoutError("Laboratory campaign exceeded its bounded supervisor timeout")

        record = lab.get(campaign_id)
        result = campaign_result(lab, record, lab_root)
        write_json(args.result, {"status": "COMPLETED", **result})
        return 0
    except BaseException as error:
        write_json(
            args.result,
            {
                "status": "FAILED",
                "campaign_id": campaign_id,
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            },
        )
        return 1
    finally:
        try:
            if campaign_id is not None:
                record = lab.get(campaign_id)
                if record["status"] in {"READY", "RUNNING"}:
                    lab.control(campaign_id, "pause")
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        thread = lab.threads.get(campaign_id)
                        if thread is None or not thread.is_alive():
                            break
                        time.sleep(1)
        finally:
            lab.close()


if __name__ == "__main__":
    raise SystemExit(main())
