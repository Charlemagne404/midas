"""Bounded public capture independent of the API and research stores."""

import asyncio
import hashlib
import json
import logging
import math
import signal
import time
import uuid
from collections import Counter, deque
from decimal import DecimalException
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from . import recovery
from .config import Config
from .discovery import GAMMA, WS, select
from .observation import discover, independent_book
from .quality import clock_health, compare
from .resources import MIN_HEADROOM_BYTES
from .resources import snapshot as resource_snapshot
from .storage import Store, atomic_json, manifest
from .transport import bounded_get


class StorageFailure(RuntimeError):
    """Persistence failure is terminal; never continue an unrecorded stream."""


APPEND_BACKPRESSURE_SECONDS = 1.0
APPEND_LATENCY_WINDOW_NS = 60 * 1_000_000_000
# The Reality API marks status older than 30 seconds stale; failures report immediately.
STATUS_REPORT_INTERVAL_SECONDS = 10.0


def collection_health(
    state: str,
    last_observation_ns: int | None,
    fresh_books: int,
    expected_books: int,
    now_ns: int,
    stale_ns: int,
    backpressured: bool = False,
    transport_backpressured: bool = False,
) -> str:
    if state == "FAILED":
        return "failed"
    if state == "STOPPED":
        return "stopped"
    if state == "STARTING":
        return "recovering"
    if state == "AWAITING_DATA":
        return "resynchronizing"
    if state in {"CONNECTING", "DEGRADED", "RECONNECTING"}:
        return "reconnecting"
    if last_observation_ns is None:
        return "active_no_events"
    if now_ns - last_observation_ns >= stale_ns or fresh_books != expected_books:
        return "stale"
    if transport_backpressured:
        return "transport_backpressured"
    if backpressured:
        return "backpressured"
    return "active_receiving"


def transport_queue_depth(websocket: Any) -> int | None:
    """Return buffered WebSocket frames when the installed library exposes them."""
    try:
        depth = len(websocket.recv_messages.frames)
    except (AttributeError, TypeError):
        return None
    return depth if isinstance(depth, int) and depth >= 0 else None


def sample_transport_queue(status: dict[str, Any], websocket: Any, bound: int) -> None:
    """Publish a current queue sample without treating unknown telemetry as empty."""
    depth = transport_queue_depth(websocket)
    status.update(
        transport_queue_observation_available=depth is not None,
        transport_queue_depth=depth,
        transport_queue_saturated=depth is not None and depth >= bound,
        transport_queue_sampled_ns=time.time_ns(),
    )
    if depth is not None:
        status["transport_queue_sample_count"] = status.get("transport_queue_sample_count", 0) + 1
        status["transport_queue_high_water_depth"] = max(
            status.get("transport_queue_high_water_depth", 0), depth
        )


def clear_transport_queue_sample(status: dict[str, Any]) -> None:
    """Mark queue depth unknown when no live WebSocket connection can be sampled."""
    status.update(
        transport_queue_observation_available=False,
        transport_queue_depth=None,
        transport_queue_saturated=False,
        transport_queue_sampled_ns=time.time_ns(),
    )


def append_latency_summary(
    samples: deque[tuple[int, int, int]], now_ns: int, process_started_ns: int
) -> dict[str, Any]:
    """Summarize durable-write and full append latency over the last minute."""
    start_ns = max(process_started_ns, now_ns - APPEND_LATENCY_WINDOW_NS)
    recent = [sample for sample in samples if start_ns <= sample[0] <= now_ns]
    window_seconds = max(0.0, (now_ns - start_ns) / 1e9)
    window_complete = process_started_ns <= now_ns - APPEND_LATENCY_WINDOW_NS
    if len(samples) == samples.maxlen and samples and samples[0][0] > start_ns:
        window_complete = False

    def seconds(values: list[int], quantile: float | None = None) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = -1 if quantile is None else max(0, math.ceil(quantile * len(ordered)) - 1)
        return ordered[index] / 1e9

    durable = [sample[1] for sample in recent]
    appended = [sample[2] for sample in recent]
    return {
        "window_seconds": window_seconds,
        "window_complete": window_complete,
        "sample_count": len(recent),
        "max_durable_write_seconds": seconds(durable),
        "p95_durable_write_seconds": seconds(durable, 0.95),
        "max_append_seconds": seconds(appended),
        "p95_append_seconds": seconds(appended, 0.95),
    }


