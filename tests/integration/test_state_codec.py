import base64
import copy
import json
import sqlite3
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
from midas.economics.attestation import digest
from midas.paper.broker import AccountConfig, ExecutionModel
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from sqlalchemy import text

from apps.api.paper import PaperBroker, replay_journal
from apps.api.state_codec import MARKER, decode_state, encode_state
from apps.api.storage import PaperAccount, Store
from scripts import paper_state_storage


def large_state():
    return {
        "version": "paper-broker-2",
        "unicode": "å市場",
        "number": 12.5,
        "none": None,
        "decisions": [{"i": i, "evidence": "repeat " * 200} for i in range(200)],
    }


def test_versioned_state_roundtrip_and_legacy_compatibility():
    state = large_state()
    before = copy.deepcopy(state)
    encoded = encode_state(state)
    assert encoded[MARKER] == "zlib-json-1"
    assert len(json.dumps(encoded)) < len(json.dumps(state)) // 5
    assert decode_state(encoded) == state == before
    assert decode_state(before) == before
    assert encode_state({"small": 1}) == {"small": 1}
    assert digest(decode_state(encoded)) == digest(state)
    with pytest.raises(ValueError, match="reserved"):
        encode_state(encoded)


@pytest.mark.parametrize(
    "change",
    [
        {MARKER: "unknown"},
        {"plain_bytes": True},
        {"plain_bytes": 1000000000},
        {"plain_bytes": 1},
        {"data": "not base64!"},
        {"extra": "field"},
        {"data": base64.b64encode(zlib.compress(b"null")).decode(), "plain_bytes": 4},
        {"data": base64.b64encode(zlib.compress(b"x" * 100000)).decode(), "plain_bytes": 1},
    ],
)
def test_invalid_or_expanding_state_fails_closed(change):
    encoded = {**encode_state(large_state()), **change}
    with pytest.raises(ValueError):
        decode_state(encoded)


def test_truncated_and_concatenated_streams_are_rejected():
    encoded = encode_state(large_state())
    raw = base64.b64decode(encoded["data"])
    for broken in (raw[:-1], raw + zlib.compress(b"{}")):
        with pytest.raises(ValueError):
            decode_state({**encoded, "data": base64.b64encode(broken).decode()})


def test_large_legacy_heads_are_preserved_without_a_new_logical_size_limit(monkeypatch):
    from apps.api import state_codec

    state = large_state()
    monkeypatch.setattr(state_codec, "MAX_STATE_BYTES", 1024)
    assert encode_state(state) == state
    assert decode_state(state) == state


async def test_account_encoding_is_transparent_and_rollback_preserves_identity(
    tmp_path, monkeypatch
):
    database = tmp_path / "paper.db"
    store = Store(f"sqlite+aiosqlite:///{database}")
    await store.initialize()
    state = large_state()
    async with store.sessions.begin() as session:
        session.add(
            PaperAccount(
                id="test", revision=7, payload=state, checksum=digest(state), journal_hash="c" * 64
            )
        )
    async with store.sessions() as session:
        account = await session.get(PaperAccount, "test")
        assert account.payload == state
    with sqlite3.connect(database) as connection:
        raw = connection.execute("SELECT payload FROM paper_accounts").fetchone()[0]
        assert MARKER in json.loads(raw)
    reports = paper_state_storage.inspect_accounts(database)
    assert reports[0]["revision"] == 7 and reports[0]["checksum"] == digest(state)
    calls = []
    monkeypatch.setattr(
        paper_state_storage, "require_stopped", lambda service: calls.append(service)
    )
    restored = paper_state_storage.inspect_accounts(
        database, materialize=True, service="midas-api.service"
    )
    assert restored[0]["materialized"] and len(calls) == 3
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT revision,payload,checksum,journal_hash FROM paper_accounts"
        ).fetchone()
        assert row == (7, json.dumps(state), digest(state), "c" * 64)
    async with store.sessions() as session:
        assert (await session.get(PaperAccount, "test")).payload == state
    # Other JSON columns retain their existing representation.
    await store.append("experiment", "test", "SYNTHETIC", 1, state)
    async with store.sessions() as session:
        raw = (await session.execute(text("SELECT payload FROM records"))).scalar_one()
        assert MARKER not in json.loads(raw)
    await store.close()


