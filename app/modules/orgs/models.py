"""SQLAlchemy models for the orgs module (internal — do not import elsewhere).

GROWTH_PLAN.md Part 4a: one row per white-label tenant (an astrologer's
branded Tara). ``persona_overlay`` adds flavor to the chat persona and is
NEVER allowed to weaken tone_safety rules — the chat module wraps it in an
immutable-guardrails preamble. ``owner_user_id`` is a plain int (users belong
to identity; no cross-module FK).
"""

from datetime import UTC, datetime

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

PLANS = ("starter", "pro")
BILLING_STATUSES = ("trial", "active", "past_due")


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
    # ---- Billing (Part 5c). trial = full features while evaluating;
    # active = paying; past_due = renewal failed → features soft-lock,
    # data NEVER deleted (dunning rule).
    billing_status: Mapped[str] = mapped_column(default="trial")  # one of BILLING_STATUSES
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        nullable=True, unique=True, default=None
    )
    billing_updated_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


BOOKING_STATUSES = ("pending", "confirmed", "completed", "cancelled")


class AvailabilitySlot(Base):
    """A weekly recurring consultation window (Part 4b).

    ``start_min``/``end_min`` are minutes from midnight in the org's local
    time (IST for the Kerala audience); the window is sliced into
    ``duration_min`` appointments when availability is computed.
    """

    __tablename__ = "availability_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(index=True)
    weekday: Mapped[int]  # 0=Monday … 6=Sunday (Python convention)
    start_min: Mapped[int]
    end_min: Mapped[int]
    duration_min: Mapped[int] = mapped_column(default=30)
    price_paise: Mapped[int] = mapped_column(default=0)  # 0 = free consult
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    # One appointment per org per start time — double-booking is impossible.
    __table_args__ = (UniqueConstraint("org_id", "starts_at", name="uq_booking_org_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    starts_at: Mapped[datetime]
    duration_min: Mapped[int]
    price_paise: Mapped[int]
    status: Mapped[str] = mapped_column(default="pending")  # one of BOOKING_STATUSES
    # The commerce order funding this booking (None for free consults).
    razorpay_order_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class CustomerNote(Base):
    """The astrologer's private note on one customer (Part 4c CRM).

    Visible only to the org owner; never to the customer, never to other
    orgs. Plain-int user ids (identity owns users).
    """

    __tablename__ = "customer_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(index=True)
    customer_user_id: Mapped[int] = mapped_column(index=True)
    author_user_id: Mapped[int]
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
