"""HTTP routes for the admin analytics dashboard.

Every route is gated by ``require_admin``, which takes either the console's
X-Admin-Token or an app session belonging to an ``admin_phones`` mobile. The
dashboard is read-only: it reports aggregate metrics and never mutates domain
data.
"""

import hmac
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Imported for its side effect: registering the operator tables on Base.metadata.
# Every table-owning module is reached through its router this way (app/main.py),
# and without it create_all/autogenerate never see operators or their sessions.
from app.modules.admin import models as _models  # noqa: F401
from app.modules.admin import operators
from app.modules.admin.auth import AdminGuard, admin_required
from app.modules.admin.schemas import AdminOverview
from app.modules.admin.service import AdminService
from app.modules.bookings.service import BookingsService
from app.modules.commerce.service import CommerceService
from app.modules.identity.schemas import MemberCreate, MemberOut, MemberUpdate
from app.modules.identity.service import IdentityService
from app.platform.admin_auth import Operator, require_operator
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/admin", tags=["admin"])

_service = AdminService()
# Composed, never reached into: the admin module owns no domain data and talks
# to each module through its public service only (AGENTS.md).
_identity = IdentityService()
_commerce = CommerceService()
_bookings = BookingsService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# Owner-only: managing who may sign in is never delegated to a scoped role.
OwnerDep = Annotated[Operator, Depends(require_operator("owner"))]
# Any authenticated operator, whatever their role — used by /operators/me.
AnyOperatorDep = Annotated[Operator, Depends(require_operator())]


class LoginPayload(BaseModel):
    # The owner's configured email.
    username: str
    password: str


class ActiveIn(BaseModel):
    active: bool


class EntitlementIn(BaseModel):
    """A hand-granted unlock. ``granted_by`` is not a field: the console always
    records ``admin``, because letting it claim `purchase` or `referral` would
    forge the audit trail that tells the three apart."""

    user_id: int
    product_key: str
    reason: str = ""
    expires_at: datetime | None = None


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


# ---- Users and payments (console plan Part 8) ----
# Owner-only. A temple_admin runs a temple; the devotee register and the
# payment ledger are not theirs to read.
#
# The admin module owns no domain data — it composes IdentityService and
# CommerceService, never their tables (AGENTS.md). GUARDRAILS §4 shapes the
# surface: birth data never enters a URL, a query string or a list response,
# and appears only in one user's detail fetched by id.


@router.get("/users", summary="Search the devotee register (owner)")
async def list_users(
    session: SessionDep,
    operator: OwnerDep,
    q: Annotated[str | None, Query(description="name or mobile")] = None,
    active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """The only operator view of users was ``/admin/users-chats``, which lists
    people who have chat history — someone who signed up and never chatted was
    invisible."""
    total, rows = await _identity.operator_search(
        session, q=q, active=active, limit=limit, offset=offset
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": u.id,
                "name": u.name,
                "phone": u.phone,
                "active": u.active,
                "org_id": u.org_id,
                "created_at": u.created_at,
            }
            for u in rows
        ],
    }


@router.get("/users/{user_id}", summary="One devotee, with their activity (owner)")
async def user_detail(user_id: int, session: SessionDep, operator: OwnerDep) -> dict:
    """Birth PLACE is included here and nowhere else — an operator handling a
    "my chart looks wrong" report needs it. Date and time of birth are not:
    nothing an operator does requires them, and §4 keeps them out of every
    surface that does not strictly need them."""
    user = await _identity.get_user(session, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    entitlements = await _commerce.list_entitlements(session, user_id)
    _, payments = await _commerce.operator_payments(session, user_id=user_id, limit=50)
    bookings = await _bookings.list_for_user(session, user_id)
    await session.commit()  # list_for_user reconciles payment states
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "active": user.active,
        "birth_place": user.birth_place,
        "tz": user.tz,
        "org_id": user.org_id,
        "transcript_consent": user.transcript_consent,
        "created_at": user.created_at,
        "bookings": bookings,
        "payments": [
            {
                "id": p.id,
                "product": p.product,
                "amount_paise": p.amount_paise,
                "status": p.status,
                "razorpay_order_id": p.razorpay_order_id,
                "created_at": p.created_at,
                "paid_at": p.paid_at,
            }
            for p in payments
        ],
        "entitlements": [
            {
                "id": e.id,
                "product_key": e.product_key,
                "granted_by": e.granted_by,
                "source": e.source,
                "expires_at": e.expires_at,
                "created_at": e.created_at,
            }
            for e in entitlements
        ],
    }


@router.post("/users/{user_id}/active", summary="Enable or disable an account (owner)")
async def set_user_active(
    user_id: int, payload: ActiveIn, session: SessionDep, operator: OwnerDep
) -> dict:
    """Disabling drops every live session as well as blocking the next login —
    otherwise the account keeps working for up to the session TTL, which is not
    what anyone means by "disable"."""
    try:
        user = await _identity.set_active(session, user_id=user_id, active=payload.active)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return {"id": user.id, "active": user.active}


