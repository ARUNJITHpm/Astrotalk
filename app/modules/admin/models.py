"""Operator accounts, roles and invites (console plan Part 4).

Operators are **not** `users` rows. That was the first design, and reading the
schema killed it: `users` requires `dob`, `birth_place`, `lat`, `lng` and `tz`,
all NOT NULL, because it models a devotee with a natal chart. A temple clerk
should not need a birth chart to sign in, and fabricating birth data for staff
is worse than a second table — `docs/GUARDRAILS.md` §4 treats birth data as
sensitive. So operators get their own small identity here and the devotee
identity in `identity/` is left alone.

Password hashing is *not* reimplemented: `identity.service.hash_password` and
`verify_password` are reused through that module's public surface (AGENTS.md).

  - ``operators``          who may sign in to the console. Either an email or a
                           phone identifies them; the owner picks which when
                           inviting.
  - ``operator_roles``     what they may do, optionally scoped to one temple.
  - ``operator_sessions``  bearer tokens. Separate from ``sessions``, whose
                           ``user_id`` is a foreign key into ``users``.
  - ``operator_invites``   an owner's pending invitation, redeemed once to set
                           a password.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

# owner            — everything, including granting roles
# temple_admin     — scoped: only the temples named on their role rows
# content_reviewer — content and the app feed
# support          — read-only lookup of users and bookings
ROLES = ("owner", "temple_admin", "content_reviewer", "support")

# Roles that are meaningless without a temple to scope them to.
SCOPED_ROLES = ("temple_admin",)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Either identifies the operator; at least one is always set (enforced in
    # the service — a CHECK across two columns is awkward to migrate). Both are
    # unique, and Postgres permits many NULLs in a unique column.
    email: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    phone: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    name: Mapped[str] = mapped_column(default="")
    # Null until the invite is redeemed — an invited operator exists but cannot
    # sign in yet.
    password_hash: Mapped[str | None] = mapped_column(default=None)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class OperatorRole(Base):
    """One grant. A person running three temples has three rows."""

    __tablename__ = "operator_roles"
    __table_args__ = (
        UniqueConstraint("operator_id", "role", "temple_id", name="uq_operator_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("operators.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(index=True)  # one of ROLES
    # NULL = unscoped (an owner, or a reviewer over all content). A temple_admin
    # always carries one.
    temple_id: Mapped[str | None] = mapped_column(index=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, index=True)
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("operators.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OperatorInvite(Base):
    """An owner's pending invitation, redeemable once.

    The role and scope are recorded up front so accepting is a single step: set
    a password, get the access you were invited for.
    """

    __tablename__ = "operator_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str | None] = mapped_column(index=True, default=None)
    phone: Mapped[str | None] = mapped_column(index=True, default=None)
    name: Mapped[str] = mapped_column(default="")
    role: Mapped[str] = mapped_column(default="temple_admin")
    temple_id: Mapped[str | None] = mapped_column(default=None)
    invited_by: Mapped[int | None] = mapped_column(default=None)  # operators.id
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
