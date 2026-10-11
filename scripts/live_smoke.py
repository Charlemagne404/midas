"""Optional public REST + WebSocket smoke. Only public GET and market subscription."""

import asyncio
import json
from pathlib import Path

import websockets
from midas.market_data.polymarket import DATA, WS, PublicClient, normalize_market


async def main():
    client = PublicClient()
    report = {"verified_date": "2026-10-11", "reads": {}, "websocket": {}}
    try:
        raws = await client.discover(3)
        report["reads"]["gamma_markets"] = {
            "count": len(raws),
            "protocols": [r.get("version", "missing") for r in raws],
        }
        markets = [normalize_market(raw) for raw in raws]
        market = next(m for m in markets if m.instruments)
        book, _, _ = await client.book(market.instruments[0].asset_id, market.condition_id)
        report["reads"]["clob_book"] = {
            "asset_id": book.asset_id,
            "ask_levels": len(book.asks),
            "bid_levels": len(book.bids),
            "tick_size": str(book.tick_size),
            "min_order_size": str(book.min_order_size),
        }
        status = await client.get(DATA, "/v2/status")
        report["reads"]["data_v2_status"] = {"envelope_has_data": "data" in status}
        try:
            async with websockets.connect(WS, ping_interval=None, open_timeout=10) as socket:
                await socket.send(json.dumps({"type": "market", "assets_ids": [book.asset_id]}))
                await socket.send("PING")
                kinds = set()
                pong = False
                async with asyncio.timeout(15):
                    while not pong or not kinds:
                        message = await socket.recv()
                        if message == "PONG":
                            pong = True
                            continue
                        raw = json.loads(message)
                        batch = raw if isinstance(raw, list) else [raw]
                        kinds.update(r.get("event_type", "unknown") for r in batch)
                report["websocket"] = {"application_pong": pong, "event_types": sorted(kinds)}
        except Exception as error:
            report["websocket"] = {"error": f"{type(error).__name__}: {error}"}
        print(json.dumps(report, indent=2))
        Path("docs/LIVE_SMOKE_RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        await client.close()


asyncio.run(main())