# ---- One user's family board and chart (console plan Part 12) ----
# Owner-only, and reachable only through a user id that is already in the path
# of an owner-gated route. Both carry birth data, so GUARDRAILS §4 shapes them:
# they never appear in a list, a search result or a query string, and the
# operator has to have navigated to one named person to see either.
#
# The write half exists because an operator taking a booking over the phone is
# told "book it for my mother, her star is Pooram" — and until now only the
# devotee's own app could record that, which is no use mid-call.


@router.get(
    "/users/{user_id}/family",
    response_model=list[MemberOut],
    summary="One user's family board (owner)",
)
async def user_family(user_id: int, session: SessionDep, operator: OwnerDep) -> list[dict]:
    members = await _identity.operator_members(session, user_id)
    if members is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    await session.commit()  # the self row is created on first read
    return members


@router.post(
    "/users/{user_id}/family",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add someone to a user's family board (owner)",
)
async def add_family_member(
    user_id: int, payload: MemberCreate, session: SessionDep, operator: OwnerDep
) -> dict:
    if await _identity.get_user(session, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        out = await _identity.add_member(session, user_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Family board is full"
        ) from exc
    await session.commit()
    return out


@router.patch(
    "/users/{user_id}/family/{member_id}",
    response_model=MemberOut,
    summary="Correct a family member's name, relation, star or birth date (owner)",
)
async def edit_family_member(
    user_id: int,
    member_id: int,
    payload: MemberUpdate,
    session: SessionDep,
    operator: OwnerDep,
) -> dict:
    out = await _identity.update_member(
        session, user_id, member_id, payload.model_dump(exclude_unset=True)
    )
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    await session.commit()
    return out


@router.delete(
    "/users/{user_id}/family/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a family member (owner)",
)
async def remove_family_member(
    user_id: int, member_id: int, session: SessionDep, operator: OwnerDep
) -> None:
    result = await _identity.delete_member(session, user_id, member_id)
    if result == "not_found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    if result == "self":
        # The account holder's own row is the one a booking defaults to; deleting
        # it would leave the account unable to book for itself.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The account holder's own row cannot be removed",
        )
    await session.commit()


@router.get("/users/{user_id}/chart", summary="One user's natal chart (owner)")
async def user_chart(user_id: int, session: SessionDep, operator: OwnerDep) -> dict:
    """The computed chart, for answering a question about a reading.

    Returned only for a single named user an operator has already opened. It is
    not searchable, not exported, and not present in any list — a chart is birth
    data by another name.
    """
    if await _identity.get_user(session, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    chart = await _identity.get_chart(session, user_id)
    if chart is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No chart has been computed for this user"
        )
    return {"computed_at": chart.computed_at, "natal": chart.natal_json}


@router.get("/engagement", summary="Check-ins, streaks and milestones (owner)")
async def engagement(
    session: SessionDep,
    operator: OwnerDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict:
    """Console plan Part 12.

    Every engagement figure the product had was per-caller, so a devotee could
    see their own streak and nobody could see whether the feature worked at all.
    """
    return await _service.engagement(session, limit=limit)


@router.get("/payments", summary="The payment ledger (owner)")
async def list_payments(
    session: SessionDep,
    operator: OwnerDep,
    payment_status: Annotated[
        str | None, Query(alias="status", description="created|paid|failed")
    ] = None,
    user_id: Annotated[int | None, Query()] = None,
    product: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    try:
        total, rows = await _commerce.operator_payments(
            session,
            status=payment_status,
            user_id=user_id,
            product=product,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": p.id,
                "user_id": p.user_id,
                "product": p.product,
                "amount_paise": p.amount_paise,
                "currency": p.currency,
                "status": p.status,
                "razorpay_order_id": p.razorpay_order_id,
                "razorpay_payment_id": p.razorpay_payment_id,
                "created_at": p.created_at,
                "paid_at": p.paid_at,
            }
            for p in rows
        ],
    }


