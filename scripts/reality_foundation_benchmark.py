"""Bounded synthetic measurements. Never opens a production recording root.

Run with PYTHONPATH pointing to the candidate. JSON labels all data synthetic.
Full-store recovery/endurance still require independent admission and evidence.
"""

from __future__ import annotations

import argparse
import gc
import json
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from midas.reality import recovery
from midas.reality.reconstruction import Engine
from midas.reality.replay import replay
from midas.reality.storage import Store, manifest

ROOT = Path(__file__).resolve().parents[1]


def memory(markets: int, depth: int, variant: str) -> dict[str, Any]:
    cls = Engine
    if variant == "loaded-2b83818":
        source = subprocess.check_output(
            ["git", "show", "2b83818:packages/midas/reality/reconstruction.py"], cwd=ROOT, text=True
        )
        namespace: dict[str, Any] = {"__package__": "midas.reality"}
        exec(compile(source, "historical-reconstruction-2b83818", "exec"), namespace)
        cls = namespace["Engine"]
    tracemalloc.start()
    engine = cls()
    engine.consume(
        dict(
            kind="discovery",
            ordinal=1,
            received_ns=1,
            cohort=[
                dict(condition=f"synthetic-condition-{m}", tokens=[f"{m}-yes", f"{m}-no"])
                for m in range(markets)
            ],
        )
    )
    for i, token in enumerate(engine.tokens):
        raw = dict(
            event_type="book",
            asset_id=token,
            market=engine.tokens[token],
            timestamp="1",
            bids=[dict(price=f"0.{p:06d}", size="1") for p in range(1, depth + 1)],
            asks=[dict(price=f"0.{500000 + p:06d}", size="2") for p in range(1, depth + 1)],
        )
        engine.consume(dict(kind="frame", ordinal=i + 2, received_ns=2, payload=json.dumps(raw)))
    del raw
    gc.collect()
    retained = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    start = time.monotonic()
    digest = engine.digest()
    digest_seconds = time.monotonic() - start
    current, peak = tracemalloc.get_traced_memory()
    allocation_sites = [str(s) for s in tracemalloc.take_snapshot().statistics("lineno")[:5]]
    tracemalloc.stop()
    return dict(
        synthetic=True,
        variant=variant,
        markets=markets,
        subscriptions=markets * 2,
        depth_per_side=depth,
        retained_heap_bytes=retained,
        digest_temporary_peak_bytes=peak - retained,
        post_digest_heap_bytes=current,
        digest_seconds=digest_seconds,
        digest=digest,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        allocation_sites=allocation_sites,
    )


def archive_build(root: Path, segments: int) -> None:
    fixture = json.loads((ROOT / "tests/fixtures/reality/observed.json").read_text())
    store = Store(root, reserve=1, budget=256 * 1024**2)
    engine = Engine()
    d = fixture["discovery"]
    engine.consume(store.append("discovery", d["payload"], cohort=d["cohort"]))
    for _ in range(segments):
        for _ in range(16):
            engine.consume(store.append("frame", fixture["frames"][0]["payload"]))
        engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
        store.rotate()
    store.rotate(reopen=False)
    recovery.save(root, engine, manifest(root))
    store.close()


def startup(root: Path, fast: bool) -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    before_io = Path("/proc/self/io").read_text()
    start = time.monotonic()
    store = Store(root, reserve=1, verify_existing=False, defer_open=True)
    catalog = manifest(root)
    if fast:
        engine, detail = recovery.recover(root, catalog)
    else:
        engine, checks = replay(root, catalog)
        detail = dict(mode="full_replay", checkpoints=checks)
    if engine.last_ordinal != store.ordinal:
        raise ValueError("startup cursor mismatch")
    # Isolated writer activation and first new durable gap model safe resumption.
    store.activate()
    row = store.append("gap", dict(reason="synthetic_restart"))
    first_durable_seconds = time.monotonic() - start
    engine.consume(row)
    store.close()
    after = resource.getrusage(resource.RUSAGE_SELF)
    return dict(
        synthetic=True,
        detail=detail,
        seconds_to_first_new_durable_record=first_durable_seconds,
        cpu_seconds=after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
        max_rss_kib=after.ru_maxrss,
        segments=len(catalog["segments"]),
        archive_bytes=sum(s["bytes"] for s in catalog["segments"]),
        io_before=before_io,
        io_after=Path("/proc/self/io").read_text(),
        digest=engine.digest(),
        ordinal=engine.last_ordinal,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["memory", "startup"])
    parser.add_argument("--markets", type=int, default=1)
    parser.add_argument("--depth", type=int, default=100)
    parser.add_argument("--variant", default="candidate")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    if args.worker:
        value = (
            memory(args.markets, args.depth, args.variant)
            if args.worker == "memory"
            else startup(args.root, args.variant == "candidate")
        )
        print(json.dumps(value))
        return
    result: dict[str, Any] = dict(
        synthetic=True,
        memory=[],
        startup=[],
        limitations=[
            "Warm disposable archives; not full-store evidence or a production ETA.",
            "RSS includes Python allocator and imports; heap is tracemalloc observed.",
            "No transport queue is allocated in the memory model; protocol buffers budget separately.",
        ],
    )
    for markets, depth in [
        (1, 100),
        (4, 100),
        (8, 100),
        (10, 100),
        (1, 1000),
        (4, 1000),
        (8, 1000),
        (10, 1000),
        (1, 10000),
    ]:
        for variant in ("candidate", "loaded-2b83818"):
            command = [
                sys.executable,
                __file__,
                "--worker",
                "memory",
                "--markets",
                str(markets),
                "--depth",
                str(depth),
                "--variant",
                variant,
            ]
            result["memory"].append(
                json.loads(subprocess.check_output(command, text=True, timeout=60))
            )
    for segments in (8, 32, 128):
        with tempfile.TemporaryDirectory(prefix="midas-reality-synthetic-") as temporary:
            root = Path(temporary)
            archive_build(root, segments)
            # Use disposable copies so startup's durable gap doesn't change the comparison.
            import shutil

            for variant in ("candidate", "full"):
                copy = root / variant
                copy.mkdir()
                for path in root.iterdir():
                    if path.is_file():
                        shutil.copyfile(path, copy / path.name)
                value = json.loads(
                    subprocess.check_output(
                        [
                            sys.executable,
                            __file__,
                            "--worker",
                            "startup",
                            "--root",
                            str(copy),
                            "--variant",
                            variant,
                        ],
                        text=True,
                        timeout=90,
                    )
                )
                result["startup"].append(dict(variant=variant, **value))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
