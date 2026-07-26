"""SQLAlchemy models for the astrologers module (internal — do not import elsewhere).

  - ``astrologers``    — the directory. It used to be a Python literal in
    ``seed_data.py`` bound in memory at service construction, so a real
    practitioner could not be onboarded without a code change and a redeploy.
    It lives here now so the operator console can manage it; ``seed_data.py``
    survives only as the migration's import fixture and as the fallback when
    the table is empty (see ``registry.py``).
  - ``astro_bookings`` — one confirmed consult slot per row, keyed by the
    astrologer id and the user's phone (the app-wide identity key, matching
    ``users.phone`` and ``chat_history.user_id``).

Consults are free today, so a booking is ``confirmed`` immediately — there is no
payment/pending state (kept deliberately simpler than the org booking engine).
Migrations are managed with Alembic (AGENTS.md); this file only declares the ORM
mapping.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Astrologer(Base):
    """One astrologer in the directory.

    Column names match ``seed_data.AstrologerSeed`` key-for-key so the registry
    round-trips a row into the dict shape the service has always read.

    ``availability`` stays a JSON array of ``{weekday, start, end,
    duration_min}`` rather than becoming its own table: that is the exact shape
    ``_open_slots_utc`` already iterates, so the booking engine needs no change,
    and a handful of weekly windows per astrologer does not want a join. The
    console edits it as a list.
    """

    __tablename__ = "astrologers"

    # The slug ("kozhikode-astro-1"), referenced by astro_bookings and by the
    # chat suggestion path, so it stays the primary key.
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    name_ml: Mapped[str] = mapped_column(default="")
    district: Mapped[str] = mapped_column(index=True)
    town: Mapped[str] = mapped_column(default="")
    lat: Mapped[float]
    lng: Mapped[float]
    specialties: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_years: Mapped[int] = mapped_column(default=0)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    rating: Mapped[float] = mapped_column(default=0.0)
    bio_ml: Mapped[str] = mapped_column(Text, default="")
    availability: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Operator controls. `active=False` hides a placeholder or a departed
    # astrologer without deleting rows that bookings still reference.
    active: Mapped[bool] = mapped_column(default=True)
    # The UI expects a ₹/min rate; consults are free today, so 0 means free and
    # the directory keeps working until real pricing is set.
    price_paise_per_min: Mapped[int] = mapped_column(default=0)
    photo_key: Mapped[str | None] = mapped_column(default=None)  # platform/storage key
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AstroBooking(Base):
    __tablename__ = "astro_bookings"
    __table_args__ = (
        UniqueConstraint("astrologer_id", "starts_at", name="uq_astro_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Seed directory id, e.g. "kozhikode-astro-1".
    astrologer_id: Mapped[str] = mapped_column(index=True)
    # Booking owner = mobile number (matches users.phone).
    user_phone: Mapped[str] = mapped_column(index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(default=30)
    status: Mapped[str] = mapped_column(default="confirmed")  # confirmed | cancelled
    note: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
