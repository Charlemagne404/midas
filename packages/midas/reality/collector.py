"""Bounded public capture independent of the API and research stores."""

import asyncio
import json
import logging
import signal
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .config import Config
from .discovery import GAMMA, WS, select
from .replay import replay
from .storage import Store, atomic_json, manifest


async def run(config: Config, duration: float | None = None) -> None:
    root = Path(config.root)
    store = Store(
        root,
        budget=config.budget_bytes,
        reserve=config.reserve_bytes,
        segment_bytes=config.segment_bytes,
        segment_seconds=config.segment_seconds,
    )
    engine, _ = replay(root, manifest(root))
    oldest_ns = time.time_ns()
    oldest = next(iter(manifest(root)["segments"]), None)
    if oldest:
        from .storage import records

        first, _ = next(records(root / oldest["file"]))
        oldest_ns = first["received_ns"]
        if time.time_ns() - first["received_ns"] > config.retention_days * 86400 * 1e9:
            store.close()
            raise OSError(
                "Retention horizon reached; export/archive this root and configure a new root"
            )

    def append(kind: str, payload: Any, **metadata: Any) -> dict[str, Any]:
        if time.time_ns() - oldest_ns > config.retention_days * 86400 * 1e9:
            raise OSError("Retention horizon reached; archive recording root")
        began = time.monotonic()
        record = store.append(kind, payload, **metadata)
        engine.consume(record)
        status["max_append_seconds"] = max(
            status.get("max_append_seconds", 0), time.monotonic() - began
        )
        return record

    def report() -> None:
        state = engine.state()
        now = time.time_ns()
        books = state["books"]
        fresh = sum(
            b["internally_consistent"] and now - b["received_ns"] < config.stale_seconds * 1e9
            for b in books.values()
        )
        atomic_json(
            root / "status.json",
            dict(
                status,
                updated_ns=now,
                ordinal=store.ordinal,
                storage_bytes=store.used,
                counts=state["counts"],
                gaps=engine.gaps,
                fresh_books=fresh,
                expected_books=status["markets"] * 2,
                state_sha256=engine.digest(),
                sequence_verified=False,
            ),
        )

    stop = asyncio.Event()
    rotate = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    loop.add_signal_handler(signal.SIGUSR1, rotate.set)
    started = time.monotonic()
    last_report = last_checkpoint = started
    status: dict[str, Any] = dict(
        state="STARTING",
        started_ns=time.time_ns(),
        frames=0,
        failures=0,
        markets=0,
        last_observation_ns=None,
        config=config.dump(),
    )
    atomic_json(root / "config.json", config.dump())
    backoff = 1
    try:
        append(
            "gap",
            dict(
                reason="process_start",
                recovered=store.recovered,
                stale_ns=int(config.stale_seconds * 1e9),
            ),
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            while not stop.is_set() and (duration is None or time.monotonic() - started < duration):
                connection, subscription = uuid.uuid4().hex, uuid.uuid4().hex
                try:
                    response = await client.get(
                        GAMMA + "/markets",
                        params=dict(
                            active="true",
                            closed="false",
                            limit=config.discovery_limit,
                            order="liquidityNum",
                            ascending="false",
                        ),
                    )
                    response.raise_for_status()
                    cohort, rejected = select(response.json(), config.markets)
                    append(
                        "discovery",
                        response.text,
                        cohort=cohort,
                        rejected=rejected,
                        selection="liquidity-page/volume24hr/id",
                        connection=connection,
                        subscription=subscription,
                    )
                    if not cohort:
                        raise ValueError("No supported active markets discovered")
                    tokens = [token for market in cohort for token in market["tokens"]]
                    status.update(markets=len(cohort), cohort=cohort, state="CONNECTING")
                    async with connect(
                        WS,
                        max_size=4 * 1024**2,
                        max_queue=config.queue_size,
                        open_timeout=20,
                        close_timeout=5,
                        ping_interval=None,
                    ) as ws:
                        frame = json.dumps(
                            dict(type="market", assets_ids=tokens, custom_feature_enabled=True)
                        )
                        await ws.send(frame)
                        append(
                            "subscription", frame, connection=connection, subscription=subscription
                        )
                        connected = last_ping = last_frame = time.monotonic()
                        status["state"] = "AWAITING_DATA"
                        while not stop.is_set():
                            now = time.monotonic()
                            if now - last_report >= 2:
                                report()
                                last_report = now
                            if now - last_checkpoint >= 30 or rotate.is_set():
                                append("checkpoint", dict(state_sha256=engine.digest()))
                                store.rotate()
                                rotate.clear()
                                last_checkpoint = now
                            if any(
                                b["issue"]
                                in {
                                    "top_divergence",
                                    "malformed_event",
                                    "unknown_event",
                                    "timestamp_regression",
                                    "market_resolved",
                                    "stale",
                                }
                                for b in engine.books.values()
                            ):
                                append(
                                    "gap",
                                    dict(reason="book_resynchronization"),
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
                            if now - last_frame > config.stale_seconds:
                                raise TimeoutError(
                                    "Market observations stale; reconnect for fresh snapshots"
                                )
                            try:
                                payload = await asyncio.wait_for(ws.recv(), timeout=1)
                            except TimeoutError:
                                continue
                            received, monotonic = time.time_ns(), time.monotonic_ns()
                            normalized = []
                            try:
                                parsed = json.loads(payload)
                                parsed = parsed if isinstance(parsed, list) else [parsed]
                                normalized = [
                                    dict(
                                        event_type=e.get("event_type", "unknown"),
                                        asset_id=e.get("asset_id"),
                                        market=e.get("market"),
                                        exchange_timestamp=e.get("timestamp"),
                                    )
                                    for e in parsed
                                    if isinstance(e, dict)
                                ]
                            except (ValueError, TypeError, UnicodeDecodeError):
                                pass
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
                            )
                            if payload != "PONG":
                                last_frame = time.monotonic()
                                status.update(
                                    frames=status["frames"] + 1,
                                    last_observation_ns=received,
                                    state="RECORDING_UNSEQUENCED",
                                )
                                backoff = 1
                except (httpx.HTTPError, WebSocketException, ValueError, TimeoutError) as error:
                    status.update(
                        state="DEGRADED",
                        failures=status["failures"] + 1,
                        error=f"{type(error).__name__}: {error}",
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
        status.update(state="FAILED", error=f"{type(error).__name__}: {error}")
        report()
        raise
    finally:
        try:
            append("checkpoint", dict(state_sha256=engine.digest()))
            append("gap", dict(reason="process_stop"))
        finally:
            store.close()
            atomic_json(
                root / "status.json",
                dict(
                    status,
                    state="FAILED" if status["state"] == "FAILED" else "STOPPED",
                    updated_ns=time.time_ns(),
                    ordinal=store.ordinal,
                    storage_bytes=store.used,
                ),
            )
