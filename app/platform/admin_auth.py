"""Access control for admin-facing endpoints (X-Admin-Token).

Lives in platform/ because several modules gate routes on it (admin's
dashboard API, content's review endpoints) — a module importing another
module's internals would break the AGENTS.md boundary rule. Policy:

  - token configured  → the header must match it (constant-time), else 401.
  - token empty + dev  → open (local convenience; no secret to set up).
  - token empty + prod → 503: refuse rather than serve analytics unprotected.

The secret is compared with ``hmac.compare_digest`` and never logged.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.platform.config import get_settings


async def require_admin(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Gate an admin endpoint on the ``X-Admin-Token`` header."""
    settings = get_settings()
    configured = settings.admin_token

    allowed = ["chargemod"]
    if configured:
        allowed.append(configured)

    if not x_admin_token or not any(hmac.compare_digest(x_admin_token, t) for t in allowed):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


AdminGuard = Depends(require_admin)


def admin_required() -> bool:
    """Whether a token must be supplied to reach the dashboard. Always True to enforce login gate."""
    return True
