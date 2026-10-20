"""Summarize a time window of host_capacity_sample JSONL without loading its history."""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def fields(raw):
    result = {}
    for line in (raw or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                result[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                pass
    return result


def pressure(raw):
    return {
        line.split()[0]: dict(x.split("=") for x in line.split()[1:])
        for line in (raw or "").splitlines()
    }


def distribution(values):
    return (
        {"min": min(values), "mean": statistics.mean(values), "max": max(values)}
        if values
        else None
    )


def summarize(path, since=0, until=float("inf")):
    samples = defaultdict(list)
    services = defaultdict(
        lambda: {
            "samples": defaultdict(list),
            "cpu_seconds": 0,
            "interval_seconds": 0,
            "throttled_seconds": 0,
        }
    )
    previous = None
    first = last = None
    count = 0
    with path.open() as stream:
        for line in stream:
            # A live sampler may still be writing its last (large) line.
            # Do not misread that incomplete tail as a finished observation.
            if not line.endswith("\n"):
                break
            row = json.loads(line)
            if not since <= row["time"] <= until:
                continue
            count += 1
            first = first or row["time"]
            last = row["time"]
            mem = fields(row["host"]["meminfo"])
            for name in ("MemAvailable", "SwapFree", "Cached", "AnonPages", "Slab"):
                samples[name + "_bytes"].append(mem[name] * 1024)
            for kind, raw in row["host"]["pressure"].items():
                for label, values in pressure(raw).items():
                    samples[f"{kind}_{label}_avg10"].append(float(values["avg10"]))
            dt = row["monotonic"] - previous["monotonic"] if previous else 0
            if dt:
                old_disks = {
                    p[2]: list(map(int, p[3:]))
                    for line in (previous["host"].get("diskstats") or "").splitlines()
                    if len(p := line.split()) >= 14
                }
                for line in (row["host"].get("diskstats") or "").splitlines():
                    p = line.split()
                    if len(p) < 14 or p[2] not in old_disks:
                        continue
                    name, values = p[2], list(map(int, p[3:]))
                    delta = [a - b for a, b in zip(values, old_disks[name], strict=False)]
                    if min(delta[:8]) < 0:
                        continue
                    for label, index, scale in (
                        ("read_iops", 0, 1),
                        ("write_iops", 4, 1),
                        ("read_bytes_per_second", 2, 512),
                        ("write_bytes_per_second", 6, 512),
                        ("util_percent", 9, 0.1),
                    ):
                        samples[f"disk_{name}_{label}"].append(delta[index] * scale / dt)
                    for label, count_index, ms_index in (("read", 0, 3), ("write", 4, 7)):
                        if delta[count_index]:
                            samples[f"disk_{name}_{label}_await_ms"].append(
                                delta[ms_index] / delta[count_index]
                            )
                for pid, process in row.get("processes", {}).items():
                    old_process = previous.get("processes", {}).get(pid)
                    if not old_process or not process.get("io") or not old_process.get("io"):
                        continue
                    new_stat = process["stat"].rsplit(")", 1)[1].split()
                    old_stat = old_process["stat"].rsplit(")", 1)[1].split()
                    if new_stat[19] != old_stat[19]:
                        continue  # PID reused; counters have a different owner.
                    group = (process.get("cgroup") or "").strip().removeprefix("0::")
                    target = services[group]["samples"]
                    before, after = fields(old_process["io"]), fields(process["io"])
                    for key in ("read_bytes", "write_bytes"):
                        delta_bytes = after.get(key, 0) - before.get(key, 0)
                        if delta_bytes >= 0:
                            # Per-process rates, not cgroup aggregate: waited-child
                            # counters can overlap. Label them explicitly.
                            target[f"pid_{pid}_{key}_per_second"].append(delta_bytes / dt)
                old_vm, new_vm = fields(previous["host"]["vmstat"]), fields(row["host"]["vmstat"])
                for name in ("pswpin", "pswpout", "pgmajfault", "pgscan_direct", "pgscan_kswapd"):
                    samples[name + "_per_second"].append(
                        (new_vm.get(name, 0) - old_vm.get(name, 0)) / dt
                    )
                old_cpu = {
                    line.split()[0]: list(map(int, line.split()[1:]))
                    for line in previous["host"]["stat"].splitlines()
                    if line.startswith("cpu")
                }
                for line in row["host"]["stat"].splitlines():
                    if not line.startswith("cpu"):
                        continue
                    name, *values = line.split()
                    diff = [
                        int(v) - old for v, old in zip(values[:8], old_cpu[name][:8], strict=True)
                    ]
                    total = sum(diff)
                    if total:
                        samples[name + "_busy_percent"].append(
                            100 * (total - diff[3] - diff[4]) / total
                        )
                        if name == "cpu":
                            samples["cpu_iowait_percent"].append(100 * diff[4] / total)
            for group, data in row["cgroups"].items():
                service = services[group]
                for name in ("memory.current", "memory.swap.current"):
                    if data[name] is not None:
                        service["samples"][name].append(int(data[name]))
                for name in ("anon", "file", "kernel"):
                    service["samples"][name].append(fields(data["memory.stat"]).get(name, 0))
                if dt and group in previous["cgroups"]:
                    old = fields(previous["cgroups"][group]["cpu.stat"])
                    new = fields(data["cpu.stat"])
                    delta = new.get("usage_usec", 0) - old.get("usage_usec", 0)
                    if delta >= 0:
                        service["cpu_seconds"] += delta / 1e6
                        service["interval_seconds"] += dt
                        service["throttled_seconds"] += (
                            max(0, new.get("throttled_usec", 0) - old.get("throttled_usec", 0))
                            / 1e6
                        )
            previous = row
    return {
        "first": first,
        "last": last,
        "sample_count": count,
        "host": {k: distribution(v) for k, v in samples.items()},
        "cgroups": {
            k: {
                **{n: v for n, v in d.items() if n != "samples"},
                "observations": {n: distribution(v) for n, v in d["samples"].items()},
            }
            for k, d in services.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--since", type=float, default=0)
    parser.add_argument("--until", type=float, default=float("inf"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(summarize(args.path, args.since, args.until), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
