"""Gate one backed-up replay migration, verify restoration, then check API reads."""

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, read_replay, sha256
from midas.arena.datasets import research_hash
from midas.arena.jobs import artifact_usage
from midas.economics.attestation import digest

from scripts.finalize_joint_cost_study import verify_bundle
from scripts.pack_replays import pack, prune, restore
from scripts.run_generator_audit import gate_result


def run(root: Path, plan_path: Path, gate_unit: str, gate_log: Path, output: Path) -> dict:
    plan = json.loads(plan_path.read_text())
    if research_hash() != plan["source_hash"]:
        raise ValueError("Preregistered source changed")
    state_path = root / "packing-pilots" / plan["identity"] / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing pilot requires inspection; refuse blind duplicate execution")
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "source_hash": plan["source_hash"],
        "plan_sha256": sha256(plan_path),
        "tool_hashes": {},
    }
    tools = Path(__file__).resolve().parent
    names = (
        "run_replay_packing_pilot.py",
        "pack_replays.py",
        "run_generator_audit.py",
        "finalize_joint_cost_study.py",
    )
    for name in names:
        atomic_bytes(state_path.parent / "source" / name, (tools / name).read_bytes())
        state["tool_hashes"][name] = sha256(tools / name)
    began = time.monotonic()

    def publish(phase, **details):
        state.update(
            phase=phase, updated_at=time.time(), elapsed_seconds=time.monotonic() - began, **details
        )
        atomic_json(state_path, state)
        print(json.dumps({"phase": phase, **details}), flush=True)

    def unchanged():
        if research_hash() != plan["source_hash"] or sha256(plan_path) != state["plan_sha256"]:
            raise ValueError("Frozen source or plan changed")
        if any(sha256(tools / name) != value for name, value in state["tool_hashes"].items()):
            raise ValueError("Captured migration tool changed")

    try:
        publish("WAITING_GATE", unit=gate_unit)
        while True:
            unchanged()
            gate = gate_result(gate_unit, gate_log)
            if gate is not None:
                break
            if time.monotonic() - began > 1200:
                raise TimeoutError("Gate observation deadline reached; inspect original unit")
            time.sleep(5)
        publish("VERIFYING_BACKUP", gate=gate)
        backup = Path(plan["backup"])
        if sha256(backup) != plan["backup_sha256"]:
            raise ValueError("Scientific backup changed")
        state["backup_payloads_verified"] = verify_bundle(backup)
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=90
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                health = json.load(
                    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=3)
                )
                if health["status"] == "READY":
                    break
            except (urllib.error.URLError, TimeoutError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("Original API did not become READY")
            time.sleep(1)
        unchanged()
        study = artifact_path(root, plan["kind"], plan["identity"])
        rows = json.loads((study / "rows.json").read_text())
        before = artifact_usage(root)
        publish("PREPARING_STORE", health=health)
        packing = pack(root, plan["kind"], plan["identity"])
        publish("VERIFYING_RESTORATION", replays=packing["replays"])
        with tempfile.TemporaryDirectory(prefix="midas-packing-proof-") as temporary:
            directory = Path(temporary)
            restore(study / "replays", directory / "restored")
            packed_only = directory / "packed-only"
            packed_only.mkdir()
            os.link(study / "replays/replays.sqlite", packed_only / "replays.sqlite")
            for filename, record in packing["files"].items():
                if sha256(directory / "restored" / filename) != record["sha256"]:
                    raise ValueError("Restored original bytes differ")
                name = record["logical_name"]
                if read_replay(packed_only / name) != read_replay(study / "replays" / name):
                    raise ValueError("Packed-only reader differs from original loose evidence")
        unchanged()
        publish("PRUNING_VERIFIED_LOOSE_FILES")
        packing = prune(root, plan["kind"], plan["identity"])
        publish("VERIFYING_FINAL_READS")
        for row in rows:
            replay = read_replay(study / "replays" / (row["id"] + ".json"))
            result = replay["result"]
            core = {
                k: v
                for k, v in result.items()
                if k not in {"result_hash", "journal_hash", "journal", "runtime"}
            }
            if (
                replay["row"] != row
                or digest(core) != row["result_hash"]
                or digest(result["journal"]) != result["journal_hash"]
            ):
                raise ValueError("Packed final financial/journal evidence differs")
        samples = []
        for policy in sorted({r["policy"] for r in rows}):
            row = min(
                (r for r in rows if r["policy"] == policy),
                key=lambda r: float(r["metrics"]["net_simulated_pnl"]),
            )
            url = (
                f"http://127.0.0.1:8000/api/arena/tournaments/{plan['identity']}/replay/{row['id']}"
            )
            replay = json.load(urllib.request.urlopen(url, timeout=15))
            if replay["result"]["result_hash"] != row["result_hash"]:
                raise ValueError("Deployed API packed replay differs")
            samples.append(row["id"])
        after = artifact_usage(root)
        if after[0] >= 1024**3:
            raise ValueError("Arena cap exceeded; evidence remains preserved")
        report = {
            "phase": "VERIFIED",
            "identity": plan["identity"],
            "packing": packing,
            "before_usage": before,
            "after_usage": after,
            "financial_replays_verified": len(rows),
            "api_replays_verified": samples,
            "backup_payloads_verified": state["backup_payloads_verified"],
            "limitations": [
                "Storage representation changed only; decoded results and original restored bytes verified.",
                "Older captured readers require restored loose files; kernel and storage caps unchanged.",
            ],
        }
        atomic_json(output, report)
        publish("VERIFIED", report=str(output), before_usage=before, after_usage=after)
        return report
    except Exception as error:
        publish("FAILED", error=str(error))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--gate-unit", required=True)
    parser.add_argument("--gate-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.plan, args.gate_unit, args.gate_log, args.output)
