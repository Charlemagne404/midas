"""Read-only Gate A evidence snapshot; finalized segments only."""

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

from midas.reality.storage import atomic_json, canonical, manifest, read_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deployment", type=Path, default=Path("docs/REALITY_GATE_A_DEPLOYMENT.json")
    )
    parser.add_argument(
        "--checks", type=Path, default=Path("docs/REALITY_GATE_A_FINAL_CHECKS.json")
    )
    parser.add_argument("--output", type=Path, default=Path("docs/REALITY_GATE_A_CHECKPOINT.json"))
    parser.add_argument("--collector-release", default="74b1dea")
    args = parser.parse_args()
    root = Path("data/recordings/reality")
    value = manifest(root)
    counts: Counter[str] = Counter()
    gaps: Counter[str] = Counter()
    comparisons: Counter[str] = Counter()
    markets: set[str] = set()
    epochs = []
    first = last = None
    raw_bytes = sampled = max_persist = max_reconstruct = 0
    for row in read_manifest(root, value):
        counts[row["kind"]] += 1
        if row["kind"] == "frame":
            ns = row["received_ns"]
            first = ns if first is None else min(first, ns)
            last = ns if last is None else max(last, ns)
            raw_bytes += len(row["payload"].encode())
        elif row["kind"] == "gap":
            gaps[row["payload"]["reason"]] += 1
            if row["payload"]["reason"] == "process_start":
                epochs.append(
                    dict(
                        ordinal=row["ordinal"],
                        received_ns=row["received_ns"],
                        implementation_sha256=row["payload"].get("implementation_sha256"),
                        reconstruction_version=row["payload"].get("reconstruction_version", 1),
                    )
                )
        elif row["kind"] == "discovery":
            markets.update(m["id"] for m in row["cohort"])
        elif row["kind"] == "book_comparison":
            comparisons[row["payload"]["assessment"]] += 1
        elif row["kind"] == "timing_measurement":
            for item in row["payload"]["samples"]:
                sampled += 1
                max_persist = max(
                    max_persist,
                    item["persistence_completed_monotonic_ns"]
                    - item["persistence_begin_monotonic_ns"],
                )
                max_reconstruct = max(
                    max_reconstruct,
                    item["reconstruction_completed_monotonic_ns"]
                    - item["persistence_completed_monotonic_ns"],
                )
    elapsed = (last - first) / 1e9 if first is not None and last is not None else 0
    status = json.loads((root / "status.json").read_text())
    capacity = json.loads(Path("data/recordings/capacity.json").read_text())
    services = {}
    for unit in (
        "midas-reality.service",
        "midas-reality-capacity.service",
        "midas-reality-capacity.timer",
        "midas-reality-archive.service",
        "midas-reality-archive.timer",
        "midas-api.service",
        "midas-web.service",
    ):
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "MainPID",
                "-p",
                "ActiveState",
                "-p",
                "MemoryCurrent",
                "-p",
                "NRestarts",
                "-p",
                "Result",
                "-p",
                "CPUUsageNSec",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        services[unit] = dict(line.split("=", 1) for line in result.stdout.splitlines())
    archive = json.loads(Path("data/recordings/reality-archive-mission2/manifest.json").read_text())
    deployment = json.loads(args.deployment.read_text())
    checks = json.loads(args.checks.read_text())
    if not (
        deployment["deployed"]
        and checks["passed"]
        and status["markets"] == 8
        and status["config"]["budget_bytes"] == 24 * 1024**3
        and services["midas-reality.service"]["ActiveState"] == "active"
        and services["midas-reality.service"]["MainPID"]
        == deployment["production_after"]["MainPID"]
        and services["midas-reality-archive.service"]["Result"] == "success"
        and services["midas-reality-capacity.service"]["Result"] == "success"
        and capacity["compressed_bytes_per_second"] is not None
    ):
        raise ValueError("Gate A runtime/check evidence incomplete")
    snapshot = dict(
        schema_version=1,
        gate="A",
        state="engineering_checkpoint",
        checked_ns=time.time_ns(),
        collector_status=status,
        capacity=capacity,
        services=services,
        raw_evidence=dict(
            finalized_segments=len(value["segments"]),
            manifest_sha256=hashlib.sha256(canonical(value)).hexdigest(),
            raw_frames=counts["frame"],
            record_kinds=dict(counts),
            raw_frame_payload_bytes=raw_bytes,
            first_frame_ns=first,
            last_frame_ns=last,
            span_seconds=elapsed,
            span_is_not_continuous_coverage=True,
            frames_per_second_including_gaps=counts["frame"] / elapsed if elapsed else None,
            distinct_markets=len(markets),
            gap_reasons=dict(gaps),
            source_epochs=epochs,
            missing_historical_epoch_source_identities=sum(
                e["implementation_sha256"] is None for e in epochs
            ),
            compressed_segment_bytes=sum(s["bytes"] for s in value["segments"]),
            independent_comparisons=dict(comparisons),
        ),
        local_timing=dict(
            frames_sampled=sampled,
            max_persistence_ns=max_persist,
            max_reconstruction_ns=max_reconstruct,
            samples_are_bounded_subsets_not_all_frames=True,
            receive_semantics="application dequeue, not wire/hardware latency",
        ),
        archive=dict(
            segments=len(archive["segments"]),
            bytes=sum(s["bytes"] for s in archive["segments"]),
            provenance=archive["archival_provenance"],
        ),
        deployment=deployment,
        checks=dict(
            passed=True,
            source_sha256=checks["source_sha256"],
            summary=checks["checks"][0]["output"].splitlines()[-1],
        ),
        collector_source_release_commit=args.collector_release,
        capacity_worker_changed_without_recorder_restart=True,
        limitations=[
            "V2, Up/Down and augmented Other contracts excluded.",
            "Transient or stale quotes are degraded even while recording succeeds.",
            "No exchange sequencing guarantee or private execution/fill evidence.",
            "Finite storage requires capacity action; no automatic raw deletion or off-host destination.",
            "Original health-window timeout and rollback gaps retained.",
            "Early historical epochs lack complete producer source identity; preserve and qualify/exclude them in research.",
            "Full protected-archive hash audit remains Gate G; Laboratory integrity/count and protected code identity checks match.",
        ],
        remaining_gates=[
            "B: datasets and labels",
            "C: calibration/scenarios/synthetic comparisons",
            "D: training/eligibility",
            "E: prospective shadow research",
            "F: native Reality UI",
            "G: final broad verification",
        ],
    )
    atomic_json(args.output, snapshot)
    print(
        json.dumps(
            dict(
                frames=counts["frame"],
                distinct_markets=len(markets),
                span_hours=elapsed / 3600,
                comparisons=dict(comparisons),
                state=status["state"],
                fresh_books=status["fresh_books"],
                timing_samples=sampled,
                storage_bytes=capacity["raw_root_bytes"],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
