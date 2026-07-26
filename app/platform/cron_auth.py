"""Access control for scheduled "cron endpoints".

The prod host (HF Spaces Docker) has no Celery/Redis, so recurring jobs
(daily content pack, festival notifications) are token-gated POST endpoints
triggered by an external scheduler — GitHub Actions cron or cron-job.org —
sending the shared secret as the ``X-Cron-Token`` header. Policy mirrors
admin auth (app/modules/admin/auth.py):

  - token configured   → the header must match it (constant-time), else 401.
  - token empty + dev  → open (local convenience; curl the endpoint directly).
  - token empty + prod → 503: refuse rather than let anyone trigger sends.

The secret is compared with ``hmac.compare_digest`` and never logged.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.config import get_settings
from app.platform.db import get_session

_bearer = HTTPBearer(auto_error=False)


async def require_cron(
    x_cron_token: Annotated[str | None, Header()] = None,
) -> None:
    """Gate a scheduled endpoint on the ``X-Cron-Token`` header."""
    settings = get_settings()
    configured = settings.cron_token

    if not configured:
        if settings.app_env == "development":
            return
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cron endpoints are not configured (CRON_TOKEN unset)",
        )

    if not x_cron_token or not hmac.compare_digest(x_cron_token, configured):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing cron token",
        )


CronGuard = Depends(require_cron)


async def require_cron_or_admin(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    x_cron_token: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Accept EITHER credential: the scheduler's cron token or an operator's.

    Lets the console offer a manual "generate now" button for the same
    endpoints the scheduler fires, without sharing the cron secret.

    This resolves the operator itself rather than delegating to ``require_admin``
    — that used to be called as ``require_admin(x_admin_token)``, which bound
    the token to the *session* parameter and could therefore never actually
    authorise anyone. Passing an admin token here silently 401'd, and once
    ``require_admin`` became a pure dependency the same call started returning
    None for everybody, which is far worse. An explicit resolve avoids both.
    """
    from app.platform.admin_auth import resolve_operator

    try:
        await require_cron(x_cron_token)
        return
    except HTTPException:
        pass

    bearer = credentials.credentials if credentials else ""
    if await resolve_operator(session, bearer, x_admin_token) is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing cron or admin credentials",
        )


CronOrAdminGuard = Depends(require_cron_or_admin)
