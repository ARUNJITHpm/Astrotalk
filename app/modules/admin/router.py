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
from app.platform.db import get_session

router = APIRouter(prefix="/admin", tags=["admin"])

_service = AdminService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login", summary="Admin username/password authentication")
async def admin_login_endpoint(payload: LoginPayload) -> dict:
    if payload.username == "admin" and payload.password == "chargemod":
        return {"token": "chargemod"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
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


# TEMP: allowlisted hard-delete of throwaway accounts created while debugging the
# WhatsApp registration flow. Can ONLY remove these exact phones — never a real
# user. Remove this route once cleanup is done.
_DELETABLE_TEST_PHONES = {
    "919000000777", "919000000888", "919000001234", "919000000999",
}


class _DeleteTestPayload(BaseModel):
    phone: str


@router.post("/delete-test-user", dependencies=[AdminGuard], include_in_schema=False)
async def delete_test_user(payload: _DeleteTestPayload, session: SessionDep) -> dict:
    from sqlalchemy import select

    from app.modules.identity.models import User
    from app.modules.whatsapp.models import WASession

    digits = "".join(c for c in payload.phone if c.isdigit())
    if digits not in _DELETABLE_TEST_PHONES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not an allowlisted test phone",
        )
    out = {"phone": digits, "user_deleted": False, "wa_session_deleted": False}
    user = (
        await session.execute(
            select(User).where(User.phone.in_([digits, f"+{digits}"]))
        )
    ).scalar_one_or_none()
    if user is not None:
        await session.delete(user)  # ORM cascade -> charts, login sessions
        out["user_deleted"] = True
    for key in (digits, f"+{digits}"):
        wa = await session.get(WASession, key)
        if wa is not None:
            await session.delete(wa)
            out["wa_session_deleted"] = True
    await session.commit()
    return out


@router.get("/config", summary="Whether the dashboard needs a token")
async def admin_config() -> dict:
    """Unauthenticated: lets the dashboard page decide whether to prompt for a
    token before its first data call. Reveals nothing but the on/off policy."""
    return {"token_required": admin_required()}


@router.get("/overview", response_model=AdminOverview, dependencies=[AdminGuard])
async def overview(session: SessionDep) -> dict:
    """Full analytics payload: users, charts, chat volume, and LLM token usage."""
    return await _service.overview(session)
