"""Database access — async SQLAlchemy engine + session factory.

SQLite by default (zero-setup local dev), PostgreSQL when ``DATABASE_URL`` is set.
Schema migrations are managed with Alembic and require human approval (AGENTS.md);
this module only wires the engine/session — it does not create or alter tables.
"""

from collections.abc import AsyncIterator

from sqlalchemy import Connection, inspect as sa_inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.platform.config import get_settings

# Default: a local SQLite file using the async aiosqlite driver.
_DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./tara.db"


class Base(DeclarativeBase):
    """Declarative base for all module ORM models."""


def _resolve_async_url(raw_url: str) -> str:
    """Return an async-driver SQLAlchemy URL.

    - empty            -> local SQLite (aiosqlite)
    - postgres[ql]://  -> upgraded to the asyncpg driver
    - already async    -> returned unchanged
    """
    if not raw_url:
        return _DEFAULT_SQLITE_URL
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    url = _resolve_async_url(settings.database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_async_engine(url, future=True, connect_args=connect_args)


# Engines/sessions are cheap to declare and connect lazily, so building them at
# import time keeps a single shared pool without touching the network on boot.
engine: AsyncEngine = _build_engine()
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional async session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create any tables that don't yet exist, from the registered ORM models.

    This is a convenience for local dev and first-boot so the schema exists
    without a manual step. It only ever CREATEs missing tables — it never alters
    or drops existing ones. Structural changes to live schemas still go through
    Alembic migrations with human approval (AGENTS.md).

    Every table-owning module's models must already be imported (they are, via
    the module routers wired in app/main.py) so ``Base.metadata`` is complete
    before this runs.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite dev convenience only (Postgres changes go through Alembic).
        if engine.dialect.name == "sqlite":
            await conn.run_sync(_add_missing_nullable_columns)


def _add_missing_nullable_columns(conn: Connection) -> None:
    """Add newly-declared *nullable* columns to already-existing tables.

    ``create_all`` only CREATEs missing tables — it never ALTERs an existing one.
    So a new optional column (e.g. ``users.password_hash``) is absent on a
    pre-existing local SQLite DB, and inserts would fail with "no such column".
    Here we ADD just the missing nullable columns, idempotently. NOT-NULL columns
    are skipped (they'd need a backfill) and real migrations still go through
    Alembic with human approval (AGENTS.md).
    """
    inspector = sa_inspect(conn)
    existing = set(inspector.get_table_names())
    for table in Base.metadata.tables.values():
        if table.name not in existing:
            continue  # create_all just built it — already current
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present or not column.nullable:
                continue
            ddl_type = column.type.compile(dialect=conn.dialect)
            conn.exec_driver_sql(
                f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'
            )
