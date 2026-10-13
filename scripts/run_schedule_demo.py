"""Gate timer deployment and verify real finite admissions, API restart and expiry alerts."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256
from midas.arena.datasets import research_hash
from midas.arena.scheduling import ScheduleSpec, control, create

from scripts.install_schedule_timer import install
from scripts.run_generator_audit import gate_result
from scripts.verify_observation_windows import verify


def ready_api() -> dict:
    deadline = time.monotonic() + 60
    while True:
        try:
            health = json.load(
                urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=3)
            )
            if health["status"] == "READY":
                return health
        except (urllib.error.URLError, TimeoutError):
            pass
        if time.monotonic() > deadline:
            raise TimeoutError("Original API did not return READY")
        time.sleep(1)


def run(root: Path, plan_path: Path, gate_unit: str, gate_log: Path, output: Path) -> dict:
    plan = json.loads(plan_path.read_text())
    specification = ScheduleSpec.model_validate(plan["schedule"])
    expiry_spec = ScheduleSpec.model_validate(plan["expiry_schedule"])
    if research_hash() != plan["source_hash"]:
        raise ValueError("Preregistered source changed")
    state_path = root / "schedule-demonstrations" / "finite-demo-1" / "state.json"
    if state_path.exists() or output.exists():
        raise ValueError("Existing demonstration requires inspection; no blind duplicate launch")
    state = {
        "phase": "WAITING_GATE",
        "created_at": time.time(),
        "source_hash": plan["source_hash"],
        "plan_sha256": sha256(plan_path),
        "tool_hashes": {},
    }
    tools = Path(__file__).resolve().parent
    names = (
        "run_schedule_demo.py",
        "install_schedule_timer.py",
        "dispatch_schedules.py",
        "run_generator_audit.py",
        "verify_observation_windows.py",
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
            raise ValueError("Package source or demo plan changed")
        if any(sha256(tools / name) != value for name, value in state["tool_hashes"].items()):
            raise ValueError("Captured producer tool changed")

    try:
        publish("WAITING_GATE", gate_unit=gate_unit)
        while True:
            unchanged()
            gate = gate_result(gate_unit, gate_log)
            if gate is not None:
                break
            if time.monotonic() - began > 1200:
                raise TimeoutError("Gate observation limit reached; inspect original process")
            time.sleep(5)
        publish("DEPLOYING", gate=gate)
        subprocess.run(
            ["systemctl", "--user", "restart", "midas-api.service"], check=True, timeout=90
        )
        health = ready_api()
        timer = install(Path(__file__).resolve().parents[1])
        publish("CREATING_PLANS", health=health, timer=timer)
        active = create(root, specification)
        state["schedule_id"] = active["schedule_id"]
        expiry = create(root, expiry_spec)
        state["expiry_schedule_id"] = expiry["schedule_id"]
        control(root, expiry["schedule_id"], "pause")
        paused_at = time.monotonic()
        restarted, resumed = False, False
        publish(
            "OBSERVING", schedule_id=active["schedule_id"], expiry_schedule_id=expiry["schedule_id"]
        )
        deadline = time.monotonic() + 900
        while True:
            unchanged()
            active = json.loads(
                (root / "schedules" / state["schedule_id"] / "manifest.json").read_text()
            )
            expiry = json.loads(
                (root / "schedules" / state["expiry_schedule_id"] / "manifest.json").read_text()
            )
            first_id = active["steps"][0]["job_id"]
            if first_id and not restarted:
                first = json.loads((root / "jobs" / first_id / "job.json").read_text())
                if first["state"] == "COMPLETED":
                    state["api_restart_started_at"] = time.time()
                    publish("RESTARTING_API_AFTER_FIRST_CHILD", job_id=first_id)
                    subprocess.run(
                        ["systemctl", "--user", "restart", "midas-api.service"],
                        check=True,
                        timeout=90,
                    )
                    ready_api()
                    state["api_restart_completed_at"] = time.time()
                    restarted = True
                    publish("OBSERVING", api_restart_verified=True)
            if not resumed and time.monotonic() - paused_at > 65:
                control(root, state["expiry_schedule_id"], "resume")
                resumed = True
            if active["state"] in {"FAILED", "STALE_SOURCE", "EXPIRED", "CANCELLED"}:
                raise ValueError("Demo schedule did not complete: " + active["state"])
            if active["state"] == "COMPLETED" and expiry["state"] == "EXPIRED":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(
                    "Demo observation deadline reached; inspect persisted plans and timer"
                )
            time.sleep(3)
        job_ids = [s["job_id"] for s in active["steps"]]
        if len(set(job_ids)) != 2 or not restarted:
            raise ValueError("Two unique child admissions and API restart were not demonstrated")
        jobs = [
            json.loads((root / "jobs" / identity / "job.json").read_text()) for identity in job_ids
        ]
        if (
            jobs[0]["completed_at"] > state["api_restart_started_at"]
            or jobs[1]["created_at"] < state["api_restart_completed_at"]
        ):
            raise ValueError(
                "API restart was not between completed first and admitted second child"
            )
        keys = {s["admission_key"] for s in active["steps"]}
        matching = [
            json.loads(p.read_text())
            for p in root.glob("jobs/*/job.json")
            if json.loads(p.read_text()).get("admission_key") in keys
        ]
        if len(matching) != 2 or any(j["state"] != "COMPLETED" for j in jobs):
            raise ValueError("Duplicate or incomplete scheduled children")
        observation_ids = [j["result"]["observation_id"] for j in jobs]
        if len(set(observation_ids)) != 1:
            raise ValueError("Same immutable recording/configuration did not reuse its dataset")
        checked = verify(root, observation_ids[0])
        alert_id = "alert-" + expiry["schedule_id"].removeprefix("schedule-")
        alert = json.loads((root / "alerts" / alert_id / "manifest.json").read_text())
        if any(s["job_id"] for s in expiry["steps"]):
            raise ValueError("Expired plan admitted a child")
        report = {
            "schedule": active,
            "expiry_schedule": expiry,
            "jobs": jobs,
            "observation_verification": checked,
            "alert": alert,
            "timer": timer,
            "api_restart_between_children": True,
            "limitations": [
                "Real bounded timer/child execution; no host reboot or multi-day elapsed run tested here.",
                "Same recording reused for operational verification; no new independent data, training or economic evidence.",
            ],
        }
        atomic_json(output, report)
        publish("VERIFIED", output=str(output), jobs=job_ids, observation_id=observation_ids[0])
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
