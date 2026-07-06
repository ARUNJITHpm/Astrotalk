"""HTTP routes for the identity module.

Birth data is sensitive (GUARDRAILS.md §4): it is never logged and never placed
in a URL query param — only the numeric user id appears in paths.
"""

import inspect
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.identity.auth import CurrentUser
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    AuthResponse,
    ChartOut,
    LoginRequest,
    PasswordReset,
    PasswordResetVerify,
    ProfileOut,
    UserCreate,
    UserOut,
)
from app.modules.identity.service import IdentityService
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/identity", tags=["identity"])

_service = IdentityService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _compute_natal_chart(user: User) -> dict[str, Any]:
    """Compute the natal chart via astrology_engine's PUBLIC service.

    astrology_engine is owned by a different agent (AGENTS.md) and is currently a
    stub. Until it exposes `compute_natal_chart`, we persist a 'pending'
    placeholder so onboarding still completes; the real chart is computed
    automatically once that module ships the method. We never reach into
    astrology_engine's internals — only its public service.
    """
    service = AstrologyEngineService()
    compute = getattr(service, "compute_natal_chart", None)
    if compute is None:
        return {"status": "pending", "reason": "astrology_engine not yet implemented"}

    result = compute(
        dob=user.dob,
        birth_time=user.birth_time,
        lat=user.lat,
        lng=user.lng,
        tz=user.tz,
    )
    if inspect.isawaitable(result):
        result = await result
    return result


def _chart_is_stale(natal: dict[str, Any] | None) -> bool:
    """A chart needs recomputing if it's missing, a mock, or a pending placeholder.

    Charts stored while MOCK_EPHEMERIS was on carry ``mock: true``; once the real
    Swiss Ephemeris engine is enabled they should be replaced with real ones.
    """
    if natal is None:
        return True
    if bool(natal.get("mock")) or natal.get("status") == "pending":
        return True
    # Real charts stored before divisional charts existed lack "vargas" — they
    # gain them on recompute.
    return "vargas" not in natal


async def _refresh_chart_if_stale(session: AsyncSession, user: User) -> None:
    """Recompute + save the user's chart when it's stale and the real engine is on.

    Runs at login so accounts onboarded during mock mode heal automatically.
    No-op while the engine itself is mocked (recomputing would gain nothing).
    """
    if get_settings().mock_ephemeris:
        return
    chart = await _service.get_chart(session, user.id)
    if not _chart_is_stale(chart.natal_json if chart else None):
        return
    natal_json = await _compute_natal_chart(user)
    await _service.save_chart(session, user.id, natal_json)
    await session.commit()


async def _auth_response(session: AsyncSession, user: User) -> AuthResponse:
    """Mint a login session for ``user`` and shape the auth payload."""
    login = await _service.create_session(session, user)
    return AuthResponse(
        user=UserOut.model_validate(user),
        token=login.token,
        expires_at=login.expires_at,
    )


@router.post(
    "/users", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def onboard_user(data: UserCreate, session: SessionDep) -> AuthResponse:
    """Register, compute the first chart, and log the new account in (one
    round-trip: the response carries the bearer session token)."""
    if await _service.get_user_by_phone(session, data.phone) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A user with this mobile already exists"
        )
    user = await _service.create_user(session, data)
    natal_json = await _compute_natal_chart(user)
    await _service.save_chart(session, user.id, natal_json)
    result = await _auth_response(session, user)
    await session.commit()
    return result


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, session: SessionDep) -> AuthResponse:
    """Authenticate by mobile number + password and mint a session token.

    Returns 401 on any failure (unknown number or wrong password), without
    revealing which — so the number space can't be probed for registrations.
    """
    user = await _service.authenticate(session, data.phone, data.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mobile number or password",
        )
    # Self-heal: charts stored while the ephemeris was mocked get recomputed with
    # the real engine on the user's next login.
    await _refresh_chart_if_stale(session, user)
    result = await _auth_response(session, user)
    await session.commit()
    return result


@router.post("/password/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_reset_identity(
    data: PasswordResetVerify, session: SessionDep
) -> None:
    """Check the birth details behind a forgotten-password reset.

    Gates the UI's second step (choose a new password) so the user isn't asked
    for one until they've proven who they are. Returns 204 on a match, 401
    otherwise — without saying which detail was wrong, so the account space
    can't be probed. /password/reset re-verifies, so this is UX only, not the
    security boundary.
    """
    user = await _service.verify_identity(session, data.phone, data.name, data.dob)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="These details do not match an account",
        )


@router.post("/password/reset", response_model=AuthResponse)
async def reset_password(data: PasswordReset, session: SessionDep) -> AuthResponse:
    """Reset the password after re-verifying the birth details, then log in.

    A forgotten-password recovery for a channel with no SMS/email: the owner
    re-proves identity with their registration birth details and sets a new
    password. On success every old session is revoked and a fresh one is minted,
    so the response logs them straight in. 401 on any identity mismatch.
    """
    if len(data.new_password) < 4:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 4 characters",
        )
    user = await _service.verify_identity(session, data.phone, data.name, data.dob)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="These details do not match an account",
        )
    await _service.reset_password(session, user, data.new_password)
    result = await _auth_response(session, user)
    await session.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ],
    session: SessionDep,
) -> None:
    """Revoke the presented session token. Idempotent — a missing or already
    revoked token still returns 204 (nothing to enumerate)."""
    if credentials:
        await _service.revoke_session(session, credentials.credentials)
        await session.commit()


@router.get("/me", response_model=ProfileOut)
async def me(user: CurrentUser) -> User:
    """The logged-in user's display profile (name only, no birth data)."""
    return user


@router.post("/recompute-chart", response_model=ChartOut)
async def recompute_chart(user: CurrentUser, session: SessionDep):
    """Recompute and store a fresh natal chart for the LOGGED-IN user.

    Unconditional (unlike the login self-heal): use after birth details change or
    to force an upgrade from a mock chart. Re-geocodes the birth place first, so
    accounts onboarded with the placeholder location gain real coordinates (and
    a correct lagna) here. The account is taken from the session token — one
    user can never recompute (or probe) another's chart.
    """
    user = await _service.regeocode_user(session, user)
    natal_json = await _compute_natal_chart(user)
    chart = await _service.save_chart(session, user.id, natal_json)
    await session.commit()
    await session.refresh(chart)
    return chart


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, user: CurrentUser, session: SessionDep) -> User:
    """Full profile (incl. birth data) — only for the account itself."""
    if user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your account")
    return user


@router.get("/users/{user_id}/chart", response_model=ChartOut)
async def get_user_chart(user_id: int, user: CurrentUser, session: SessionDep):
    """The newest natal chart — only for the account itself."""
    if user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your account")
    chart = await _service.get_chart(session, user_id)
    if chart is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chart not found")
    return chart
