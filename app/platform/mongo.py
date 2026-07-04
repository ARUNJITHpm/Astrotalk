"""MongoDB access — async pymongo client + lazy database handle.

The document store for chat history and durable memory. Relational data
(users/charts) stays in Postgres (see platform/db.py); this is the parallel
connection layer for document-shaped data.

Resilience mirrors the rest of the app: if ``mock_mongo`` is set (default) or a
local mongod is unreachable, ``get_db()`` returns ``None`` and callers degrade
to a no-op — chat must never fail because the document store is down.

Modules own their own collections/queries (e.g. chat/history.py); this file only
wires the client, exactly as db.py only wires the SQL engine.
"""

from typing import TYPE_CHECKING

from app.platform.config import get_settings
from app.platform.logging_config import get_logger

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase

logger = get_logger(__name__)

_client = None
_db = None
_initialized = False


def get_db() -> "AsyncDatabase | None":
    """Return the shared async Mongo database, or None if disabled/unavailable.

    Cheap and lazy: the client connects on first real operation, not here, so a
    down mongod does not block app boot. On any construction failure we log once
    and return None so callers fall back to a no-op.
    """
    global _client, _db, _initialized
    if _initialized:
        return _db

    _initialized = True
    settings = get_settings()
    if settings.mock_mongo:
        logger.info("mongo: MOCK_MONGO on — chat history/memory persistence disabled.")
        return None
    try:
        from pymongo import AsyncMongoClient

        _client = AsyncMongoClient(settings.mongodb_url)
        _db = _client[settings.mongodb_db]
        logger.info("mongo: client configured for db=%s.", settings.mongodb_db)
    except Exception as exc:  # pragma: no cover - depends on driver/config
        logger.warning("mongo: client unavailable (%s); persistence disabled.", exc)
        _db = None
    return _db


async def close_mongo() -> None:
    """Close the client on app shutdown (no-op if never opened)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