def test_materialization_refuses_a_running_or_protected_service(monkeypatch):
    monkeypatch.setattr(
        paper_state_storage.subprocess,
        "check_output",
        lambda *a, **k: "MainPID=123\nActiveState=active\n",
    )
    with pytest.raises(ValueError, match="Stop the API"):
        paper_state_storage.require_stopped("midas-api.service")
    with pytest.raises(ValueError, match="recorder control"):
        paper_state_storage.require_stopped("midas-reality.service")


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_large_compressed_head_crash_and_journal_recovery(tmp_path, boundary):
    database = tmp_path / "paper.db"
    store = Store(f"sqlite+aiosqlite:///{database}")
    await store.initialize()
    config = AccountConfig(execution=ExecutionModel.preset("optimistic"))
    broker = PaperBroker(store, "test", config)
    await broker.start(DEMO_EPOCH)
    market, books = binary_fixture()
    for i in range(50):
        await broker.apply(
            {
                "id": f"observe:{i}",
                "kind": "observe",
                "ts": DEMO_EPOCH,
                "market": market.model_dump(mode="json"),
                "books": {a: b.model_dump(mode="json") for a, b in books.items()},
            }
        )
    with sqlite3.connect(database) as connection:
        assert MARKER in json.loads(
            connection.execute("SELECT payload FROM paper_accounts").fetchone()[0]
        )
        assert all(
            MARKER not in json.loads(r[0])
            for r in connection.execute("SELECT payload FROM paper_events")
        )
    command = {"id": "control", "kind": "control", "ts": DEMO_EPOCH, "paused": True}
    with pytest.raises(RuntimeError):
        await broker.apply(command, crash=boundary)
    recovered = PaperBroker(store, "test", config)
    await recovered.start(DEMO_EPOCH)
    assert recovered.healthy and recovered.state["paused"] == (boundary == "after_commit")
    await recovered.apply(command)
    revision = recovered.revision
    await recovered.apply(command)
    assert recovered.revision == revision and recovered.state["paused"] is True
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT revision,event_id,command,payload,checksum,previous_checksum "
            "FROM paper_events WHERE account_id='test' ORDER BY revision"
        )
        streamed = (
            {
                "revision": r[0],
                "event_id": r[1],
                "command": json.loads(r[2]),
                "payload": json.loads(r[3]),
                "checksum": r[4],
                "previous_checksum": r[5],
            }
            for r in rows
        )
        assert replay_journal(streamed) == recovered.state
    await store.close()
    # The independent read-only CLI validates the compressed snapshot and
    # streams full transition replay without collecting the journal in a list.
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_paper_journal.py",
            "--database",
            str(database),
            "--account",
            "test",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["valid"] and report["snapshot_checksum_matches"]


async def test_failed_materialization_rolls_back_every_account(tmp_path, monkeypatch):
    database = tmp_path / "paper.db"
    store = Store(f"sqlite+aiosqlite:///{database}")
    await store.initialize()
    state = large_state()
    async with store.sessions.begin() as session:
        for identity in ("a", "b"):
            session.add(
                PaperAccount(
                    id=identity,
                    revision=7,
                    payload=state,
                    checksum=digest(state) if identity == "a" else "0" * 64,
                    journal_hash="c" * 64,
                )
            )
    monkeypatch.setattr(paper_state_storage, "require_stopped", lambda _: None)
    with pytest.raises(ValueError, match="checksum mismatch"):
        paper_state_storage.inspect_accounts(
            database, materialize=True, service="midas-api.service"
        )
    with sqlite3.connect(database) as connection:
        assert all(
            MARKER in json.loads(r[0])
            for r in connection.execute("SELECT payload FROM paper_accounts")
        )
    await store.close()
