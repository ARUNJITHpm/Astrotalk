"""HTTP routes for the admin analytics dashboard.

Every route is gated by ``require_admin``, which takes either the console's
X-Admin-Token or an app session belonging to an ``admin_phones`` mobile. The
dashboard is read-only: it reports aggregate metrics and never mutates domain
data.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Imported for its side effect: registering the operator tables on Base.metadata.
# Every table-owning module is reached through its router this way (app/main.py),
# and without it create_all/autogenerate never see operators or their sessions.
from app.modules.admin import models as _models  # noqa: F401
from app.modules.admin.auth import AdminGuard, admin_required
from app.modules.admin.schemas import AdminOverview
from app.modules.admin.service import AdminService
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/admin", tags=["admin"])

_service = AdminService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class LoginPayload(BaseModel):
    # The owner's configured email.
    username: str
    password: str


@router.post("/login", summary="Owner login (email + password) → admin token")
async def admin_login_endpoint(payload: LoginPayload) -> dict:
    """The owner's own sign-in. Operators use POST /admin/operators/login.

    The legacy ``admin`` / ``chargemod`` pair was accepted here until console
    plan Part 4; it is gone, along with the hardcoded token it returned. If
    ``admin_token`` is not configured there is no token to hand out and this
    route fails closed.
    """
    settings = get_settings()
    username = payload.username.strip().lower()

    if not (
        settings.admin_password
        and username == settings.admin_email.strip().lower()
        and hmac.compare_digest(payload.password, settings.admin_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN is not configured on this deployment",
        )
    return {"token": settings.admin_token, "email": settings.admin_email}


@router.get(
    "/users-chats",
    dependencies=[AdminGuard],
    summary="Fetch all users who have chat logs",
)
async def get_users_chats(session: SessionDep) -> list[dict]:
    return await _service.get_users_chats(session)


@router.get(
    "/user-chat/{phone}",
    dependencies=[AdminGuard],
    summary="Fetch raw chat log for a specific user",
)
async def get_user_chat(phone: str, session: SessionDep) -> list[dict]:
    return await _service.get_user_chat(session, phone)


@router.get("/config", summary="Whether the dashboard needs a token")
async def admin_config() -> dict:
    """Unauthenticated: lets the dashboard page decide whether to prompt for a
    token before its first data call. Reveals nothing but the on/off policy."""
    return {"token_required": admin_required()}


@router.get("/overview", response_model=AdminOverview, dependencies=[AdminGuard])
async def overview(session: SessionDep) -> dict:
    """Full analytics payload: users, charts, chat volume, and LLM token usage."""
    return await _service.overview(session)
