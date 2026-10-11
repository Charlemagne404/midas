import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from midas.paper.broker import AccountConfig, ExecutionModel, audit, summary
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture
from sqlalchemy import update

from apps.api.paper import PaperBroker
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