@router.post("/entitlements", summary="Grant an entitlement by hand (owner)")
async def grant_entitlement(
    payload: EntitlementIn, session: SessionDep, operator: OwnerDep
) -> dict:
    """``granted_by="admin"`` has been a declared value since the module was
    written with no route that could produce one, so a goodwill unlock or a
    comped report meant editing the database.

    Always recorded as ``admin`` — the console cannot claim a grant came from a
    purchase or a referral, because that would forge the audit trail that
    distinguishes them. ``source`` is the operator's free-text reason.
    """
    user = await _identity.get_user(session, payload.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    row = await _commerce.grant_entitlement(
        session,
        user_id=payload.user_id,
        product_key=payload.product_key,
        granted_by="admin",
        source=payload.reason or f"granted by operator {operator.operator_id or 'token'}",
        expires_at=payload.expires_at,
    )
    await session.commit()
    return {
        "id": row.id,
        "user_id": row.user_id,
        "product_key": row.product_key,
        "granted_by": row.granted_by,
        "source": row.source,
        "expires_at": row.expires_at,
    }


@router.delete(
    "/entitlements/{entitlement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw a grant (owner)",
)
async def revoke_entitlement(
    entitlement_id: int, session: SessionDep, operator: OwnerDep
) -> None:
    if not await _commerce.revoke_entitlement(session, entitlement_id=entitlement_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown entitlement")
    await session.commit()


# ---- Operator accounts (console plan Part 4) ----
# Invite-only: the owner creates accounts, nobody self-registers. Sign-in and
# accept are PUBLIC by necessity — you cannot present operator credentials
# before you have any — and are rate-limited by their own failure modes:
# login returns one indistinguishable error, accept needs an unguessable token.


class OperatorLogin(BaseModel):
    identifier: str  # email or mobile — whichever the owner invited them with
    password: str


class OperatorInviteIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    name: str = ""
    role: str = "temple_admin"
    temple_id: str | None = None


class OperatorAcceptIn(BaseModel):
    token: str
    password: str


class GrantIn(BaseModel):
    role: str
    temple_id: str | None = None


@router.post("/operators/login", summary="Operator sign-in → bearer token")
async def operator_login(payload: OperatorLogin, session: SessionDep) -> dict:
    try:
        token = await operators.login(
            session, identifier=payload.identifier, password=payload.password
        )
    except operators.OperatorError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        ) from None
    await session.commit()
    return {"token": token}


@router.get("/operators/me", summary="Who the caller is and what they may touch")
async def operator_me(operator: AnyOperatorDep) -> dict:
    """The console's first call after sign-in (console plan Part 9).

    Part 4 issues a session token but nothing told the holder what it is *for*,
    so a console had no way to render a role-aware sidebar. This returns the
    already-resolved ``Operator`` — no new authorisation logic, just the same
    answer `require_operator` computes, made readable.

    ``temple_ids`` is empty for an owner, who is unrestricted. A client must not
    read "empty" as "no temples": `is_owner` is the field that distinguishes
    them, and conflating the two is how a scoped operator becomes unscoped.
    Because it takes any authenticated operator, an `X-Admin-Token` caller sees
    ``operator_id: null`` with the owner role — they are a credential, not a row.
    """
    return {
        "operator_id": operator.operator_id,
        "roles": sorted(operator.roles),
        "temple_ids": sorted(operator.temple_ids),
        "is_owner": operator.is_owner,
    }


@router.post("/operators/accept", summary="Redeem an invitation and set a password")
async def operator_accept(payload: OperatorAcceptIn, session: SessionDep) -> dict:
    try:
        operator = await operators.accept(
            session, token=payload.token, password=payload.password
        )
    except operators.InviteInvalid as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except operators.OperatorError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return {"id": operator.id, "email": operator.email, "phone": operator.phone}


@router.post(
    "/operators/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Drop the caller's console session",
)
async def operator_logout(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Revoke the presented session server-side rather than trusting the client
    to forget it. Always 204: whether the token existed is not the caller's
    business, and a failed logout must never leave a usable token behind."""
    if authorization and authorization.lower().startswith("bearer "):
        await operators.logout(session, authorization.split(None, 1)[1].strip())
        await session.commit()


@router.get("/operators", summary="Every operator and their grants (owner)")
async def operator_list(session: SessionDep, operator: OwnerDep) -> list[dict]:
    return await operators.listing(session)


@router.post("/operators/invite", summary="Invite an operator by email or mobile (owner)")
async def operator_invite(
    payload: OperatorInviteIn, session: SessionDep, operator: OwnerDep
) -> dict:
    try:
        row = await operators.invite(
            session,
            email=payload.email,
            phone=payload.phone,
            name=payload.name,
            role=payload.role,
            temple_id=payload.temple_id,
            invited_by=operator.operator_id,
        )
    except operators.OperatorError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    # The token is returned rather than emailed: there is no mail transport in
    # this deployment yet, so the owner passes the link on themselves.
    return {"invite_token": row.token, "expires_at": row.expires_at, "role": row.role}


@router.post("/operators/{operator_id}/roles", summary="Grant a role (owner)")
async def operator_grant(
    operator_id: int, payload: GrantIn, session: SessionDep, operator: OwnerDep
) -> dict:
    try:
        row = await operators.grant(
            session, operator_id=operator_id, role=payload.role, temple_id=payload.temple_id
        )
    except operators.OperatorError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return {"id": row.id, "role": row.role, "temple_id": row.temple_id}


@router.delete(
    "/operators/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a role (owner)",
)
async def operator_revoke(role_id: int, session: SessionDep, operator: OwnerDep) -> None:
    if not await operators.revoke(session, role_id=role_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown role grant")
    await session.commit()


@router.post("/operators/{operator_id}/active", summary="Enable or disable (owner)")
async def operator_set_active(
    operator_id: int, payload: ActiveIn, session: SessionDep, operator: OwnerDep
) -> dict:
    """Takes ``{"active": bool}`` as a body.

    It used to declare `active: bool` bare, which FastAPI reads as a QUERY
    parameter — so this one endpoint wanted `?active=false` while its three
    siblings (temples, astrologers, users) all take a body. Nothing called it
    yet and no test covered it; the console is the first client, so it was
    aligned rather than left as a trap.
    """
    active = payload.active
    try:
        row = await operators.set_active(session, operator_id=operator_id, active=active)
    except operators.OperatorError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return {"id": row.id, "active": row.active}
