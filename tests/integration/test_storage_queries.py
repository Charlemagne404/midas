"""Selective history queries must not traverse unrelated observation payloads."""

import pytest
from sqlalchemy import text

from apps.api.storage import Record, Store


@pytest.mark.asyncio
async def test_recent_source_filter_preserves_order_and_bounds(tmp_path):
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/records.db")
    await store.initialize()
    async with store.sessions.begin() as session:
        session.add_all(
            [
                Record(
                    kind=kind, key=str(i), source=source, received_ts_ms=100 - i, payload={"i": i}
                )
                for i, (kind, source) in enumerate(
                    [
                        ("simulation", "SYNTHETIC"),
                        ("simulation", "LIVE"),
                        ("observation", "SYNTHETIC"),
                        ("simulation", "SYNTHETIC"),
                    ]
                )
            ]
        )
    rows = await store.recent("simulation", 1, "SYNTHETIC")
    assert [r["key"] for r in rows] == ["3"]
    assert [r["key"] for r in await store.recent("simulation", 200, "SYNTHETIC")] == ["3", "0"]
    assert [r["key"] for r in await store.recent("simulation", 200)] == ["3", "1", "0"]
    assert await store.recent("simulation", 0, "SYNTHETIC") == []
    assert await store.recent("simulation", 200, "untrusted' OR 1=1 --") == []
    await store.close()


@pytest.mark.asyncio
async def test_rare_kind_avoids_whole_source_scan(tmp_path):
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/records.db")
    await store.initialize()
    async with store.sessions.begin() as session:
        session.add(
            Record(
                kind="simulation",
                key="old",
                source="SYNTHETIC",
                received_ts_ms=1,
                payload={"result": "preserved"},
            )
        )
        session.add_all(
            [
                Record(
                    kind="observation",
                    key=str(i),
                    source="SYNTHETIC",
                    received_ts_ms=i,
                    payload={"i": i},
                )
                for i in range(5000)
            ]
        )
    # An SQLite VM budget distinguishes a selective query from a full scan
    # without a timing-sensitive assertion or production-sized fixture.
    async with store.engine.connect() as connection:
        driver = (await connection.get_raw_connection()).driver_connection
        await driver.set_progress_handler(lambda: 1, 1000)
        try:
            # Bind this session to the instrumented connection.
            async with store.sessions(bind=connection) as session:
                original = store.sessions
                store.sessions = lambda: session
                try:
                    rows = await store.recent("simulation", 200, "SYNTHETIC")
                finally:
                    store.sessions = original
            assert rows[0]["payload"] == {"result": "preserved"}
        finally:
            await driver.set_progress_handler(None, 0)
        plan = (
            await connection.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT * FROM records INDEXED BY ix_records_kind "
                    "WHERE kind='simulation' AND source='SYNTHETIC' ORDER BY id DESC LIMIT 200"
                )
            )
        ).all()
        assert any("ix_records_kind" in row[-1] for row in plan)
        assert all("TEMP B-TREE" not in row[-1] for row in plan)
    await store.close()