def prune_cohort_tracking(
    book_updates: Counter[str],
    coverage_started: dict[str, int],
    coverage_last: dict[str, int],
    active_assets: set[str],
) -> None:
    """Keep per-asset coverage counters bounded to the current market cohort."""
    for tracker in (book_updates, coverage_started, coverage_last):
        for asset in tuple(tracker):
            if asset not in active_assets:
                del tracker[asset]


def frame_metadata(payload: str | bytes) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    """Bound decoded-frame lifetime to this call, before any transport await.

    Engine consumes the durable raw payload independently; metadata/constraints
    share one parse. No decoded depth arrays escape into the collector loop.
    """
    normalized: list[dict[str, Any]] = []
    constraints: list[dict[str, str]] = []
    try:
        parsed = json.loads(payload)
    except (ValueError, TypeError, UnicodeDecodeError):
        return normalized, constraints, False
    events = parsed if isinstance(parsed, list) else [parsed]
    normalized = [
        dict(
            event_type=e.get("event_type", "unknown"),
            asset_id=e.get("asset_id"),
            market=e.get("market"),
            exchange_timestamp=e.get("timestamp"),
        )
        for e in events
        if isinstance(e, dict)
    ]
    try:
        from .reconstruction import number

        for event in events:
            if (
                isinstance(event, dict)
                and event.get("event_type") == "book"
                and "tick_size" in event
            ):
                tick = number(event["tick_size"], price=True)
                if tick > 0:
                    constraints.append(dict(asset_id=event["asset_id"], tick_size=str(tick)))
    except (ValueError, TypeError, KeyError, DecimalException):
        return normalized, constraints, True
    return normalized, constraints, False


