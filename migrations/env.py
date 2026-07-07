"""Alembic environment — async engine, URL + metadata from the app itself.

The URL comes from app settings (DATABASE_URL env / .env) through the same
``_resolve_async_url`` the app uses, so migrations always target the exact
database the app would connect to (SQLite in dev, Neon Postgres in prod).

Every table-owning module's models are imported below so ``Base.metadata``
is complete before autogenerate diffs it against the live schema.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.platform.config import get_settings
from app.platform.db import Base, _resolve_async_url

# Import ALL module models so autogenerate sees the full schema.
from app.modules.admin import models as _admin_models  # noqa: F401
from app.modules.astrology_engine import models as _astro_models  # noqa: F401
from app.modules.chat import models as _chat_models  # noqa: F401
from app.modules.commerce import models as _commerce_models  # noqa: F401
from app.modules.community import models as _community_models  # noqa: F401
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.identity import models as _identity_models  # noqa: F401
from app.modules.knowledge import models as _knowledge_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.orgs import models as _orgs_models  # noqa: F401
from app.modules.temples import models as _temples_models  # noqa: F401
from app.modules.tone_safety import models as _tone_models  # noqa: F401
from app.modules.whatsapp import consent as _whatsapp_consent  # noqa: F401
from app.modules.whatsapp import models as _whatsapp_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return _resolve_async_url(get_settings().database_url)


def run_migrations_offline() -> None:
    """'offline' mode — emit SQL to stdout without a DB connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    url = _database_url()
    if url.startswith("postgresql+asyncpg://"):
        connect_args = {"ssl": True}  # managed Postgres (Neon) requires TLS
    else:
        connect_args = {}
    engine = create_async_engine(url, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
        await connection.commit()
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
