"""Immutable normalized observations, simulation artifacts and system incidents."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Index,
    Integer,
    String,
    delete,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from apps.api.state_codec import VERSION as STATE_CODEC_VERSION
from apps.api.state_codec import decode_state, encode_state


class Base(DeclarativeBase):
    pass


class PaperStateJSON(TypeDecorator[dict[str, Any]]):
    """Only the account head is encoded; all event journal columns stay plain JSON."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return encode_state(value) if isinstance(value, dict) else value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return decode_state(value) if isinstance(value, dict) else value


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(16), index=True)
    received_ts_ms: Mapped[int] = mapped_column(BigInteger, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (Index("ix_records_kind_received", "kind", "received_ts_ms"),)


class Store:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine.sync_engine, "connect")
            def sqlite_durability(connection: Any, _: Any) -> None:
                cursor = connection.cursor()
                cursor.execute("PRAGMA synchronous=FULL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.healthy = True

    async def initialize(self) -> None:
        from alembic import command
        from alembic.config import Config

        async with self.engine.connect() as connection:
            if self.engine.dialect.name == "sqlite":
                await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            tables = await connection.run_sync(lambda c: inspect(c).get_table_names())
            columns = (
                await connection.run_sync(
                    lambda c: {x["name"] for x in inspect(c).get_columns("records")}
                )
                if "records" in tables
                else set()
            )
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[2] / "infra/migrations")
        )
        config.attributes["database_url"] = self.engine.url.render_as_string(hide_password=False)
        if "records" in tables and "alembic_version" not in tables:
            # Adopt the exact legacy bootstrap only; unknown schemas fail migration.
            if set(tables) != {"records"} or columns != {
                "id",
                "kind",
                "key",
                "source",
                "received_ts_ms",
                "payload",
            }:
                raise ValueError(
                    "Unversioned database has unexpected tables; manual migration required"
                )
            await asyncio.to_thread(command.stamp, config, "001")
        await asyncio.to_thread(command.upgrade, config, "head")
        logging.getLogger("uvicorn.error").info(
            "MIDAS storage runtime: source=%s account_codec=%s", __file__, STATE_CODEC_VERSION
        )

    async def append(
        self, kind: str, key: str, source: str, ts: int, payload: dict[str, Any]
    ) -> None:
        try:
            async with self.sessions.begin() as session:
                session.add(
                    Record(kind=kind, key=key, source=source, received_ts_ms=ts, payload=payload)
                )
            self.healthy = True
        except Exception:
            self.healthy = False
            raise

    async def recent(
        self, kind: str, limit: int = 200, source: str | None = None
    ) -> list[dict[str, Any]]:
        statement = select(Record).where(Record.kind == kind)
        if source:
            statement = statement.where(Record.source == source)
        statement = statement.order_by(Record.id.desc()).limit(min(limit, 2000))
        if source and kind in {"simulation", "experiment"} and self.engine.dialect.name == "sqlite":
            # SQLite otherwise chooses the source index for these equalities.
            # Rare simulation/experiment rows then require scanning all the
            # (potentially millions of) newer synthetic market observations.
            # Keep the planner's source index for observations: a rare LIVE
            # source within a large synthetic history needs that selectivity.
            # The kind index, created by migration 001, includes rowid order;
            # filter source within that kind without sorting or archive scans.
            statement = (
                select(Record)
                .from_statement(  # type: ignore[assignment]
                    text(
                        "SELECT * FROM records INDEXED BY ix_records_kind "
                        "WHERE kind = :kind AND source = :source "
                        "ORDER BY id DESC LIMIT :limit"
                    )
                )
                .params(kind=kind, source=source, limit=min(limit, 2000))
            )
        async with self.sessions() as session:
            result = await session.scalars(statement)
            return [
                {
                    "id": r.id,
                    "key": r.key,
                    "source": r.source,
                    "received_ts_ms": r.received_ts_ms,
                    "payload": r.payload,
                }
                for r in result
            ]

    async def prune(self, before_ms: int) -> int:
        async with self.sessions.begin() as session:
            result = await session.execute(delete(Record).where(Record.received_ts_ms < before_ms))
            return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def close(self) -> None:
        await self.engine.dispose()


class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(PaperStateJSON())
    checksum: Mapped[str] = mapped_column(String(64))
    journal_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PaperEvent(Base):
    __tablename__ = "paper_events"
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    command: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    previous_checksum: Mapped[str] = mapped_column(String(64))
    __table_args__ = (Index("ix_paper_event_revision", "account_id", "revision", unique=True),)
