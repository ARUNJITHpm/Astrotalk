"""SQLAlchemy models for the orgs module (internal — do not import elsewhere).

GROWTH_PLAN.md Part 4a: one row per white-label tenant (an astrologer's
branded Tara). ``persona_overlay`` adds flavor to the chat persona and is
NEVER allowed to weaken tone_safety rules — the chat module wraps it in an
immutable-guardrails preamble. ``owner_user_id`` is a plain int (users belong
to identity; no cross-module FK).
"""

from datetime import UTC, datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

PLANS = ("starter", "pro")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL slug: /a/{handle}/ui is the org's branded app.
    handle: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    # Storage key of the uploaded logo (platform/storage); None = text brand.
    logo_key: Mapped[str | None] = mapped_column(nullable=True, default=None)
    theme_primary: Mapped[str] = mapped_column(default="#e8b64c")
    theme_bg: Mapped[str] = mapped_column(default="#0b0f2a")
    # Flavor text merged into the chat persona (identity/tone only — the
    # guardrails preamble in chat always wins).
    persona_overlay: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[str] = mapped_column(default="starter")  # one of PLANS
    owner_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
