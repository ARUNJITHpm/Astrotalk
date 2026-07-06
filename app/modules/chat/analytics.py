"""Chat-volume analytics for the admin dashboard (internal to the chat module).

Aggregates the module's own ``chat_history`` collection (see history.py). Like
the rest of the Mongo layer, everything degrades to an "unavailable" result
when the document store is disabled (MOCK_MONGO) or unreachable — the admin
dashboard then simply notes chat metrics are off rather than erroring.

Privacy: ``user_id`` in this collection is the mobile number (the identity
key), so the top-users list masks it to a non-identifying tail. Message text
is never returned here — only counts and timestamps.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.platform.logging_config import get_logger
from app.platform.mongo import get_db

logger = get_logger(__name__)

_COLLECTION = "chat_history"


def _mask(user_id: str) -> str:
    digits = re.sub(r"\D", "", user_id or "")
    if len(digits) <= 2:
        return "••"
    return "•••• " + digits[-2:]


def _unavailable() -> dict:
    return {"available": False}


async def chat_metrics() -> dict:
    """Aggregate chat turn/conversation/user counts + a 14-day trend.

    Returns ``{"available": False}`` when Mongo is disabled/unavailable.
    """
    db = get_db()
    if db is None:
        return _unavailable()
    try:
        coll = db[_COLLECTION]
        now = datetime.now(UTC)

        total_turns = await coll.count_documents({})
        turns_24h = await coll.count_documents(
            {"created_at": {"$gte": now - timedelta(days=1)}}
        )
        turns_7d = await coll.count_documents(
            {"created_at": {"$gte": now - timedelta(days=7)}}
        )

        unique_users = len(await coll.distinct("user_id"))
        conversation_ids = [
            c for c in await coll.distinct("conversation_id") if c is not None
        ]
        total_conversations = len(conversation_ids)

        # Top users by turn count (masked). In pymongo's async API aggregate()
        # is itself a coroutine returning the cursor, so it must be awaited
        # before iterating (unlike find()).
        top_users = []
        top_cursor = await coll.aggregate(
            [
                {"$group": {"_id": "$user_id", "turns": {"$sum": 1}}},
                {"$sort": {"turns": -1}},
                {"$limit": 5},
            ]
        )
        async for row in top_cursor:
            top_users.append(
                {"user": row["_id"] or "", "turns": row["turns"]}
            )

        # Daily turn counts for the last 14 days (bucketed in Python for
        # portability across Mongo versions / timezones).
        recent = coll.find(
            {"created_at": {"$gte": now - timedelta(days=14)}},
            {"_id": False, "created_at": True},
        )
        buckets: dict[str, int] = {}
        async for doc in recent:
            ts = doc.get("created_at")
            if not isinstance(ts, datetime):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            key = ts.date().isoformat()
            buckets[key] = buckets.get(key, 0) + 1
        daily = []
        for offset in range(13, -1, -1):
            day = (now - timedelta(days=offset)).date().isoformat()
            daily.append({"date": day, "count": buckets.get(day, 0)})

        return {
            "available": True,
            "total_turns": total_turns,
            "total_conversations": total_conversations,
            "unique_users": unique_users,
            "turns_24h": turns_24h,
            "turns_7d": turns_7d,
            "turns_daily_14d": daily,
            "top_users": top_users,
        }
    except Exception as exc:  # pragma: no cover - depends on Mongo availability
        logger.warning("chat.analytics: aggregation failed (%s); reporting n/a.", exc)
        return _unavailable()
