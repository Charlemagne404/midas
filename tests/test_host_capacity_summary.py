import json

import pytest

from scripts.host_capacity_summary import fields, summarize


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
    assert summarize(path, since=102)["sample_count"] == 1
