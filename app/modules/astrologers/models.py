"""SQLAlchemy model for the astrologers module (internal — do not import elsewhere).

The astrologer *directory* is static seed data (``seed_data.py``); the only real
state is a booking. ``astro_bookings`` holds one confirmed consult slot per row,
keyed by the seed astrologer id and the user's phone (the app-wide identity key,
matching ``users.phone`` and ``chat_history.user_id``).

Consults are free, so a booking is ``confirmed`` immediately — there is no
payment/pending state (kept deliberately simpler than the org booking engine).
Migrations are managed with Alembic (AGENTS.md); this file only declares the ORM
mapping.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