async def run(config: Config, duration: float | None = None) -> None:
    root = Path(config.root)
    store = Store(
        root,
        budget=config.budget_bytes,
        reserve=config.reserve_bytes,
        segment_bytes=config.segment_bytes,
        segment_seconds=config.segment_seconds,
        verify_existing=False,
        defer_open=True,
    )
    startup_began = time.monotonic()
    process_started_ns = time.monotonic_ns()
    last_transport_message = startup_began
    last_market_event = startup_began
    try:
        source_manifest = manifest(root)
        engine, recovery_status = recovery.recover(root, source_manifest)
        if engine.last_ordinal != store.ordinal:
            raise ValueError("Verified replay ordinal differs from the durable segment index")
    except BaseException:
        store.close()
        raise
    oldest_ns = time.time_ns()
    oldest = next((s for s in source_manifest["segments"] if s["count"]), None)
    if oldest:
        from .storage import records

        first, _ = next(records(root / oldest["file"]))
        oldest_ns = first["received_ns"]
        if time.time_ns() - first["received_ns"] > config.retention_days * 86400 * 1e9:
            store.close()
            raise OSError(
                "Retention horizon reached; export/archive this root and configure a new root"
            )
    del source_manifest
    store.activate()

    append_samples: deque[dict[str, int]] = deque(maxlen=1024)
    append_latency_samples: deque[tuple[int, int, int]] = deque(maxlen=4096)
    slow_append_timestamps: deque[int] = deque()
    book_updates: Counter[str] = Counter()
    coverage_started: dict[str, int] = {}
    coverage_last: dict[str, int] = {}
    comparison_task: asyncio.Task[dict[str, Any]] | None = None
    last_comparison = 0.0
    comparison_index = 0
    active_websocket: Any | None = None

    def append(kind: str, payload: Any, **metadata: Any) -> dict[str, Any]:
        if time.time_ns() - oldest_ns > config.retention_days * 86400 * 1e9:
            raise StorageFailure("Retention horizon reached; archive recording root")
        began = time.monotonic()
        began_ns = time.monotonic_ns()
        try:
            record = store.append(kind, payload, **metadata)
        except OSError as error:
            raise StorageFailure(str(error)) from error
        status.setdefault("first_new_durable_record_ns", time.time_ns())
        status.setdefault(
            "seconds_until_first_new_durable_record", time.monotonic() - startup_began
        )
        persisted_ns = time.monotonic_ns()
        engine.consume(record)
        processed_ns = time.monotonic_ns()
        append_latency_samples.append(
            (processed_ns, persisted_ns - began_ns, processed_ns - began_ns)
        )
        if kind == "frame":
            status.setdefault("first_frame_received_ns", record["received_ns"])
            append_samples.append(
                dict(
                    ordinal=record["ordinal"],
                    received_monotonic_ns=record["monotonic_ns"],
                    persistence_begin_monotonic_ns=began_ns,
                    persistence_completed_monotonic_ns=persisted_ns,
                    reconstruction_completed_monotonic_ns=processed_ns,
                )
            )
            for asset, book in engine.books.items():
                if book["last"][0] == record["ordinal"]:
                    book_updates[asset] += 1
                    coverage_started.setdefault(asset, record["received_ns"])
                    coverage_last[asset] = record["received_ns"]
        append_seconds = time.monotonic() - began
        status["process_max_append_seconds"] = max(
            status.get("process_max_append_seconds", 0), append_seconds
        )
        durable_seconds = (persisted_ns - began_ns) / 1e9
        status["process_max_persist_seconds"] = max(
            status.get("process_max_persist_seconds", 0), durable_seconds
        )
        if append_seconds >= APPEND_BACKPRESSURE_SECONDS:
            status["process_backpressure_events"] += 1
        while (
            slow_append_timestamps
            and slow_append_timestamps[0] < processed_ns - APPEND_LATENCY_WINDOW_NS
        ):
            slow_append_timestamps.popleft()
        if append_seconds >= APPEND_BACKPRESSURE_SECONDS:
            slow_append_timestamps.append(processed_ns)
        status["backpressure_active"] = bool(slow_append_timestamps)
        return record

    def save_recovery() -> None:
        # Reserve the full bounded temporary file, including while the previous
        # checkpoint still exists. Raw append durability has priority.
        import shutil

        if (
            store.used + recovery.MAX_CHECKPOINT_BYTES > store.budget
            or shutil.disk_usage(root).free < store.reserve + recovery.MAX_CHECKPOINT_BYTES
        ):
            status["recovery_checkpoint_error"] = "insufficient_checkpoint_disk_budget"
            return
        began = time.monotonic()
        path = root / recovery.CHECKPOINT_NAME
        old_size = path.stat().st_size if path.exists() else 0
        try:
            size = recovery.save(root, engine, manifest(root))
            store.used += size - old_size
            status.pop("recovery_checkpoint_error", None)
            status["recovery_checkpoint_ordinal"] = engine.last_ordinal
        except (OSError, ValueError) as error:
            status["recovery_checkpoint_error"] = f"{type(error).__name__}: {error}"
        status["process_recovery_checkpoint_seconds"] = time.monotonic() - began

    def report() -> None:
        state = engine.state(max_depth=50)
        now = time.time_ns()
        latency_now_ns = time.monotonic_ns()
        if active_websocket is not None:
            sample_transport_queue(status, active_websocket, config.queue_size)
        latency = append_latency_summary(append_latency_samples, latency_now_ns, process_started_ns)
        while (
            slow_append_timestamps
            and slow_append_timestamps[0] < latency_now_ns - APPEND_LATENCY_WINDOW_NS
        ):
            slow_append_timestamps.popleft()
        status["persistence_latency_window_seconds"] = APPEND_LATENCY_WINDOW_NS / 1e9
        status["persistence_latency_window_covered_seconds"] = latency["window_seconds"]
        status["persistence_latency_window_complete"] = latency["window_complete"]
        status["recent_append_sample_count"] = latency["sample_count"]
        status["recent_max_append_seconds"] = latency["max_append_seconds"]
        status["recent_p95_append_seconds"] = latency["p95_append_seconds"]
        status["recent_max_persist_seconds"] = latency["max_durable_write_seconds"]
        status["recent_p95_persist_seconds"] = latency["p95_durable_write_seconds"]
        status["backpressure_window_seconds"] = APPEND_LATENCY_WINDOW_NS / 1e9
        status["backpressure_active"] = bool(slow_append_timestamps)
        books = state["books"]
        fresh = sum(
            b["internally_consistent"] and now - b["received_ns"] < config.stale_seconds * 1e9
            for b in books.values()
        )
        stale_book_ids = [
            asset
            for asset, book in books.items()
            if not book["internally_consistent"]
            or now - book["received_ns"] >= config.stale_seconds * 1e9
        ]
        timing_uncertain = sum(bool(b.get("timing_uncertainty")) for b in books.values())
        try:
            resources = resource_snapshot()
            margin = resources["memory_high_margin_bytes"]
            status["resource_constrained"] = margin is not None and margin < MIN_HEADROOM_BYTES
            status["resources"] = resources
        except (OSError, ValueError, StopIteration):
            status["resource_metrics_available"] = False
        atomic_json(
            root / "status.json",
            dict(
                status,
                state=(
                    "DEGRADED_BOOKS"
                    if status["state"] == "RECORDING_UNSEQUENCED" and fresh != status["markets"] * 2
                    else "DEGRADED_SOURCE_TIMING"
                    if status["state"] == "RECORDING_UNSEQUENCED" and timing_uncertain
                    else status["state"]
                ),
                timing_uncertain_books=timing_uncertain,
                updated_ns=now,
                ordinal=store.ordinal,
                storage_bytes=store.used,
                process_frames=status["process_frames"],
                lifetime_frames=store.counts["frame"],
                lifetime_gap_records=store.counts["gap"],
                lifetime_records=sum(store.counts.values()),
                lifetime_record_counts=dict(store.counts),
                collection_health=collection_health(
                    status["state"],
                    status["last_observation_ns"],
                    fresh,
                    status["markets"] * 2,
                    now,
                    int(config.stale_seconds * 1e9),
                    status["backpressure_active"],
                    status.get("transport_queue_saturated") is True,
                ),
                counts=state["counts"],
                gaps=engine.gaps,
                fresh_books=fresh,
                expected_books=status["markets"] * 2,
                stale_book_count=len(stale_book_ids),
                stale_book_asset_ids=stale_book_ids,
                book_freshness_basis=(
                    "age since last per-token market update; a quiet book is not proof of loss or completeness"
                ),
                transport_message_age_seconds=max(0, time.monotonic() - last_transport_message),
                market_event_age_seconds=max(0, time.monotonic() - last_market_event),
                state_sha256=engine.digest(),
                sequence_verified=False,
                clock_health=clock_health(),
                books=books,
                observation_coverage={
                    asset: dict(
                        book_update_frames=book_updates[asset],
                        first_received_ns=coverage_started.get(asset),
                        last_received_ns=coverage_last.get(asset),
                    )
                    for asset in engine.tokens
                },
                cross_outcome_skew_ns={
                    m["id"]: max(engine.books[t]["received_ns"] for t in m["tokens"])
                    - min(engine.books[t]["received_ns"] for t in m["tokens"])
                    for m in status.get("cohort", [])
                    if all(t in engine.books for t in m["tokens"])
                },
                transport_queue_bound=config.queue_size,
            ),
        )

    stop = asyncio.Event()
    rotate = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    loop.add_signal_handler(signal.SIGUSR1, rotate.set)
    started = time.monotonic()
    last_report = last_checkpoint = last_recovery_checkpoint = started
    status: dict[str, Any] = dict(
        state="STARTING",
        recovery=recovery_status,
        startup_seconds=time.monotonic() - startup_began,
        event_counter_scope="durable_reconstructed_history",
        transport_queue_unit="websocket_frames",
        transport_queue_bound=config.queue_size,
        transport_queue_observation_available=False,
        transport_queue_depth=None,
        transport_queue_high_water_depth=0,
        transport_queue_sample_count=0,
        transport_queue_saturated=False,
        transport_max_message_bytes=1024**2,
        transport_backpressure="pause_transport_reads; reconnect gaps remain unsequenced",
        started_ns=time.time_ns(),
        frames=store.counts["frame"],
        process_frames=0,
        process_backpressure_events=0,
        backpressure_active=False,
        failures=0,
        markets=0,
        last_observation_ns=None,
        config=config.dump(),
    )
    atomic_json(root / "config.json", config.dump())
    backoff = 1
    try:
        # Bootstrap the accelerator once from the fully verified pre-start boundary.
        save_recovery()
        append(
            "gap",
            dict(
                reason="process_start",
                reconstruction_version=5,
                clock_health=clock_health(),
                recovered=store.recovered,
                stale_ns=int(config.stale_seconds * 1e9),
                config=config.dump(),
                implementation_sha256=hashlib.sha256(
                    b"".join(
                        p.name.encode() + p.read_bytes()
                        for p in sorted(Path(__file__).parent.glob("*.py"))
                    )
                ).hexdigest(),
            ),
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            while not stop.is_set() and (duration is None or time.monotonic() - started < duration):
                connection, subscription = uuid.uuid4().hex, uuid.uuid4().hex
                try:
                    if config.selection_mode == "stratified-v1":
                        update_rates = {}
                        for market in status.get("cohort", []):
                            assets = list(market["tokens"])
                            if all(t in coverage_started for t in assets):
                                seconds = (
                                    time.time_ns() - min(coverage_started[t] for t in assets)
                                ) / 1e9
                                if seconds >= 60:
                                    update_rates[market["id"]] = (
                                        sum(book_updates[t] for t in assets) / seconds
                                    )
                        cohort, selection_audit = await discover(
                            client, config, append, update_rates=update_rates
                        )
                        append(
                            "discovery",
                            json.dumps(dict(page_ordinals=selection_audit["page_ordinals"])),
                            cohort=cohort,
                            selection_audit=selection_audit,
                            selection=selection_audit["version"],
                            connection=connection,
                            subscription=subscription,
                        )
                        status["selection_audit"] = selection_audit
                    else:
                        response = await bounded_get(
                            client,
                            GAMMA + "/markets",
                            append=append,
                            params=dict(
                                active="true",
                                closed="false",
                                limit=config.discovery_limit,
                                order="liquidityNum",
                                ascending="false",
                            ),
                        )
                        try:
                            response.raise_for_status()
                            raw_markets = response.json()
                            if not isinstance(raw_markets, list) or any(
                                not isinstance(m, dict) for m in raw_markets
                            ):
                                raise ValueError("Discovery response must be a market array")
                            cohort, rejected = select(raw_markets, config.markets)
                        except (httpx.HTTPError, ValueError, TypeError):
                            append(
                                "discovery_error",
                                response.text,
                                status_code=response.status_code,
                                connection=connection,
                                subscription=subscription,
                            )
                            raise
                        append(
                            "discovery",
                            response.text,
                            cohort=cohort,
                            rejected=rejected,
                            selection="liquidity-page/volume24hr/id",
                            connection=connection,
                            subscription=subscription,
                        )
                        del response, raw_markets
                    if not cohort:
                        raise ValueError("No supported active markets discovered")
                    tokens = [token for market in cohort for token in market["tokens"]]
                    prune_cohort_tracking(
                        book_updates, coverage_started, coverage_last, set(tokens)
                    )
                    status.update(markets=len(cohort), cohort=cohort, state="CONNECTING")
                    async with connect(
                        WS,
                        max_size=1024**2,
                        max_queue=config.queue_size,
                        open_timeout=20,
                        close_timeout=5,
                        ping_interval=None,
                    ) as ws:
                        active_websocket = ws
                        sample_transport_queue(status, ws, config.queue_size)
                        frame = json.dumps(
                            dict(
                                type="market",
                                assets_ids=tokens,
                                custom_feature_enabled=True,
                                initial_dump=True,
                            )
                        )
                        await ws.send(frame)
                        subscription_record = append(
                            "subscription", frame, connection=connection, subscription=subscription
                        )
                        status["subscription_restored_ns"] = time.time_ns()
                        status.setdefault(
                            "seconds_until_subscription", time.monotonic() - startup_began
                        )
                        connected = last_ping = last_market_event = last_transport_message = (
                            time.monotonic()
                        )
                        pending_snapshots = set(tokens)
                        status["state"] = "AWAITING_DATA"
                        while not stop.is_set():
                            now = time.monotonic()
                            sample_transport_queue(status, ws, config.queue_size)
                            if now - last_report >= STATUS_REPORT_INTERVAL_SECONDS:
                                report()
                                last_report = now
                            if now - last_checkpoint >= 30 or rotate.is_set():
                                if append_samples:
                                    append(
                                        "timing_measurement",
                                        dict(
                                            samples=list(append_samples),
                                            clock_health=clock_health(),
                                            coverage="last <=1024 persisted frames; local process timings only",
                                        ),
                                    )
                                    append_samples.clear()
                                append("checkpoint", dict(state_sha256=engine.digest()))
                                store.rotate()
                                rotate.clear()
                                last_checkpoint = now
                                if (
                                    now - last_recovery_checkpoint
                                    >= recovery.CHECKPOINT_INTERVAL_SECONDS
                                ):
                                    save_recovery()
                                    last_recovery_checkpoint = time.monotonic()
                            if comparison_task is not None and comparison_task.done():
                                result = comparison_task.result()
                                comparison_task = None
                                raw_record = append(
                                    "independent_book",
                                    result["payload"],
                                    received_ns=result["response_ns"],
                                    **{
                                        k: v
                                        for k, v in result.items()
                                        if k not in {"payload", "before", "after", "response_ns"}
                                    },
                                )
                                try:
                                    if result.get("error") or result.get("status_code") != 200:
                                        assessment = dict(
                                            assessment="public_comparison_unavailable",
                                            error=result.get("error"),
                                        )
                                    else:
                                        assessment = compare(
                                            json.loads(result["payload"]),
                                            asset=result["asset"],
                                            condition=result["condition"],
                                            before=result["before"],
                                            after=result["after"],
                                            request_ns=result["request_ns"],
                                            response_ns=result["response_ns"],
                                            stale_ns=int(config.stale_seconds * 1e9),
                                        )
                                    assessment["raw_ordinal"] = raw_record["ordinal"]
                                except (ValueError, TypeError, KeyError, DecimalException) as error:
                                    assessment = dict(
                                        assessment="invalid_public_comparison",
                                        raw_ordinal=raw_record["ordinal"],
                                        error=str(error),
                                    )
                                append("book_comparison", assessment)
                                status["last_book_comparison"] = assessment
                                counts = status.setdefault("book_comparisons", {})
                                label = assessment["assessment"]
                                counts[label] = counts.get(label, 0) + 1
                            if (
                                config.comparison_seconds
                                and comparison_task is None
                                and not pending_snapshots
                                and now - last_comparison >= config.comparison_seconds
                            ):
                                asset = tokens[comparison_index % len(tokens)]
                                comparison_index += 1
                                comparison_task = asyncio.create_task(
                                    independent_book(
                                        client,
                                        engine,
                                        asset,
                                        engine.tokens[asset],
                                        config.comparison_timeout_seconds,
                                        append=append,
                                    )
                                )
                                last_comparison = now
                            if any(
                                b["issue"] == "advertised_top_pending"
                                and time.time_ns() - b["pending_top_advertisement"]["received_ns"]
                                > 2_000_000_000
                                for b in engine.books.values()
                            ):
                                append(
                                    "gap",
                                    dict(
                                        reason="unconfirmed_top_advertisement",
                                        affected_assets={
                                            t: b["pending_top_advertisement"]
                                            for t, b in engine.books.items()
                                            if b["issue"] == "advertised_top_pending"
                                        },
                                    ),
                                    connection=connection,
                                )
                                break
                            if any(
                                b["issue"]
                                in {
                                    "top_divergence",
                                    "malformed_event",
                                    "unknown_event",
                                    "timestamp_regression",
                                    "market_resolved",
                                    "stale",
                                    "gap:malformed_constraints",
                                    "crossed_or_locked",
                                    "malformed_frame",
                                }
                                for asset, b in engine.books.items()
                                if asset not in pending_snapshots
                            ):
                                append(
                                    "gap",
                                    dict(
                                        reason="book_resynchronization",
                                        affected_assets={
                                            t: b["issue"]
                                            for t, b in engine.books.items()
                                            if b["issue"]
                                        },
                                    ),
                                    connection=connection,
                                )
                                break
                            if duration is not None and now - started >= duration:
                                stop.set()
                                break
                            if now - connected >= min(
                                config.refresh_seconds, config.resync_seconds
                            ):
                                append(
                                    "gap", dict(reason="scheduled_refresh"), connection=connection
                                )
                                break
                            if now - last_ping >= 10:
                                await ws.send("PING")
                                last_ping = now
                            if pending_snapshots and now - connected > config.stale_seconds:
                                raise TimeoutError(
                                    "Initial snapshots incomplete; reconnect for fresh books"
                                )
                            if now - last_transport_message > config.stale_seconds:
                                raise TimeoutError("Market WebSocket heartbeat or event stale")
                            try:
                                payload = await asyncio.wait_for(ws.recv(), timeout=1)
                            except TimeoutError:
                                sample_transport_queue(status, ws, config.queue_size)
                                continue
                            sample_transport_queue(status, ws, config.queue_size)
                            last_transport_message = time.monotonic()
                            received, monotonic = time.time_ns(), time.monotonic_ns()
                            normalized, constraints, invalid_constraints = frame_metadata(payload)
                            if isinstance(payload, bytes):
                                import base64

                                payload = base64.b64encode(payload).decode()
                                encoding = "base64"
                            else:
                                encoding = "utf8"
                            append(
                                "heartbeat" if payload == "PONG" else "frame",
                                payload,
                                connection=connection,
                                subscription=subscription,
                                received_ns=received,
                                monotonic_ns=monotonic,
                                encoding=encoding,
                                normalized=normalized,
                                receive_semantics="application_websocket_dequeue_not_hardware_network_arrival",
                            )
                            original_frame_ordinal = store.ordinal
                            for constraint in constraints:
                                append(
                                    "snapshot_constraints",
                                    dict(constraint, raw_ordinal=original_frame_ordinal),
                                    connection=connection,
                                    subscription=subscription,
                                )
                            if invalid_constraints:
                                append(
                                    "gap",
                                    dict(reason="malformed_constraints"),
                                    connection=connection,
                                )
                            for asset in tuple(pending_snapshots):
                                book = engine.books.get(asset)
                                if (
                                    book
                                    and book["snapshot"][0] > subscription_record["ordinal"]
                                    and book["issue"] is None
                                ):
                                    pending_snapshots.remove(asset)
                            if payload != "PONG":
                                last_market_event = time.monotonic()
                                # Keep current health separate from the historical gap
                                # journal: a successful frame clears the prior
                                # connection diagnostic while preserving failures.
                                status.pop("error", None)
                                status.update(
                                    frames=status["frames"] + 1,
                                    process_frames=status["process_frames"] + 1,
                                    last_observation_ns=received,
                                    state="RECORDING_UNSEQUENCED",
                                )
                                if not pending_snapshots:
                                    backoff = 1
                            sample_transport_queue(status, ws, config.queue_size)
                    active_websocket = None
                    clear_transport_queue_sample(status)
                    if comparison_task is not None:
                        comparison_task.cancel()
                        await asyncio.gather(comparison_task, return_exceptions=True)
                        comparison_task = None
                except (
                    httpx.HTTPError,
                    WebSocketException,
                    ValueError,
                    OSError,
                    TimeoutError,
                ) as error:
                    active_websocket = None
                    clear_transport_queue_sample(status)
                    if comparison_task is not None:
                        comparison_task.cancel()
                        await asyncio.gather(comparison_task, return_exceptions=True)
                        comparison_task = None
                    diagnostic = f"{type(error).__name__}: {error}"
                    status.update(
                        state="DEGRADED",
                        failures=status["failures"] + 1,
                        error=diagnostic,
                        last_error=diagnostic,
                        last_error_ns=time.time_ns(),
                    )
                    append(
                        "gap",
                        dict(reason="connection_failure", error=status["error"]),
                        connection=connection,
                    )
                    logging.warning(json.dumps(dict(event="connection_failure", **status)))
                    report()
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=backoff)
                    except TimeoutError:
                        pass
                    backoff = min(60, backoff * 2)
    except BaseException as error:
        diagnostic = f"{type(error).__name__}: {error}"
        status.update(
            state="FAILED",
            error=diagnostic,
            last_error=diagnostic,
            last_error_ns=time.time_ns(),
        )
        report()
        raise
    finally:
        if comparison_task is not None:
            comparison_task.cancel()
            await asyncio.gather(comparison_task, return_exceptions=True)
        try:
            append("checkpoint", dict(state_sha256=engine.digest()))
            append("gap", dict(reason="process_stop"))
        except BaseException:
            status["state"] = "FAILED"
            raise
        finally:
            try:
                if not store.write_failed and status["state"] != "FAILED":
                    store.rotate(reopen=False)
                    save_recovery()
            finally:
                store.close()
            status["state"] = "FAILED" if status["state"] == "FAILED" else "STOPPED"
            report()
