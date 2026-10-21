import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.prepare_capacity_interface_release import prepare


def test_interface_launcher_uses_shared_admission_and_pinned_worker(tmp_path):
    release = tmp_path / "release"
    prepare(release)
    repository_route = Path(__file__).resolve().parents[1] / "apps/api/reality.py"
    assert (release / "apps/api/reality.py").read_bytes() == repository_route.read_bytes()
    site_packages = next(p for p in sys.path if p.endswith("site-packages"))
    env = {
        **os.environ,
        "PYTHONPATH": f"{release / 'packages'}:{release}:{site_packages}",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    program = r"""
import json, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
from midas.arena import admission, jobs
from midas.arena.datasets import DatasetSpec
root = Path(sys.argv[1])
admission.global_lock_path = lambda: root / "test-global.lock"
snapshot = {"active_job_ids": [], "available_memory_bytes": 3 * 1024**3,
            "disk_free_bytes": 20 * 1024**3, "cpu_psi": {"some": 0},
            "available_cpu_count": 6, "host_load_avg1": 1.0,
            "memory_psi": {"some": 0, "full": 0}, "io_psi": {"some": 0}}
admission.resource_snapshot = lambda _: snapshot
spec = jobs.JobSpec(kind="dataset", dataset=DatasetSpec(episodes=30))
calls = []
runner = subprocess.run
jobs.subprocess.run = lambda command, **kwargs: (calls.append(command) or SimpleNamespace())
try:
    try:
        jobs.create(root / "denied", spec)
    except admission.ResourceAdmissionDenied:
        pass
    else:
        raise AssertionError("Legacy interface bypassed memory admission")
    assert not calls and not list(root.glob("denied/jobs/*/job.json"))
    snapshot["available_memory_bytes"] = 8 * 1024**3
    record = jobs.create(root / "allowed", spec, admission_key="once")
    assert jobs.create(root / "allowed", spec, admission_key="once") == record
    assert len(calls) == 1
    command = calls[0]
    assert "--property=MemorySwapMax=0" in command and "-S" in command
    assert "--property=CPUWeight=10" in command
    assert any(str(Path(jobs.__file__).parents[3] / "packages") in p
               for p in command if p.startswith("--setenv=PYTHONPATH="))
    assert record["budget"]["minimum_available_memory_mb"] == 6144
finally:
    jobs.subprocess.run = runner
# Exercise the actual disposable worker using the emitted interpreter/import flags.
result = runner([sys.executable, "-S", "-m", "midas.arena.jobs", "--root",
                 str(root / "allowed"), "--job", record["job_id"]],
                capture_output=True, text=True, timeout=45)
final = json.loads((root / "allowed/jobs" / record["job_id"] / "job.json").read_text())
assert result.returncode == 0, result.stdout + result.stderr
assert final["state"] == "COMPLETED", final
print(json.dumps({"state": final["state"], "source": jobs.__file__}))
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", program, str(tmp_path / "jobs")],
        env=env,
        cwd=release,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["state"] == "COMPLETED"
