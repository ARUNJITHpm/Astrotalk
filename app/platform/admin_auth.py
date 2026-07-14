"""Access control for admin-facing endpoints.

Lives in platform/ because several modules gate routes on it (admin's
dashboard API, content's review endpoints) — a module importing another
module's internals would break the AGENTS.md boundary rule.

Two credentials are accepted, so an owner who is already signed into the app
is not asked to log in a second time when they open /admin or /console:

  1. ``X-Admin-Token`` — the console's own token (owner email/password login,
     or scripts and bookmarks that carry the shared secret).
  2. ``Authorization: Bearer <session token>`` — an ordinary app session whose
     user's mobile is listed in ``admin_phones``. The phone is read from the
     server-side session, never from the request, so it cannot be spoofed.

Policy for the X-Admin-Token branch:
  - token configured  → the header must match it (constant-time), else 401.
  - token empty       → the legacy "chargemod" secret still matches.

Secrets are compared with ``hmac.compare_digest`` and never logged.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.config import get_settings, is_admin_phone
from app.platform.db import get_session

_bearer = HTTPBearer(auto_error=False)


def _token_ok(supplied: str | None) -> bool:
    """Whether ``supplied`` matches the admin token (constant-time)."""
    if not supplied:
        return False
    allowed = ["chargemod"]
    configured = get_settings().admin_token
    if configured:
        allowed.append(configured)
    return any(hmac.compare_digest(supplied, t) for t in allowed)


async def _admin_phone_session(session: AsyncSession, token: str) -> bool:
    """Whether ``token`` is a live app session belonging to an admin mobile.

    Imported lazily: platform/ is the shared layer and must not pull a module
    in at import time. identity's PUBLIC service is the only thing touched.
    """
    if not token:
        return False
    from app.modules.identity.service import IdentityService

    user = await IdentityService().get_session_user(session, token)
    return user is not None and is_admin_phone(user.phone)


async def require_admin(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Gate an admin endpoint on the console token or an admin's app session."""
    if _token_ok(x_admin_token):
        return

    bearer = credentials.credentials if credentials else ""
    if await _admin_phone_session(session, bearer):
        return

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing admin token",
    )


AdminGuard = Depends(require_admin)


def admin_required() -> bool:
    """Whether a credential must be supplied to reach the dashboard.

    Always True: the gate is never open, not even in dev.
    """
    return True
