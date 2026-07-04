"""Chat history persistence for the chat module (internal).

Stores conversation turns in MongoDB (document-shaped, append-heavy) via the
platform Mongo connection. This is the chat module's own collection, mirroring
how identity owns its SQL tables.

Everything degrades to a safe no-op when Mongo is disabled/unavailable
(get_db() -> None), so a down document store never breaks a chat reply.

PRIVACY (GUARDRAILS.md §4): crisis-turn content is never persisted — the router
only calls save_turn on the normal path, never after a safety response.
"""

from datetime import UTC, datetime

from app.platform.logging_config import get_logger
from app.platform.mongo import get_db

logger = get_logger(__name__)

_COLLECTION = "chat_history"


def _latest_user_turn(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """The user message(s) for THIS turn only — everything after the last
    assistant reply. The client resends the whole transcript each request, so
    storing all of it would make every history doc overlap the previous one.
    We keep just the new user input(s) (usually one) paired with the reply."""
    turn: list[dict[str, str]] = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            break
        turn.append(msg)
    turn.reverse()
    return turn or messages[-1:]  # fallback: never store an empty turn


async def save_turn(
    user_id: str,
    messages: list[dict[str, str]],
    reply: str,
    conversation_id: str | None = None,
) -> None:
    """Append one conversation turn (this turn's user message(s) + Tara's reply).

    ``conversation_id`` groups turns from the same chat session so the history
    sidebar can show one entry per conversation instead of one per message.
    """
    db = get_db()
    if db is None:
        return
    try:
        await db[_COLLECTION].insert_one(
            {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "messages": _latest_user_turn(messages),
                "reply": reply,
                "created_at": datetime.now(UTC),
            }
        )
    except Exception as exc:  # pragma: no cover - depends on Mongo availability
        logger.warning("chat.history: save failed (%s); continuing.", exc)


async def get_history(user_id: str, limit: int = 20) -> list[dict]:
    """Return the user's most recent turns (newest first). Empty if unavailable."""
    db = get_db()
    if db is None:
        return []
    try:
        cursor = (
            db[_COLLECTION]
            .find({"user_id": user_id}, {"_id": False})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [doc async for doc in cursor]
    except Exception as exc:  # pragma: no cover - depends on Mongo availability
        logger.warning("chat.history: read failed (%s); returning empty.", exc)
        return []
