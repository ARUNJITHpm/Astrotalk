"""Chat history persistence for the chat module (internal).

Stores conversation turns in Postgres (the ``chat_history`` table, see
models.py) via the platform SQL session. This lives on the same managed DB as
users/charts (Neon in prod) so history works without a separate document store.

``save_turn`` runs as a FastAPI BackgroundTask AFTER the reply is sent, so it
opens its own short-lived session from the shared factory (the request session
is already closed by then). Reads take the caller's session.

PRIVACY (GUARDRAILS.md §4): crisis-turn content is never persisted — the router
only calls save_turn on the normal path, never after a safety response.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import ChatTurn
from app.platform.db import async_session_factory
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _latest_user_turn(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """The user message(s) for THIS turn only — everything after the last
    assistant reply. The client resends the whole transcript each request, so
    storing all of it would make every history row overlap the previous one.
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
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    price_inr: float | None = None,
    price_usd: float | None = None,
) -> None:
    """Append one conversation turn (this turn's user message(s) + Tara's reply).

    ``conversation_id`` groups turns from the same chat session so the history
    sidebar can show one entry per conversation instead of one per message.

    Opens its own session (background-task context). Never raises — a failed
    history write must not surface anywhere near the already-sent reply.
    """
    try:
        async with async_session_factory() as session:
            session.add(
                ChatTurn(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    messages=_latest_user_turn(messages),
                    reply=reply,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    price_inr=price_inr,
                    price_usd=price_usd,
                )
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - defensive; DB should be up
        logger.warning("chat.history: save failed (%s); continuing.", exc)


async def get_history(
    session: AsyncSession, user_id: str, limit: int = 20
) -> list[dict]:
    """Return the user's most recent turns (newest first). Empty on error."""
    try:
        rows = (
            await session.execute(
                select(ChatTurn)
                .where(ChatTurn.user_id == user_id)
                .order_by(ChatTurn.created_at.desc())
                .limit(limit)
            )
        ).scalars()
        return [row.as_dict() for row in rows]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("chat.history: read failed (%s); returning empty.", exc)
        return []
