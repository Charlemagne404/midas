import hashlib
import json
from pathlib import Path

import pytest
from midas.reality import storage as storage_module
from midas.reality.collector import collection_health, prune_cohort_tracking
from midas.reality.discovery import select
from midas.reality.reconstruction import Engine
from midas.reality.replay import replay
from midas.reality.storage import MAGIC, Store, canonical, manifest, read_manifest

FIXTURE = json.loads((Path(__file__).parent / "fixtures/reality/observed.json").read_text())


def ready():
    e = Engine()
    e.consume(FIXTURE["discovery"])
    e.consume(FIXTURE["frames"][0])
    return e


def event_record(raw, ordinal=100, received_ns=None):
    return dict(
        kind="frame",
        ordinal=ordinal,
        payload=json.dumps(raw),
        received_ns=received_ns or FIXTURE["frames"][1]["received_ns"],
    )


def test_observed_discovery_and_books():
    raw = json.loads(FIXTURE["discovery"]["payload"])
    chosen, rejected = select(raw, 3)
    assert chosen == FIXTURE["discovery"]["cohort"]
    assert len({t for m in chosen for t in m["tokens"]}) == 6
    bad = dict(raw[0], version="v2")
    assert select([bad], 1)[0] == []
    assert "Unsupported" in select([bad], 1)[1][0]["reason"]
    e = ready()
    assert len(e.books) == 6
    assert all(b["internally_consistent"] for b in e.state()["books"].values())
    assert all(not b["sequence_verified"] for b in e.state()["books"].values())
    e.consume(FIXTURE["frames"][1])
    raw = json.loads(FIXTURE["frames"][1]["payload"])
    for change in raw["price_changes"]:
        from decimal import Decimal

        b = e.books[change["asset_id"]]
        assert b["bids" if change["side"] == "BUY" else "asks"][
            Decimal(change["price"])
        ] == Decimal(change["size"])
        assert b["issue"] is None


def test_bounded_status_depth_preserves_full_reconstruction_digest():
    from decimal import Decimal

    engine = ready()
    asset = next(iter(engine.books))
    book = engine.books[asset]
    book["bids"] = {Decimal(i) / 1000: Decimal(i) for i in range(1, 101)}
    book["asks"] = {Decimal(i) / 1000: Decimal(i) for i in range(201, 301)}
    digest_before = engine.digest()

    full = engine.state()["books"][asset]
    status = engine.state(max_depth=50)["books"][asset]

    assert len(full["bids"]) == len(full["asks"]) == 100
    assert status["bids"] == full["bids"][:50]
    assert status["asks"] == full["asks"][:50]
    assert status["bid_depth_levels"] == status["ask_depth_levels"] == 100
    assert status["depth_truncated"] is True
    assert "depth_truncated" not in full
    assert "bid_depth_levels" not in full
    assert engine.digest() == digest_before

    with pytest.raises(ValueError, match="positive integer"):
        engine.state(max_depth=0)


@pytest.mark.parametrize(("reconstruction_version", "last_gap_ordinal"), [(1, 0), (4, 17)])
def test_streaming_digest_matches_canonical_full_state(
    reconstruction_version, last_gap_ordinal, monkeypatch
):
    from decimal import Decimal

    engine = ready()
    engine.reconstruction_version = reconstruction_version
    engine.last_gap_ordinal = last_gap_ordinal
    asset = next(iter(engine.books))
    book = engine.books[asset]
    book["bids"] = {Decimal(i) / 100_000: Decimal(i) for i in range(1, 10_001)}
    book["asks"] = {Decimal(i) / 100_000: Decimal(i) for i in range(20_001, 30_001)}

    expected = hashlib.sha256(canonical(engine.state())).hexdigest()

    def fail_if_full_state_is_materialized(**kwargs):
        raise AssertionError("digest must stream state instead of calling state()")

    monkeypatch.setattr(engine, "state", fail_if_full_state_is_materialized)
    assert engine.digest() == expected


