"""HTTP routes for the temples module.

Three surfaces (GROWTH_PLAN.md Part 3 added the last two):
  - /temples/suggest            — remedy-linked suggestions (chat uses this).
  - /temples/partners...        — the admin partner console (X-Admin-Token):
    register partners, add festivals, download the printable QR.
  - /t/{slug} + /widget/panchangam — the PUBLIC pages a QR or an embed points
    at (root-level, no /temples prefix: short URLs print better).
"""

import html as html_lib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.temples import partners
from app.modules.temples.schemas import (
    FestivalCreate,
    FestivalOut,
    PartnerCreate,
    PartnerOut,
    SubscribePayload,
    TempleSuggestion,
)
from app.modules.temples.service import TemplesService
from app.platform import metrics
from app.platform.admin_auth import AdminGuard
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/temples", tags=["temples"])

# Public microsite + widget, mounted at the root (short printable URLs).
site_router = APIRouter(tags=["temples"])

_service = TemplesService()
_engine = AstrologyEngineService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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


# ---- Partner console (admin) ----


@router.post(
    "/partners",
    response_model=PartnerOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminGuard],
)
async def create_partner(payload: PartnerCreate, session: SessionDep) -> PartnerOut:
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return PartnerOut.model_validate(partner)


@router.get("/partners", response_model=list[PartnerOut], dependencies=[AdminGuard])
async def list_partners(session: SessionDep) -> list[PartnerOut]:
    return [PartnerOut.model_validate(p) for p in await partners.list_partners(session)]


@router.post(
    "/partners/{slug}/festivals",
    response_model=FestivalOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminGuard],
)
async def add_festival(slug: str, payload: FestivalCreate, session: SessionDep) -> FestivalOut:
    partner = await partners.get_partner_by_slug(session, slug)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    festival = await partners.add_festival(
        session,
        temple_id=partner.temple_id,
        name=payload.name,
        name_ml=payload.name_ml,
        day=payload.day,
    )
    await session.commit()
    return FestivalOut.model_validate(festival)


@router.get("/partners/{slug}/qr.png", dependencies=[AdminGuard])
async def partner_qr(slug: str, session: SessionDep, request: Request) -> Response:
    """The printable QR poster asset: points at /t/{slug}?src=qr."""
    partner = await partners.get_partner_by_slug(session, slug)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    base = get_settings().public_base_url.rstrip("/") or str(request.base_url).rstrip("/")
    png = partners.qr_png(f"{base}/t/{partner.slug}?src=qr")
    return Response(content=png, media_type="image/png")


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
