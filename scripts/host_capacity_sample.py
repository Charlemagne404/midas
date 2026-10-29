"""Low-frequency, read-only Linux host/cgroup sampling; no process attachment."""

import argparse
import json
import time
from pathlib import Path, PurePosixPath


def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def cgroup_ancestor_paths(path: str) -> tuple[str, ...]:
    """Return a process cgroup path and its ancestors, from leaf through root.

    ``/proc/<pid>/cgroup`` is kernel-provided, but keeping path validation here
    ensures malformed or unexpected paths can never escape the cgroup mount
    when mapped to files under ``/sys/fs/cgroup``.
    """
    if not path.startswith("/") or path.startswith("//") or "\x00" in path:
        return ()
    parsed = PurePosixPath(path)
    if parsed.anchor != "/" or ".." in parsed.parts:
        return ()
    parts = parsed.parts[1:]
    return tuple(
        "/" + "/".join(parts[:end]) if end else "/"
        for end in range(len(parts), -1, -1)
    )


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
    # Record active process groups and ancestors. Ancestors capture aggregate
    # limits/events (for example user@UID.service) that leaf-only sampling misses.
    for value in processes.values():
        for line in (value["cgroup"] or "").splitlines():
            if line.startswith("0::"):
                for group in cgroup_ancestor_paths(line[3:]):
                    if group not in groups:
                        relative = PurePosixPath(group).relative_to("/")
                        group_dir = root.joinpath(*relative.parts)
                        groups[group] = {
                            k: read(group_dir / k)
                            for k in (
                                "cpu.stat",
                                "cpu.max",
                                "cpu.pressure",
                                "memory.current",
                                "memory.peak",
                                "memory.high",
                                "memory.max",
                                "memory.swap.max",
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
