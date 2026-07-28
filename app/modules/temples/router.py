"""HTTP routes for the temples module.

Three surfaces (GROWTH_PLAN.md Part 3 added the last two):
  - /temples/suggest            — remedy-linked suggestions (chat uses this).
  - /temples/partners...        — the admin partner console (X-Admin-Token):
    register partners, add festivals, download the printable QR.
  - /t/{slug} + /widget/panchangam — the PUBLIC pages a QR or an embed points
    at (root-level, no /temples prefix: short URLs print better).
"""

import html as html_lib
from datetime import date
from functools import partial
from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.identity.auth import CurrentUser
from app.modules.temples import admin as temple_admin
from app.modules.temples import partners, registry
from app.modules.temples.models import TempleFestival, TemplePartner
from app.modules.temples.schemas import (
    ActiveIn,
    CheckinOut,
    FestivalCreate,
    FestivalOut,
    FestivalUpdate,
    PartnerCreate,
    PartnerOut,
    PartnerUpdate,
    PoojaAdminIn,
    PoojaAdminOut,
    PoojaAdminPatch,
    PoojaCatalogueOut,
    ReviewedIn,
    SubscribePayload,
    TempleAdminIn,
    TempleAdminOut,
    TempleAdminPatch,
    TempleDetailOut,
    TempleDirectoryItem,
    TempleImageOut,
    TempleOut,
    TemplePoojaIn,
    TemplePoojaOut,
    TempleSuggestion,
)
from app.modules.temples.service import TemplesService
from app.platform import metrics
from app.platform.admin_auth import AdminGuard, Operator, require_operator
from app.platform.config import get_settings
from app.platform.db import get_session
from app.platform.storage import ImageRejected, get_storage, sniff_image

router = APIRouter(prefix="/temples", tags=["temples"])

# Public microsite + widget, mounted at the root (short printable URLs).
site_router = APIRouter(tags=["temples"])

