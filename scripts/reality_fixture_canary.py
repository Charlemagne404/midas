"""Run the candidate collector against captured fixtures over loopback only.

This is a deployment canary for the real collector and persistence code. HTTP
responses use an in-process MockTransport, and WebSocket frames come from the
checked-in observed fixture. It never contacts a market provider.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import httpx
from midas.reality import collector, discovery, observation
from midas.reality.config import Config
from midas.reality.panel import select_panel
from midas.reality.replay import replay
from midas.reality.storage import atomic_json, canonical, manifest, read_manifest
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests/fixtures/reality/observed.json"
LOOPBACK_HTTP = "http://127.0.0.1:1"
CGROUP_ROOT = Path("/sys/fs/cgroup")


def source_identity() -> str:
    package = Path(__file__).resolve().parents[1] / "packages/midas/reality"
    return hashlib.sha256(
        b"".join(path.name.encode() + path.read_bytes() for path in sorted(package.glob("*.py")))
    ).hexdigest()


def build_markets(
    fixture: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if fixture is None:
        fixture = json.loads(FIXTURE_PATH.read_text())
    markets = json.loads(fixture["discovery"]["payload"])
    now = datetime.now(UTC)
    token_market: dict[str, dict[str, Any]] = {}
    for index, original in enumerate(markets):
        market = copy.deepcopy(original)
        condition = hashlib.sha256(f"fixture-condition-{index}".encode()).hexdigest()
        tokens = [str(10**70 + index * 2 + 1), str(10**70 + index * 2 + 2)]
        category = f"fixture-category-{index:02d}"
        end = now + timedelta(days=2 if index == 5 else 30)
        market.update(
            id=f"fixture-{index:02d}",
            question=f"Local fixture market {index:02d}",
            conditionId=f"0x{condition}",
            clobTokenIds=tokens,
            outcomes=["Yes", "No"],
            active=True,
            closed=False,
            enableOrderBook=True,
            acceptingOrders=True,
            negRisk=False,
            negRiskMarketID=None,
            negRiskOther=False,
            feesEnabled=True,
            feeSchedule={"takerOnly": True, "rate": "0", "exponent": "1"},
            orderPriceMinTickSize="0.01",
            orderMinSize="1",
            volume24hr=str(1_000_000 - index),
            # This is a synthetic expansion universe, not captured liquidity
            # evidence. Repeat each liquidity stratum so the unchanged panel
            # selector can fill its bounded ten-market configuration.
            liquidityNum=str(
                20_000 if index % 8 == 0 else 100 if index == 2 else 5_000 if index == 1 else 2_000
            ),
            oneDayPriceChange=str((index + 1) / 1000),
            endDate=end.isoformat().replace("+00:00", "Z"),
            endDateIso=end.isoformat().replace("+00:00", "Z"),
            tags=[{"id": f"tag-{index:02d}", "label": category}],
            events=[{"id": f"event-{index:02d}"}],
        )
        for token, outcome in zip(tokens, market["outcomes"], strict=True):
            token_market[token] = {
                "condition": market["conditionId"],
                "outcome": outcome,
                "index": index,
            }
        markets[index] = market
    return markets, token_market


def select_book_template(fixture: dict[str, Any]) -> dict[str, Any]:
    """Select one captured book event from the provider's event-array payload."""
    for frame in fixture.get("frames", []):
        decoded = json.loads(frame["payload"])
        events = decoded if isinstance(decoded, list) else [decoded]
        for event in events:
            if not isinstance(event, dict) or event.get("event_type") != "book":
                continue
            bids, asks = event.get("bids"), event.get("asks")
            if isinstance(bids, list) and bids and isinstance(asks, list) and asks:
                return {"bids": copy.deepcopy(bids), "asks": copy.deepcopy(asks)}
    raise ValueError("Captured fixture contains no book event with both sides populated")


def resource_snapshot() -> dict[str, Any]:
    cgroup = cgroup_directory(Path("/proc/self/cgroup").read_text())
    files = (
        "memory.current",
        "memory.peak",
        "memory.high",
        "memory.max",
        "memory.swap.current",
        "memory.swap.peak",
        "memory.events",
        "memory.pressure",
        "cpu.pressure",
        "io.pressure",
        "cpu.stat",
    )
    values: dict[str, Any] = {}
    if cgroup is not None:
        for name in files:
            file_path = cgroup / name
            if file_path.is_file():
                values[name] = file_path.read_text().strip()
    for name in ("cpu", "memory", "io"):
        pressure_path = Path("/proc/pressure") / name
        if pressure_path.is_file():
            values[f"host_{name}.pressure"] = pressure_path.read_text().strip()
    values["cgroup"] = str(cgroup) if cgroup is not None else None
    return values


