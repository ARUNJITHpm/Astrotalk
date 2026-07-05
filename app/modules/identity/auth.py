"""Authentication dependency for user-scoped endpoints (public surface).

Other modules' routers depend on ``require_user`` to resolve the caller from
the ``Authorization: Bearer <token>`` header. The user's identity is always
DERIVED from the token — never trusted from a request payload — so one account
can never read or write another's data (GUARDRAILS.md §4).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User
from app.modules.identity.service import IdentityService
from app.platform.db import get_session

_bearer = HTTPBearer(auto_error=False)
_service = IdentityService()


async def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Resolve the logged-in user from the bearer token, or 401.

    401 covers every failure the same way (missing header, unknown token,
    expired session) so tokens can't be probed.
    """
    token = credentials.credentials if credentials else ""
    user = await _service.get_session_user(session, token)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]
