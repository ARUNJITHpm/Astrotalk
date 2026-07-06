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

from app.platform.config import get_settings


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
    x_cron_token: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Accept EITHER credential: the scheduler's cron token or an admin's token.

    Lets the /admin dashboard offer a manual "generate now" button for the
    same endpoints the scheduler fires, without sharing the cron secret."""
    from app.platform.admin_auth import require_admin

    try:
        await require_cron(x_cron_token)
        return
    except HTTPException:
        pass
    await require_admin(x_admin_token)


CronOrAdminGuard = Depends(require_cron_or_admin)
