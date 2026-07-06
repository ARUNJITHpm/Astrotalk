"""SQLAlchemy models for the commerce module (internal — do not import elsewhere).

GROWTH_PLAN.md Part 5a. Two tables:

  - ``payments`` — one row per Razorpay order, from creation through capture.
    Amounts are integer paise (Razorpay's unit; never floats for money).
  - ``entitlements`` — what a user (or, later, an org) is allowed to use.
    Feature code checks entitlements and NEVER payment rows: purchases,
    referral rewards, and admin grants all converge here, so unlock logic
    has exactly one shape.

``user_id``/``org_id`` are plain ints — users belong to identity and orgs to
Part 4's orgs module, so no cross-module FKs. Migrations via Alembic.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

PAYMENT_STATUSES = ("created", "paid", "failed")
GRANTED_BY = ("purchase", "referral", "admin")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    # Filled from Part 4 onward for org-scoped purchases (SaaS plans).
    org_id: Mapped[int | None] = mapped_column(nullable=True, default=None)
    product: Mapped[str]  # a key in service.PRODUCTS
    amount_paise: Mapped[int]
    currency: Mapped[str] = mapped_column(default="INR")
    razorpay_order_id: Mapped[str] = mapped_column(unique=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    status: Mapped[str] = mapped_column(default="created")  # one of PAYMENT_STATUSES
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    org_id: Mapped[int | None] = mapped_column(nullable=True, index=True, default=None)
    product_key: Mapped[str] = mapped_column(index=True)
    granted_by: Mapped[str]  # one of GRANTED_BY
    # Audit trail: the payment's order id, the referral code, or the admin note.
    source: Mapped[str | None] = mapped_column(nullable=True, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
