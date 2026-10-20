import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from midas.economics.attestation import digest
from midas.paper.broker import AccountConfig, ExecutionModel, audit, summary, transition
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from sqlalchemy import event, update

from apps.api.paper import (
    PaperBroker,
    advance_journal_hash,
    journal_entry,
    journal_payload,
)
from apps.api.storage import PaperAccount, PaperEvent, Store


async def setup(tmp_path):
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/paper.db")
    await store.initialize()
    broker = PaperBroker(
        store, "test", AccountConfig(execution=ExecutionModel.preset("optimistic"))
    )
    await broker.start(DEMO_EPOCH)
    m, bs = binary_fixture()
    command = {
        "id": "signal",
        "kind": "observe",
        "ts": DEMO_EPOCH,
        "market": m.model_dump(mode="json"),
        "books": {a: b.model_dump(mode="json") for a, b in bs.items()},
    }
    return store, broker, command


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_crash_at_atomic_ledger_boundary_and_duplicate_fill(tmp_path, boundary):
    store, broker, c = await setup(tmp_path)
    await broker.apply(c)
    actions = sorted(broker.state["pending"], key=lambda p: (p["due"], p["id"]))
    for a in actions:
        cmd = {"id": a["id"], "kind": "action", "ts": a["due"], "action_id": a["id"]}
        if a["kind"] == "match":
            with pytest.raises(RuntimeError):
                await broker.apply(cmd, crash=boundary)
            recovered = PaperBroker(store, "test", AccountConfig())
            await recovered.start(DEMO_EPOCH + 100)
            await recovered.apply(cmd)
            before = summary(recovered.state)
            await recovered.apply(cmd)
            assert summary(recovered.state) == before
            assert not audit(recovered.state)
            broker = recovered
        else:
            await broker.apply(cmd)
    assert summary(broker.state)["hypothetical_fills"] == 2
    for _ in range(3):
        recovered = PaperBroker(store, "test", AccountConfig())
        await recovered.start(DEMO_EPOCH + 200)
        assert summary(recovered.state)["hypothetical_fills"] == 2
        assert Decimal(summary(recovered.state)["locked"]) == Decimal("9.5")
    await store.close()


async def test_summary_can_skip_redundant_decision_history(tmp_path):
    store, broker, command = await setup(tmp_path)
    await broker.apply(command)

    full = summary(broker.state)
    lightweight = summary(broker.state, include_decisions=False)
    compact = summary(broker.state, include_decisions=False, include_details=False)

    assert "decisions" in full
    assert "decisions" not in lightweight
    assert {key: value for key, value in full.items() if key != "decisions"} == lightweight
    assert not {"decisions", "positions", "incidents"} & compact.keys()
    assert all(compact[key] == full[key] for key in compact)
    await store.close()


async def test_transition_detaches_retained_history_and_keeps_audit_compact(tmp_path, monkeypatch):
    store, broker, command = await setup(tmp_path)
    await broker.apply(command)
    original = json.loads(json.dumps(broker.state))
    calls = []

    def measured_summary(state, now=0, **kwargs):
        calls.append(kwargs)
        return summary(state, now, **kwargs)

    monkeypatch.setattr("midas.paper.broker.summary", measured_summary)
    result = transition(original, {**command, "id": "second", "ts": command["ts"] + 1})
    assert calls and all(c.get("include_decisions") is False for c in calls)
    assert not audit(result)
    result["decisions"][0]["risk"]["reasons"].append("mutated output")
    assert original == broker.state
    assert "mutated output" not in original["decisions"][0]["risk"]["reasons"]
    # The no-op action return path also returns a detached state.
    result = transition(
        original, {"id": "missing", "kind": "action", "ts": command["ts"], "action_id": "missing"}
    )
    result["decisions"][0]["risk"]["reasons"].append("mutated no-op")
    assert original == broker.state
    await store.close()


@pytest.mark.parametrize("target", ["snapshot", "journal"])
async def test_inconsistent_financial_state_fails_closed(tmp_path, target):
    store, broker, c = await setup(tmp_path)
    await broker.apply(c)
    async with store.sessions.begin() as session:
        if target == "snapshot":
            await session.execute(
                update(PaperAccount).where(PaperAccount.id == "test").values(checksum="corrupt")
            )
        else:
            await session.execute(
                update(PaperEvent)
                .where(PaperEvent.event_id == "signal")
                .values(previous_checksum="corrupt")
            )
    recovered = PaperBroker(store, "test", AccountConfig())
    with pytest.raises(ValueError):
        await recovered.start(DEMO_EPOCH + 100)
    assert not recovered.healthy
    await store.close()