def cgroup_directory(contents: str, root: Path = CGROUP_ROOT) -> Path | None:
    """Resolve the unified cgroup-v2 path from ``/proc/self/cgroup``."""
    for line in contents.splitlines():
        hierarchy, separator, path = line.partition("::")
        if hierarchy != "0" or not separator or not path.startswith("/"):
            continue
        relative = Path(path.lstrip("/"))
        if ".." in relative.parts:
            raise ValueError("Invalid cgroup-v2 path")
        return root / relative
    return None


def parse_event_counts(contents: str) -> Counter[str]:
    """Parse cgroup event counters as integers so zero remains false."""
    values: dict[str, int] = {}
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) != 2:
            raise ValueError("Invalid cgroup event counter")
        name, raw_count = fields
        try:
            count = int(raw_count)
        except ValueError as error:
            raise ValueError("Invalid cgroup event counter") from error
        if count < 0:
            raise ValueError("Invalid cgroup event counter")
        values[name] = count
    return Counter(values)


def parse_pressure(contents: str) -> dict[str, dict[str, float]]:
    """Parse Linux pressure-stall averages as percentages."""
    result: dict[str, dict[str, float]] = {}
    for line in contents.splitlines():
        fields = line.split()
        if not fields or fields[0] not in {"some", "full"}:
            raise ValueError("Invalid pressure sample")
        values: dict[str, float] = {}
        for field in fields[1:]:
            name, separator, raw_value = field.partition("=")
            if not separator or name not in {"avg10", "avg60", "avg300", "total"}:
                raise ValueError("Invalid pressure sample")
            try:
                values[name] = float(raw_value)
            except ValueError as error:
                raise ValueError("Invalid pressure sample") from error
        result[fields[0]] = values
    return result


def pressure_peaks(samples: list[dict[str, Any]], name: str) -> dict[str, float | None]:
    parsed = [parse_pressure(sample[name]) for sample in samples if sample.get(name)]
    return {
        f"{kind}_{interval}_max_percent": max(
            (
                pressure[kind][interval]
                for pressure in parsed
                if kind in pressure and interval in pressure[kind]
            ),
            default=None,
        )
        for kind in ("some", "full")
        for interval in ("avg10", "avg60")
    }


def full_book_coverage_seconds(status: dict[str, Any]) -> float | None:
    """Measure post-recovery start-to-first-update coverage for every token."""
    started_ns = status.get("started_ns")
    coverage = status.get("observation_coverage")
    if (
        type(started_ns) is not int
        or started_ns < 0
        or not isinstance(coverage, dict)
        or not coverage
    ):
        return None
    expected_books = status.get("expected_books")
    if type(expected_books) is not int or expected_books <= 0 or len(coverage) != expected_books:
        return None
    first_received_ns: list[int] = []
    for item in coverage.values():
        if not isinstance(item, dict):
            return None
        value = item.get("first_received_ns")
        if not isinstance(value, int) or isinstance(value, bool) or value < started_ns:
            return None
        first_received_ns.append(value)
    return (max(first_received_ns) - started_ns) / 1e9


def fresh_book_count_at_boundary(
    state: dict[str, Any], boundary_ns: int, stale_seconds: float
) -> tuple[int, int]:
    """Count consistent books at the final live record, before shutdown invalidates them."""
    books = state.get("books")
    if not isinstance(books, dict) or type(boundary_ns) is not int or stale_seconds <= 0:
        raise ValueError("Canary lacks a valid pre-shutdown book state")
    fresh = 0
    for book in books.values():
        if not isinstance(book, dict) or book.get("internally_consistent") is not True:
            continue
        received_ns = book.get("received_ns")
        if (
            type(received_ns) is int
            and 0 <= boundary_ns - received_ns < stale_seconds * 1_000_000_000
        ):
            fresh += 1
    return fresh, len(books)


