"""Persistent historical paper decisions from genuine recorded public observations."""

import argparse
import asyncio
import json
from decimal import Decimal
from pathlib import Path

from midas.core.models import MarketEvent
from midas.paper.broker import AccountConfig, ExecutionModel, audit, summary
from midas.paper.experiments import replay_events

from apps.api.paper import PaperBroker
from apps.api.storage import Store


async def run(path: Path, database: str, capital: Decimal, model: str) -> None:
    events = [MarketEvent.model_validate_json(line) for line in path.read_text().splitlines()]
    if not events:
        raise ValueError("Recording is empty")
    store = Store(database)
    try:
        await store.initialize()
        broker = PaperBroker(
            store,
            "historical-" + path.stem,
            AccountConfig(
                capital=capital, mode="historical", execution=ExecutionModel.preset(model)
            ),
        )
        await broker.start(events[0].received_ts_ms)
        await replay_events(broker, events)
        print(
            json.dumps(
                {
                    "portfolio": summary(broker.state, events[-1].received_ts_ms),
                    "reconciliation_errors": audit(broker.state),
                    "context": "HISTORICAL PUBLIC DATA; fills hypothetical; pending actions beyond dataset end retained, no future observations exposed",
                },
                indent=2,
            )
        )
    finally:
        await store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--db", default="sqlite+aiosqlite:///data/historical-paper.db")
    parser.add_argument("--capital", type=Decimal, default=Decimal(100))
    parser.add_argument(
        "--model", choices=["optimistic", "standard", "conservative"], default="standard"
    )
    args = parser.parse_args()
    asyncio.run(run(args.recording, args.db, args.capital, args.model))
