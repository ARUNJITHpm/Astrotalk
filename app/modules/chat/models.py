"""SQLAlchemy models for the chat module (internal — do not import elsewhere).

``chat_history`` stores one row per conversation TURN (this turn's user
message(s) + Tara's reply). It is the persistence behind the sidebar history and
the admin chat explorer. Kept in Postgres (the single managed DB, Neon in prod)
rather than a separate document store, so history works without standing up
MongoDB. Migrations are managed with Alembic (AGENTS.md); this file only
declares the ORM mapping.

PRIVACY (GUARDRAILS.md §4): crisis-turn content is never persisted — the router
only calls save_turn on the normal path, never after a safety response.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ChatTurn(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The identity key = mobile number (matches users.phone). Indexed: every
    # sidebar / admin read filters or groups by it.
    user_id: Mapped[str] = mapped_column(index=True)
    # Groups the turns of one chat session; None for legacy/ungrouped turns.
    conversation_id: Mapped[str | None] = mapped_column(
        index=True, nullable=True, default=None
    )
    # This turn's user message(s): [{"role": ..., "content": ...}, ...].
    messages: Mapped[list] = mapped_column(JSON, default=list)
    reply: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(index=True, default=_utcnow)
    llm_provider: Mapped[str | None] = mapped_column(nullable=True, default=None)
    llm_model: Mapped[str | None] = mapped_column(nullable=True, default=None)
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True, default=None)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True, default=None)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True, default=None)
    price_inr: Mapped[float | None] = mapped_column(nullable=True, default=None)
    price_usd: Mapped[float | None] = mapped_column(nullable=True, default=None)

    def as_dict(self) -> dict:
        """Shape matching the ChatHistoryEntry schema / the old Mongo doc."""
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "messages": self.messages or [],
            "reply": self.reply,
            "created_at": self.created_at,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "price_inr": self.price_inr,
            "price_usd": self.price_usd,
        }
