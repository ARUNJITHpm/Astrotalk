"""ORM model for pooja bookings (NITHARA-BUILD-PLAN Part 1).

``pooja_bookings`` — a devotee's booked temple offering. Distinct
from the astrologer-consult table (``astro_bookings``) and the white-label
org-consult table (``bookings``); this one is temple poojas only.

Payment runs through the commerce module (a Razorpay custom order); this row
holds the booking's own facts and a link to that order. ``state`` is reconciled
to ``ok`` once the payment is captured (read-time, against commerce). ``user_id``
and ``member_id`` are plain ints — no cross-module FKs (AGENTS.md). Migrations
via Alembic.
"""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

# A booking's lifecycle. It was ("wait", "ok") only — nothing but the payment
# reconciler ever wrote state, so a booking could be paid but never marked
# performed, and there was no cancel path at all, for an operator OR a user.
#
#   wait      — order opened, payment not captured
#   ok        — paid and confirmed. Only the reconciler sets this.
#   completed — the temple performed the offering
#   cancelled — called off. Money, if any, is settled outside the app.
#   refunded  — bookkeeping: the refund was issued in the Razorpay dashboard.
#               Nothing here moves money; see the note on the status route.
BOOKING_STATES = ("wait", "ok", "completed", "cancelled", "refunded")

# What an operator may do, keyed by the state the booking is in.
#
# `ok` is absent from every target on purpose: it means "the payment reconciler
# saw a captured payment", and letting the console assert it by hand would make
# a paid booking indistinguishable from a mistaken click. `wait` is likewise
# never a target — you cannot un-pay an order.
OPERATOR_TRANSITIONS: dict[str, frozenset[str]] = {
    "wait": frozenset({"cancelled"}),
    "ok": frozenset({"completed", "cancelled", "refunded"}),
    "completed": frozenset({"refunded"}),
    "cancelled": frozenset({"refunded"}),
    "refunded": frozenset(),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BookingSettings(Base):
    """Operator-tunable booking settings — a single row, ``id=1``.

    Deliberately narrow rather than an app-wide key/value store: the service fee
    is the bookings module's own number, and a shared settings table would be a
    cross-module surface that `docs/AGENTS.md` puts behind human approval. Other
    modules can add their own when they need one.

    When the row is absent the service falls back to ``SERVICE_FEE_PAISE``, so a
    database that predates this table (and every test's fresh one) prices
    exactly as it always did.
    """

    __tablename__ = "booking_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    service_fee_paise: Mapped[int] = mapped_column(default=1500)  # ₹15
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


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
    # The day the temple performs it. `when_label` above is free display text
    # the client composes, so it can never be queried — this is the machine
    # -readable half, and it is what the operator worklist groups by. Nullable:
    # every booking made before console plan Part 7 has none, and the client
    # may still omit it.
    perform_on: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True, default=None
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(
        nullable=True, index=True, default=None
    )
    state: Mapped[str] = mapped_column(default="wait")  # one of BOOKING_STATES
    # Whatever the temple needs to remember about this booking: a phone call, a
    # substitution, why it was cancelled.
    operator_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, onupdate=_utcnow
    )
