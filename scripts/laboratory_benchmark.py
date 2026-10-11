"""Measured scheduler, full audited episodes, profile and durable campaign workloads."""

import argparse
import cProfile
import io
import json
import platform
import pstats
import resource
import tempfile
import time
from pathlib import Path

from midas.laboratory.campaigns import Campaigns, CampaignSpec, code_hash
from midas.laboratory.clock import Clock
from midas.laboratory.runtime import execute
from midas.laboratory.spec import generate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("docs/MILESTONE_3_BENCHMARK.json"))
    args = parser.parse_args()
    if not 1 <= args.runs <= 10000:
        parser.error("Benchmark run count must be 1..10000; larger research uses the campaign CLI")
    profiler = cProfile.Profile()
    profiler.enable()
    for index in range(50):
        execute(generate("calm", index), retain=False)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(18)
    clock = Clock()
    count = 100_000
    began = time.perf_counter()
    for i in range(count):
        clock.schedule(i, str(i), "probe", {})
    while clock.peek():
        clock.pop()
    scheduler_seconds = time.perf_counter() - began
    began = time.perf_counter()
    events = 0
    for index in range(100):
        result = execute(generate("calm", index), retain=False)
        events += result["event_count"]
    audited_seconds = time.perf_counter() - began
    with tempfile.TemporaryDirectory(prefix="midas-m3-benchmark-") as temporary:
        root = Path(temporary)
        lab = Campaigns(root, Path("data/datasets"))
        try:
            campaign = lab.create(
                CampaignSpec(
                    runs=args.runs,
                    workers=args.workers,
                    retain_successes=0,
                    max_wall_seconds=600,
                    seed=20261011,
                )
            )
            while True:
                campaign = lab.get(campaign["id"])
                if campaign["status"] != "RUNNING":
                    break
                time.sleep(0.5)
            lab.threads[campaign["id"]].join()
            campaign = lab.get(campaign["id"])
            rows = lab.runs(campaign["id"], limit=200)
            sample_worker_peaks = [r["result"]["runtime"]["peak_rss_mb"] for r in rows]
            disk = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
            result = {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "code_hash": code_hash(),
                "scheduler": {
                    "events": count,
                    "seconds": scheduler_seconds,
                    "scheduled_and_popped_per_second": count / scheduler_seconds,
                },
                "audited_episodes": {
                    "runs": 100,
                    "events": events,
                    "seconds": audited_seconds,
                    "events_per_second": events / audited_seconds,
                    "runs_per_second": 100 / audited_seconds,
                },
                "campaign": campaign,
                "campaign_storage_bytes": disk,
                "sampled_worker_peak_rss_mb": max(sample_worker_peaks, default=0),
                "coordinator_lifetime_peak_rss_mb": resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                / 1024,
                "profile_50_calm_episodes": stream.getvalue(),
                "limits": "Local Linux measurements under concurrent activity; scheduler benchmark excludes strategy, risk, accounting and persistence. Worker RSS is sampled from first 200 canonical runs; process lifetime peak includes preceding scheduler/profile phases.",
            }
        finally:
            lab.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in result.items() if k != "profile_50_calm_episodes"}, indent=2)
    )


if __name__ == "__main__":
    main()
