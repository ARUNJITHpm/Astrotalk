"""Run schema migrations at boot — the Docker entrypoint calls this before uvicorn.

Three database states, three actions:

  1. ``alembic_version`` table present   → ``alembic upgrade head`` (normal path).
  2. No ``alembic_version`` but ``users``
     exists (the pre-Alembic Neon DB,
     created by ``create_all``)          → ``alembic stamp head``: adopt the
                                           live schema as the baseline without
                                           re-running CREATEs that would fail.
  3. Fresh/empty database               → ``alembic upgrade head`` builds all.

Exits non-zero on failure so the container stops instead of serving an app
against a half-migrated schema. Run manually any time: ``python scripts/migrate.py``.
"""

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.platform.config import get_settings
from app.platform.db import _resolve_async_url, connect_args_for


async def _table_names() -> set[str]:
    raw = get_settings().database_url
    url = _resolve_async_url(raw)
    connect_args = connect_args_for(raw, url)
    engine = create_async_engine(url, connect_args=connect_args)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: sa_inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def main() -> None:
    tables = asyncio.run(_table_names())
    config = Config(str(_ROOT / "alembic.ini"))

    if "alembic_version" not in tables and "users" in tables:
        # Pre-Alembic database (schema came from create_all): mark the baseline
        # as already applied, then upgrade applies only what came after it.
        print("migrate: existing pre-Alembic schema detected -> stamping baseline")
        command.stamp(config, "head")
    print("migrate: upgrading to head")
    command.upgrade(config, "head")
    print("migrate: done")


if __name__ == "__main__":
    main()