def test_gaps_staleness_unknown_malformed_crossed():
    e = ready()
    e.consume(dict(kind="gap", ordinal=10, received_ns=e.now_ns, payload=dict(reason="disconnect")))
    assert all(b["issue"] == "gap:disconnect" for b in e.books.values())
    e.consume(FIXTURE["frames"][0])
    e.consume(event_record({"event_type": "future_unknown"}))
    assert e.counts["unknown"] == 1
    assert all(b["issue"] == "unknown_event" for b in e.books.values())
    e.consume(FIXTURE["frames"][0])
    e.consume(dict(kind="frame", ordinal=11, received_ns=e.now_ns, payload="bad json"))
    assert e.counts["malformed_frame"] == 1
    e.consume(FIXTURE["frames"][0])
    raw = json.loads(FIXTURE["frames"][1]["payload"])
    raw["price_changes"][0]["price"] = "NaN"
    e.consume(event_record(raw))
    assert e.counts["malformed_event"] == 1
    e = ready()
    e.now_ns += e.stale_ns + 1
    e.invalidate_stale()
    assert all(b["issue"] == "stale" for b in e.books.values())
    e = ready()
    raw = json.loads(FIXTURE["frames"][0]["payload"])[0]
    raw["bids"] = [dict(price="0.99", size="1")]
    e.consume(event_record(raw))
    assert e.counts["crossed"] > 0


def test_duplicate_removal_tick_regression_and_divergence():
    e = ready()
    raw = json.loads(FIXTURE["frames"][1]["payload"])
    change = raw["price_changes"][0]
    raw["price_changes"] = [dict(change, size="0")]
    raw["price_changes"][0].pop("best_bid")
    raw["price_changes"][0].pop("best_ask")
    e.consume(event_record(raw))
    e.consume(event_record(raw, 101))
    assert e.counts["duplicate"] == 1
    from decimal import Decimal

    assert Decimal(change["price"]) not in e.books[change["asset_id"]]["bids"]
    tick = dict(
        event_type="tick_size_change",
        asset_id=change["asset_id"],
        market=raw["market"],
        timestamp=raw["timestamp"],
        new_tick_size="0.001",
    )
    e.consume(event_record(tick, 102))
    assert e.books[change["asset_id"]]["tick"] == "0.001"
    tick["timestamp"] = "1"
    e.consume(event_record(tick, 103))
    assert e.books[change["asset_id"]]["issue"] == "timestamp_regression"
    e = ready()
    e.consume(FIXTURE["frames"][1])
    raw = json.loads(FIXTURE["frames"][0]["payload"])
    # Snapshot with a newer timestamp establishes a fresh lineage and reports drift.
    for book in raw:
        book["timestamp"] = str(int(json.loads(FIXTURE["frames"][1]["payload"])["timestamp"]) + 1)
    e.consume(event_record(raw))
    assert e.counts["snapshot_divergence"] > 0


def test_storage_integrity_rotation_lock_budget_and_replay(tmp_path):
    store = Store(tmp_path, reserve=1, segment_bytes=500)
    with pytest.raises(RuntimeError):
        Store(tmp_path, reserve=1)
    engine = Engine()
    d = FIXTURE["discovery"]
    r = store.append("discovery", d["payload"], cohort=d["cohort"])
    engine.consume(r)
    for f in FIXTURE["frames"]:
        r = store.append("frame", f["payload"], received_ns=f["received_ns"])
        engine.consume(r)
    store.append("checkpoint", dict(state_sha256=engine.digest()))
    store.close()
    m = manifest(tmp_path)
    assert len(m["segments"]) > 1
    first, c = replay(tmp_path, m)
    second, _ = replay(tmp_path, m)
    assert c == 1 and first.digest() == second.digest()
    assert first.counts["book"] == 6
    p = tmp_path / m["segments"][0]["file"]
    data = bytearray(p.read_bytes())
    data[-1] ^= 1
    p.write_bytes(data)
    with pytest.raises(ValueError):
        list(read_manifest(tmp_path, m))
    with pytest.raises(ValueError):
        Store(tmp_path, reserve=1)
    tiny = Store(tmp_path / "tiny", reserve=1, budget=100)
    with pytest.raises(OSError):
        tiny.append("test", {})
    tiny.close()


