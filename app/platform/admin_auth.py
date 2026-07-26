"""Access control for admin-facing endpoints.

Lives in platform/ because several modules gate routes on it (admin's dashboard
API, content's review endpoints, temple partner tooling) — a module importing
another module's internals would break the AGENTS.md boundary rule.

Three credentials are accepted:

  1. ``X-Admin-Token`` — the configured shared secret, for scripts, cron and
     bookmarks. It resolves to a full **owner**.
  2. ``Authorization: Bearer <operator session>`` — a console sign-in. Carries
     whatever roles that operator was granted, which is the only credential
     that can be less than an owner.
  3. ``Authorization: Bearer <app session>`` whose user's mobile is listed in
     ``admin_phones``. Also a full owner. The phone is read from the
     server-side session, never from the request, so it cannot be spoofed.

There is no longer a hardcoded fallback secret. ``X-Admin-Token`` matches only
``settings.admin_token``; when that is unset the header cannot authenticate
anyone at all, and the ``admin_phones`` route is the only way in.

Secrets are compared with ``hmac.compare_digest`` and never logged.

Two gates are exported:
  - ``AdminGuard``          — the coarse "is an operator at all" check.
  - ``require_operator()``  — role- and scope-aware; returns an ``Operator``
                              describing what the caller may touch.
"""

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.config import get_settings, is_admin_phone
from app.platform.db import get_session

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Operator:
    """Who the caller is and what they are allowed to touch.

    ``operator_id`` is None for the two owner-by-credential paths (admin token,
    admin phone) — they are not rows in ``operators``.
    """

    operator_id: int | None
    roles: frozenset[str]
    temple_ids: frozenset[str]

    @property
    def is_owner(self) -> bool:
        return "owner" in self.roles

    def can_edit_temple(self, temple_id: str) -> bool:
        """Owners may edit any temple; a temple_admin only their own."""
        return self.is_owner or temple_id in self.temple_ids

    def visible_temple_ids(self) -> frozenset[str] | None:
        """Temples this operator may see. ``None`` means no restriction.

        Callers MUST treat None and an empty set differently: None is "all
        temples", an empty set is "none", and confusing them turns a scoped
        operator into an unscoped one.
        """
        return None if self.is_owner else self.temple_ids

    def require_temple(self, temple_id: str) -> None:
        if not self.can_edit_temple(temple_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="You do not manage this temple",
            )


_OWNER = Operator(operator_id=None, roles=frozenset({"owner"}), temple_ids=frozenset())


def _token_ok(supplied: str | None) -> bool:
    """Whether ``supplied`` matches the configured admin token (constant-time).

    Returns False when no token is configured: an unset secret must not mean
    "anything matches", and it no longer means "chargemod matches" either.
    """
    configured = get_settings().admin_token
    if not supplied or not configured:
        return False
    return hmac.compare_digest(supplied, configured)


async def _operator_from_session(session: AsyncSession, token: str) -> Operator | None:
    """Resolve a console session token to its operator and granted roles.

    Imported lazily: platform/ is the shared layer and must not pull a module in
    at import time.
    """
    if not token:
        return None
    from sqlalchemy import select

    from app.modules.admin.models import Operator as OperatorRow
    from app.modules.admin.models import OperatorRole, OperatorSession

    row = (
        await session.execute(
            select(OperatorSession, OperatorRow)
            .join(OperatorRow, OperatorRow.id == OperatorSession.operator_id)
            .where(OperatorSession.token == token)
        )
    ).first()
    if row is None:
        return None
    sess, operator = row
    if not operator.active:
        return None
    expires = sess.expires_at
    if expires.tzinfo is None:  # SQLite reads back naive; stored UTC
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        return None

    grants = (
        await session.execute(
            select(OperatorRole).where(OperatorRole.operator_id == operator.id)
        )
    ).scalars().all()
    return Operator(
        operator_id=operator.id,
        roles=frozenset(g.role for g in grants),
        temple_ids=frozenset(g.temple_id for g in grants if g.temple_id),
    )


async def _admin_phone_session(session: AsyncSession, token: str) -> bool:
    """Whether ``token`` is a live app session belonging to an admin mobile."""
    if not token:
        return False
    from app.modules.identity.service import IdentityService

    user = await IdentityService().get_session_user(session, token)
    return user is not None and is_admin_phone(user.phone)


async def resolve_operator(
    session: AsyncSession,
    bearer: str,
    x_admin_token: str | None,
) -> Operator | None:
    """The caller's operator context, or None when unauthenticated."""
    if _token_ok(x_admin_token):
        return _OWNER
    operator = await _operator_from_session(session, bearer)
    if operator is not None:
        return operator
    if await _admin_phone_session(session, bearer):
        return _OWNER
    return None


async def current_operator(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> Operator:
    """Any authenticated operator, whatever their role."""
    operator = await resolve_operator(
        session, credentials.credentials if credentials else "", x_admin_token
    )
    if operator is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin credentials",
        )
    return operator


def require_operator(*roles: str):
    """Dependency factory: authenticated, and holding one of ``roles``.

    An owner satisfies every role. No roles listed = any operator will do.
    401 is "we do not know you", 403 is "we know you and the answer is no" —
    keep them distinct so a console can tell a re-login from a permission wall.
    """

    async def _dep(
        operator: Annotated[Operator, Depends(current_operator)],
    ) -> Operator:
        if roles and not operator.is_owner and not (operator.roles & set(roles)):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Your role does not allow this",
            )
        return operator

    return _dep


async def require_admin(
    operator: Annotated[Operator, Depends(current_operator)],
) -> None:
    """Gate an admin endpoint on any authenticated operator.

    The coarse check the existing endpoints use. New endpoints should prefer
    ``require_operator(...)`` so their scope is explicit.
    """
    return None


AdminGuard = Depends(require_admin)
OperatorDep = Annotated[Operator, Depends(current_operator)]


def admin_required() -> bool:
    """Whether a credential must be supplied to reach the dashboard.

    Always True: the gate is never open, not even in dev.
    """
    return True
