from unittest.mock import AsyncMock

import pytest
from midas.simulation.fixtures import binary_fixture

from apps.api.config import Settings
from apps.api.service import Service


@pytest.mark.asyncio
async def test_demo_refresh_reuses_deterministic_initial_conditions(tmp_path, monkeypatch):
    market, books = binary_fixture()
    calls = []

    def scenario(scenario_id, seed):
        calls.append((scenario_id, seed))
        return {
            "initial_conditions": {
                "market": market.model_dump(mode="json"),
                "books": {asset: book.model_dump(mode="json") for asset, book in books.items()},
            }
        }

    monkeypatch.setattr("apps.api.service.run_scenario", scenario)
    service = Service(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db"))
    service.store.append = AsyncMock()
    service.record = AsyncMock()
    service.scan = AsyncMock()

    await service.refresh_demo()
    await service.refresh_demo()

    assert len(calls) == 6
    assert {seed for _, seed in calls} == {7}
    assert len(service.demo_initial_conditions) == 6
