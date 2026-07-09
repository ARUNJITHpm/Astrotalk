"""SQLAlchemy models for the whatsapp module (internal — do not import elsewhere).

Migrations require human approval (AGENTS.md). This file declares ORM mappings;
the tables are created by ``init_db()`` at startup (dev) or by Alembic (prod).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WASession(Base):
    """Per-phone WhatsApp conversation state: onboarding FSM + active chat context.

    Keyed by the normalized phone number (same form as ``users.phone``).
    Created the first time a phone sends us a WhatsApp message.

    During onboarding, ``state`` tracks the FSM step and ``onboarding_data``
    accumulates the fields collected so far. After registration completes,
    ``state`` moves to ``chatting`` and ``onboarding_data`` is cleared.

    ``chat_context`` holds the last N messages (user + assistant) as a JSON
    list so multi-turn context flows into ChatService without re-fetching
    the full history from Mongo/Postgres on every turn. Capped in code.
    """

    __tablename__ = "wa_sessions"

    phone: Mapped[str] = mapped_column(primary_key=True)
    # FSM state: casual | collect_name | collect_dob | collect_time
    #            | collect_place | chatting | opted_out
    state: Mapped[str] = mapped_column(default="casual")
    # Partial onboarding data collected so far. Cleared after registration.
    onboarding_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    # Rolling chat context: list of {"role": ..., "content": ...} dicts.
    chat_context: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    # Groups turns for the history sidebar (same semantics as chat.schemas).
    conversation_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)
