import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from apps.api.config import Settings
from apps.api.storage import Base

config = context.config
config.set_main_option(
    "sqlalchemy.url", config.attributes.get("database_url", Settings().database_url)
)


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy."
    )
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
