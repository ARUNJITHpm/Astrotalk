"""ORM model for pooja bookings (NITHARA-BUILD-PLAN Part 1).

One table, ``pooja_bookings`` — a devotee's booked temple offering. Distinct
from the astrologer-consult table (``astro_bookings``) and the white-label
org-consult table (``bookings``); this one is temple poojas only.

Payment runs through the commerce module (a Razorpay custom order); this row
holds the booking's own facts and a link to that order. ``state`` is reconciled
to ``ok`` once the payment is captured (read-time, against commerce). ``user_id``
and ``member_id`` are plain ints — no cross-module FKs (AGENTS.md). Migrations
via Alembic.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

BOOKING_STATES = ("wait", "ok")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PoojaBooking(Base):
    __tablename__ = "pooja_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    ref: Mapped[str] = mapped_column(unique=True, index=True)  # human ref, "NT######"

    temple_id: Mapped[str] = mapped_column(index=True)  # seed directory id
    pooja_key: Mapped[str]
    pooja_name: Mapped[str] = mapped_column(default="")  # snapshot display name

    amount_paise: Mapped[int]  # the offering price
    service_fee_paise: Mapped[int] = mapped_column(default=1500)  # ₹15

    # Who the pooja is for. Members arrive in Part 2 — until then these are a
    # snapshot the client sends (name + nakshatram index), no FK.
    member_id: Mapped[int | None] = mapped_column(nullable=True, default=None)
    member_name: Mapped[str] = mapped_column(default="")
    member_nak: Mapped[int | None] = mapped_column(nullable=True, default=None)

    when_label: Mapped[str] = mapped_column(default="")  # display date, e.g. "28 Jul"
    razorpay_order_id: Mapped[str | None] = mapped_column(
        nullable=True, index=True, default=None
    )
    state: Mapped[str] = mapped_column(default="wait")  # one of BOOKING_STATES
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
