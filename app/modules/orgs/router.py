"""HTTP routes for the orgs module (GROWTH_PLAN.md Part 4a).

  - /orgs (admin)            — create/list tenants.
  - /orgs/{handle}/public    — branding anyone may fetch.
  - /a/{handle}/ui, /a/{handle}/login — the white-label app: the SAME chat
    and login pages with the org's branding injected (root-level router).

The injected snippet only re-skins the page (title, brand text, theme colors)
and tags registrations with the org handle; the chat brain, guardrails, and
API stay identical for every tenant.
"""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.auth import CurrentUser
from app.modules.orgs import booking as booking_svc
from app.modules.orgs.models import Org
from app.modules.orgs.schemas import (
    BookingCreate,
    BookingCreated,
    BookingOut,
    OrgCreate,
    OrgOut,
    OrgPublic,
    SlotCreate,
    SlotOut,
)
from app.modules.orgs.service import OrgError, OrgsService
from app.platform.admin_auth import AdminGuard
from app.platform.db import get_session

router = APIRouter(prefix="/orgs", tags=["orgs"])

# White-label page routes, mounted at the root.
whitelabel_router = APIRouter(tags=["orgs"])

_service = OrgsService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@router.post(
    "", response_model=OrgOut, status_code=status.HTTP_201_CREATED, dependencies=[AdminGuard]
)
async def create_org(payload: OrgCreate, session: SessionDep) -> OrgOut:
    owner_user_id = None
    if payload.owner_phone:
        # Identity's PUBLIC service — the owner must already have an account.
        from app.modules.identity.service import IdentityService

        owner = await IdentityService().get_user_by_phone(session, payload.owner_phone)
        if owner is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Owner account not found — register first"
            )
        owner_user_id = owner.id
    try:
        org = await _service.create_org(
            session,
            handle=payload.handle,
            name=payload.name,
            persona_overlay=payload.persona_overlay,
            theme_primary=payload.theme_primary,
            theme_bg=payload.theme_bg,
            plan=payload.plan,
            owner_user_id=owner_user_id,
        )
    except OrgError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return OrgOut.model_validate(org)


@router.get("", response_model=list[OrgOut], dependencies=[AdminGuard])
async def list_orgs(session: SessionDep) -> list[OrgOut]:
    return [OrgOut.model_validate(o) for o in await _service.list_orgs(session)]


@router.get("/{handle}/public", response_model=OrgPublic)
async def org_public(handle: str, session: SessionDep) -> OrgPublic:
    org = await _service.get_by_handle(session, handle)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Org not found")
    return OrgPublic(**_service.public_branding(org))


# ---- Booking (Part 4b) ----


async def _org_or_404(session: AsyncSession, handle: str) -> Org:
    org = await _service.get_by_handle(session, handle)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Org not found")
    return org


def _require_owner(org: Org, user) -> None:
    if org.owner_user_id is None or user.id != org.owner_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Org owner only")


@router.post(
    "/{handle}/booking/slots",
    response_model=SlotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a weekly availability window (org owner)",
)
async def add_slot(
    handle: str, payload: SlotCreate, user: CurrentUser, session: SessionDep
) -> SlotOut:
    org = await _org_or_404(session, handle)
    _require_owner(org, user)
    try:
        slot = await booking_svc.add_slot(
            session,
            org_id=org.id,
            weekday=payload.weekday,
            start=payload.start,
            end=payload.end,
            duration_min=payload.duration_min,
            price_paise=payload.price_paise,
        )
    except booking_svc.BookingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return SlotOut.model_validate(slot)


@router.get(
    "/{handle}/booking/availability",
    summary="Open appointment times for one day (public)",
)
async def availability(
    handle: str,
    session: SessionDep,
    day: Annotated[date, Query()],
) -> list[dict]:
    org = await _org_or_404(session, handle)
    return await booking_svc.availability(session, org.id, day)


