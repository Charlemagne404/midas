"""Immutable normalized observations, simulation artifacts and system incidents."""

from typing import Any

from sqlalchemy import JSON, BigInteger, Index, Integer, String, delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.healthy = True

    async def initialize(self) -> None:
        if self.engine.dialect.name == "sqlite":
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        else:
            # Production schema is managed by the versioned Alembic migration.
            async with self.sessions() as session:
                await session.execute(select(Record.id).limit(1))

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
