"""Operator accounts: invite, accept, sign in, grant and revoke.

The owner invites; nobody self-registers. An invite records the role and scope
up front, so redeeming it is a single step — set a password, get exactly the
access you were invited for. Either an email or a mobile identifies the
operator; the owner picks which, and the invitee signs in with whichever it was.

Password hashing is reused from ``identity.service`` (that module's public
surface) rather than reimplemented — one hashing scheme for the whole app.
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import (
    ROLES,
    SCOPED_ROLES,
    Operator,
    OperatorInvite,
    OperatorRole,
    OperatorSession,
)
from app.modules.identity.service import hash_password, verify_password
from app.platform.config import get_settings

INVITE_TTL_DAYS = 14
MIN_PASSWORD_LEN = 8


class OperatorError(ValueError):
    """Bad request — unknown role, missing identifier, duplicate account."""


class InviteInvalid(OperatorError):
    """The invite token is unknown, already redeemed, or expired."""


def _norm_email(email: str | None) -> str | None:
    return email.strip().lower() or None if email else None


def _norm_phone(phone: str | None) -> str | None:
    return phone.strip() or None if phone else None


def _validate_grant(role: str, temple_id: str | None) -> None:
    if role not in ROLES:
        raise OperatorError(f"unknown role: {role}")
    if role in SCOPED_ROLES and not temple_id:
        raise OperatorError(f"{role} must be scoped to a temple")
    if role not in SCOPED_ROLES and temple_id:
        raise OperatorError(f"{role} cannot be scoped to a temple")


async def _by_identifier(
    session: AsyncSession, email: str | None, phone: str | None
) -> Operator | None:
    if email:
        found = (
            await session.execute(select(Operator).where(Operator.email == email))
        ).scalar_one_or_none()
        if found:
            return found
    if phone:
        return (
            await session.execute(select(Operator).where(Operator.phone == phone))
        ).scalar_one_or_none()
    return None


async def invite(
    session: AsyncSession,
    *,
    email: str | None = None,
    phone: str | None = None,
    name: str = "",
    role: str = "temple_admin",
    temple_id: str | None = None,
    invited_by: int | None = None,
) -> OperatorInvite:
    """Create a pending invitation. Owner-only at the route layer."""
    email, phone = _norm_email(email), _norm_phone(phone)
    if not email and not phone:
        raise OperatorError("an email or a mobile number is required")
    _validate_grant(role, temple_id)
    if await _by_identifier(session, email, phone) is not None:
        raise OperatorError("an operator with that email or mobile already exists")

    row = OperatorInvite(
        token=secrets.token_urlsafe(32),
        email=email,
        phone=phone,
        name=name.strip(),
        role=role,
        temple_id=temple_id,
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
    )
    session.add(row)
    await session.flush()
    return row


async def accept(session: AsyncSession, *, token: str, password: str) -> Operator:
    """Redeem an invite: create the operator, set the password, grant the role."""
    if len(password) < MIN_PASSWORD_LEN:
        raise OperatorError(f"password must be at least {MIN_PASSWORD_LEN} characters")

    row = (
        await session.execute(select(OperatorInvite).where(OperatorInvite.token == token))
    ).scalar_one_or_none()
    if row is None or row.accepted_at is not None:
        raise InviteInvalid("this invitation is not valid")
    expires = row.expires_at
    if expires.tzinfo is None:  # SQLite reads back naive; stored UTC
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise InviteInvalid("this invitation has expired")

    operator = Operator(
        email=row.email,
        phone=row.phone,
        name=row.name,
        password_hash=hash_password(password),
        active=True,
    )
    session.add(operator)
    await session.flush()
    session.add(
        OperatorRole(operator_id=operator.id, role=row.role, temple_id=row.temple_id)
    )
    row.accepted_at = datetime.now(UTC)
    await session.flush()
    return operator


async def login(session: AsyncSession, *, identifier: str, password: str) -> str:
    """Sign in with an email or a mobile. Returns a bearer token.

    One error for every failure mode — unknown account, no password set,
    deactivated, wrong password — so the response cannot be used to discover
    which operators exist.
    """
    ident = identifier.strip()
    operator = await _by_identifier(session, _norm_email(ident), _norm_phone(ident))
    if (
        operator is None
        or not operator.active
        or not verify_password(password, operator.password_hash)
    ):
        raise OperatorError("invalid credentials")

    token = secrets.token_urlsafe(32)
    session.add(
        OperatorSession(
            token=token,
            operator_id=operator.id,
            expires_at=datetime.now(UTC)
            + timedelta(hours=get_settings().session_ttl_hours),
        )
    )
    operator.last_login_at = datetime.now(UTC)
    await session.flush()
    return token


async def logout(session: AsyncSession, token: str) -> None:
    row = (
        await session.execute(
            select(OperatorSession).where(OperatorSession.token == token)
        )
    ).scalar_one_or_none()
    if row is not None:
        await session.delete(row)


async def grant(
    session: AsyncSession, *, operator_id: int, role: str, temple_id: str | None = None
) -> OperatorRole:
    _validate_grant(role, temple_id)
    existing = (
        await session.execute(
            select(OperatorRole).where(
                OperatorRole.operator_id == operator_id,
                OperatorRole.role == role,
                OperatorRole.temple_id == temple_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing  # idempotent
    row = OperatorRole(operator_id=operator_id, role=role, temple_id=temple_id)
    session.add(row)
    await session.flush()
    return row


async def revoke(session: AsyncSession, *, role_id: int) -> bool:
    row = await session.get(OperatorRole, role_id)
    if row is None:
        return False
    await session.delete(row)
    return True


async def set_active(session: AsyncSession, *, operator_id: int, active: bool) -> Operator:
    """Deactivate or restore an operator. Their live sessions are dropped too —
    revoking access has to mean *now*, not when the token happens to expire."""
    operator = await session.get(Operator, operator_id)
    if operator is None:
        raise OperatorError("unknown operator")
    operator.active = active
    if not active:
        for row in (
            await session.execute(
                select(OperatorSession).where(OperatorSession.operator_id == operator_id)
            )
        ).scalars().all():
            await session.delete(row)
    await session.flush()
    return operator


async def listing(session: AsyncSession) -> list[dict]:
    """Every operator with their grants, for the console's Operators page."""
    operators = (
        await session.execute(select(Operator).order_by(Operator.id))
    ).scalars().all()
    grants = (await session.execute(select(OperatorRole))).scalars().all()
    by_operator: dict[int, list[OperatorRole]] = {}
    for g in grants:
        by_operator.setdefault(g.operator_id, []).append(g)
    return [
        {
            "id": o.id,
            "email": o.email,
            "phone": o.phone,
            "name": o.name,
            "active": o.active,
            "pending": o.password_hash is None,
            "last_login_at": o.last_login_at,
            "roles": [
                {"id": g.id, "role": g.role, "temple_id": g.temple_id}
                for g in by_operator.get(o.id, [])
            ],
        }
        for o in operators
    ]