@router.post(
    "/{handle}/booking",
    response_model=BookingCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Book an open time (paid slots return a checkout order)",
)
async def create_booking(
    handle: str, payload: BookingCreate, user: CurrentUser, session: SessionDep
) -> BookingCreated:
    org = await _org_or_404(session, handle)
    try:
        booking, order = await booking_svc.book(
            session, org=org, user_id=user.id, starts_at=payload.starts_at
        )
    except booking_svc.BookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return BookingCreated(booking=BookingOut.model_validate(booking), order=order)


@router.get(
    "/{handle}/booking/mine",
    response_model=list[BookingOut],
    summary="The logged-in user's bookings with this org",
)
async def my_bookings(
    handle: str, user: CurrentUser, session: SessionDep
) -> list[BookingOut]:
    org = await _org_or_404(session, handle)
    rows = await booking_svc.bookings_for_user(session, org.id, user.id)
    out = [await booking_svc.reconcile(session, org, b) for b in rows]
    await session.commit()
    return [BookingOut.model_validate(b) for b in out]


@router.get(
    "/{handle}/booking/bookings",
    response_model=list[BookingOut],
    summary="Every booking at this org (owner)",
)
async def org_bookings(
    handle: str, user: CurrentUser, session: SessionDep
) -> list[BookingOut]:
    org = await _org_or_404(session, handle)
    _require_owner(org, user)
    rows = await booking_svc.bookings_for_org(session, org.id)
    out = [await booking_svc.reconcile(session, org, b) for b in rows]
    await session.commit()
    return [BookingOut.model_validate(b) for b in out]


@router.post(
    "/{handle}/booking/{booking_id}/cancel",
    response_model=BookingOut,
    summary="Cancel a booking (its user or the org owner)",
)
async def cancel_booking(
    handle: str, booking_id: int, user: CurrentUser, session: SessionDep
) -> BookingOut:
    org = await _org_or_404(session, handle)
    booking = await booking_svc.get_booking(session, org.id, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    is_owner = org.owner_user_id is not None and user.id == org.owner_user_id
    if booking.user_id != user.id and not is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your booking")
    try:
        await booking_svc.cancel(session, booking)
    except booking_svc.BookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return BookingOut.model_validate(booking)


# ---- White-label pages ----

_BRAND_SNIPPET = """<script>
window.TARA_ORG = {branding};
(function () {{
  const org = window.TARA_ORG;
  document.title = org.name + " · powered by Tara";
  const root = document.documentElement;
  root.style.setProperty("--accent", org.theme_primary);
  root.style.setProperty("--gold", org.theme_primary);
  // Registrations from this page belong to the org (identity resolves it).
  sessionStorage.setItem("tara_org", org.handle);
  document.addEventListener("DOMContentLoaded", function () {{
    // Re-skin visible brand text without touching the page's logic.
    document.querySelectorAll(".brand, .brand-name, .logo-text, h1.title").forEach(function (el) {{
      if (el.textContent.trim().toLowerCase() === "tara") el.textContent = org.name;
    }});
  }});
}})();
</script>"""


def _inject(page_file: str, branding: dict) -> HTMLResponse:
    html = (_WEB_DIR / page_file).read_text(encoding="utf-8")
    snippet = _BRAND_SNIPPET.replace("{branding}", json.dumps(branding, ensure_ascii=False))
    if "</head>" in html:
        html = html.replace("</head>", snippet + "\n</head>", 1)
    else:  # defensive: prepend
        html = snippet + html
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@whitelabel_router.get("/a/{handle}/ui", include_in_schema=False)
async def whitelabel_chat(handle: str, session: SessionDep) -> HTMLResponse:
    org = await _service.get_by_handle(session, handle)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Org not found")
    return _inject("ui/chat.html", _service.public_branding(org))


@whitelabel_router.get("/a/{handle}/login", include_in_schema=False)
async def whitelabel_login(handle: str, session: SessionDep) -> HTMLResponse:
    org = await _service.get_by_handle(session, handle)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Org not found")
    return _inject("ui/login.html", _service.public_branding(org))
