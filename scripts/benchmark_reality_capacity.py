"""Bounded in-memory synthetic ingestion; never opens a recording directory."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import midas.reality.reconstruction as reconstruction
from midas.reality.reconstruction import Engine


def benchmark(markets: int, depth: int, frames: int, variant: str) -> dict:
    engine_class = Engine
    source_path = Path(reconstruction.__file__)
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if variant == "loaded-2b83818":
        namespace = {"__package__": "midas.reality"}
        source = subprocess.check_output(
            ["git", "show", "2b83818:packages/midas/reality/reconstruction.py"], text=True
        )
        exec(compile(source, "historical-reconstruction-2b83818", "exec"), namespace)
        engine_class = namespace["Engine"]
        source_sha256 = hashlib.sha256(source.encode()).hexdigest()
    engine = engine_class()
    engine.consume(
        {
            "kind": "discovery",
            "ordinal": 1,
            "received_ns": 1_000_000_000,
            "cohort": [
                {"condition": f"synthetic-{i}", "tokens": [f"{i}-yes", f"{i}-no"]}
                for i in range(markets)
            ],
        }
    )
    tokens = list(engine.tokens)
    ordinal = 1
    for token in tokens:
        raw = {
            "event_type": "book",
            "asset_id": token,
            "market": engine.tokens[token],
            "timestamp": "1000",
            "bids": [{"price": f"0.{i:06d}", "size": "1"} for i in range(1, depth + 1)],
            "asks": [{"price": f"0.{500000 + i:06d}", "size": "2"} for i in range(1, depth + 1)],
        }
        ordinal += 1
        engine.consume(
            {
                "kind": "frame",
                "ordinal": ordinal,
                "received_ns": 1_000_000_000,
                "payload": json.dumps(raw),
            }
        )
    del raw
    records = []
    input_hash = hashlib.sha256()
    for i in range(frames):
        token = tokens[i % len(tokens)]
        payload = json.dumps(
            {
                "event_type": "price_change",
                "market": engine.tokens[token],
                "timestamp": str(1001 + i),
                "price_changes": [
                    {
                        "asset_id": token,
                        "side": "BUY",
                        "price": f"0.{depth:06d}",
                        "size": str(i % 7 + 1),
                    }
                ],
            }
        )
        input_hash.update(payload.encode())
        records.append(
            {
                "kind": "frame",
                "ordinal": ordinal + i + 1,
                "received_ns": (1001 + i) * 1_000_000,
                "payload": payload,
            }
        )
    started, cpu = time.monotonic(), time.process_time()
    for record in records:
        engine.consume(record)
    elapsed, cpu_seconds = time.monotonic() - started, time.process_time() - cpu
    assert engine.counts["price_change"] == frames and not engine.counts["malformed_event"]
    digest_started, digest_cpu = time.monotonic(), time.process_time()
    digest = engine.digest()
    digest_cpu_seconds = time.process_time() - digest_cpu
    digest_wall_seconds = time.monotonic() - digest_started
    memory = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(("VmRSS:", "VmHWM:"))
    }
    return {
        "synthetic": True,
        "candidate_source": str(source_path),
        "engine_source_sha256": source_sha256,
        "variant": variant,
        "markets": markets,
        "depth_per_side": depth,
        "represented_levels": markets * 4 * depth,
        "frames": frames,
        "cpu_seconds": cpu_seconds,
        "wall_seconds": elapsed,
        "frames_per_cpu_second": frames / cpu_seconds,
        "digest_cpu_seconds": digest_cpu_seconds,
        "digest_wall_seconds": digest_wall_seconds,
        "state_sha256": digest,
        "input_sha256": input_hash.hexdigest(),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "proc_memory_kib": memory,
        "scope": "synthetic fixed-depth books/deltas; no networking, fsync, recovery or live capacity claim",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markets", type=int, choices=(8, 16, 32), required=True)
    parser.add_argument("--depth", type=int, choices=(100, 1000), required=True)
    parser.add_argument("--frames", type=int, default=2000)
    parser.add_argument("--variant", choices=("candidate", "loaded-2b83818"), required=True)
    args = parser.parse_args()
    if not 1 <= args.frames <= 20000:
        parser.error("frames must be 1..20000")
    print(json.dumps(benchmark(args.markets, args.depth, args.frames, args.variant)))
