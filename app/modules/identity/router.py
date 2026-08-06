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
    AnonRequest,
    AnonResponse,
    AuthResponse,
    BirthDetailsIn,
    BirthDetailsOut,
    ChartOut,
    HomeTempleIn,
    HomeTempleOut,
    LoginRequest,
    MemberCreate,
    MemberOut,
    MemberUpdate,
    MilestoneOut,
    PasswordReset,
    PasswordResetVerify,
    ProfileOut,
    ReferralSummary,
    StatsOut,
    UserCreate,
    UserOut,
)
from app.modules.identity.service import IdentityService
from app.platform.config import get_settings, is_admin_phone
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
    if "vargas" not in natal:
        return True
    # Charts computed before chovva parihara (cancellation) rules lack the
    # "severity" field — recompute so cancelled doshas stop reading as present.
    chovva = (natal.get("doshas") or {}).get("chovva_dosha") or {}
    return bool(chovva.get("computed")) and "severity" not in chovva


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
        is_admin=is_admin_phone(user.phone),
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
    if data.ref:
        # Chart saved above = onboarding complete = the referral activates now.
        await _service.record_referral(session, data.ref, user.id)
    result = await _auth_response(session, user)
    await session.commit()
    return result


@router.post("/anon", response_model=AnonResponse)
async def anon_session(payload: AnonRequest, session: SessionDep) -> AnonResponse:
    """No-signup device session — the app calls this on first run so temple
    check-ins, bookings and the family board work without an account.

    The returned ``anon_id`` is server-minted; send it back to resume the same
    anonymous account. An anonymous account is never an administrator, and its
    key carries no digits, so it can never resolve to a real user's number
    (see IdentityService.get_or_create_anon_user).
    """
    user, anon_id = await _service.get_or_create_anon_user(session, payload.anon_id)
    base = await _auth_response(session, user)
    await session.commit()
    return AnonResponse(**base.model_dump(), anon_id=anon_id)


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
async def me(user: CurrentUser) -> ProfileOut:
    """The logged-in user's display profile (name only, no birth data)."""
    return ProfileOut(
        phone=user.phone,
        name=user.name,
        is_admin=is_admin_phone(user.phone),
    )


@router.get("/me/members", response_model=list[MemberOut])
async def list_members(user: CurrentUser, session: SessionDep) -> list[dict]:
    """The account's family board (poojas are booked in a member's name). The
    account holder's own 'self' row is created on first read."""
    out = await _service.list_members(session, user)
    await session.commit()
    return out


@router.post("/me/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    payload: MemberCreate, user: CurrentUser, session: SessionDep
) -> dict:
    try:
        out = await _service.add_member(session, user.id, payload)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Family board is full")
    await session.commit()
    return out


@router.patch("/me/members/{member_id}", response_model=MemberOut)
async def update_member(
    member_id: int, payload: MemberUpdate, user: CurrentUser, session: SessionDep
) -> dict:
    out = await _service.update_member(
        session, user.id, member_id, payload.model_dump(exclude_unset=True)
    )
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    await session.commit()
    return out


@router.delete("/me/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: int, user: CurrentUser, session: SessionDep
) -> None:
    result = await _service.delete_member(session, user.id, member_id)
    if result == "not_found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    if result == "self":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Can't remove your own row"
        )
    await session.commit()


@router.get("/me/stats", response_model=StatsOut)
async def my_stats(user: CurrentUser, session: SessionDep) -> dict:
    """Profile header counters: temples visited, poojas, streak, badges."""
    return await _service.profile_stats(session, user.id)


@router.get("/me/milestones", response_model=list[MilestoneOut])
async def my_milestones(user: CurrentUser, session: SessionDep) -> list[dict]:
    """Badge progress toward each milestone, from real activity."""
    return await _service.milestones(session, user.id)


@router.post("/transcript-consent", status_code=status.HTTP_204_NO_CONTENT)
async def transcript_consent(
    payload: dict, user: CurrentUser, session: SessionDep
) -> None:
    """The customer's explicit switch letting their org's astrologer read
    their chat transcripts (Part 4c). Only the account itself can flip it."""
    await _service.set_transcript_consent(session, user, bool(payload.get("allow")))
    await session.commit()


