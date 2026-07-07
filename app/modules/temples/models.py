"""ORM models for the temples module (GROWTH_PLAN.md Part 3).

The temple DIRECTORY itself stays curated seed data (seed_data.py); these
tables hold what varies per partnership:

  - ``temple_partners``     — a temple that signed up as a distribution
    partner: public slug (the QR / microsite URL), contact, tier.
  - ``temple_subscriptions``— a person who asked THIS temple for festival
    updates. Keyed by phone (the WhatsApp consent key); the actual opt-in
    lives in the whatsapp module's consent ledger — this row only scopes it
    to a temple.
  - ``temple_festivals``    — dated festival entries per temple (the seed
    directory has no dates; partners supply theirs via the admin console).

Migrations via Alembic (AGENTS.md).
"""

from datetime import UTC, date, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

TIERS = ("free", "partner")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TemplePartner(Base):
    __tablename__ = "temple_partners"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Seed directory id (e.g. "tvm-padmanabhaswamy") — name/deity/vazhipadu
    # come from the curated seed, so partners can't edit devotional content.
    temple_id: Mapped[str] = mapped_column(unique=True, index=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    contact_name: Mapped[str] = mapped_column(default="")
    contact_phone: Mapped[str] = mapped_column(default="")  # sensitive: never logged
    tier: Mapped[str] = mapped_column(default="free")  # one of TIERS
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class TempleSubscription(Base):
    __tablename__ = "temple_subscriptions"
    __table_args__ = (
        UniqueConstraint("phone", "temple_id", name="uq_subscription_phone_temple"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(index=True)
    temple_id: Mapped[str] = mapped_column(index=True)
    channel: Mapped[str] = mapped_column(default="whatsapp")  # whatsapp|web
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class TempleFestival(Base):
    __tablename__ = "temple_festivals"

    id: Mapped[int] = mapped_column(primary_key=True)
    temple_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    name_ml: Mapped[str] = mapped_column(default="")
    day: Mapped[date] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