def test_lifetime_record_counts_survive_store_restart(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("frame", {"raw": "first"})
    store.append("gap", {"reason": "disconnect"})
    store.close()

    resumed = Store(tmp_path, reserve=1)
    assert resumed.counts == {"frame": 1, "gap": 1}
    resumed.append("frame", {"raw": "second"})
    assert resumed.counts["frame"] == 2
    resumed.close()

    restarted = Store(tmp_path, reserve=1)
    assert restarted.counts == {"frame": 2, "gap": 1}
    restarted.close()


def test_manifest_integrity_and_replay_share_one_segment_pass(tmp_path, monkeypatch):
    store = Store(tmp_path, reserve=1)
    store.append("gap", {"reason": "fixture"})
    store.close()
    value = manifest(tmp_path)

    def unexpected_second_pass(_path):
        raise AssertionError("read_manifest must not call standalone hash or describe passes")

    monkeypatch.setattr(storage_module, "file_hash", unexpected_second_pass)
    monkeypatch.setattr(storage_module, "describe", unexpected_second_pass)
    rows = list(read_manifest(tmp_path, value))
    assert len(rows) == 1 and rows[0]["payload"]["reason"] == "fixture"


def test_startup_store_defers_writer_until_verified_replay(tmp_path):
    created = Store(tmp_path, reserve=1)
    created.append("gap", {"reason": "startup"})
    created.close()
    before = {p.name for p in tmp_path.iterdir()}

    store = Store(tmp_path, reserve=1, verify_existing=False, defer_open=True)
    assert store.file is None
    engine, _ = replay(tmp_path, manifest(tmp_path))
    assert engine.last_ordinal == store.ordinal == 1
    assert {p.name for p in tmp_path.iterdir()} == before
    store.activate()
    store.append("gap", {"reason": "after_verified_replay"})
    store.close()


def test_startup_store_does_not_write_after_corrupt_replay(tmp_path):
    created = Store(tmp_path, reserve=1)
    created.append("gap", {"reason": "startup"})
    created.close()
    value = manifest(tmp_path)
    segment = tmp_path / value["segments"][0]["file"]
    data = bytearray(segment.read_bytes())
    data[-1] ^= 1
    segment.write_bytes(data)
    before = {p.name for p in tmp_path.iterdir()}

    store = Store(tmp_path, reserve=1, verify_existing=False, defer_open=True)
    assert store.file is None
    with pytest.raises(ValueError):
        replay(tmp_path, value)
    store.close()
    assert {p.name for p in tmp_path.iterdir()} == before


def test_cohort_tracking_retains_only_active_assets():
    from collections import Counter

    updates = Counter({"old-1": 5, "active-1": 2})
    started = {"old-1": 10, "active-1": 20}
    last = {"old-1": 15, "active-1": 25}
    prune_cohort_tracking(updates, started, last, {"active-1", "active-2"})
    assert updates == {"active-1": 2}
    assert started == {"active-1": 20}
    assert last == {"active-1": 25}


def test_prefix_replay_still_checks_segment_tail_integrity(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("gap", {"reason": "prefix"})
    store.append("gap", {"reason": "tail"})
    store.close()
    value = manifest(tmp_path)
    segment = tmp_path / value["segments"][0]["file"]
    payload = bytearray(segment.read_bytes())
    payload[-1] ^= 1
    segment.write_bytes(payload)

    with pytest.raises(ValueError):
        replay(tmp_path, value, through=1)


@pytest.mark.parametrize(
    (
        "state",
        "last_observation",
        "fresh",
        "expected",
        "now",
        "stale",
        "backpressured",
        "health",
    ),
    [
        ("STARTING", None, 0, 6, 100, 10, False, "recovering"),
        ("RECORDING_UNSEQUENCED", None, 0, 6, 100, 10, False, "active_no_events"),
        ("RECORDING_UNSEQUENCED", 95, 6, 6, 100, 10, False, "active_receiving"),
        ("RECORDING_UNSEQUENCED", 95, 6, 6, 100, 10, True, "backpressured"),
        ("RECORDING_UNSEQUENCED", 80, 6, 6, 100, 10, False, "stale"),
        ("RECORDING_UNSEQUENCED", 80, 6, 6, 100, 10, True, "stale"),
        ("DEGRADED", 95, 6, 6, 100, 10, True, "reconnecting"),
        ("FAILED", 95, 6, 6, 100, 10, False, "failed"),
    ],
)
def test_collection_health_reports_state(
    state, last_observation, fresh, expected, now, stale, backpressured, health
):
    assert (
        collection_health(
            state, last_observation, fresh, expected, now, stale, backpressured=backpressured
        )
        == health
    )


def test_crash_tail_recovery_preserves_complete_records(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("test", {"raw": "original"})
    path = store.path
    store.file.write(b"partial")
    store.file.flush()
    store.file.close()
    store.file = None
    store.lock.close()
    resumed = Store(tmp_path, reserve=1)
    assert resumed.recovered[0]["discarded_partial_bytes"] == 7
    assert path.with_suffix(".tail").read_bytes() == b"partial"
    resumed.append("gap", dict(reason="crash"))
    resumed.close()
    rows = list(read_manifest(tmp_path, manifest(tmp_path)))
    assert rows[0]["payload"] == {"raw": "original"} and rows[1]["ordinal"] == 2
    assert MAGIC == b"MIDASR1\n"


async def test_network_interruption_reconnect_and_safe_stop(tmp_path, monkeypatch):
    import asyncio

    import httpx
    from midas.reality import collector
    from midas.reality.config import Config
    from midas.reality.storage import Store
    from websockets.asyncio.server import serve

    connections = []

    async def handler(ws):
        subscription = json.loads(await ws.recv())
        connections.append(subscription)
        await ws.send(FIXTURE["frames"][0]["payload"])
        await ws.send("PONG")
        if len(connections) == 1:
            await ws.close()
        else:
            await asyncio.sleep(2)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=FIXTURE["discovery"]["payload"])
        )
    )
    monkeypatch.setattr(collector.httpx, "AsyncClient", lambda **kwargs: client)
    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setattr(collector, "WS", f"ws://127.0.0.1:{port}")

        # Config confines production paths; this explicit test subclass uses pytest's root.
        class TestConfig(Config):
            def __post_init__(self):
                pass

        config = TestConfig(root=str(tmp_path), reserve_bytes=1)
        await collector.run(config, duration=2)
    assert len(connections) == 2
    assert connections[0]["assets_ids"] == connections[1]["assets_ids"]
    rows = list(read_manifest(tmp_path, manifest(tmp_path)))
    assert any(r["kind"] == "gap" and r["payload"]["reason"] == "connection_failure" for r in rows)
    assert not any(
        r["kind"] == "gap" and r["payload"]["reason"] == "malformed_constraints" for r in rows
    )
    latest_frame = None
    for row in rows:
        if row["kind"] == "frame":
            latest_frame = row["ordinal"]
        if row["kind"] == "snapshot_constraints":
            assert row["payload"]["raw_ordinal"] == latest_frame
    engine, checkpoints = replay(tmp_path, manifest(tmp_path))
    assert engine.counts["book"] >= 12 and checkpoints >= 1
    assert json.loads((tmp_path / "status.json").read_text())["state"] == "STOPPED"
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["frames"] == 2
    assert status["process_frames"] == 2
    assert status["lifetime_frames"] == 2
    assert status["lifetime_record_counts"]["frame"] == 2
    resumed = Store(tmp_path, reserve=1)
    resumed.close()


