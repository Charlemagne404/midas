import json
from pathlib import Path

import pytest
from midas.reality.discovery import select
from midas.reality.reconstruction import Engine
from midas.reality.replay import replay
from midas.reality.storage import MAGIC, Store, manifest, read_manifest

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
