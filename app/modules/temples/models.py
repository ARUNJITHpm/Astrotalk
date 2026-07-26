"""ORM models for the temples module.

  - ``temples``             — the directory itself. It used to be a Python
    literal in seed_data.py bound in memory at service construction, which
    meant adding a temple or fixing a price required a code change and a
    redeploy. It now lives here so the operator console can edit it;
    seed_data.py survives only as the import fixture for the migration and as
    the fallback when the table is empty (see registry.py).
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
from typing import Any

from sqlalchemy import JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

TIERS = ("free", "partner")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Temple(Base):
    """One temple in the curated directory.

    Column names match ``seed_data.TempleSeed`` key-for-key so the registry can
    round-trip a row to the same ``dict`` shape the service has always handed
    out — that equivalence is what keeps every reader unchanged.

    The four JSON columns are all optional overrides. ``hours``/``timings``
    fall back to the module's DEFAULT_*, and ``poojas`` to DEFAULT_POOJAS, so a
    minimally-filled temple still behaves. (Today *every* seeded temple relies
    on all three fallbacks; Part 3 normalises poojas into their own tables.)
    """

    __tablename__ = "temples"

    # The curated slug ("tvm-padmanabhaswamy"). It is the public id the app,
    # bookings, visits, partners and festivals all reference, so it stays the
    # primary key rather than gaining a surrogate int.
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    name_ml: Mapped[str] = mapped_column(default="")
    deity: Mapped[str] = mapped_column(index=True)  # keys into remedy_map.DEITIES
    district: Mapped[str] = mapped_column(index=True)
    town: Mapped[str] = mapped_column(default="")
    town_ml: Mapped[str | None] = mapped_column(default=None)
    lat: Mapped[float]
    lng: Mapped[float]
    famous_for: Mapped[str] = mapped_column(Text, default="")
    vazhipadu: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Whether an astrologer has signed off the devotional content (GUARDRAILS
    # §1). Served to clients via TempleSuggestion.reviewed; only an operator
    # may flip it.
    reviewed: Mapped[bool] = mapped_column(default=False)
    story: Mapped[str | None] = mapped_column(Text, default=None)
    story_ml: Mapped[str | None] = mapped_column(Text, default=None)
    hours: Mapped[list[list[int]] | None] = mapped_column(JSON, default=None)
    timings: Mapped[dict[str, str] | None] = mapped_column(JSON, default=None)
    poojas: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=None)
    # Strings, not numbers: they are display text and stay unset until REAL
    # review data exists — the service never invents them.
    rating: Mapped[str | None] = mapped_column(default=None)
    reviews: Mapped[str | None] = mapped_column(default=None)
    # Operator controls. `active=False` retires a temple without deleting it
    # (bookings and visits still reference the id).
    active: Mapped[bool] = mapped_column(default=True)
    image_key: Mapped[str | None] = mapped_column(default=None)  # platform/storage key
    sort_order: Mapped[int] = mapped_column(default=0)  # preserves the curated order
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)


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


class TempleVisit(Base):
    """A recorded darshan — the app's temple check-in (Part 2).

    One row per (user, temple, day); the profile's "temples visited" counts
    distinct temples, and each check-in also advances the daily streak (via the
    community module). ``user_id`` is a plain int — no cross-module FK.
    """

    __tablename__ = "temple_visits"
    __table_args__ = (
        UniqueConstraint("user_id", "temple_id", "day", name="uq_visit_user_temple_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    temple_id: Mapped[str] = mapped_column(index=True)
    day: Mapped[date] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class TempleFestival(Base):
    __tablename__ = "temple_festivals"

    id: Mapped[int] = mapped_column(primary_key=True)
    temple_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    name_ml: Mapped[str] = mapped_column(default="")
    day: Mapped[date] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
