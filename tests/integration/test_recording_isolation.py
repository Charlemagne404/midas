from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from midas.core.models import MarketEvent, Source

from apps.api.config import Settings
from apps.api.service import Service


def test_temporary_database_has_its_own_recording_directory(tmp_path):
    service = Service(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db"))
    assert service.recorder.root == tmp_path / "recordings"


def test_explicit_recording_root_is_preserved(tmp_path):
    destination = tmp_path / "separate-capture"
    service = Service(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db",
            recording_root=destination,
        )
    )
    assert service.recorder.root == destination


def test_default_production_recording_location_is_compatible():
    service = Service(Settings(database_url="sqlite+aiosqlite:///./data/midas.db"))
    assert service.recorder.root == Path("data/recordings")


@pytest.mark.asyncio
async def test_recording_budget_failure_is_reported_once_and_parks_workers(tmp_path):
    service = Service(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/paper.db",
            recording_root=tmp_path / "recordings",
            recording_max_bytes=1000,
        )
    )
    service.report = AsyncMock()
    event = MarketEvent(
        event_id="budget-exhausted",
        kind="snapshot",
        source=Source.SYNTHETIC,
        received_ts_ms=1,
        raw={"fixture": "x" * 2000},
    )

    await service.record(event)
    await service.record(event)

    assert service.recorder.halted
    assert not service.recording_healthy
    assert service.status == "DEGRADED"
    service.report.assert_awaited_once()
    assert not list((tmp_path / "recordings").glob("*.jsonl"))

    await service.loop()
    await service.broker_loop()
