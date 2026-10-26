"""Comparable durable paper commands in a NEW disposable database only."""

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from midas.economics.attestation import digest
from midas.paper.broker import AccountConfig, ExecutionModel
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

import apps.api.storage as storage
from apps.api.paper import PaperBroker
from apps.api.storage import Store


def io_counters() -> dict[str, int]:
    return {
        line.split(":")[0]: int(line.split()[1])
        for line in Path("/proc/self/io").read_text().splitlines()
    }


async def benchmark(database: Path, count: int) -> dict:
    path = database.resolve()
    owned = Path.home() / "midas/data"
    disposable = path.is_relative_to(Path(tempfile.gettempdir()).resolve()) or (
        path.is_relative_to(owned) and path.relative_to(owned).parts[0].startswith("host-capacity-")
    )
    if not disposable or path.exists() or database.is_symlink():
        raise ValueError(
            "Benchmark requires a new disposable database; production paths are forbidden"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(f"sqlite+aiosqlite:///{path}")
    await store.initialize()
    config = AccountConfig(execution=ExecutionModel.preset("optimistic"))
    broker = PaperBroker(store, "benchmark", config)
    await broker.start(DEMO_EPOCH)
    market, books = binary_fixture()
    observation = {
        "kind": "observe",
        "market": market.model_dump(mode="json"),
        "books": {a: b.model_dump(mode="json") for a, b in books.items()},
    }
    for i in range(200):
        await broker.apply({**observation, "id": f"observe:{i}", "ts": DEMO_EPOCH + i})
    before = io_counters()
    started, cpu = time.monotonic(), time.process_time()
    for i in range(200, 200 + count):
        await broker.apply({**observation, "id": f"observe:{i}", "ts": DEMO_EPOCH + i})
    async with store.engine.connect() as connection:
        checkpoint = (await connection.exec_driver_sql("PRAGMA wal_checkpoint(FULL)")).one()
        assert checkpoint[0] == 0 and checkpoint[1] == checkpoint[2]
        stored = (
            await connection.exec_driver_sql("SELECT payload FROM paper_accounts")
        ).scalar_one()
    await store.close()
    cpu_seconds, wall_seconds = time.process_time() - cpu, time.monotonic() - started
    after = io_counters()
    logical_hash = digest(broker.state)
    recovery_started = time.monotonic()
    recovered_store = Store(f"sqlite+aiosqlite:///{path}")
    recovered = PaperBroker(recovered_store, "benchmark", config)
    await recovered.start(DEMO_EPOCH + 1000)
    assert recovered.healthy and recovered.state["observations"] == 200 + count
    await recovered_store.close()
    memory = {
        line.split(":")[0]: int(line.split()[1])
        for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(("VmRSS:", "VmHWM:"))
    }
    return {
        "pid": os.getpid(),
        "store_source": storage.__file__,
        "store_source_sha256": hashlib.sha256(Path(storage.__file__).read_bytes()).hexdigest(),
        "commands": count,
        "cpu_seconds": cpu_seconds,
        "wall_seconds": wall_seconds,
        "io_delta": {key: after[key] - before[key] for key in before},
        "stored_head_bytes": len(stored.encode()),
        "logical_head_bytes": len(json.dumps(broker.state).encode()),
        "compressed": "__midas_paper_state_codec__" in json.loads(stored),
        "logical_state_sha256": logical_hash,
        "proc_memory_kib": memory,
        "recovery_seconds": time.monotonic() - recovery_started,
        "recovered_journal_events": recovered.journal_event_count,
        "scope": "fixed synthetic observations, FULL-sync commits plus final checkpoint; warm disposable SQLite",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--commands", type=int, default=64)
    args = parser.parse_args()
    if not 16 <= args.commands <= 256:
        parser.error("commands must be 16..256")
    print(json.dumps(asyncio.run(benchmark(args.database, args.commands))))