def test_checkpoint_mismatch_and_no_future_state(tmp_path):
    store = Store(tmp_path, reserve=1)
    d = FIXTURE["discovery"]
    store.append("discovery", d["payload"], cohort=d["cohort"])
    store.append("frame", FIXTURE["frames"][0]["payload"])
    store.append("checkpoint", dict(state_sha256="bad"))
    store.close()
    earlier, _ = replay(tmp_path, manifest(tmp_path), through=1)
    assert earlier.books == {}
    with pytest.raises(ValueError, match="Online/replay"):
        replay(tmp_path, manifest(tmp_path))


def test_config_isolation_and_bounds():
    from pathlib import Path

    from midas.reality.config import Config

    assert Path(Config().root) == Path(__file__).resolve().parents[1] / "data/recordings/reality"
    with pytest.raises(ValueError):
        Config(root="/home/charlie/midas/data/laboratory-final")
    with pytest.raises(ValueError):
        Config(markets=11)
    with pytest.raises(ValueError):
        Config(queue_size=1000)


def test_exact_spread_and_malformed_identifier():
    from decimal import Decimal

    from midas.reality.reconstruction import spread

    assert (
        spread(Decimal("0.0000000000000000000000000000000000000001"), Decimal("1"))
        == "0.9999999999999999999999999999999999999999"
    )
    e = ready()
    raw = json.loads(FIXTURE["frames"][1]["payload"])
    raw["price_changes"][0]["asset_id"] = []
    e.consume(event_record(raw))
    assert e.counts["malformed_event"] == 1


