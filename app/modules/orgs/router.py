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
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs.schemas import OrgCreate, OrgOut, OrgPublic
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