@router.get("/referral", response_model=ReferralSummary)
async def my_referral(user: CurrentUser, session: SessionDep) -> ReferralSummary:
    """The logged-in user's referral panel: code, link, progress, reward.

    Minting the code is lazy — first open creates it. The share link lands on
    the login page with ``?ref=`` prefilled; friends registering through it
    are credited automatically.
    """
    summary = await _service.referral_summary(session, user.id)
    await session.commit()
    base = get_settings().public_base_url.rstrip("/")
    return ReferralSummary(
        share_link=f"{base}/ui/login?ref={summary['code']}",
        **summary,
    )


@router.get("/me/home-temple", response_model=HomeTempleOut)
async def my_home_temple(user: CurrentUser) -> HomeTempleOut:
    """The temple this account chose during onboarding, or null."""
    return HomeTempleOut(temple_id=user.home_temple_id)


@router.put("/me/home-temple", response_model=HomeTempleOut)
async def set_my_home_temple(
    payload: HomeTempleIn, user: CurrentUser, session: SessionDep
) -> HomeTempleOut:
    """Record the chosen temple against the account.

    It lived in `localStorage`, so clearing site data or opening the app on a
    second phone threw away the one thing onboarding asks for — while the
    account itself survived, because it is keyed by a server-minted anon id.

    The id is validated here rather than constrained in the database: identity
    and temples are separate modules that compose through services (AGENTS.md),
    and a foreign key would also make retiring a temple fail against every
    account that had chosen it.
    """
    from app.modules.temples.service import TemplesService

    temple_id = payload.temple_id.strip()
    if TemplesService().get_temple(temple_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple not found")
    user.home_temple_id = temple_id
    await session.commit()
    return HomeTempleOut(temple_id=temple_id)


@router.get("/me/chart", response_model=ChartOut)
async def my_chart(user: CurrentUser, session: SessionDep):
    """This account's stored natal chart, or 404 when it has none.

    Token-scoped, like /me/members and /me/stats. The alternative —
    ``/users/{id}/chart`` — obliges the client to know and send its own user id,
    which puts an account identifier in a URL for no gain: the session already
    says who is asking, and it cannot be spoofed.

    404 is the ordinary case, not an error. Nithara accounts start anonymous and
    birth details are optional, so most accounts have no chart and the profile
    screen offers to make one.
    """
    chart = await _service.get_chart(session, user.id)
    if chart is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No chart yet")
    return chart


@router.get("/me/birth", response_model=BirthDetailsOut)
async def my_birth_details(user: CurrentUser):
    """The three fields behind this account's chart, for correcting them.

    Its own account, over its own session — which is the one place birth data
    legitimately goes. GUARDRAILS §4 is about URLs, query strings, logs and list
    responses; a person reading back what they themselves entered is none of
    those, and the alternative is making them retype all three to fix a typo in
    one.
    """
    return BirthDetailsOut(
        dob=user.dob,
        birth_time=user.birth_time,
        birth_place=user.birth_place,
    )


@router.put("/me/birth", response_model=ChartOut)
async def set_birth_details(
    payload: BirthDetailsIn, user: CurrentUser, session: SessionDep
):
    """Record the logged-in account's birth details and compute its chart.

    The missing half of the chart flow. ``recompute-chart`` recomputes from
    details already on the row, and the only writer of those details was the
    signup form — which an anonymous account never sees. So an app account could
    READ a chart it had no way to create, and the profile screen said "coming
    soon" because there was genuinely nothing to show.

    The account comes from the session token, so one user can never write
    another's birth data — the same rule ``/users/{id}`` enforces for reads.

    Geocodes the place before computing: the lagna is location-sensitive, and a
    chart drawn on the placeholder coordinates is wrong in the one way a devotee
    would notice.
    """
    user.dob = payload.dob
    user.birth_time = payload.birth_time
    user.birth_place = payload.birth_place.strip()
    user = await _service.regeocode_user(session, user)
    natal_json = await _compute_natal_chart(user)
    chart = await _service.save_chart(session, user.id, natal_json)
    await session.commit()
    await session.refresh(chart)
    return chart


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