_service = TemplesService()
_engine = AstrologyEngineService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Console plan Part 4 roles. Directory-wide decisions (adding or retiring a
# temple, the master offering catalogue) are the owner's; per-temple edits are
# open to that temple's admin, who is then scoped by require_temple(). The
# review flag is a third gate — see set_temple_reviewed.
OwnerDep = Annotated[Operator, Depends(require_operator("owner"))]
TempleOperatorDep = Annotated[Operator, Depends(require_operator("owner", "temple_admin"))]
ReviewerDep = Annotated[Operator, Depends(require_operator("owner", "content_reviewer"))]


@router.get("/suggest", response_model=list[TempleSuggestion])
async def suggest(
    concern: str | None = Query(default=None, description="career, marriage, children, education, health, wealth, ancestors, obstacles, peace"),
    dosha: list[str] = Query(default=[]),
    graha: list[str] = Query(default=[]),
    district: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    k: int = Query(default=2, ge=1, le=5),
) -> list[TempleSuggestion]:
    """Suggest temples for a concern/dosha/graha, optionally near a location.

    No birth data is accepted or returned here (GUARDRAILS.md §4) — callers pass
    already-derived keys (e.g. ``dosha=sade_sati``, ``graha=shani``).
    """
    return _service.suggest(
        concern=concern,
        doshas=dosha,
        grahas=graha,
        district=district,
        lat=lat,
        lng=lng,
        k=k,
    )


# ---- Partner console ----
# These predate roles: they were written when every operator was an owner, so
# they gated on the coarse AdminGuard. Console plan Part 5 scopes them, because
# leaving creation unscoped next to a scoped PATCH would mean a temple_admin
# could register a partner for a temple they are then forbidden to edit — and
# `GET /partners` carries partner contact phone numbers.


@router.get(
    "/directory",
    response_model=list[TempleDirectoryItem],
    dependencies=[AdminGuard],
    summary="List directory temples (for the partner-registration picker)",
)
async def temple_directory() -> list[dict]:
    return _service.list_temples()


@router.post(
    "/partners",
    response_model=PartnerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_partner(
    payload: PartnerCreate, session: SessionDep, operator: TempleOperatorDep
) -> PartnerOut:
    operator.require_temple(payload.temple_id)
    if _service.get_temple(payload.temple_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown temple id")
    try:
        partner = await partners.create_partner(
            session,
            temple_id=payload.temple_id,
            slug=payload.slug,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            tier=payload.tier,
        )
    except partners.PartnerError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return PartnerOut.model_validate(partner)


@router.get("/partners", response_model=list[PartnerOut])
async def list_partners(
    session: SessionDep, operator: TempleOperatorDep
) -> list[PartnerOut]:
    visible = operator.visible_temple_ids()
    return [
        PartnerOut.model_validate(p)
        for p in await partners.list_partners(session)
        if visible is None or p.temple_id in visible
    ]


@router.post(
    "/partners/{slug}/festivals",
    response_model=FestivalOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_festival(
    slug: str, payload: FestivalCreate, session: SessionDep, operator: TempleOperatorDep
) -> FestivalOut:
    partner = await partners.get_partner_by_slug(session, slug)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    operator.require_temple(partner.temple_id)
    festival = await partners.add_festival(
        session,
        temple_id=partner.temple_id,
        name=payload.name,
        name_ml=payload.name_ml,
        day=payload.day,
    )
    await session.commit()
    return FestivalOut.model_validate(festival)


@router.get("/partners/{slug}/qr.png")
async def partner_qr(
    slug: str, session: SessionDep, request: Request, operator: TempleOperatorDep
) -> Response:
    """The printable QR poster asset: points at /t/{slug}?src=qr."""
    partner = await partners.get_partner_by_slug(session, slug)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    operator.require_temple(partner.temple_id)
    base = get_settings().public_base_url.rstrip("/") or str(request.base_url).rstrip("/")
    png = partners.qr_png(f"{base}/t/{partner.slug}?src=qr")
    return Response(content=png, media_type="image/png")


@router.patch(
    "/partners/{slug}",
    response_model=PartnerOut,
    summary="Edit a partner, or end the partnership (`active: false`)",
)
async def update_partner(
    slug: str, payload: PartnerUpdate, session: SessionDep, operator: TempleOperatorDep
) -> PartnerOut:
    # Scope is checked before anything is written, not after: an unauthorised
    # PATCH must not depend on the session being discarded to stay harmless.
    existing = (
        await session.execute(select(TemplePartner).where(TemplePartner.slug == slug))
    ).scalars().first()
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    operator.require_temple(existing.temple_id)
    try:
        partner = await partners.update_partner(
            session, slug=slug, **payload.model_dump(exclude_unset=True)
        )
    except partners.PartnerError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return PartnerOut.model_validate(partner)


@router.get(
    "/festivals",
    response_model=list[FestivalOut],
    summary="The festival calendar for the temples this operator manages",
)
async def list_festivals(
    session: SessionDep,
    operator: TempleOperatorDep,
    temple_id: str | None = Query(default=None, description="narrow to one temple"),
) -> list[FestivalOut]:
    """Console plan Part 10 needs this; nothing before it did.

    Festivals were write-only: the console could add one and the microsite
    could render the next few, but no route enumerated them — so the PATCH and
    DELETE below had no way for an operator to name the row they meant. This is
    the missing half, scoped the same way the rest of the section is.
    """
    visible = operator.visible_temple_ids()
    if temple_id is not None:
        # Checked rather than intersected: asking for a temple you do not manage
        # is a mistake worth a 403, not a silently empty list.
        operator.require_temple(temple_id)
        visible = frozenset({temple_id})
    rows = await partners.list_festivals(session, temple_ids=visible)
    return [FestivalOut.model_validate(r) for r in rows]


@router.patch(
    "/festivals/{festival_id}",
    response_model=FestivalOut,
    summary="Correct a festival entry",
)
async def update_festival(
    festival_id: int,
    payload: FestivalUpdate,
    session: SessionDep,
    operator: TempleOperatorDep,
) -> FestivalOut:
    existing = await session.get(TempleFestival, festival_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Festival not found")
    operator.require_temple(existing.temple_id)
    festival = await partners.update_festival(
        session, festival_id=festival_id, **payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return FestivalOut.model_validate(festival)


@router.delete(
    "/festivals/{festival_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a festival",
)
async def delete_festival(
    festival_id: int, session: SessionDep, operator: TempleOperatorDep
) -> None:
    festival = await session.get(TempleFestival, festival_id)
    if festival is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Festival not found")
    operator.require_temple(festival.temple_id)
    await partners.delete_festival(session, festival_id=festival_id)
    await session.commit()


# ---- Directory administration (console plan Part 5) ----
# The first writes the temple directory has ever had: until Part 1 it was a
# Python literal, so correcting a temple's coordinates meant a redeploy.
#
# Two roles reach these routes. An `owner` may do everything; a `temple_admin`
# is scoped — `operator.require_temple(...)` 403s them out of temples they do
# not run, and their listing is filtered rather than merely hidden in the UI.
# Creating and retiring temples, and the master offering catalogue, stay
# owner-only: they are directory-wide decisions.
#
# Every write that changes what the app serves ends in `_publish`, which
# commits and then rebuilds the in-memory snapshot the (synchronous) readers
# use. Without it an operator's edit would not appear until the next restart.


async def _publish(session: AsyncSession) -> None:
    await session.commit()
    await registry.load(session)


def _temple_error(exc: temple_admin.TempleAdminError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, temple_admin.NotFound)
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(code, detail=str(exc))


@router.get(
    "/manage",
    response_model=list[TempleAdminOut],
    summary="Directory rows for the console (includes retired temples)",
)
async def manage_temples(
    session: SessionDep,
    operator: TempleOperatorDep,
    include_inactive: bool = Query(default=True),
) -> list[TempleAdminOut]:
    rows = await temple_admin.list_temples(
        session,
        temple_ids=operator.visible_temple_ids(),
        include_inactive=include_inactive,
    )
    return [TempleAdminOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=TempleAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a temple to the directory (owner)",
)
async def create_temple(
    payload: TempleAdminIn, session: SessionDep, operator: OwnerDep
) -> TempleAdminOut:
    fields = payload.model_dump()
    try:
        row = await temple_admin.create_temple(session, temple_id=fields.pop("id"), **fields)
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TempleAdminOut.model_validate(row)


@router.patch(
    "/{temple_id}", response_model=TempleAdminOut, summary="Edit a temple record"
)
async def update_temple(
    temple_id: str,
    payload: TempleAdminPatch,
    session: SessionDep,
    operator: TempleOperatorDep,
) -> TempleAdminOut:
    operator.require_temple(temple_id)
    try:
        row = await temple_admin.update_temple(
            session, temple_id=temple_id, changes=payload.model_dump(exclude_unset=True)
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TempleAdminOut.model_validate(row)


@router.post(
    "/{temple_id}/active",
    response_model=TempleAdminOut,
    summary="Retire or restore a temple (owner)",
)
async def set_temple_active(
    temple_id: str, payload: ActiveIn, session: SessionDep, operator: OwnerDep
) -> TempleAdminOut:
    """Retiring is a soft delete, and the only one on offer. Bookings, visits,
    partners and festivals all reference ``temples.id`` as a plain string with
    no foreign key, so a real DELETE would orphan them without a word."""
    try:
        row = await temple_admin.update_temple(
            session, temple_id=temple_id, changes={"active": payload.active}
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TempleAdminOut.model_validate(row)


@router.patch(
    "/{temple_id}/review",
    response_model=TempleAdminOut,
    summary="Flip the astrologer sign-off flag (owner or content reviewer)",
)
async def set_temple_reviewed(
    temple_id: str, payload: ReviewedIn, session: SessionDep, operator: ReviewerDep
) -> TempleAdminOut:
    """Not part of PATCH /{id}, and not open to a temple_admin, on purpose.

    ``reviewed`` asserts that an astrologer checked the devotional content
    (GUARDRAILS §1) and it is served to clients. Letting the same role that
    writes a temple's copy also certify it would make the flag self-issued and
    therefore meaningless.
    """
    try:
        row = await temple_admin.set_reviewed(
            session, temple_id=temple_id, reviewed=payload.reviewed
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TempleAdminOut.model_validate(row)


@router.post(
    "/{temple_id}/image",
    response_model=TempleImageOut,
    summary="Upload the temple photo (raw image bytes as the request body)",
)
async def upload_temple_image(
    temple_id: str, request: Request, session: SessionDep, operator: TempleOperatorDep
) -> TempleImageOut:
    """The body is the file itself, not a multipart form: multipart would pull
    in python-multipart, which is not a pinned dependency, for a single route a
    console can serve with ``fetch(url, {method: 'POST', body: file})``.
    """
    operator.require_temple(temple_id)
    if await temple_admin.get_temple(session, temple_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple not found")

    data = await request.body()
    try:
        extension, content_type = sniff_image(data)
    except ImageRejected as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    storage = get_storage()
    key = f"temples/{temple_id}.{extension}"
    await to_thread.run_sync(partial(storage.put, key, data, content_type))
    try:
        await temple_admin.update_temple(
            session, temple_id=temple_id, changes={"image_key": key}
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TempleImageOut(temple_id=temple_id, image_key=key, url=storage.url(key))


# ---- Master offering catalogue (owner) ----
# Registered before `/{temple_id}` so the catch-all never claims "/poojas".


@router.get(
    "/poojas", response_model=list[PoojaAdminOut], summary="The master catalogue"
)
async def list_master_poojas(
    session: SessionDep, operator: TempleOperatorDep
) -> list[PoojaAdminOut]:
    return [PoojaAdminOut.model_validate(p) for p in await temple_admin.list_poojas(session)]


@router.post(
    "/poojas",
    response_model=PoojaAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a master offering (owner)",
)
async def create_master_pooja(
    payload: PoojaAdminIn, session: SessionDep, operator: OwnerDep
) -> PoojaAdminOut:
    fields = payload.model_dump()
    try:
        row = await temple_admin.upsert_pooja(
            session, key=fields.pop("key"), changes=fields, create=True
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return PoojaAdminOut.model_validate(row)


@router.patch(
    "/poojas/{pooja_key}",
    response_model=PoojaAdminOut,
    summary="Edit a master offering (owner)",
)
async def update_master_pooja(
    pooja_key: str, payload: PoojaAdminPatch, session: SessionDep, operator: OwnerDep
) -> PoojaAdminOut:
    try:
        row = await temple_admin.upsert_pooja(
            session,
            key=pooja_key,
            changes=payload.model_dump(exclude_unset=True),
            create=False,
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return PoojaAdminOut.model_validate(row)


# ---- Per-temple catalogue overrides ----


@router.get(
    "/{temple_id}/overrides",
    response_model=list[TemplePoojaOut],
    summary="This temple's overrides of the master catalogue",
)
async def list_temple_overrides(
    temple_id: str, session: SessionDep, operator: TempleOperatorDep
) -> list[TemplePoojaOut]:
    operator.require_temple(temple_id)
    rows = await temple_admin.list_overrides(session, temple_id)
    return [TemplePoojaOut.model_validate(r) for r in rows]


@router.put(
    "/{temple_id}/poojas/{pooja_key}",
    response_model=TemplePoojaOut,
    summary="Set this temple's price, lead time, or whether it offers this at all",
)
async def set_temple_override(
    temple_id: str,
    pooja_key: str,
    payload: TemplePoojaIn,
    session: SessionDep,
    operator: TempleOperatorDep,
) -> TemplePoojaOut:
    operator.require_temple(temple_id)
    try:
        row = await temple_admin.set_override(
            session,
            temple_id=temple_id,
            pooja_key=pooja_key,
            amount_paise=payload.amount_paise,
            lead_days=payload.lead_days,
            active=payload.active,
        )
    except temple_admin.TempleAdminError as exc:
        raise _temple_error(exc) from exc
    await _publish(session)
    return TemplePoojaOut.model_validate(row)


@router.delete(
    "/{temple_id}/poojas/{pooja_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Drop the override so the master entry applies again",
)
async def clear_temple_override(
    temple_id: str, pooja_key: str, session: SessionDep, operator: TempleOperatorDep
) -> None:
    operator.require_temple(temple_id)
    if not await temple_admin.clear_override(
        session, temple_id=temple_id, pooja_key=pooja_key
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No override to clear")
    await _publish(session)


# ---- Public app surface (Nithara): list / search / nearby / detail ----
# Registered AFTER the static routes above (/suggest, /directory, /partners...)
# so the `/{temple_id}` catch-all never shadows them.


@router.get("", response_model=list[TempleOut])
async def list_temples(
    q: str | None = Query(default=None, description="search text"),
    by: str = Query(default="name", pattern="^(name|place)$"),
    deity: str | None = Query(default=None, description="shiva | devi | vishnu"),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    sort: str | None = Query(default=None, pattern="^(near|rating)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """Public temple list/search/nearby for the app home, search and map."""
    return _service.list_public(
        q=q, by=by, deity=deity, lat=lat, lng=lng, sort=sort, limit=limit
    )


@router.get("/by-qr/{token}", response_model=TempleDetailOut)
async def temple_by_qr(token: str, session: SessionDep) -> dict:
    """Resolve a scanned temple QR poster (partner slug) to its detail."""
    partner = await partners.get_partner_by_slug(session, token)
    temple = _service.get_temple(partner.temple_id) if partner else None
    if partner is None or temple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No temple for that code")
    return _service.to_detail(temple)


@router.get("/{temple_id}/poojas", response_model=PoojaCatalogueOut)
async def temple_poojas(
    temple_id: str,
    nak: int | None = Query(default=None, ge=0, le=26, description="star to book for"),
) -> dict:
    """A temple's offering catalogue. With ``nak`` given, each offering is locked
    when its lead time can't be met before that star's next recurrence."""
    temple = _service.get_temple(temple_id)
    if temple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple not found")
    days_until: int | None = None
    if nak is not None:
        star_day = await _engine.next_nakshatram_day(nak)
        if star_day is not None:
            days_until = (star_day - date.today()).days
    return _service.pooja_catalogue(temple, days_until=days_until)


@router.post("/{temple_id}/checkin", response_model=CheckinOut)
async def temple_checkin(
    temple_id: str, user: CurrentUser, session: SessionDep
) -> dict:
    """Record a darshan at this temple (idempotent per day) and advance the
    daily streak. Feeds the profile's 'temples visited' counter."""
    temple = _service.get_temple(temple_id)
    if temple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple not found")
    fresh = await _service.record_visit(session, user.id, temple_id)
    stats = await _service.visit_stats(session, user.id)
    await session.commit()
    return {
        "fresh": fresh,
        "temple_id": temple_id,
        "temples_visited": stats["temples_visited"],
    }


@router.get("/{temple_id}", response_model=TempleDetailOut)
async def temple_detail(temple_id: str) -> dict:
    """Full detail for one temple (story, timings, offering catalogue)."""
    temple = _service.get_temple(temple_id)
    if temple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple not found")
    return _service.to_detail(temple)


# ---- Public microsite + widget ----

_MICROSITE_HTML = """<!doctype html>
<html lang="ml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · Tara</title>
<style>
  body {{ margin:0; background:#0b0f2a; color:#f5f1e8; font-family:system-ui,sans-serif; }}
  .wrap {{ max-width:520px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ font-size:26px; margin:8px 0 2px; }}
  .sub {{ color:#9aa3c4; font-size:14px; margin-bottom:24px; }}
  .card {{ background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1);
           border-radius:14px; padding:16px 18px; margin-bottom:16px; }}
  .card h2 {{ font-size:15px; color:#e8b64c; margin:0 0 10px; }}
  .row {{ display:flex; justify-content:space-between; font-size:14px; padding:4px 0; }}
  .muted {{ color:#9aa3c4; }}
  ul {{ margin:0; padding-left:18px; font-size:14px; }} li {{ padding:2px 0; }}
  .cta {{ display:block; text-align:center; background:#e8b64c; color:#0b0f2a;
          font-weight:700; text-decoration:none; padding:14px; border-radius:999px;
          margin:20px 0 8px; }}
  input {{ width:100%; box-sizing:border-box; background:rgba(255,255,255,.07);
           border:1px solid rgba(255,255,255,.15); color:#f5f1e8; border-radius:10px;
           padding:12px; font-size:15px; margin-bottom:10px; }}
  button {{ width:100%; background:transparent; border:1px solid #e8b64c; color:#e8b64c;
            padding:12px; border-radius:999px; font-size:15px; cursor:pointer; }}
  .note {{ font-size:12px; color:#9aa3c4; margin-top:8px; }}
  .ok {{ color:#4caf82; font-size:14px; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="muted" style="font-size:13px;">🪔 Tara temple page</div>
  <h1>{name}</h1>
  <div class="sub">{town}, {district}</div>

  <div class="card">
    <h2>ഇന്നത്തെ പഞ്ചാംഗം · {p_date}</h2>
    <div class="row"><span class="muted">നക്ഷത്രം</span><span>{p_nakshatram}</span></div>
    <div class="row"><span class="muted">തിഥി</span><span>{p_tithi}</span></div>
    <div class="row"><span class="muted">നല്ല നേരം</span><span>{p_nalla_neram}</span></div>
  </div>

  <div class="card">
    <h2>വരുന്ന ഉത്സവങ്ങൾ</h2>
    {festivals}
  </div>

  <div class="card">
    <h2>പ്രധാന വഴിപാടുകൾ</h2>
    <ul>{vazhipadu}</ul>
  </div>

  <a class="cta" href="/ui?src=temple-{slug}">നിങ്ങളുടെ നക്ഷത്രം അറിയാൻ Tara-യോട് ചോദിക്കൂ ✨</a>

  <div class="card">
    <h2>ഉത്സവ അറിയിപ്പുകൾ WhatsApp-ൽ</h2>
    <input id="phone" type="tel" placeholder="മൊബൈൽ നമ്പർ (+91...)">
    <button onclick="subscribe()">അറിയിപ്പുകൾ വേണം 🔔</button>
    <div class="note">സബ്സ്ക്രൈബ് ചെയ്യുന്നത് WhatsApp സന്ദേശങ്ങൾക്കുള്ള സമ്മതമാണ്.
    എപ്പോൾ വേണമെങ്കിലും 'STOP' അയച്ച് നിർത്താം. ദിവസം പരമാവധി 3 സന്ദേശം.</div>
    <div id="msg"></div>
  </div>
</div>
<script>
async function subscribe() {{
  const phone = document.getElementById('phone').value.trim();
  const msg = document.getElementById('msg');
  if (!phone) {{ msg.textContent = 'നമ്പർ നൽകൂ'; return; }}
  try {{
    const res = await fetch('/t/{slug}/subscribe', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{phone}}),
    }});
    msg.className = res.ok ? 'ok' : 'note';
    msg.textContent = res.ok ? 'സബ്സ്ക്രൈബ് ചെയ്തു ✓ ഉത്സവത്തിന് 3 ദിവസം മുൻപ് അറിയിക്കാം.'
                             : 'ശരിയായ നമ്പർ നൽകൂ';
  }} catch (e) {{ msg.textContent = 'ശ്രമം പരാജയപ്പെട്ടു — വീണ്ടും നോക്കൂ'; }}
}}
</script>
</body>
</html>"""


@site_router.get("/t/{slug}", include_in_schema=False, response_class=HTMLResponse)
async def temple_microsite(
    slug: str, session: SessionDep, src: str | None = None
) -> HTMLResponse:
    partner = await partners.get_partner_by_slug(session, slug)
    temple = _service.get_temple(partner.temple_id) if partner else None
    if partner is None or temple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple page not found")
    metrics.increment("temples.microsite_visits")
    if src == "qr":
        metrics.increment("temples.qr_visits")

    panchangam = await _engine.get_panchangam()
    festivals = await partners.upcoming_festivals(session, partner.temple_id)
    festival_html = (
        "".join(
            f'<div class="row"><span>{html_lib.escape(f.name_ml or f.name)}</span>'
            f'<span class="muted">{f.day.strftime("%d-%m-%Y")}</span></div>'
            for f in festivals
        )
        or '<div class="muted" style="font-size:14px;">ഉത്സവ തീയതികൾ ഉടൻ ചേർക്കുന്നു.</div>'
    )
    vazhipadu_html = "".join(
        f"<li>{html_lib.escape(v)}</li>" for v in temple.get("vazhipadu", [])
    )
    page = _MICROSITE_HTML.format(
        name=html_lib.escape(temple.get("name_ml") or temple["name"]),
        town=html_lib.escape(temple.get("town", "")),
        district=html_lib.escape(temple.get("district", "")),
        slug=html_lib.escape(slug),
        p_date=html_lib.escape(str(panchangam.get("date", ""))),
        p_nakshatram=html_lib.escape(str(panchangam.get("nakshatram", ""))),
        p_tithi=html_lib.escape(str(panchangam.get("tithi", "—"))),
        p_nalla_neram=html_lib.escape(str(panchangam.get("nalla_neram", ""))),
        festivals=festival_html,
        vazhipadu=vazhipadu_html,
    )
    return HTMLResponse(page)


@site_router.post("/t/{slug}/subscribe", include_in_schema=False)
async def microsite_subscribe(
    slug: str, payload: SubscribePayload, session: SessionDep
) -> dict:
    partner = await partners.get_partner_by_slug(session, slug)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Temple page not found")
    try:
        await partners.subscribe(session, phone=payload.phone, temple_id=partner.temple_id)
    except partners.PartnerError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return {"status": "subscribed"}


_WIDGET_HTML = """<!doctype html>
<html lang="ml">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ margin:0; font-family:system-ui,sans-serif; background:#0b0f2a; color:#f5f1e8;
         padding:14px 16px; font-size:14px; }}
  .t {{ color:#e8b64c; font-weight:700; font-size:13px; margin-bottom:8px; }}
  .row {{ display:flex; justify-content:space-between; padding:3px 0; }}
  .muted {{ color:#9aa3c4; }}
  a {{ color:#e8b64c; text-decoration:none; font-size:12px; }}
  .foot {{ margin-top:10px; border-top:1px solid rgba(255,255,255,.12); padding-top:8px; }}
</style>
</head>
<body>
  <div class="t">🪔 {title} · {p_date}</div>
  <div class="row"><span class="muted">നക്ഷത്രം</span><span>{p_nakshatram}</span></div>
  <div class="row"><span class="muted">തിഥി</span><span>{p_tithi}</span></div>
  <div class="row"><span class="muted">നല്ല നേരം</span><span>{p_nalla_neram}</span></div>
  <div class="foot"><a href="{base}/ui" target="_blank" rel="noopener">Tara — AI ജ്യോതിഷ സഹായി ✨</a></div>
</body>
</html>"""


@site_router.get("/widget/panchangam", include_in_schema=False, response_class=HTMLResponse)
async def panchangam_widget(
    session: SessionDep, request: Request, temple: str | None = None
) -> HTMLResponse:
    """Embeddable iframe: today's panchangam with a Tara footer link.

    ``?temple={slug}`` brands the header with the partner temple's name.
    One static snippet for webmasters:
    ``<iframe src=".../widget/panchangam?temple=SLUG" width="320" height="200"></iframe>``
    """
    title = "ഇന്നത്തെ പഞ്ചാംഗം"
    if temple:
        partner = await partners.get_partner_by_slug(session, temple)
        seed = _service.get_temple(partner.temple_id) if partner else None
        if seed:
            title = seed.get("name_ml") or seed["name"]
            metrics.increment("temples.widget_views")
    panchangam = await _engine.get_panchangam()
    base = get_settings().public_base_url.rstrip("/") or str(request.base_url).rstrip("/")
    page = _WIDGET_HTML.format(
        title=html_lib.escape(title),
        base=html_lib.escape(base),
        p_date=html_lib.escape(str(panchangam.get("date", ""))),
        p_nakshatram=html_lib.escape(str(panchangam.get("nakshatram", ""))),
        p_tithi=html_lib.escape(str(panchangam.get("tithi", "—"))),
        p_nalla_neram=html_lib.escape(str(panchangam.get("nalla_neram", ""))),
    )
    # Embeddable by design: no frame-blocking headers, cache for an hour.
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=3600"})
