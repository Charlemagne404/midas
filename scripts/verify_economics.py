"""Controlled public read probe. Never authenticates or creates exchange orders."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import websockets
from midas.arbitrage.engine import BinaryStrategy
from midas.market_data.ctf import CTFVerifier
from midas.market_data.polymarket import WS, PublicClient, normalize_market, now_ms
from midas.paper.broker import AccountConfig, initial, summary, transition


async def main() -> None:
    client, verifier = PublicClient(), CTFVerifier()
    root = Path("tests/fixtures/milestone2")
    root.mkdir(parents=True, exist_ok=True)
    matrix = {
        "captured_ts_ms": now_ms(),
        "reads_only": True,
        "v2": {
            "status": "UNVERIFIED",
            "reason": "No V2 market returned by controlled Gamma version=v2 probe; fixture routing only",
        },
        "markets": [],
    }
    try:
        raw, _ = await client.discover_wire(100)
        v2 = await client.get(
            "https://gamma-api.polymarket.com",
            "/markets",
            {"active": "true", "closed": "false", "version": "v2", "limit": 5},
        )
        matrix["v2"]["returned_versions"] = [m.get("version") for m in v2]
        matrix["v2"]["reason"] = (
            "V2 discovery returned metadata, but identifiers, books and economics remain unverified"
            if v2
            else "No V2 market returned by controlled Gamma version=v2 probe; fixture routing only"
        )
        selected = [m for m in raw if m.get("version") == "v1" and m.get("negRisk") is False][:2]
        for raw_market in selected:
            market = normalize_market(raw_market)
            market, details = await client.enrich(market)
            proof = await verifier.verify(market)
            market = market.model_copy(
                update={
                    "attestation": proof.model_dump(mode="json"),
                    "payout_verified": proof.status == "VERIFIED_STRUCTURE",
                    "complementary_verified": proof.status == "VERIFIED_STRUCTURE",
                    "payout_evidence": proof.relationship,
                }
            )
            books, raws = {}, {}
            for instrument in market.instruments:
                book, wire_raw, _ = await client.book(instrument.asset_id, market.condition_id)
                books[instrument.asset_id], raws[instrument.asset_id] = book, wire_raw
            ts = now_ms()
            evaluation = BinaryStrategy().evaluate(market, books, ts, Decimal(100))
            account = initial(AccountConfig(mode="live_shadow"))
            command = {
                "id": f"public:{market.id}",
                "kind": "observe",
                "ts": ts,
                "market": market.model_dump(mode="json"),
                "books": {a: b.model_dump(mode="json") for a, b in books.items()},
            }
            state = transition(account, command)
            artifact = {
                "raw_market": raw_market,
                "raw_books": raws,
                "clob_details": details,
                "market": market.model_dump(mode="json"),
                "attestation": proof.model_dump(mode="json"),
                "evaluation": evaluation.model_dump(mode="json"),
                "paper_account": summary(state, ts),
                "command": command,
            }
            (root / f"ctf-{market.id}.json").write_text(json.dumps(artifact, indent=2, default=str))
            matrix["markets"].append(
                {
                    "id": market.id,
                    "protocol": market.protocol,
                    "structural_attestation": proof.status,
                    "evaluation": evaluation.status.value,
                    "net_profit": str(evaluation.net_profit),
                    "paper_decision": state["decisions"][-1]["risk"],
                    "fixture": str(root / f"ctf-{market.id}.json"),
                }
            )
        matrix["streaming"] = {"status": "UNVERIFIED"}
        if selected:
            instrument = normalize_market(selected[0]).instruments[0].asset_id
            frames = []
            pong = False
            try:
                async with websockets.connect(WS, ping_interval=None, open_timeout=10) as socket:
                    await socket.send(json.dumps({"type": "market", "assets_ids": [instrument]}))
                    await socket.send("PING")
                    async with asyncio.timeout(15):
                        while not frames or not pong:
                            wire = await socket.recv()
                            if wire == "PONG":
                                pong = True
                            else:
                                frames.append(json.loads(wire))
                (root / "websocket-ctf.json").write_text(
                    json.dumps(
                        {
                            "asset_id": instrument,
                            "frames": frames,
                            "pong": pong,
                            "received_ts_ms": now_ms(),
                        },
                        indent=2,
                    )
                )
                matrix["streaming"] = {
                    "status": "LIVE_PUBLIC_SUBSCRIPTION_VERIFIED",
                    "protocol": "v1",
                    "asset_id": instrument,
                    "pong": pong,
                    "frame_count": len(frames),
                    "limits": "Snapshot/PONG probe; sustained deltas and reconnect campaign not verified",
                }
            except Exception as error:
                matrix["streaming"] = {
                    "status": "UNVERIFIED",
                    "error": f"{type(error).__name__}: {error}",
                }
    finally:
        await client.close()
        await verifier.close()
    Path("docs/MILESTONE_2_LIVE_EVIDENCE.json").write_text(
        json.dumps(matrix, indent=2, default=str)
    )
    print(json.dumps(matrix, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
