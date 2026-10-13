"""Gate-bound exact-evidence cold retention pilot; never blindly restarts a pilot."""

import argparse
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from midas.arena.artifacts import atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import artifact_usage

from scripts.archive_replays import archive
from scripts.arena_bundle import export_tournament
from scripts.finalize_joint_cost_study import verify_bundle
from scripts.pack_replays import restore
from scripts.reproduce_archived_policy import reproduce
from scripts.verify_cold_retention import verify


def properties(unit):
    response = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "MainPID",
            "-p",
            "Result",
            "-p",
            "ExecMainStatus",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return dict(line.split("=", 1) for line in response.stdout.splitlines() if "=" in line)


def run(plan_path: Path, state_path: Path, output: Path, max_seconds=1800):
    if state_path.exists() or output.exists():
        raise ValueError("Existing pilot evidence requires inspection; refuse duplicate execution")
    plan = json.loads(plan_path.read_text())
    began = time.monotonic()
    state = {
        "state": "WAITING_GATE",
        "created_at": time.time(),
        "plan_sha256": sha256(plan_path),
        "producer_sha256": sha256(Path(__file__)),
    }

    def publish(phase, **details):
        state.update(state=phase, updated_at=time.time(), **details)
        atomic_json(state_path, state)
        print(json.dumps({"state": phase, **details}), flush=True)

    def sources():
        if research_hash() != plan["source_hash"] or sha256(plan_path) != state["plan_sha256"]:
            raise ValueError("Pilot research source or plan changed")
        for name, expected in plan["tools"].items():
            if sha256(Path(__file__).parent / name) != expected:
                raise ValueError("Pilot tool changed: " + name)

    try:
        sources()
        publish("WAITING_GATE")
        while True:
            gate = properties(plan["full_gate_unit"])
            if gate["ActiveState"] in {"inactive", "failed"}:
                if gate["Result"] != "success" or gate["ExecMainStatus"] != "0":
                    raise ValueError("Full gate failed; production evidence untouched")
                break
            if gate["ActiveState"] != "active" or not int(gate.get("MainPID", "0")):
                raise ValueError("Full gate lacks verified live process")
            if time.monotonic() - began > max_seconds:
                raise TimeoutError("Pilot gate wait exceeded budget")
            time.sleep(5)
        sources()
        log = Path("docs/PROMETHEUS_COLD_RETENTION_FULL_TESTS.log").read_text()
        if "passed" not in log or "failed" in log:
            raise ValueError("Full gate log does not establish passing tests")
        root = Path("data/arena").resolve()
        identity = plan["pilot_tournament"]
        backup = Path(plan["backup"])
        if sha256(backup) != plan["backup_expected_sha256"]:
            raise ValueError("Pilot backup checksum differs")
        backup_payloads = verify_bundle(backup)
        publish("DEPLOYING_READER", backup_payloads=backup_payloads)
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=45
        )
        for _attempt in range(30):
            try:
                health = json.load(
                    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
                )
                overview = json.load(
                    urllib.request.urlopen("http://127.0.0.1:8000/api/arena", timeout=10)
                )
                if health["status"] == "READY" and "cold_storage" in overview:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise ValueError("API reader readiness not established")
        sources()
        before = artifact_usage(root)
        publish("PREPARING")
        prepared = archive(root, "tournaments", identity)
        checked_before = verify(
            root, "tournaments", identity, backup, plan["backup_expected_sha256"]
        )
        if not checked_before["hot_copy_present"]:
            raise ValueError("Expected hot copy before controlled removal")
        publish("REMOVING_VERIFIED_HOT_DUPLICATE", prepared_verification=checked_before)
        sources()
        moved = archive(root, "tournaments", identity, prune=True)
        checked_after = verify(
            root, "tournaments", identity, backup, plan["backup_expected_sha256"]
        )
        study = root / "tournaments" / identity
        rows = json.loads((study / "rows.json").read_text())
        api_rows = []
        for policy in sorted({r["policy"] for r in rows}):
            row = next(r for r in rows if r["policy"] == policy)
            result = json.load(
                urllib.request.urlopen(
                    f"http://127.0.0.1:8000/api/arena/tournaments/{identity}/replay/{row['id']}",
                    timeout=15,
                )
            )
            if result["row"] != row:
                raise ValueError("Cold API replay row differs")
            api_rows.append(row["id"])
        publish("RESTORING_AND_REPRODUCING", verification=checked_after)
        with tempfile.TemporaryDirectory(prefix="midas-cold-pilot-") as temporary:
            restored_count = restore(study / "replays", Path(temporary))
        inference = []
        for model_id in json.loads((study / "manifest.json").read_text())["model_artifact_hashes"]:
            row = next(r for r in rows if r["policy"] == model_id)
            inference.append(reproduce(root, identity, row["id"]))
        publish("EXPORTING")
        bundle = Path("data/exports/cold-retention-pilot") / (identity + ".tar.gz")
        exported = export_tournament(root, identity, bundle)
        bundle_payloads = verify_bundle(bundle)
        after = artifact_usage(root)
        report = {
            "state": "VERIFIED",
            "prepared": prepared,
            "archived": moved,
            "before_hot_usage": before,
            "after_hot_usage": after,
            "original_backup_payloads": backup_payloads,
            "verification": checked_after,
            "api_replay_rows": api_rows,
            "restored_original_files": restored_count,
            "captured_source_inference": inference,
            "export": exported,
            "export_payloads": bundle_payloads,
            "limitations": [
                "Cold relocation frees active-tier budget, not total disk space.",
                "Browser inspection remains a separate gate; no new model or independent scientific sample.",
            ],
        }
        atomic_json(output, report)
        publish("VERIFIED", report=str(output))
        return report
    except BaseException as error:
        publish("FAILED", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.state, args.output)
