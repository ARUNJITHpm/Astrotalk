"""HTTP routes for the admin analytics dashboard.

Every route is gated by ``require_admin`` (X-Admin-Token). The dashboard is
read-only: it reports aggregate metrics and never mutates domain data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.auth import AdminGuard, admin_required
from app.modules.admin.schemas import AdminOverview
from app.modules.admin.service import AdminService
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/admin", tags=["admin"])

_service = AdminService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class LoginPayload(BaseModel):
    # Accepts either the owner email or the legacy "admin" username.
    username: str
    password: str


def _admin_token() -> str:
    """The token the console uses on every later call (configured, else legacy)."""
    return get_settings().admin_token or "chargemod"


@router.post("/login", summary="Owner login (email or legacy username) → admin token")
async def admin_login_endpoint(payload: LoginPayload) -> dict:
    settings = get_settings()
    username = payload.username.strip().lower()

    # 1) Owner console login: the email + configured password.
    email_ok = (
        username == settings.admin_email.strip().lower()
        and payload.password == settings.admin_password
    )
    # 2) Legacy username/password kept working for existing bookmarks/scripts.
    legacy_ok = payload.username == "admin" and payload.password == "chargemod"

    if email_ok or legacy_ok:
        return {"token": _admin_token(), "email": settings.admin_email}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


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
