"""Measure deterministic CPU workloads; no live profitability claims."""

import json
import platform
import statistics
import time
from decimal import Decimal

from midas.arbitrage.engine import BinaryStrategy
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from midas.simulation.scenarios import SCENARIOS, run_scenario

market, books = binary_fixture()
strategy = BinaryStrategy()
samples = []
for _ in range(1000):
    start = time.perf_counter_ns()
    strategy.evaluate(market, books, DEMO_EPOCH, Decimal(1000))
    samples.append((time.perf_counter_ns() - start) / 1e6)
start = time.perf_counter()
results = [run_scenario(key, 7) for key in SCENARIOS]
print(
    json.dumps(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "benchmark": "Two one-level synthetic books; excludes HTTP, storage and frontend",
            "evaluations": len(samples),
            "median_ms": statistics.median(samples),
            "p95_ms": sorted(samples)[949],
            "scenario_count": len(results),
            "scenario_suite_seconds": time.perf_counter() - start,
            "scenario_failures": sum(not r["passed"] for r in results),
        },
        indent=2,
    )
)
