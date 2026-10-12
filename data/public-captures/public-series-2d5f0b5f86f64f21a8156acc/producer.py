"""Bounded public GET-only observation capture; no executions or empirical fill labels."""

import argparse
import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_bytes, atomic_json, sha256
from midas.core.models import MarketEvent, Source
from midas.laboratory.datasets import create_manifest, validate
from midas.market_data.polymarket import PublicClient, normalize_market, now_ms


def publish_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".capture-publish-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


async def capture(
    root: Path,
    output: Path,
    samples: int = 12,
    interval_seconds: float = 5,
    wall_seconds: int = 180,
    capture_id: str | None = None,
    client: Any = None,
) -> dict[str, Any]:
    if not 2 <= samples <= 120 or not 5 <= interval_seconds <= 60 or not 30 <= wall_seconds <= 1800:
        raise ValueError("Use 2–120 polls, 5–60 second intervals and 30–1800 second wall budget")
    identity = capture_id or "public-series-" + uuid.uuid4().hex[:24]
    if not identity.replace("-", "").isalnum() or len(identity) > 80:
        raise ValueError("Invalid capture identity")
    directory = root / identity
    directory.mkdir(parents=True, exist_ok=False)
    state: dict[str, Any] = {
        "capture_id": identity,
        "state": "RUNNING",
        "created_at": time.time(),
        "samples_requested": samples,
        "samples_completed": 0,
        "events": 0,
        "interval_seconds": interval_seconds,
        "wall_seconds": wall_seconds,
        "byte_cap": 16 * 1024 * 1024,
        "producer_sha256": sha256(Path(__file__)),
        "execution_labels_available": False,
        "pid": os.getpid(),
    }
    atomic_bytes(directory / "producer.py", Path(__file__).read_bytes())
    atomic_json(directory / "state.json", state)
    transport = client or PublicClient()
    staging = directory / "observations.jsonl"
    began = time.monotonic()
    byte_count = 0

    def append(event: MarketEvent) -> None:
        nonlocal byte_count
        payload = (event.model_dump_json() + "\n").encode()
        if byte_count + len(payload) > state["byte_cap"]:
            raise ValueError("Observation byte budget exceeded")
        with staging.open("ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        byte_count += len(payload)
        state["events"] += 1

    try:
        async with asyncio.timeout(wall_seconds):
            raw_markets, wire = await transport.discover_wire(20)
            if len(wire.encode()) > state["byte_cap"]:
                raise ValueError("Discovery response byte budget exceeded")
            atomic_bytes(directory / "discovery.json", wire.encode())
            market = None
            selected_raw = None
            for raw in raw_markets:
                try:
                    candidate = normalize_market(raw)
                except (ValueError, KeyError, TypeError):
                    continue
                if (
                    candidate.active
                    and not candidate.closed
                    and candidate.accepting_orders
                    and len(candidate.instruments) == 2
                    and candidate.complementary_verified
                ):
                    market, selected_raw = candidate, raw
                    break
            if market is None:
                raise ValueError("No supported active complementary market in bounded discovery")
            append(
                MarketEvent(
                    event_id=identity + ":metadata",
                    kind="public_metadata",
                    source=Source.LIVE,
                    received_ts_ms=now_ms(),
                    raw={"market": market.model_dump(mode="json"), "gamma": selected_raw},
                    raw_wire_json=wire,
                )
            )
            state["market_id"] = market.id
            hashes: dict[str, set[str]] = {i.asset_id: set() for i in market.instruments}
            last_poll = time.monotonic()
            for index in range(samples):
                if index:
                    await asyncio.sleep(max(0, interval_seconds - (time.monotonic() - last_poll)))
                last_poll = time.monotonic()
                for instrument in market.instruments:
                    book, raw_book, raw_wire = await transport.book(
                        instrument.asset_id, market.condition_id
                    )
                    append(
                        MarketEvent(
                            event_id=f"{identity}:poll:{index}:{instrument.asset_id}",
                            kind="book",
                            source=Source.LIVE,
                            received_ts_ms=book.received_ts_ms,
                            exchange_ts_ms=book.exchange_ts_ms,
                            asset_id=book.asset_id,
                            raw=raw_book,
                            raw_wire_json=raw_wire,
                            book=book,
                        )
                    )
                    # Quote diversity excludes receipt clocks, not changes in exchange book content.
                    from midas.economics.attestation import digest

                    hashes[instrument.asset_id].add(
                        digest(
                            {
                                "asks": [v.model_dump(mode="json") for v in book.asks],
                                "bids": [v.model_dump(mode="json") for v in book.bids],
                            }
                        )
                    )
                state["samples_completed"] = index + 1
                state["elapsed_seconds"] = time.monotonic() - began
                atomic_json(directory / "state.json", state)
            manifest = create_manifest(
                staging,
                identity,
                "Polymarket bounded public REST book series",
                (market,),
                (
                    "Periodic REST snapshots are not a continuous or sequence-complete feed.",
                    "Two instrument requests are sequential; snapshots are not atomic across legs.",
                    "No observed fills, private order reports, settlement or empirical execution labels.",
                    "Public metadata is not an onchain payout attestation; no attested_metadata event emitted.",
                    "Single selected market and short interval; not representative independent market history.",
                ),
            )
            evidence = validate(staging, manifest)
            publish_exclusive(output / f"{identity}.jsonl", staging.read_bytes())
            publish_exclusive(
                output / f"{identity}.manifest.json", manifest.model_dump_json(indent=2).encode()
            )
            state.update(
                state="COMPLETED",
                completed_at=time.time(),
                validation=evidence,
                dataset_id=identity,
                content_sha256=manifest.content_sha256,
                unique_quote_books_by_asset={k: len(v) for k, v in hashes.items()},
                capture_start_ms=manifest.capture_start_ms,
                capture_end_ms=manifest.capture_end_ms,
            )
    except BaseException as error:
        state.update(
            state="FAILED", error=f"{type(error).__name__}: {error}", completed_at=time.time()
        )
        raise
    finally:
        state["elapsed_seconds"] = time.monotonic() - began
        atomic_json(directory / "state.json", state)
        await transport.close()
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/public-captures"))
    parser.add_argument("--output", type=Path, default=Path("data/datasets"))
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--interval-seconds", type=float, default=5)
    parser.add_argument("--wall-seconds", type=int, default=180)
    parser.add_argument("--capture-id")
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                capture(
                    args.root,
                    args.output,
                    args.samples,
                    args.interval_seconds,
                    args.wall_seconds,
                    args.capture_id,
                )
            ),
            indent=2,
        )
    )
