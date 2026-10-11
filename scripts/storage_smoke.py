import asyncio

from midas.market_data.polymarket import now_ms

from apps.api.config import Settings
from apps.api.storage import Store


async def main():
    store = Store(Settings().database_url)
    try:
        await store.initialize()
        await store.append(
            "event",
            "storage-smoke",
            "SYNTHETIC",
            now_ms(),
            {"message": "Storage integration smoke"},
        )
        assert (await store.recent("event", 1))[0]["key"] == "storage-smoke"
        print("Storage insert/read passed:", store.engine.dialect.name)
    finally:
        await store.close()


asyncio.run(main())
