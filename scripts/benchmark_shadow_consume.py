#!/usr/bin/env python3
"""Profile the complete Reality shadow consume path on finalized source data.

The campaign plan and model artifacts are read-only inputs. Each repetition
uses a fresh temporary journal and restores a previously captured runtime
checkpoint. No collector, campaign journal, network client, or order API is
opened for writing.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import resource
import sys
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any

from midas.reality import shadow_campaign, shadow_source, shadow_worker, storage
from midas.reality.shadow_source import Context, Tail
from midas.reality.shadow_worker import Shadow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--runtime-snapshot", required=True, type=Path)
    parser.add_argument("--segments", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--allow-current-code", action="store_true")
    parser.add_argument("--include-research-events", action="store_true")
    parser.add_argument(
        "--runtime-snapshot-output",
        type=Path,
        help="Write the last repetition's read-only replay runtime for a successor window.",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def stable_json(value: Any) -> bytes:
    """Serialize comparison data identically across frozen and branch code."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value)).hexdigest()


def process_peak_rss_bytes() -> int:
    """Read this process's peak resident set size in bytes when available."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024  # Linux reports kB here.
    except (OSError, ValueError, IndexError):
        pass
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def verify_module_roots(expected_root: Path) -> dict[str, str]:
    root = expected_root.resolve()
    paths: dict[str, str] = {}
    unexpected: list[str] = []
    for name, module in tuple(sys.modules.items()):
        if name != "midas" and not name.startswith("midas."):
            continue
        source = getattr(module, "__file__", None)
        if not source:
            continue
        path = Path(source).resolve()
        paths[name] = str(path)
        if not path.is_relative_to(root):
            unexpected.append(f"{name}: {path}")
    if unexpected:
        raise ValueError("MIDAS modules escaped selected code root: " + "; ".join(unexpected))
    return paths


def read_inputs(
    campaign_path: Path, snapshot_path: Path, allow_current_code: bool
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if sys.pycache_prefix is None:
        raise ValueError("Run with an isolated, empty PYTHONPYCACHEPREFIX")
    cache_root = Path(sys.pycache_prefix)
    if cache_root.exists() and any(cache_root.rglob("*.pyc")):
        raise ValueError("PYTHONPYCACHEPREFIX must not contain bytecode before the run")
    campaign = json.loads(campaign_path.read_text())
    snapshot = json.loads(snapshot_path.read_text())
    runtime = snapshot["runtime"]
    runtime_sha = stable_sha256(runtime)
    if snapshot.get("schema_version") != 1 or snapshot.get("runtime_sha256") != runtime_sha:
        raise ValueError("Runtime snapshot digest mismatch")
    persisted_runtime = snapshot.get("persisted_runtime_json")
    persisted_runtime_sha = snapshot.get("persisted_runtime_sha256")
    if not isinstance(persisted_runtime, str) or not isinstance(persisted_runtime_sha, str):
        raise ValueError("Snapshot lacks the original persisted runtime bytes and digest")
    persisted_bytes = persisted_runtime.encode("utf-8")
    if hashlib.sha256(persisted_bytes).hexdigest() != persisted_runtime_sha:
        raise ValueError("Persisted runtime source digest mismatch")
    if json.loads(persisted_bytes) != runtime:
        raise ValueError("Persisted runtime source does not match snapshot runtime")
    if snapshot.get("campaign_id") != campaign["campaign_id"]:
        raise ValueError("Runtime snapshot campaign identity mismatch")
    if runtime.get("campaign_id") != campaign["campaign_id"]:
        raise ValueError("Runtime checkpoint campaign identity mismatch")

    shadow_campaign.verify(campaign, check_code=not allow_current_code)
    if allow_current_code:
        expected_root = Path(__file__).resolve().parents[1] / "packages" / "midas"
        pinned_code = campaign_path.parent / "code" / "midas"
        for relative, expected in campaign["identity"]["code"].items():
            if storage.file_hash(pinned_code / relative) != expected:
                raise ValueError(f"Pinned campaign code mismatch: {relative}")
        # Keep all campaign identity and measurement checks, while permitting
        # the explicitly selected branch implementation under comparison.
        shadow_worker.verify = lambda plan: shadow_campaign.verify(plan, check_code=False)
    else:
        expected_root = campaign_path.parent / "code" / "midas"
    verify_module_roots(expected_root)

    return campaign, runtime, runtime_sha, persisted_runtime_sha


def normalized_research_digest(db: Any) -> tuple[str, int, list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    decision_index: dict[str, int] = {}
    for kind, body in db.execute(
        "select kind,body from events where kind in ('decision','decision_committed','followup') order by seq"
    ):
        row = json.loads(zlib.decompress(body))
        if kind == "decision":
            decision_index[row.pop("id")] = len(decision_index)
        elif kind == "decision_committed":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
        elif kind == "followup":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
        normalized.append({"kind": kind, "row": row})
    return stable_sha256(normalized), len(normalized), normalized


def run_once(
    campaign: dict[str, Any],
    runtime: dict[str, Any],
    runtime_sha: str,
    segment_target: int,
    include_research_events: bool,
    include_final_runtime: bool,
) -> dict[str, Any]:
    identity = campaign["identity"]
    raw_root = Path(identity["raw_root"])
    cursor = copy.deepcopy(runtime["cursor"])
    stem = cursor["segment"]
    if not stem:
        raise ValueError("Runtime cursor has no finalized source segment")
    sealed_path = raw_root / f"{stem}.seg"
    if (
        not sealed_path.is_file()
        or sealed_path.is_symlink()
        or (raw_root / f"{stem}.open").exists()
    ):
        raise ValueError("Benchmark cursor must point into a finalized regular segment")

    prior_clock = runtime.get("context", {}).get("clock")
    wall_now = [int(prior_clock[0]) if prior_clock else 0]
    mono_now = [int(prior_clock[1]) if prior_clock else 0]
    real_time_ns = time.time_ns
    real_monotonic = time.monotonic
    real_monotonic_ns = time.monotonic_ns
    time.time_ns = lambda: wall_now[0]
    # Shadow.save() and Tail.refresh() use the float monotonic API. Keep those
    # cadence checks on the same recorded clock as the nanosecond API; using
    # the host clock makes a faster implementation save less often and can
    # change the provenance histories emitted into decisions.
    time.monotonic = lambda: mono_now[0] / 10**9
    time.monotonic_ns = lambda: mono_now[0]
    try:
        with tempfile.TemporaryDirectory(prefix="veritas-shadow-consume-") as temp_dir:
            worker = Shadow(Path(temp_dir), campaign)
            verify_module_roots(Path(shadow_worker.__file__).resolve().parents[1])
            worker.ctx = Context.restore(copy.deepcopy(runtime["context"]))
            worker.tail.close()
            worker.tail = Tail(raw_root, cursor)
            worker.next_decision = copy.deepcopy(runtime["next_decision"])
            worker.next_observation = copy.deepcopy(runtime["next_observation"])
            worker.counters = copy.deepcopy(runtime["counters"])
            worker.pending = worker.journal.pending(identity["horizons_ms"])
            worker.status = "WARMING_OR_LAGGED_SOURCE"
            worker.last_clock = None
            worker.last_save = time.monotonic()

            first_ordinal: int | None = None
            last_ordinal: int | None = None
            records = frames = 0
            cpu_start = time.process_time()
            wall_start = time.perf_counter()
            try:
                while len(worker.tail.verified_seals) < segment_target:
                    item = worker.tail.next()
                    if item is None:
                        raise ValueError("Finalized source ended before the segment bound")
                    row, ref = item
                    segment_path = raw_root / ref["segment"]
                    if not segment_path.is_file() or segment_path.is_symlink():
                        raise ValueError("Tail returned a non-finalized or unsafe source segment")
                    first_ordinal = first_ordinal if first_ordinal is not None else row["ordinal"]
                    last_ordinal = row["ordinal"]
                    records += 1
                    frames += row["kind"] == "frame"
                    wall_now[0] = row["received_ns"] + 1_000_000
                    mono_now[0] = row["monotonic_ns"] + 1_000_000
                    worker.consume(row, ref)
                    for seal in worker.tail.seals:
                        with worker.journal.db:
                            worker.journal.append("source_segment_sealed", seal)
                    worker.tail.seals.clear()
                    if time.monotonic() - worker.last_save >= 5:
                        aliases = worker.ctx.families.identities()
                        with worker.journal.db:
                            worker.journal.db.executemany(
                                "insert or replace into family_map values(?,?)",
                                [
                                    (key.removeprefix("condition:"), value)
                                    for key, value in aliases.items()
                                    if key.startswith("condition:")
                                ],
                            )
                        totals = worker.journal.summary()
                        if (
                            totals["decisions"] >= identity["max_decisions"]
                            or totals["observations"] >= identity["max_observations"]
                        ):
                            raise ValueError(
                                "Frozen evidence-row limit reached in temporary journal"
                            )
                        worker.save()
                        worker.last_save = time.monotonic()
                worker.save()
                cpu_seconds = time.process_time() - cpu_start
                wall_seconds = time.perf_counter() - wall_start
                summary = worker.journal.summary()
                research_sha, research_events, research_rows = normalized_research_digest(
                    worker.journal.db
                )
                context_sha = stable_sha256(worker.ctx.snapshot())
                result = {
                    "runtime_snapshot_sha256": runtime_sha,
                    "start_cursor": runtime["cursor"],
                    "first_ordinal": first_ordinal,
                    "last_ordinal": last_ordinal,
                    "records": records,
                    "frames": frames,
                    "sealed_segments_verified": len(worker.tail.verified_seals),
                    "engine_state_sha256": worker.ctx.engine.digest(),
                    "context_state_sha256": context_sha,
                    "decision_count": summary["decisions"],
                    "observation_count": summary["observations"],
                    "followup_status_counts": summary["followups"],
                    "research_event_count": research_events,
                    "research_semantics_sha256": research_sha,
                    "source_ordinal_end": worker.tail.cursor["ordinal"],
                    "cpu_seconds": cpu_seconds,
                    "wall_seconds": wall_seconds,
                    "max_rss_bytes_process": process_peak_rss_bytes(),
                }
                if include_research_events:
                    result["research_semantics_rows"] = research_rows
                if include_final_runtime:
                    result["_final_runtime"] = worker.runtime()
                return result
            finally:
                worker.tail.close()
                worker.journal.close()
    finally:
        time.time_ns = real_time_ns
        time.monotonic = real_monotonic
        time.monotonic_ns = real_monotonic_ns


def main() -> None:
    args = parse_args()
    if args.segments <= 0 or args.repetitions <= 0:
        raise SystemExit("--segments and --repetitions must be positive")
    campaign, runtime, runtime_sha, persisted_runtime_sha = read_inputs(
        args.campaign, args.runtime_snapshot, args.allow_current_code
    )
    results = [
        run_once(
            campaign,
            runtime,
            runtime_sha,
            args.segments,
            args.include_research_events,
            args.runtime_snapshot_output is not None,
        )
        for _ in range(args.repetitions)
    ]
    if args.runtime_snapshot_output is not None:
        runtime_output = results[-1].pop("_final_runtime")
        persisted_runtime = storage.canonical(runtime_output)
        # Canonical JSON stringifies integer mapping keys. Hash the same
        # normalized object that a later JSON reader will restore.
        snapshot_runtime = json.loads(persisted_runtime)
        snapshot = {
            "schema_version": 1,
            "campaign_id": campaign["campaign_id"],
            "runtime": snapshot_runtime,
            "runtime_sha256": stable_sha256(snapshot_runtime),
            "persisted_runtime_json": persisted_runtime.decode("utf-8"),
            "persisted_runtime_sha256": hashlib.sha256(persisted_runtime).hexdigest(),
        }
        args.runtime_snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_snapshot_output.write_bytes(stable_json(snapshot))
    output = {
        "schema_version": 1,
        "implementation_module": str(Path(shadow_worker.__file__).resolve()),
        "implementation_modules": {
            "shadow_campaign": str(Path(shadow_campaign.__file__).resolve()),
            "shadow_source": str(Path(shadow_source.__file__).resolve()),
            "shadow_worker": str(Path(shadow_worker.__file__).resolve()),
            "storage": str(Path(storage.__file__).resolve()),
        },
        "python_bytecode_cache_prefix": sys.pycache_prefix,
        "implementation_code_hashes_checked_against_campaign": not args.allow_current_code,
        "pinned_campaign_code_verified": True,
        "campaign_id": campaign["campaign_id"],
        "campaign_identity_sha256": stable_sha256(campaign["identity"]),
        "runtime_snapshot_sha256": runtime_sha,
        "persisted_runtime_sha256": persisted_runtime_sha,
        "segment_target": args.segments,
        "repetitions": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stable_json(output))
    printable = copy.deepcopy(output)
    for repetition in printable["repetitions"]:
        repetition.pop("research_semantics_rows", None)
    print(json.dumps(printable, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