async def test_large_journal_startup_restores_snapshot_without_replaying_history(
    tmp_path, monkeypatch
):
    store, broker, _ = await setup(tmp_path)
    async with store.sessions() as session:
        account = await session.get(PaperAccount, "test")
        assert account is not None and account.journal_hash is not None
        state = account.payload
        checksum = account.checksum
        previous_hash = account.journal_hash
        revision = account.revision

    # These are valid no-op pause commands. Their persisted state and checksum remain unchanged.
    rows = []
    for index in range(10_000):
        event_id = f"bulk-control:{index}"
        command = {
            "id": event_id,
            "kind": "control",
            "ts": state["last_processed_ms"],
            "paused": False,
        }
        payload = journal_payload(state, state, "control")
        revision += 1
        entry = journal_entry("test", event_id, revision, command, payload, checksum, checksum)
        previous_hash = advance_journal_hash(previous_hash, entry)
        rows.append(
            PaperEvent(
                account_id="test",
                event_id=event_id,
                revision=revision,
                command=command,
                payload=payload,
                checksum=checksum,
                previous_checksum=checksum,
            )
        )

    async with store.sessions.begin() as session:
        session.add_all(rows)
        await session.execute(
            update(PaperAccount)
            .where(PaperAccount.id == "test")
            .values(revision=revision, journal_hash=previous_hash)
        )

    import apps.api.paper as paper_module

    original_transition = paper_module.transition
    transition_calls = 0

    def counted_transition(*args, **kwargs):
        nonlocal transition_calls
        transition_calls += 1
        return original_transition(*args, **kwargs)

    monkeypatch.setattr(paper_module, "transition", counted_transition)
    journal_query_options = {}

    def record_journal_query_options(
        connection, cursor, statement, parameters, context, executemany
    ):
        if "FROM paper_events" in statement:
            journal_query_options.update(context.execution_options)

    event.listen(store.engine.sync_engine, "before_cursor_execute", record_journal_query_options)
    recovered = PaperBroker(store, "test", AccountConfig())
    await recovered.start(DEMO_EPOCH + 500)
    event.remove(store.engine.sync_engine, "before_cursor_execute", record_journal_query_options)
    assert journal_query_options.get("yield_per") == 256
    assert journal_query_options.get("stream_results") is True
    assert transition_calls == 1  # The single durable recovery event, not 10,000 history rows.
    assert recovered.recovery_status == "CHECKPOINT_VERIFIED"
    assert recovered.journal_event_count == 10_003
    assert recovered.revision == 10_002
    assert recovered.state["recovery_count"] == broker.state["recovery_count"] + 1

    async with store.sessions() as session:
        account = await session.get(PaperAccount, "test")
        assert account is not None
        assert account.revision == recovered.revision
        assert digest(account.payload) == account.checksum
        assert account.journal_hash is not None
    assert audit(recovered.state) == []
    await store.close()


async def test_rolling_journal_hash_detects_command_tampering(tmp_path):
    store, broker, _ = await setup(tmp_path)
    await broker.apply({"id": "control", "kind": "control", "ts": DEMO_EPOCH, "paused": False})
    async with store.sessions.begin() as session:
        event = await session.get(PaperEvent, ("test", "control"))
        assert event is not None
        event.command = {**event.command, "paused": True}
    recovered = PaperBroker(store, "test", AccountConfig())
    with pytest.raises(ValueError, match="integrity hash"):
        await recovered.start(DEMO_EPOCH + 100)
    assert not recovered.healthy
    await store.close()


async def test_stop_and_pause_survive_restart_and_wrong_ids_rejected(tmp_path):
    store, broker, c = await setup(tmp_path)
    await broker.apply(c)
    with pytest.raises(ValueError):
        await broker.apply({**c, "ts": DEMO_EPOCH + 1})
    broker = PaperBroker(store, "test", AccountConfig())
    await broker.start(DEMO_EPOCH)
    await broker.apply(
        {
            "id": "stop",
            "kind": "control",
            "ts": DEMO_EPOCH + 1,
            "emergency_stop": True,
            "paused": True,
        }
    )
    restarted = PaperBroker(store, "test", AccountConfig())
    await restarted.start(DEMO_EPOCH + 2)
    s = summary(restarted.state)
    assert s["status"] == "STOPPED" and not restarted.state["pending"]
    assert Decimal(s["available"]) == 100 and not audit(restarted.state)
    await store.close()


@pytest.mark.parametrize("phase", ["before_commit", "after_commit", "partial_exit"])
def test_real_process_termination_and_repeat_recovery(tmp_path, phase):
    root = Path(__file__).resolve().parents[2]
    db = f"sqlite+aiosqlite:///{tmp_path}/process.db"

    def run(p):
        return subprocess.run(
            [
                sys.executable,
                str(root / "scripts/paper_recovery_demo.py"),
                "--db",
                db,
                "--phase",
                p,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert run("prepare").returncode == 0
    assert run(phase).returncode in {91, 92}
    inspection = run("inspect")
    assert inspection.returncode == 0, inspection.stderr
    data = json.loads(inspection.stdout)
    assert data["reconciliation_errors"] == []
    assert data["portfolio"]["hypothetical_fills"] == (0 if phase == "before_commit" else 1)
    finish = run("finish")
    assert finish.returncode == 0, finish.stderr
    result = json.loads(finish.stdout)
    assert result["portfolio"]["realized_pnl"] == "0.500000"
    assert result["portfolio"]["hypothetical_fills"] == 2
    repeated = json.loads(run("inspect").stdout)
    assert repeated["portfolio"]["available"] == result["portfolio"]["available"]
    assert repeated["portfolio"]["hypothetical_fills"] == 2
