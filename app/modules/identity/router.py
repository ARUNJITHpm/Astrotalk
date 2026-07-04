"""HTTP routes for the identity module.

Birth data is sensitive (GUARDRAILS.md §4): it is never logged and never placed
in a URL query param — only the numeric user id appears in paths.
"""

import inspect
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    ChartOut,
    LoginRequest,
    PhoneLookup,
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


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def onboard_user(data: UserCreate, session: SessionDep) -> User:
    if await _service.get_user_by_phone(session, data.phone) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A user with this mobile already exists"
        )
    user = await _service.create_user(session, data)
    natal_json = await _compute_natal_chart(user)
    await _service.save_chart(session, user.id, natal_json)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
async def login(data: LoginRequest, session: SessionDep) -> User:
    """Authenticate an existing account by mobile number + password.

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
    return user


@router.post("/recompute-chart", response_model=ChartOut)
async def recompute_chart(data: PhoneLookup, session: SessionDep):
    """Recompute and store a fresh natal chart for a registered mobile number.

    Unconditional (unlike the login self-heal): use after birth details change or
    to force an upgrade from a mock chart. Phone travels in the body, never the
    URL (GUARDRAILS.md §4).
    """
    user = await _service.get_user_by_phone(session, data.phone)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    natal_json = await _compute_natal_chart(user)
    chart = await _service.save_chart(session, user.id, natal_json)
    await session.commit()
    await session.refresh(chart)
    return chart


@router.post("/profile", response_model=ProfileOut)
async def get_profile(data: PhoneLookup, session: SessionDep) -> User:
    """Return the display name for a registered mobile number (name only, no
    birth data). Lets the web UI greet a returning user whose name wasn't cached
    locally. 404 if the number isn't registered."""
    user = await _service.get_user_by_phone(session, data.phone)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, session: SessionDep) -> User:
    user = await _service.get_user(session, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users/{user_id}/chart", response_model=ChartOut)
async def get_user_chart(user_id: int, session: SessionDep):
    chart = await _service.get_chart(session, user_id)
    if chart is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chart not found")
    return chart
