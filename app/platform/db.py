"""Database access — async SQLAlchemy engine + session factory.

SQLite by default (zero-setup local dev), PostgreSQL when ``DATABASE_URL`` is set.
Schema migrations are managed with Alembic and require human approval (AGENTS.md);
this module only wires the engine/session — it does not create or alter tables.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Connection, DateTime
from sqlalchemy import inspect as sa_inspect
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
    """Declarative base for all module ORM models.

    Every model timestamp is written as a timezone-aware UTC value
    (``datetime.now(UTC)``). Map bare ``Mapped[datetime]`` columns to a
    timezone-AWARE type so Postgres gets ``TIMESTAMP WITH TIME ZONE``: the
    asyncpg driver rejects an aware datetime into a naive ``timestamp`` column
    ("can't subtract offset-naive and offset-aware datetimes"), which 500s
    every insert. SQLite ignores the flag (no tz storage), so dev is unaffected.
    """

    type_annotation_map = {datetime: DateTime(timezone=True)}


# libpq/psycopg connection options that the asyncpg driver does NOT accept as
# URL query params (it would raise "invalid connection option"). Managed hosts
# like Neon/Supabase append these to their copy-paste URLs, so we strip them
# here and re-express SSL through connect_args instead (see _build_engine).
_ASYNCPG_INCOMPATIBLE_PARAMS = {"sslmode", "channel_binding"}


def _resolve_async_url(raw_url: str) -> str:
    """Return an async-driver SQLAlchemy URL.

    - empty            -> local SQLite (aiosqlite)
    - postgres[ql]://  -> upgraded to the asyncpg driver, libpq-only query
                          params (sslmode/channel_binding) stripped
    - already async    -> returned unchanged
    """
    if not raw_url:
        return _DEFAULT_SQLITE_URL
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if not raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    parts = urlsplit(raw_url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in _ASYNCPG_INCOMPATIBLE_PARAMS
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def connect_args_for(raw_url: str, resolved_url: str) -> dict:
    """asyncpg/aiosqlite ``connect_args`` for a (raw, resolved) URL pair.

    TLS decision for Postgres: managed hosts (Neon/Supabase) require it; a
    local/in-container Postgres doesn't offer it, so forcing ``ssl=True`` there
    makes asyncpg reject the connection ("rejected SSL upgrade"). We pass an
    explicit ``ssl=False`` for local so asyncpg never even attempts the upgrade.
    We honor an explicit ``sslmode`` in the original URL, else infer from the
    host — ``localhost`` and bare single-label Docker hostnames (e.g. compose's
    ``postgres``) are local (no TLS); an FQDN with a dot (``ep-x.neon.tech``) is
    a managed host (TLS on).
    """
    if resolved_url.startswith("sqlite"):
        return {"check_same_thread": False}
    if not resolved_url.startswith("postgresql+asyncpg://"):
        return {}
    sslmode = dict(parse_qsl(urlsplit(raw_url).query)).get("sslmode")
    if sslmode in {"disable", "allow"}:
        return {"ssl": False}
    if sslmode in {"prefer", "require", "verify-ca", "verify-full"}:
        return {"ssl": True}
    host = urlsplit(resolved_url).hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or "." not in host:
        return {"ssl": False}
    return {"ssl": True}


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    url = _resolve_async_url(settings.database_url)
    connect_args = connect_args_for(settings.database_url, url)
    kwargs: dict = {"future": True, "connect_args": connect_args}
    if url.startswith("postgresql+asyncpg://"):
        # Managed Postgres (Neon/Supabase free tiers) auto-suspends when idle and
        # closes its pooled connections. Without a liveness check the FIRST query
        # after an idle period hits a dead socket, raises, and poisons the whole
        # request session — so the next commit fails too. Observed as: the first
        # WhatsApp message after ~5 min idle erroring instead of replying.
        # pool_pre_ping tests+reconnects transparently (waking Neon); pool_recycle
        # caps connection age so we never lean on a soon-to-be-dropped socket.
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300
    return create_async_engine(url, **kwargs)


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
