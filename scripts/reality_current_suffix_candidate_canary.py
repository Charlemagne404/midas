#!/usr/bin/env python3
"""Run the verified candidate collector on an isolated copy of a pinned history view."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any


def load_canary(path: Path):
    spec = importlib.util.spec_from_file_location("midas_full_history_fixture_canary", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load candidate fixture canary")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_digest(value: Any, canonical) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_link_fingerprint(paths: list[Path], raw_root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_symlink():
            raise ValueError(f"Historical segment stopped being a read-only symlink: {path.name}")
        target = path.resolve(strict=True)
        if not target.is_relative_to(raw_root):
            raise ValueError(f"Historical segment escaped the pinned raw root: {path.name}")
        stat = target.stat()
        digest.update(
            f"{path.name}\0{target}\0{stat.st_dev}\0{stat.st_ino}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode()
        )
    return digest.hexdigest()


def parse_counter(text: str) -> dict[str, int]:
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2:
            result[fields[0]] = int(fields[1])
    return result


async def execute_and_sample(module, config, duration: float, interval: float, status_path: Path):
    finished = asyncio.Event()
    live_samples: list[dict[str, Any]] = []

    async def watch_status() -> None:
        while not finished.is_set():
            try:
                value = json.loads(status_path.read_text())
                if value.get("state") not in {"STARTING", "STOPPED", "FAILED"}:
                    fields = (
                        "state", "updated_ns", "markets", "fresh_books", "expected_books",
                        "process_frames", "failures", "sequence_verified",
                        "persistence_latency_window_complete",
                        "persistence_latency_window_covered_seconds",
                        "process_max_persist_seconds", "recent_max_persist_seconds",
                        "recent_p95_persist_seconds", "process_max_append_seconds",
                        "recent_max_append_seconds", "recent_p95_append_seconds",
                        "backpressure_active",
                        "transport_queue_observation_available", "transport_queue_depth",
                        "transport_queue_high_water_depth", "transport_queue_sample_count",
                        "transport_queue_saturated", "startup_seconds",
                        "seconds_until_first_new_durable_record", "first_frame_received_ns",
                        "recovery", "error", "last_error", "last_error_ns",
                    )
                    sample = {key: value.get(key) for key in fields if key in value}
                    sample["sampled_at_ns"] = time.time_ns()
                    live_samples.append(sample)
            except (OSError, ValueError, TypeError):
                pass
            await asyncio.sleep(1.0)

    task = asyncio.create_task(watch_status())
    try:
        unexpected, resources = await module.execute(config, duration, interval)
    finally:
        finished.set()
        await task
    return unexpected, resources, live_samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--candidate-config", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw-source", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--identities", type=Path, required=True)
    parser.add_argument("--cold", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--markets", type=int, default=10)
    parser.add_argument("--duration-seconds", type=float, default=75)
    parser.add_argument("--frame-interval-seconds", type=float, default=1.5625)
    args = parser.parse_args()

    repository = args.repository.resolve(strict=True)
    packages = args.packages.resolve(strict=True)
    raw_source = args.raw_source.resolve(strict=True)
    root = args.root.resolve(strict=True)
    if args.root.is_symlink() or not root.is_relative_to(repository / "data/recordings"):
        raise ValueError("Candidate test root must be a regular candidate recording directory")
    if not root.is_dir() or not args.receipt.parent.is_dir() or args.receipt.exists() or args.receipt.is_symlink():
        raise ValueError("Candidate root/receipt path is missing, unsafe or already used")
    if args.markets < 1 or args.markets > 10 or args.duration_seconds < 75 or args.frame_interval_seconds < 0.1:
        raise ValueError("Invalid bounded fixture parameters")

    args.packages.resolve(strict=True)
    import sys
    sys.path.insert(0, str(packages))
    from midas.reality.config import Config
    from midas.reality.storage import canonical, records

    canary = load_canary(repository / "scripts/reality_fixture_canary.py")
    config_base = Config.load(args.candidate_config)
    if args.markets > config_base.discovery_limit:
        raise ValueError("Fixture market count exceeds candidate discovery limit")
    config = Config(**{**config_base.dump(), "markets": args.markets, "root": str(root)})

    catalog = json.loads(args.catalog.read_text())
    identities = json.loads(args.identities.read_text())
    cold = json.loads(args.cold.read_text())
    catalog_sha = json_digest(catalog, canonical)
    identities_sha = json_digest(identities, canonical)
    if catalog_sha != cold.get("boundary_catalog_sha256") or identities_sha != cold.get("boundary_identities_sha256"):
        raise ValueError("Candidate startup pin differs from the verified cold boundary")
    if canary.source_identity() != cold.get("implementation_source_sha256"):
        raise ValueError("Candidate package changed from the full-scale recovery identity")
    checkpoint = root / "recovery-v1.checkpoint"
    if not checkpoint.is_file() or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != cold["recovery"]["checkpoint_sha256"]:
        raise ValueError("Staged candidate checkpoint is missing or differs from cold recovery")
    history = sorted(root.glob("*.seg"))
    expected_names = {item["file"] for item in catalog["segments"]}
    if {path.name for path in history} != expected_names or len(history) != len(expected_names):
        raise ValueError("Isolated candidate view does not exactly match the pinned finalized boundary")
    if any(path.with_suffix(".json").is_symlink() for path in history):
        raise ValueError("Historical segment manifest unexpectedly became a symlink")
    if list(root.glob("*.open")) or (root / "status.json").exists():
        raise ValueError("Candidate view must have no open tail or prior live status")
    before_links = source_link_fingerprint(history, raw_source)
    before_names = {path.name for path in history}
    before_bytes = sum(path.stat().st_size for path in history)

    started_ns = time.time_ns()
    unexpected, resource_samples, live_samples = asyncio.run(
        execute_and_sample(canary, config, args.duration_seconds, args.frame_interval_seconds, root / "status.json")
    )
    status = json.loads((root / "status.json").read_text())
    after_links = source_link_fingerprint(history, raw_source)
    if before_links != after_links:
        raise ValueError("Pinned raw segment metadata changed during candidate startup canary")

    new_segments = sorted(
        path for path in root.glob("*.seg") if not path.is_symlink() and path.name not in before_names
    )
    kinds: Counter[str] = Counter()
    for path in new_segments:
        for record, _ in records(path):
            kinds[str(record.get("kind", "unknown"))] += 1
    last_active = next(
        (item for item in reversed(live_samples) if item.get("fresh_books") == item.get("expected_books") and item.get("expected_books") == args.markets * 2),
        None,
    )
    if unexpected:
        raise ValueError(f"Fixture attempted an unexpected route: {unexpected[0]}")
    if (
        status.get("state") != "STOPPED" or status.get("failures") != 0
        or status.get("markets") != args.markets or status.get("process_frames", 0) < 20
        or status.get("sequence_verified") is not False or last_active is None
        or last_active.get("persistence_latency_window_complete") is not True
        or last_active.get("transport_queue_observation_available") is not True
        or kinds["frame"] < 20 or kinds["gap"] < 2
    ):
        raise ValueError("Full-history candidate collector did not meet bounded live acceptance")

    verified_prefix = cold.get("verified_r10_prefix")
    # Collector.status() publishes this contract under ``recovery``.
    recovery_status = status.get("recovery")
    if not isinstance(verified_prefix, dict) or not isinstance(recovery_status, dict):
        raise ValueError("Current-boundary canary lacks its verified-prefix recovery contract")
    expected_suffix_segments = verified_prefix.get("suffix_segment_count")
    expected_suffix_bytes = verified_prefix.get("suffix_bytes")
    if not isinstance(expected_suffix_segments, int) or not isinstance(expected_suffix_bytes, int):
        raise ValueError("Pinned boundary lacks exact appended-suffix accounting")
    if (
        recovery_status.get("mode") != "checkpoint_and_verified_tail"
        or recovery_status.get("source_integrity") != "verified"
        or recovery_status.get("prefix_segments_hashed") != verified_prefix.get("segment_count")
        or recovery_status.get("prefix_bytes_hashed") != verified_prefix.get("archive_bytes")
        or recovery_status.get("segments_reconstructed") != expected_suffix_segments
        or recovery_status.get("reconstructed_bytes") != expected_suffix_bytes
    ):
        raise ValueError("Candidate did not verify the R10 prefix and reconstruct the current suffix")

    cpu_samples = [sample for sample in resource_samples if sample.get("sampled_monotonic_ns") and sample.get("cpu.stat")]
    cpu_seconds = None
    sampled_seconds = None
    if len(cpu_samples) >= 2:
        cpu_seconds = (parse_counter(cpu_samples[-1]["cpu.stat"]).get("usage_usec", 0) - parse_counter(cpu_samples[0]["cpu.stat"]).get("usage_usec", 0)) / 1e6
        sampled_seconds = (cpu_samples[-1]["sampled_monotonic_ns"] - cpu_samples[0]["sampled_monotonic_ns"]) / 1e9
    memory_peak = max((int(sample.get("memory.peak", "0")) for sample in resource_samples), default=0)
    last_resource = resource_samples[-1] if resource_samples else {}
    receipt = {
        "schema_version": 1,
        "status": "PASSED",
        "created_at_ns": time.time_ns(),
        "started_at_ns": started_ns,
        "candidate_source_sha256": canary.source_identity(),
        "boundary_catalog_sha256": catalog_sha,
        "boundary_identities_sha256": identities_sha,
        "boundary_segments": len(history),
        "boundary_bytes": before_bytes,
        "boundary_state_sha256": cold.get("state_sha256"),
        "boundary_checkpoint_sha256": cold["recovery"]["checkpoint_sha256"],
        "verification_mode": "verified_r10_checkpoint_plus_current_suffix",
        "verified_r10_prefix": verified_prefix,
        "current_boundary_recovery_status": recovery_status,
        "candidate_root": str(root),
        "raw_source_link_metadata_sha256_before_after": before_links,
        "fixture_network_mode": "loopback WebSocket plus in-process HTTP MockTransport",
        "unexpected_external_routes": unexpected,
        "markets": args.markets,
        "duration_seconds": args.duration_seconds,
        "frame_interval_seconds": args.frame_interval_seconds,
        "collector_startup_seconds": status.get("startup_seconds"),
        "first_new_durable_record_seconds": status.get("seconds_until_first_new_durable_record"),
        "first_frame_received_ns": status.get("first_frame_received_ns"),
        "active_full_fresh_status_sample": last_active,
        "collector_final_status": status,
        "new_local_segments": [dict(name=path.name, bytes=path.stat().st_size) for path in new_segments],
        "new_local_segment_bytes": sum(path.stat().st_size for path in new_segments),
        "new_local_record_kinds": dict(kinds),
        "cgroup_sample_count": len(resource_samples),
        "cgroup_cpu_seconds": cpu_seconds,
        "cgroup_sampled_seconds": sampled_seconds,
        "cgroup_peak_bytes": memory_peak,
        "cgroup_memory_events": parse_counter(last_resource.get("memory.events", "")),
        "cgroup_cpu_pressure_peak_percent": canary.pressure_peaks(resource_samples, "cpu.pressure"),
        "cgroup_io_pressure_peak_percent": canary.pressure_peaks(resource_samples, "io.pressure"),
        "host_cpu_pressure_peak_percent": canary.pressure_peaks(resource_samples, "host_cpu.pressure"),
        "host_io_pressure_peak_percent": canary.pressure_peaks(resource_samples, "host_io.pressure"),
    }
    temp = args.receipt.with_suffix(args.receipt.suffix + ".tmp")
    with temp.open("xb") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, args.receipt)
    dirfd = os.open(args.receipt.parent, os.O_DIRECTORY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)
    print(json.dumps({key: receipt[key] for key in ("status", "boundary_segments", "boundary_bytes", "collector_startup_seconds", "first_new_durable_record_seconds", "new_local_record_kinds", "cgroup_cpu_seconds", "cgroup_peak_bytes", "cgroup_memory_events")}, sort_keys=True))


if __name__ == "__main__":
    main()