def test_crash_before_segment_header_is_complete(tmp_path):
    path = tmp_path / "00000000000000000001-header.open"
    path.write_bytes(MAGIC[:3])
    s = Store(tmp_path, reserve=1)
    assert s.recovered[0]["reason"] == "incomplete_header"
    assert path.with_suffix(".tail").read_bytes() == MAGIC[:3]
    s.append("gap", dict(reason="recovered_header"))
    s.close()
    assert list(read_manifest(tmp_path, manifest(tmp_path)))[0]["ordinal"] == 1


async def test_bounded_transport_burst_is_preserved_under_slow_writes(tmp_path, monkeypatch):
    import asyncio
    import os
    import signal
    import time

    import httpx
    from midas.reality import collector
    from midas.reality.config import Config
    from websockets.asyncio.server import serve

    # Real localhost transport using labeled captured fixtures, not venue observations.
    total = 100

    async def handler(ws):
        await ws.recv()
        for _ in range(total):
            await ws.send(FIXTURE["frames"][0]["payload"])
        await ws.wait_closed()

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=FIXTURE["discovery"]["payload"])
        )
    )
    monkeypatch.setattr(collector.httpx, "AsyncClient", lambda **kwargs: client)
    finished = asyncio.Event()
    persisted = 0
    original_append = collector.Store.append

    def slow_append(self, kind, payload, **metadata):
        nonlocal persisted
        if kind == "frame":
            time.sleep(0.005)
        record = original_append(self, kind, payload, **metadata)
        if kind == "frame":
            persisted += 1
            if persisted == total:
                finished.set()
        return record

    monkeypatch.setattr(collector.Store, "append", slow_append)
    settings = []
    original_connect = collector.connect

    def bounded_connect(uri, **kwargs):
        settings.append(kwargs)
        return original_connect(uri, **kwargs)

    monkeypatch.setattr(collector, "connect", bounded_connect)

    class TestConfig(Config):
        def __post_init__(self):
            pass

    async with serve(handler, "127.0.0.1", 0) as server:
        monkeypatch.setattr(collector, "WS", f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}")
        task = asyncio.create_task(
            collector.run(
                TestConfig(root=str(tmp_path), reserve_bytes=1, queue_size=10), duration=30
            )
        )
        try:
            await asyncio.wait_for(finished.wait(), timeout=20)
        finally:
            os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.wait_for(task, timeout=5)
    rows = list(read_manifest(tmp_path, manifest(tmp_path)))
    frames = [r for r in rows if r["kind"] == "frame"]
    assert len(frames) == total
    assert all(r["payload"] == FIXTURE["frames"][0]["payload"] for r in frames)
    assert settings[0]["max_queue"] == 10 and settings[0]["max_size"] == 1024**2
    engine, checkpoints = replay(tmp_path, manifest(tmp_path))
    assert engine.counts["book"] == total * 6 and checkpoints >= 1


