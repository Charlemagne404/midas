"""Measured local critical paths; synthetic data, no profit/latency inference."""

import asyncio
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path

from midas.paper.broker import AccountConfig
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

from apps.api.paper import PaperBroker
from apps.api.storage import Store


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="midas-benchmark-") as root:
        store = Store(f"sqlite+aiosqlite:///{root}/benchmark.db")
        await store.initialize()
        broker = PaperBroker(store, "benchmark", AccountConfig())
        await broker.start(DEMO_EPOCH)
        m, bs = binary_fixture("unprofitable")
        samples = []
        for index in range(30):
            start = time.perf_counter()
            await broker.apply(
                {
                    "id": f"bench:{index}",
                    "kind": "observe",
                    "ts": DEMO_EPOCH,
                    "market": m.model_dump(mode="json"),
                    "books": {a: b.model_dump(mode="json") for a, b in bs.items()},
                }
            )
            samples.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        restarted = PaperBroker(store, "benchmark", AccountConfig())
        await restarted.start(DEMO_EPOCH + 1)
        report = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "workload": "30 rejected synthetic observations with FULL-synchronous SQLite WAL, journal and account commits; one shared account; no network",
            "samples": len(samples),
            "median_ms": statistics.median(samples),
            "p95_ms": sorted(samples)[28],
            "replay_and_reconciliation_ms": (time.perf_counter() - start) * 1000,
            "recovered_revision": restarted.revision,
        }
        Path("docs/MILESTONE_2_BENCHMARK.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
