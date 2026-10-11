"""Actual subprocess termination at a transaction boundary; SQLite/PostgreSQL URLs supported."""

import argparse
import asyncio
import json
import os

from midas.paper.broker import AccountConfig, ExecutionModel, audit, summary
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

from apps.api.paper import PaperBroker
from apps.api.storage import Store


async def run(url: str, phase: str) -> None:
    store = Store(url)
    await store.initialize()
    broker = PaperBroker(
        store, "recovery-demo", AccountConfig(execution=ExecutionModel.preset("optimistic"))
    )
    await broker.start(DEMO_EPOCH)
    market, books = binary_fixture()
    if phase == "prepare":
        await broker.apply(
            {
                "id": "signal",
                "kind": "observe",
                "ts": DEMO_EPOCH,
                "market": market.model_dump(mode="json"),
                "books": {a: b.model_dump(mode="json") for a, b in books.items()},
            }
        )
        action = next(
            a
            for a in broker.state["pending"]
            if a["kind"] == "submit" and a["asset"].endswith("yes")
        )
        await broker.apply(
            {"id": action["id"], "kind": "action", "ts": action["due"], "action_id": action["id"]}
        )
    elif phase in {"before_commit", "after_commit", "partial_exit"}:
        action = next(
            a
            for a in broker.state["pending"]
            if a["kind"] == "match" and a["asset"].endswith("yes")
        )

        def terminate(stage: str) -> None:
            if stage == phase:
                os._exit(91)

        await broker.apply(
            {"id": action["id"], "kind": "action", "ts": action["due"], "action_id": action["id"]},
            crash_hook=terminate,
        )
        if phase == "partial_exit":
            os._exit(92)
    elif phase == "finish":
        await broker.tick(DEMO_EPOCH + 100, books, {market.id: market})
        await broker.apply(
            {
                "id": "settle",
                "kind": "settle",
                "ts": DEMO_EPOCH + 1000,
                "position": "signal",
                "payout": {
                    i.asset_id: "1" if n == 0 else "0" for n, i in enumerate(market.instruments)
                },
            }
        )
    result = {
        "phase": phase,
        "revision": broker.revision,
        "portfolio": summary(broker.state, DEMO_EPOCH + 1000),
        "reconciliation_errors": audit(broker.state),
    }
    print(json.dumps(result, indent=2), flush=True)
    await store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="sqlite+aiosqlite:///data/recovery-demo.db")
    parser.add_argument(
        "--phase",
        choices=["prepare", "before_commit", "after_commit", "partial_exit", "inspect", "finish"],
        default="inspect",
    )
    args = parser.parse_args()
    asyncio.run(run(args.db, args.phase))