def test_market_closure_and_metadata_turnover():
    engine = ready()
    first_market = FIXTURE["discovery"]["cohort"][0]
    closed_assets = list(first_market["tokens"])
    engine.consume(
        event_record(
            dict(
                event_type="market_resolved",
                assets_ids=closed_assets,
                market=first_market["condition"],
                timestamp="1791965112318",
            )
        )
    )
    assert all(engine.books[a]["issue"] == "market_resolved" for a in closed_assets)
    assert all(b["issue"] is None for a, b in engine.books.items() if a not in closed_assets)
    refreshed = dict(FIXTURE["discovery"], ordinal=101, cohort=FIXTURE["discovery"]["cohort"][1:])
    engine.consume(refreshed)
    assert not set(closed_assets) & set(engine.tokens)
    assert not set(closed_assets) & set(engine.books)


async def test_restart_with_stale_books_waits_for_initial_snapshots(tmp_path, monkeypatch):
    import time

    import httpx
    from midas.reality import collector
    from midas.reality.config import Config
    from websockets.asyncio.server import serve

    store = Store(tmp_path, reserve=1)
    old_ns = time.time_ns() - 120_000_000_000
    discovery = FIXTURE["discovery"]
    store.append("discovery", discovery["payload"], cohort=discovery["cohort"], received_ns=old_ns)
    store.append("frame", FIXTURE["frames"][0]["payload"], received_ns=old_ns)
    store.close()
    connections = []

    async def handler(ws):
        connections.append(json.loads(await ws.recv()))
        await ws.send(FIXTURE["frames"][0]["payload"])
        await ws.wait_closed()

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=discovery["payload"])
        )
    )
    monkeypatch.setattr(collector.httpx, "AsyncClient", lambda **kwargs: client)

    class TestConfig(Config):
        def __post_init__(self):
            pass

    async with serve(handler, "127.0.0.1", 0) as server:
        monkeypatch.setattr(collector, "WS", f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}")
        await collector.run(
            TestConfig(root=str(tmp_path), reserve_bytes=1, stale_seconds=10), duration=2
        )
    rows = list(read_manifest(tmp_path, manifest(tmp_path)))
    assert len(connections) == 1
    assert len([r for r in rows if r["kind"] == "frame"]) == 2
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["frames"] == 2
    assert status["process_frames"] == 1
    assert status["lifetime_gap_records"] >= 2
    assert not any(
        r["kind"] == "gap" and r["payload"]["reason"] == "book_resynchronization" for r in rows
    )
    engine, checkpoints = replay(tmp_path, manifest(tmp_path))
    assert engine.counts["book"] == 12 and checkpoints >= 1


async def test_missing_initial_snapshots_timeout_even_with_updates(tmp_path, monkeypatch):

    import httpx
    from midas.reality import collector
    from midas.reality.config import Config
    from websockets.asyncio.server import serve

    connections = []

    async def handler(ws):
        connections.append(await ws.recv())
        await ws.send(FIXTURE["frames"][1]["payload"])
        await ws.wait_closed()

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=FIXTURE["discovery"]["payload"])
        )
    )
    monkeypatch.setattr(collector.httpx, "AsyncClient", lambda **kwargs: client)

    class TestConfig(Config):
        def __post_init__(self):
            pass

    async with serve(handler, "127.0.0.1", 0) as server:
        monkeypatch.setattr(collector, "WS", f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}")
        await collector.run(
            TestConfig(root=str(tmp_path), reserve_bytes=1, stale_seconds=0.05), duration=3
        )
    rows = list(read_manifest(tmp_path, manifest(tmp_path)))
    assert 1 <= len(connections) <= 2
    errors = [
        r["payload"]["error"]
        for r in rows
        if r["kind"] == "gap" and r["payload"]["reason"] == "connection_failure"
    ]
    assert errors and all("Initial snapshots incomplete" in error for error in errors)
    engine, _ = replay(tmp_path, manifest(tmp_path))
    assert not engine.books and engine.counts["update_without_snapshot"] >= 2
