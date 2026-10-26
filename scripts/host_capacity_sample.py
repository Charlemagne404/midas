"""Low-frequency, read-only Linux host/cgroup sampling; no process attachment."""

import argparse
import json
import time
from pathlib import Path


def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except (OSError, PermissionError):
        return None


def snapshot() -> dict:
    proc = Path("/proc")
    host = {
        name: read(proc / name) for name in ("stat", "meminfo", "vmstat", "diskstats", "loadavg")
    }
    host["pressure"] = {k: read(proc / "pressure" / k) for k in ("cpu", "memory", "io")}
    processes = {}
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        stat = read(p / "stat")
        if stat:
            processes[p.name] = {k: read(p / k) for k in ("stat", "io", "cgroup")}
    groups = {}
    root = Path("/sys/fs/cgroup")
    # Discover active leaf groups from processes, including unrelated services.
    for value in processes.values():
        for line in (value["cgroup"] or "").splitlines():
            if line.startswith("0::"):
                group = line[3:]
                if group not in groups:
                    groups[group] = {
                        k: read(root / group.lstrip("/") / k)
                        for k in (
                            "cpu.stat",
                            "cpu.max",
                            "cpu.pressure",
                            "memory.current",
                            "memory.peak",
                            "memory.high",
                            "memory.max",
                            "memory.events",
                            "memory.stat",
                            "memory.swap.current",
                            "memory.pressure",
                            "io.stat",
                            "io.pressure",
                            "pids.current",
                        )
                    }
    return {
        "time": time.time(),
        "monotonic": time.monotonic(),
        "host": host,
        "processes": processes,
        "cgroups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=3600)
    parser.add_argument("--interval", type=float, default=15)
    args = parser.parse_args()
    if args.interval < 5 or args.seconds < 0:
        parser.error("interval must be >=5 seconds; duration must be nonnegative")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with args.output.open("x") as stream:
        while True:
            stream.write(json.dumps(snapshot(), separators=(",", ":")) + "\n")
            stream.flush()
            remaining = args.seconds - (time.monotonic() - start)
            if remaining <= 0:
                break
            time.sleep(min(args.interval, remaining))


if __name__ == "__main__":
    main()
