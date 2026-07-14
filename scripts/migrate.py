"""Run schema migrations at boot — the Docker entrypoint calls this before uvicorn.

Database states and actions:

  1. ``alembic_version`` table present   → ``alembic upgrade head`` (normal path).
  2. Fresh/empty database               → ``alembic upgrade head`` builds all.
  3. Tables present but NO
     ``alembic_version`` (un-versioned
     schema of unknown provenance)       → ABORT loudly. See below.

Why (3) aborts instead of auto-stamping: the old behavior here was
``alembic stamp head`` — "adopt whatever's live as fully migrated". That is
silently WRONG whenever the live schema is *stale* (e.g. a database first
built by ``create_all`` at an early point, before ``users.org_id`` existed):
stamping head marks every migration as applied, so the columns the code needs
are never created, and the app 500s on every query with a schema mismatch that
looks nothing like a migration problem. An un-versioned schema's true revision
is unknowable, so we refuse to guess. To recover, reset the schema
(``DROP SCHEMA public CASCADE; CREATE SCHEMA public;``) and let migrations
rebuild it from empty, or ``alembic stamp <rev>`` to the known-correct revision.

Exits non-zero on failure so the container stops instead of serving an app
against a half-migrated schema. Run manually any time: ``python scripts/migrate.py``.
"""

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

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
    # Announce the target BEFORE connecting, and flush: this is the first thing
    # the container does, so an unreachable database stalls here with no output
    # at all — indistinguishable in the Space log from a container that never
    # started. Host only, never the credentials in the URL.
    print(f"migrate: connecting to {urlsplit(url).hostname or url.split('://', 1)[0]}",
          flush=True)
    engine = create_async_engine(url, connect_args=connect_args)
    try:
        async with engine.connect() as conn:
            names = set(await conn.run_sync(lambda c: sa_inspect(c).get_table_names()))
        print(f"migrate: connected ({len(names)} tables)", flush=True)
        return names
    finally:
        await engine.dispose()


def main() -> None:
    tables = asyncio.run(_table_names())
    config = Config(str(_ROOT / "alembic.ini"))

    if "alembic_version" not in tables and tables:
        # Tables exist but nothing records which migration they're at. We can't
        # know their true revision, and guessing (the old `stamp head`) silently
        # skips real migrations and serves a broken schema. Fail loudly instead.
        raise SystemExit(
            "migrate: refusing to auto-adopt an un-versioned schema. The database "
            f"has tables ({', '.join(sorted(tables))}) but no alembic_version, so "
            "its true revision is unknown. Reset it to rebuild from empty "
            "(DROP SCHEMA public CASCADE; CREATE SCHEMA public;), or run "
            "`alembic stamp <rev>` to the revision that matches the live schema."
        )
    print("migrate: upgrading to head")
    command.upgrade(config, "head")
    print("migrate: done")


if __name__ == "__main__":
    main()