def manifest_record_count(value: dict[str, Any]) -> int:
    """Count durable records from the segment index used by this manifest schema."""
    segments = value.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Canary manifest lacks a segment index")
    total = 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Canary manifest contains an invalid segment record count")
        count = segment.get("count")
        if type(count) is not int or count < 0:
            raise ValueError("Canary manifest contains an invalid segment record count")
        total += count
    return total


async def execute(
    config: Config, duration: float, frame_interval_seconds: float
) -> tuple[list[str], list[dict[str, Any]]]:
    fixture = json.loads(FIXTURE_PATH.read_text())
    markets, token_market = build_markets(fixture)
    template = select_book_template(fixture)
    selected, _ = select_panel(
        markets, config.markets, now_ns=time.time_ns(), seed=config.selection_seed
    )
    if len(selected) != config.markets:
        raise ValueError("Local fixtures did not fill the configured candidate market panel")

    def book(token: str) -> dict[str, Any]:
        item = token_market[token]
        source_timestamp_ms = time.time_ns() // 1_000_000
        return dict(
            market=item["condition"],
            asset_id=token,
            timestamp=str(source_timestamp_ms),
            hash=hashlib.sha256(f"{token}:{source_timestamp_ms}".encode()).hexdigest()[:40],
            bids=template["bids"],
            asks=template["asks"],
            tick_size="0.01",
            event_type="book",
            last_trade_price="0.5",
        )

    by_condition = {market["conditionId"]: market for market in markets}
    unexpected_routes: list[str] = []
    gamma_calls = 0

    def response(request: httpx.Request) -> httpx.Response:
        nonlocal gamma_calls
        if request.url.scheme != "http" or request.url.host != "127.0.0.1":
            unexpected_routes.append(str(request.url))
            return httpx.Response(451, text="Only loopback fixture routes are allowed")
        path = request.url.path
        if path == "/markets":
            gamma_calls += 1
            return httpx.Response(200, json=markets)
        if path.startswith("/markets/"):
            condition = "0x" + path.rsplit("/", 1)[-1].removeprefix("0x")
            market = by_condition.get(condition)
            if market is None:
                return httpx.Response(404, json={"error": "unknown fixture market"})
            return httpx.Response(
                200,
                json={
                    "version": "v1",
                    "condition_id": condition,
                    "tokens": [
                        {"token_id": token, "outcome": outcome}
                        for token, outcome in zip(
                            market["clobTokenIds"], market["outcomes"], strict=True
                        )
                    ],
                    "closed": False,
                    "accepting_orders": True,
                    "neg_risk": False,
                    "tags": [tag["label"] for tag in market["tags"]],
                    "minimum_order_size": "1",
                    "minimum_tick_size": "0.01",
                    "seconds_delay": 0,
                    "end_date_iso": market["endDateIso"],
                },
            )
        if path == "/fee-rate":
            return httpx.Response(200, json={"base_fee": 0})
        if path == "/book":
            token = request.url.params.get("token_id")
            if token not in token_market:
                return httpx.Response(404, json={"error": "unknown fixture token"})
            return httpx.Response(200, json=book(token))
        unexpected_routes.append(str(request.url))
        return httpx.Response(404, json={"error": "unexpected fixture route"})

    async def websocket_handler(socket: Any) -> None:
        try:
            subscription = json.loads(await socket.recv())
            tokens = subscription.get("assets_ids", [])
            if not isinstance(tokens, list) or not set(tokens).issubset(token_market):
                unexpected_routes.append("invalid websocket subscription")
                return
            next_emit = 0.0
            while True:
                now = time.monotonic()
                if now >= next_emit:
                    for token in tokens:
                        await socket.send(json.dumps(book(token), separators=(",", ":")))
                    next_emit = now + frame_interval_seconds
                try:
                    message = await asyncio.wait_for(socket.recv(), timeout=0.25)
                except TimeoutError:
                    continue
                if message == "PING":
                    await socket.send("PONG")
        except ConnectionClosed:
            return
        except Exception as exc:
            unexpected_routes.append(
                f"loopback WebSocket fixture error: {type(exc).__name__}: {exc}"
            )
            return

    samples: list[dict[str, Any]] = []
    done = asyncio.Event()

    async def monitor() -> None:
        while not done.is_set():
            sample = resource_snapshot()
            sample["sampled_monotonic_ns"] = time.monotonic_ns()
            samples.append(sample)
            await asyncio.sleep(1)
        sample = resource_snapshot()
        sample["sampled_monotonic_ns"] = time.monotonic_ns()
        samples.append(sample)

    original_client = httpx.AsyncClient

    def local_http_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(response)
        return original_client(*args, **kwargs)

    async with serve(websocket_handler, "127.0.0.1", 0) as server:
        listener = next(iter(server.sockets), None)
        if listener is None:
            raise RuntimeError("Loopback WebSocket fixture server has no listener")
        port = listener.getsockname()[1]
        with (
            mock.patch.object(httpx, "AsyncClient", local_http_client),
            mock.patch.object(discovery, "GAMMA", LOOPBACK_HTTP),
            mock.patch.object(discovery, "CLOB", LOOPBACK_HTTP),
            mock.patch.object(observation, "GAMMA", LOOPBACK_HTTP),
            mock.patch.object(observation, "CLOB", LOOPBACK_HTTP),
            mock.patch.object(collector, "WS", f"ws://127.0.0.1:{port}"),
        ):
            monitor_task = asyncio.create_task(monitor())
            try:
                await collector.run(config, duration=duration)
            finally:
                done.set()
                await monitor_task
    if unexpected_routes:
        raise ValueError(f"Unexpected non-loopback or unsupported route: {unexpected_routes[0]}")
    if gamma_calls <= 0:
        raise ValueError("Candidate collector did not exercise fixture discovery")
    return unexpected_routes, samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-config", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--duration-seconds", type=float, default=95)
    parser.add_argument("--frame-interval-seconds", type=float, default=5.0)
    parser.add_argument("--markets", type=int)
    parser.add_argument("--canary-config-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    if args.markets is not None and (args.markets < 1 or args.markets > 10):
        raise ValueError("Fixture market count must be between one and ten")
    if not math.isfinite(args.duration_seconds) or args.duration_seconds < 75:
        raise ValueError("Fixture canary must run for at least 75 finite seconds")
    if not math.isfinite(args.frame_interval_seconds) or args.frame_interval_seconds < 0.1:
        raise ValueError("Frame interval must be finite and at least 100 ms")
    workspace = Path(__file__).resolve().parents[1]
    root = args.root.absolute()
    if (
        args.root.is_symlink()
        or root.resolve() != root
        or not root.is_relative_to(workspace / "data/recordings")
    ):
        raise ValueError(
            "Fixture canary data root must be a regular path under candidate recordings"
        )
    if any(
        path.is_symlink()
        for path in (args.candidate_config, args.canary_config_output, args.receipt_output)
    ):
        raise ValueError("Fixture canary input/output paths must not be symlinks")
    for output in (args.canary_config_output, args.receipt_output):
        if (
            output.parent.resolve() != output.parent.absolute()
            or not output.parent.resolve().is_relative_to(workspace)
        ):
            raise ValueError(
                "Fixture canary outputs must use regular paths inside the candidate worktree"
            )
    if args.canary_config_output.absolute() == args.receipt_output.absolute():
        raise ValueError("Fixture canary config and receipt outputs must be different files")
    if args.canary_config_output.exists() or args.receipt_output.exists():
        raise ValueError("Fixture canary config and receipt outputs must be new files")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Fixture canary root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    candidate = Config.load(args.candidate_config)
    market_count = args.markets if args.markets is not None else candidate.markets
    if market_count > candidate.discovery_limit:
        raise ValueError("Fixture market count exceeds the configured discovery bound")
    canary = Config(
        **{
            **candidate.dump(),
            "markets": market_count,
            "root": str(root.resolve()),
            "budget_bytes": 512 * 1024**2,
            "reserve_bytes": 1024**2,
        }
    )
    atomic_json(args.canary_config_output, canary.dump())
    before_source = source_identity()
    started_ns = time.time_ns()
    _, samples = asyncio.run(execute(canary, args.duration_seconds, args.frame_interval_seconds))
    value = manifest(root)
    engine, checkpoints = replay(root, value)
    records = list(read_manifest(root, value))
    status = json.loads((root / "status.json").read_text())
    process_start = next(
        record
        for record in records
        if record["kind"] == "gap" and record["payload"].get("reason") == "process_start"
    )
    process_stop = next(
        (
            record
            for record in reversed(records)
            if record["kind"] == "gap" and record["payload"].get("reason") == "process_stop"
        ),
        None,
    )
    if process_stop is None:
        raise ValueError("Fixture canary lacks its durable process-stop boundary")
    pre_stop_engine, _ = replay(root, value, through=process_stop["ordinal"] - 1)
    pre_stop_fresh_books, pre_stop_expected_books = fresh_book_count_at_boundary(
        pre_stop_engine.state(),
        process_stop["received_ns"],
        canary.stale_seconds,
    )
    gap_reasons = Counter(
        record["payload"].get("reason", "unknown") for record in records if record["kind"] == "gap"
    )
    comparison_counts = Counter(
        record["payload"].get("assessment", "unknown")
        for record in records
        if record["kind"] == "book_comparison"
    )
    if before_source != source_identity():
        raise ValueError("Candidate source changed during the fixture canary")
    if (
        status.get("state") != "STOPPED"
        or status.get("failures") != 0
        or status.get("markets") != canary.markets
        or pre_stop_fresh_books != canary.markets * 2
        or pre_stop_expected_books != canary.markets * 2
        or status.get("sequence_verified") is not False
        or type(status.get("transport_queue_high_water_depth")) is not int
        or type(status.get("transport_queue_sample_count")) is not int
        or status.get("transport_queue_sample_count", 0) < 1
        or process_start["payload"].get("implementation_sha256") != before_source
        or checkpoints < 3
        or status.get("frames", 0) < 20
        or comparison_counts["stable_local_lineage_match_unsequenced"] < 2
        or comparison_counts["stable_local_lineage_divergence"]
        or comparison_counts["invalid_public_comparison"]
        or set(gap_reasons) - {"process_start", "process_stop"}
    ):
        raise ValueError("Candidate fixture canary did not meet the bounded readiness checks")
    coverage_seconds = full_book_coverage_seconds(status)
    if coverage_seconds is None:
        raise ValueError("Candidate fixture canary lacks complete first-book coverage timing")

    def event_map(name: str) -> Counter[str]:
        lines = next((sample.get(name, "") for sample in reversed(samples) if sample.get(name)), "")
        return parse_event_counts(lines)

    event_counts = event_map("memory.events")
    cpu_samples = [
        sample
        for sample in samples
        if sample.get("sampled_monotonic_ns") and sample.get("cpu.stat")
    ]
    cgroup_paths = {sample.get("cgroup") for sample in samples if sample.get("cgroup")}
    if (
        len(cgroup_paths) != 1
        or not event_counts
        or len(cpu_samples) < 2
        or max((int(sample.get("memory.peak", "0")) for sample in samples), default=0) <= 0
        or any(
            not any(sample.get(name) for sample in samples)
            for name in ("cpu.pressure", "io.pressure", "host_cpu.pressure", "host_io.pressure")
        )
    ):
        raise ValueError("Fixture canary lacks complete cgroup memory and CPU accounting")
    if any(event_counts.get(name, 0) for name in ("max", "oom", "oom_kill", "oom_group_kill")):
        raise ValueError("Fixture canary cgroup recorded a hard memory event")
    cpu_seconds = None
    sampled_duration = None
    if len(cpu_samples) >= 2:

        def cpu_usage_usec(sample: dict[str, Any]) -> int:
            values = dict(line.split() for line in sample["cpu.stat"].splitlines())
            return int(values["usage_usec"])

        cpu_seconds = (cpu_usage_usec(cpu_samples[-1]) - cpu_usage_usec(cpu_samples[0])) / 1_000_000
        sampled_duration = (
            cpu_samples[-1]["sampled_monotonic_ns"] - cpu_samples[0]["sampled_monotonic_ns"]
        ) / 1e9
    root_bytes = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    observed_duration = sampled_duration or args.duration_seconds
    observed_frames_per_second = status["frames"] / observed_duration
    durable_bytes_per_second = root_bytes / observed_duration
    manifest_digest = hashlib.sha256(canonical(value)).hexdigest()
    receipt = {
        "schema_version": 1,
        "status": "PASSED",
        "started_ns": started_ns,
        "completed_ns": time.time_ns(),
        "candidate_source_sha256": before_source,
        "fixture_sha256": hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
        "network_mode": "loopback WebSocket plus in-process httpx MockTransport",
        "external_market_requests": 0,
        "root": str(root.resolve()),
        "config": canary.dump(),
        "canary_config": str(args.canary_config_output.resolve()),
        "duration_seconds": args.duration_seconds,
        "frame_interval_seconds": args.frame_interval_seconds,
        "configured_markets": canary.markets,
        "simulated_target_frames_per_second": canary.markets * 2 / args.frame_interval_seconds,
        "observed_frames_per_second": observed_frames_per_second,
        "durable_root_bytes": root_bytes,
        "durable_root_bytes_per_second": durable_bytes_per_second,
        "estimated_durable_gib_per_day": durable_bytes_per_second * 86400 / 1024**3,
        "collector_cpu_seconds": cpu_seconds,
        "collector_sampled_duration_seconds": sampled_duration,
        "collector_cpu_seconds_per_frame": (
            cpu_seconds / status["frames"] if cpu_seconds is not None and status["frames"] else None
        ),
        "segment_count": len(value["segments"]),
        "record_count": manifest_record_count(value),
        "frame_count": status["frames"],
        "market_count": status["markets"],
        "fresh_books": pre_stop_fresh_books,
        "expected_books": pre_stop_expected_books,
        "fresh_book_sample_boundary": "immediately_before_durable_process_stop",
        "stopped_status_fresh_books": status["fresh_books"],
        "pre_stop_fresh_books": pre_stop_fresh_books,
        "pre_stop_expected_books": pre_stop_expected_books,
        "pre_stop_health_sample_ns": process_stop["received_ns"],
        "sequence_verified": status["sequence_verified"],
        "checkpoint_count": checkpoints,
        "gap_reasons": dict(gap_reasons),
        "comparison_counts": dict(comparison_counts),
        "state_sha256": engine.digest(),
        "manifest_sha256": manifest_digest,
        "recovery_status": status.get("recovery_status"),
        "empty_source_startup_seconds": status.get("startup_seconds"),
        "first_new_durable_record_seconds": status.get("seconds_until_first_new_durable_record"),
        "first_frame_after_recovery_seconds": (
            (status["first_frame_received_ns"] - status["started_ns"]) / 1e9
            if type(status.get("first_frame_received_ns")) is int
            and type(status.get("started_ns")) is int
            and status["first_frame_received_ns"] >= status["started_ns"]
            else None
        ),
        "full_book_coverage_seconds": coverage_seconds,
        "persistence_window_complete": status.get("persistence_latency_window_complete"),
        "transport_queue_depth": status.get("transport_queue_depth"),
        "transport_queue_high_water_depth": status.get("transport_queue_high_water_depth"),
        "transport_queue_sample_count": status.get("transport_queue_sample_count"),
        "transport_queue_observation_available": status.get(
            "transport_queue_observation_available"
        ),
        "transport_queue_bound": status.get("transport_queue_bound"),
        "transport_queue_saturated_at_status": status.get("transport_queue_saturated"),
        "cgroup_samples": len(samples),
        "cgroup_peak_bytes": max(
            (int(sample.get("memory.peak", "0")) for sample in samples), default=0
        ),
        "cgroup_memory_events": dict(event_counts),
        "cgroup_cpu_stat": next(
            (sample["cpu.stat"] for sample in reversed(samples) if sample.get("cpu.stat")), None
        ),
        "cgroup_cpu_pressure_peak_percent": pressure_peaks(samples, "cpu.pressure"),
        "cgroup_io_pressure_peak_percent": pressure_peaks(samples, "io.pressure"),
        "host_cpu_pressure_peak_percent": pressure_peaks(samples, "host_cpu.pressure"),
        "host_io_pressure_peak_percent": pressure_peaks(samples, "host_io.pressure"),
        "collector_status": status,
    }
    atomic_json(args.receipt_output, receipt)
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "status",
                    "duration_seconds",
                    "frame_interval_seconds",
                    "segment_count",
                    "record_count",
                    "frame_count",
                    "observed_frames_per_second",
                    "durable_root_bytes",
                    "durable_root_bytes_per_second",
                    "estimated_durable_gib_per_day",
                    "collector_cpu_seconds",
                    "market_count",
                    "fresh_books",
                    "expected_books",
                    "checkpoint_count",
                    "comparison_counts",
                    "state_sha256",
                    "manifest_sha256",
                    "cgroup_peak_bytes",
                    "empty_source_startup_seconds",
                    "first_new_durable_record_seconds",
                    "first_frame_after_recovery_seconds",
                    "full_book_coverage_seconds",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
