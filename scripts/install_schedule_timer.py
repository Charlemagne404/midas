"""Install the bounded user dispatcher service/timer; no existing Midas units changed."""

import json
import subprocess
from pathlib import Path


def unit_contents(repository: Path) -> dict[str, str]:
    python = repository / ".venv/bin/python"
    root = repository / "data/arena"

    def argument(path):
        return json.dumps(str(path).replace("%", "%%"))

    service = f"""# Managed by Midas finite research scheduling
[Unit]
Description=Midas finite research schedule dispatcher

[Service]
Type=oneshot
WorkingDirectory={str(repository).replace("%", "%%")}
ExecStart={argument(python)} -B -m scripts.dispatch_schedules --root {argument(root)}
CPUQuota=100%
MemoryMax=512M
Nice=10
TimeoutStartSec=60
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=OMP_NUM_THREADS=1
Environment=MKL_NUM_THREADS=1
Environment=OPENBLAS_NUM_THREADS=1
Environment=CUDA_VISIBLE_DEVICES=
"""
    timer = """# Managed by Midas finite research scheduling
[Unit]
Description=Poll bounded Midas research schedules

[Timer]
OnCalendar=minutely
Persistent=true
RandomizedDelaySec=5
AccuracySec=5
Unit=midas-arena-scheduler.service

[Install]
WantedBy=timers.target
"""
    return {"midas-arena-scheduler.service": service, "midas-arena-scheduler.timer": timer}


def install(repository: Path) -> dict:
    units = Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    for name, payload in unit_contents(repository).items():
        path = units / name
        if path.exists() and path.read_text() != payload:
            raise ValueError("Existing scheduler unit differs; inspect before replacing it")
        if not path.exists():
            path.write_text(payload)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=15)
    subprocess.run(
        [
            "systemd-analyze",
            "--user",
            "verify",
            *[str(units / name) for name in unit_contents(repository)],
        ],
        check=True,
        timeout=15,
    )
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", "midas-arena-scheduler.timer"],
        check=True,
        timeout=15,
    )
    subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", "midas-arena-scheduler.timer"],
        check=True,
        timeout=15,
    )
    python = repository / ".venv/bin/python"
    root = repository / "data/arena"
    return {
        "timer": "midas-arena-scheduler.timer",
        "service": "midas-arena-scheduler.service",
        "python": str(python),
        "root": str(root),
        "polling": "minutely; finite plans only",
        "stop": "systemctl --user disable --now midas-arena-scheduler.timer",
    }


if __name__ == "__main__":
    repository = Path(__file__).resolve().parents[1]
    print(json.dumps(install(repository), indent=2))
