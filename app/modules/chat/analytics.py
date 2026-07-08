"""Chat-volume analytics for the admin dashboard (internal to the chat module).

Aggregates the module's own ``chat_history`` table (see models.py / history.py).
Now that history lives in Postgres, chat metrics are always "available"; a query
error still degrades to ``{"available": False}`` so the dashboard notes metrics
are off rather than 500-ing.

Privacy: ``user_id`` in this table is the mobile number (the identity key), so
the top-users list masks it to a non-identifying tail. Message text is never
returned here — only counts and timestamps.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import ChatTurn
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _mask(user_id: str) -> str:
    digits = re.sub(r"\D", "", user_id or "")
    if len(digits) <= 2:
        return "••"
    return "•••• " + digits[-2:]


def _unavailable() -> dict:
    return {"available": False}


async def chat_metrics(session: AsyncSession) -> dict:
    """Aggregate chat turn/conversation/user counts + a 14-day trend.

    Returns ``{"available": False}`` only if the aggregation errors.
    """
    try:
        now = datetime.now(UTC)

        async def _count(*where) -> int:
            stmt = select(func.count()).select_from(ChatTurn)
            for cond in where:
                stmt = stmt.where(cond)
            return int((await session.execute(stmt)).scalar_one())

        total_turns = await _count()
        turns_24h = await _count(ChatTurn.created_at >= now - timedelta(days=1))
        turns_7d = await _count(ChatTurn.created_at >= now - timedelta(days=7))

        unique_users = int(
            (
                await session.execute(
                    select(func.count(func.distinct(ChatTurn.user_id)))
                )
            ).scalar_one()
        )
        total_conversations = int(
            (
                await session.execute(
                    select(func.count(func.distinct(ChatTurn.conversation_id))).where(
                        ChatTurn.conversation_id.is_not(None)
                    )
                )
            ).scalar_one()
        )

        # Top users by turn count (masked).
        top_rows = (
            await session.execute(
                select(ChatTurn.user_id, func.count().label("turns"))
                .group_by(ChatTurn.user_id)
                .order_by(func.count().desc())
                .limit(5)
            )
        ).all()
        top_users = [{"user": _mask(uid), "turns": turns} for uid, turns in top_rows]

        # Daily turn counts for the last 14 days (bucketed in Python for
        # portability across SQLite/Postgres date handling & timezones).
        recent = (
            await session.execute(
                select(ChatTurn.created_at).where(
                    ChatTurn.created_at >= now - timedelta(days=14)
                )
            )
        ).scalars()
        buckets: dict[str, int] = {}
        for ts in recent:
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
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("chat.analytics: aggregation failed (%s); reporting n/a.", exc)
        return _unavailable()
