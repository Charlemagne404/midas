import json

import pytest

from scripts.host_capacity_sample import cgroup_ancestor_paths
from scripts.host_capacity_summary import fields, summarize


def test_cgroup_ancestor_paths_cover_leaf_to_root():
    assert cgroup_ancestor_paths("/user.slice/user-1000.slice/user@1000.service") == (
        "/user.slice/user-1000.slice/user@1000.service",
        "/user.slice/user-1000.slice",
        "/user.slice",
        "/",
    )
    assert cgroup_ancestor_paths("/") == ("/",)


@pytest.mark.parametrize("path", ("relative/group", "/safe/../../escape", "//double-root/group"))
def test_cgroup_ancestor_paths_reject_untrusted_path_shapes(path):
    assert cgroup_ancestor_paths(path) == ()
    assert cgroup_ancestor_paths("/safe/" + chr(0) + "escape") == ()


def test_units_pressure_cpu_and_swap_rates_are_distinct(tmp_path):
    assert fields("MemAvailable: 10 kB\nusage_usec 42\n") == {"MemAvailable": 10, "usage_usec": 42}
    path = tmp_path / "samples.jsonl"
    rows = []
    for i in range(2):
        rows.append(
            {
                "time": 100 + i * 2,
                "monotonic": 200 + i * 2,
                "host": {
                    "meminfo": f"MemAvailable: {10 + i} kB\nSwapFree: 0 kB\nCached: 2 kB\nAnonPages: 3 kB\nSlab: 1 kB\n",
                    "vmstat": f"pswpin {i * 2}\npswpout 0\n",
                    "stat": "cpu 25 0 0 50 25 0 0 0\n" if i else "cpu 0 0 0 0 0 0 0 0\n",
                    "diskstats": f"259 0 nvme0n1 {i * 4} 0 {i * 8} {i * 12} {i * 2} 0 {i * 16} {i * 8} 0 {i * 20} {i * 20}\n",
                    "pressure": {"cpu": f"some avg10={i * 10}.00 total=0\n"},
                },
                "cgroups": {
                    "/example": {
                        "memory.current": "100",
                        "memory.swap.current": "90",
                        "memory.high": "1000",
                        "memory.max": "2000",
                        "memory.swap.max": "max",
                        "memory.events": f"high {2 + i}\nmax {i}\noom 0\noom_kill 0\n",
                        "memory.pressure": (
                            f"some avg10={1 + i}.00 avg60={2 + i}.00 avg300={3 + i}.00 total={100 + 50 * i}\n"
                            f"full avg10={0.5 + i:.2f} avg60={1 + i}.00 avg300={2 + i}.00 total={40 + 20 * i}\n"
                        ),
                        "memory.stat": "anon 40\nfile 60\n",
                        "cpu.stat": f"usage_usec {500000 + i * 1000000}\nthrottled_usec {100 + i * 500}\n",
                    }
                },
            }
        )
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + '{"unfinished":')
    result = summarize(path)
    assert result["sample_count"] == 2
    assert result["host"]["MemAvailable_bytes"]["mean"] == 10.5 * 1024
    assert result["host"]["cpu_busy_percent"]["mean"] == 25
    assert result["host"]["cpu_iowait_percent"]["mean"] == 25
    assert result["host"]["cpu_some_avg10"]["mean"] == 5
    assert result["host"]["pswpin_per_second"]["mean"] == 1
    assert result["host"]["disk_nvme0n1_read_iops"]["mean"] == 2
    assert result["host"]["disk_nvme0n1_read_bytes_per_second"]["mean"] == 2048
    assert result["host"]["disk_nvme0n1_read_await_ms"]["mean"] == 3
    assert result["host"]["disk_nvme0n1_util_percent"]["mean"] == 1
    group = result["cgroups"]["/example"]
    assert group["cpu_seconds"] == 1
    assert group["interval_seconds"] == 2
    assert group["throttled_seconds"] == pytest.approx(0.0005)
    assert group["memory_limits"] == {
        "memory.high": "1000",
        "memory.max": "2000",
        "memory.swap.max": "max",
    }
    assert group["memory_event_deltas"]["high"] == {
        "first": 2,
        "last": 3,
        "delta": 1,
        "counter_reset": False,
    }
    assert group["memory_event_deltas"]["oom_kill"]["delta"] == 0
    assert group["memory_event_deltas"]["max"]["delta"] == 1
    assert group["memory_pressure"]["averages"]["some_avg10"] == {
        "min": 1.0,
        "mean": 1.5,
        "max": 2.0,
    }
    assert group["memory_pressure"]["total_us"]["some"]["delta"] == 50
    assert summarize(path, since=102)["sample_count"] == 1


def test_cgroup_counter_resets_are_not_reported_as_negative_activity(tmp_path):
    path = tmp_path / "counter-reset.jsonl"
    rows = []
    for i, count in enumerate((4, 1)):
        rows.append(
            {
                "time": 100 + i,
                "monotonic": 200 + i,
                "host": {
                    "meminfo": (
                        "MemAvailable: 1 kB\nSwapFree: 1 kB\nCached: 1 kB\n"
                        "AnonPages: 1 kB\nSlab: 1 kB\n"
                    ),
                    "vmstat": "",
                    "stat": "",
                    "diskstats": "",
                    "pressure": {},
                },
                "cgroups": {
                    "/example": {
                        "memory.current": None,
                        "memory.swap.current": None,
                        "memory.stat": "",
                        "memory.events": f"oom {count}\n",
                        "memory.pressure": (
                            f"some avg10=0.00 avg60=0.00 avg300=0.00 total={count}\n"
                        ),
                        "cpu.stat": "usage_usec 0\n",
                    }
                },
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    group = summarize(path)["cgroups"]["/example"]
    assert group["memory_event_deltas"]["oom"] == {
        "first": 4,
        "last": 1,
        "delta": None,
        "counter_reset": True,
    }
    assert group["memory_pressure"]["total_us"]["some"] == {
        "first": 4,
        "last": 1,
        "delta": None,
        "counter_reset": True,
    }
