"""Actual service lifecycle with a small supported public-data sample and temporary account."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

from apps.api.config import Settings
from apps.api.service import Service


async def main() -> None:
    output = Path("docs/MILESTONE_2_SERVICE_EVIDENCE.json").resolve()
    with tempfile.TemporaryDirectory(prefix="midas-live-paper-") as root:
        os.chdir(root)
        service = Service(
            Settings(
                mode="live",
                market_limit=2,
                discovery_limit=100,
                database_url=f"sqlite+aiosqlite:///{root}/live.db",
                refresh_seconds=300,
            )
        )
        try:
            await service.start()
            async with asyncio.timeout(55):
                while service.last_refresh_ms is None:
                    await asyncio.sleep(0.2)
            await asyncio.sleep(1)
            state = await service.state()
            evidence = {
                "state": state,
                "markets": [m.model_dump(mode="json") for m in service.markets.values()],
                "evaluations": [e.model_dump(mode="json") for e in service.current_evaluations()],
                "live_execution": False,
                "account_database": "temporary SQLite, actual SQL transactions",
                "discovery": "100 highest-liquidity Gamma observations, monitor first two supported non-negative-risk v1 markets",
            }
            output.write_text(json.dumps(evidence, indent=2))
            print(
                json.dumps(
                    {
                        "mode": state["mode"],
                        "status": state["status"],
                        "connection": state["connection"],
                        "markets": [
                            {
                                "id": m.id,
                                "attestation": m.attestation["status"] if m.attestation else None,
                            }
                            for m in service.markets.values()
                        ],
                        "paper_status": state["paper_broker"]["status"],
                        "paper_trades": state["paper_broker"]["paper_trades"],
                        "live_execution": False,
                    },
                    indent=2,
                )
            )
        finally:
            await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
