"""SQLAlchemy models for the identity module (internal — do not import elsewhere).

These map PROJECT_DOCS.md §7's `users` and `charts` tables. Birth data
(dob/birth_time/birth_place/lat/lng) is sensitive (GUARDRAILS.md §4): it is never
logged and never placed in URLs. Cross-module access goes only through
IdentityService — no other module reads these tables directly.

Migrations are managed with Alembic and require human approval (AGENTS.md);
this file only declares the ORM mapping.
"""

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Mobile number — the natural identity key. Unique across users; how a person
    # is recognised across channels (WhatsApp, web). Stored normalized.
    phone: Mapped[str] = mapped_column(unique=True, index=True)
    # PBKDF2 hash of the account password (see identity.service.hash_password).
    # Nullable so pre-existing rows (created before auth) survive; registration
    # always sets it, and login rejects accounts without one.
    password_hash: Mapped[str | None] = mapped_column(nullable=True, default=None)
    name: Mapped[str]
    dob: Mapped[date]
    # Birth time is frequently unknown; allow it to be omitted.
    birth_time: Mapped[time | None] = mapped_column(nullable=True)
    birth_place: Mapped[str]
    # Derived from birth_place at onboarding (see IdentityService._geocode).
    lat: Mapped[float]
    lng: Mapped[float]
    tz: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    # Right-to-delete (GUARDRAILS.md §4): deleting a user cascades to charts.
    charts: Mapped[list["Chart"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """A bearer login session. The token authenticates every user-scoped API
    call; it expires after ``settings.session_ttl_hours`` and is revoked by
    logout. Deleting a user cascades their sessions away too."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Chart(Base):
    __tablename__ = "charts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    natal_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="charts")


class ReferralCode(Base):
    """One share code per user (GROWTH_PLAN.md Part 2's referral loop).

    Created lazily the first time the user opens their referral panel or
    shares a card. ``reward_granted_at`` marks the one-time premium-report
    reward as claimed — set when activations reach the configured threshold
    (the grant itself lands in commerce's entitlements once Part 5a exists).
    """

    __tablename__ = "referral_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    code: Mapped[str] = mapped_column(unique=True, index=True)
    reward_granted_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Referral(Base):
    """One referred signup. A user can be referred at most once (unique),
    and only counts as ``activated`` once onboarding completed — i.e. their
    birth chart was computed, which registration does in the same request."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    referred_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # The code as typed/linked — kept for audit even if the code row changes.
    code: Mapped[str]
    status: Mapped[str] = mapped_column(default="activated")  # pending|activated
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
