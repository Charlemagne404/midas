import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from midas.core.models import Market, MarketEvent, Source
from midas.market_data.ctf import CTFVerifier
from midas.market_data.polymarket import CLOB, PublicClient, normalize_book
from midas.paper.broker import AccountConfig, audit, summary
from midas.paper.experiments import replay_events

from apps.api.config import Settings
from apps.api.main import create_app
from apps.api.paper import PaperBroker
from apps.api.service import Service
from apps.api.storage import Store

ROOT = Path(__file__).resolve().parents[1] / "fixtures/milestone2"


async def test_health_exposes_invalid_books_and_recovers_on_confirmed_snapshot(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    service = Service(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/health.db", refresh_seconds=300)
    )
    try:
        await service.start()
        assert (await service.state())["status"] == "READY"
        original = next(iter(service.books.books.values()))
        service.books.invalidate(original.asset_id, "Unsequenced stream requires confirmation")
        assert service.health_status() == "DEGRADED"
        assert (await service.state())["status"] == "DEGRADED"
        service.books.snapshot(original)
        assert service.health_status() == "READY"
    finally:
        await service.stop()


async def test_captured_public_reads_use_production_verifier_and_paper_broker(tmp_path):
    fixture = json.loads((ROOT / "ctf-4024677.json").read_text())
    reads = fixture["attestation"]["evidence"]["calls"]

    def rpc(request):
        msg = json.loads(request.content)
        match = next(
            x for x in reads if x["method"] == msg["method"] and x["params"] == msg["params"]
        )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": match["result"]})

    verifier = CTFVerifier(transport=httpx.MockTransport(rpc))
    # Replay fixture's recorded machine evidence; not a new live network verification.
    market = Market.model_validate(fixture["market"])
    proof = await verifier.verify(market)
    assert proof.status == "VERIFIED_STRUCTURE"
    await verifier.close()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/observed.db")
    await store.initialize()
    broker = PaperBroker(store, "recorded", AccountConfig(mode="historical"))
    ts = fixture["command"]["ts"]
    await broker.start(ts)
    market = Market.model_validate(fixture["market"])
    events = [
        MarketEvent(
            event_id="metadata",
            kind="attested_metadata",
            source=Source.LIVE,
            received_ts_ms=ts,
            raw={"market": market.model_dump(mode="json")},
        )
    ]
    for n, (asset, raw) in enumerate(fixture["raw_books"].items()):
        b = normalize_book(raw, Source.LIVE, ts, asset, market.condition_id)
        events.append(
            MarketEvent(
                event_id=f"book:{n}",
                kind="snapshot",
                source=Source.LIVE,
                received_ts_ms=ts,
                asset_id=asset,
                book=b,
                raw=raw,
            )
        )
    await replay_events(broker, events)
    assert len(broker.state["decisions"]) == 2
    assert not broker.state["decisions"][0]["risk"]["allowed"]  # No future second book.
    assert not broker.state["decisions"][1]["risk"]["allowed"]  # Real capture has negative edge.
    assert summary(broker.state)["paper_trades"] == 0
    assert not audit(broker.state)
    restarted = PaperBroker(store, "recorded", AccountConfig(mode="historical"))
    await restarted.start(ts + 1000)
    assert summary(restarted.state)["paper_trades"] == 0
    await store.close()


async def test_read_transports_cannot_send_real_orders():
    sent = []

    def public(request):
        sent.append((request.method, str(request.url)))
        assert request.method == "GET"
        return httpx.Response(200, json={})

    c = PublicClient(httpx.MockTransport(public))
    for path in [
        "/order",
        "/orders",
        "/cancel",
        "/balance-allowance",
        "/clob-markets/../../order",
        "/clob-markets/0x00",
    ]:
        with pytest.raises(ValueError):
            await c.get(CLOB, path)
    assert not sent
    await c.get(CLOB, "/book", {"token_id": "123"})
    assert sent[0][0] == "GET"
    await c.close()
    verifier = CTFVerifier(transport=httpx.MockTransport(public))
    for method in ["eth_sendTransaction", "eth_sendRawTransaction", "personal_sign", "eth_sign"]:
        with pytest.raises(ValueError):
            await verifier._read(method, [])
    await verifier.close()


def test_dashboard_paper_controls_decisions_and_experiment_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/ui.db", refresh_seconds=300)
    )
    with TestClient(app) as c:
        p = c.get("/api/paper").json()
        assert p["mode"] == "synthetic" and p["unit"].startswith("virtual")
        assert p["decisions"] and p["paper_trades"] == 1
        assert c.patch("/api/paper", json={"paused": True}).json()["status"] == "PAUSED"
        assert (
            c.patch("/api/paper", json={"paused": False, "execution_model": "conservative"}).json()[
                "execution"
            ]["name"]
            == "conservative"
        )
        assert c.get("/api/paper/journal").json()
        assert c.get("/api/paper/decisions").json()
        x = c.post("/api/experiments", json={"seed": 7, "compare": True}).json()
        assert len(x["result"]["runs"]) == 3
        assert len(c.get("/api/experiments").json()) == 1
        artifact = c.get("/api/experiments/" + x["id"])
        assert "attachment" in artifact.headers["content-disposition"]
        assert artifact.json() == x["result"]
        assert "feasibility" in c.get("/api/analytics").json()
        assert c.patch("/api/settings", json={"emergency_stop": True}).status_code == 200
        assert c.post("/api/experiments", json={}).status_code == 409
    with TestClient(
        create_app(
            Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/ui.db", refresh_seconds=300)
        )
    ) as c:
        assert c.get("/api/paper").json()["status"] == "STOPPED"
        assert c.get("/api/experiments").json()


async def test_concurrent_managers_cannot_overwrite_shared_finances(tmp_path):
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/writers.db")
    await store.initialize()
    a = PaperBroker(store, "shared", AccountConfig())
    await a.start(1)
    b = PaperBroker(store, "shared", AccountConfig())
    await b.start(2)
    results = await asyncio.gather(
        a.apply({"id": "a", "kind": "control", "ts": 3, "paused": True}),
        b.apply({"id": "b", "kind": "control", "ts": 3, "emergency_stop": True}),
        return_exceptions=True,
    )
    # Both may serialize successfully, or one may conflict. Neither loses a committed event.
    restored = PaperBroker(store, "shared", AccountConfig())
    await restored.start(4)
    assert not audit(restored.state)
    successes = sum(not isinstance(r, Exception) for r in results)
    assert restored.revision == 3 + successes
    await store.close()
