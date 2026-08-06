"""HTTP routes for the content module.

Access levels:
  - POST /content/run-daily — the scheduled trigger (X-Cron-Token; an external
    scheduler like GitHub Actions cron fires it each morning), or an owner /
    content_reviewer pressing "generate now" in the console.
  - /content/posts..., /content/studio... — the review/approve/publish surface,
    owner or content_reviewer.
  - POST /content/cards     — personal share cards (logged-in users).
  - GET /content/cards/daily/{nakshatra} + GET /s/{slug} — public virality
    surfaces (Part 2): cacheable daily cards and the OG-tagged landing page.
"""

import html as html_lib
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content import feed, feed_admin, share_cards
from app.modules.content.models import STUDIO_KINDS, ShareCard
from app.modules.content.schemas import (
    ApprovePayload,
    ContentPostOut,
    FeedItemIn,
    FeedItemOut,
    FeedItemPatch,
    MarkPublishedPayload,
    PublishedIn,
    RunDailySummary,
    ShareCardCreate,
    ShareCardOut,
    StudioDraftOut,
    StudioGeneratePayload,
)
from app.modules.content.service import (
    ContentPostNotFound,
    ContentService,
    InvalidTransition,
)
from app.modules.identity.auth import CurrentUser
from app.modules.identity.service import IdentityService
from app.platform.admin_auth import Operator, require_operator
from app.platform.config import get_settings
from app.platform.cron_auth import require_cron_or_operator
from app.platform.db import get_session
from app.platform.storage import get_storage

router = APIRouter(prefix="/content", tags=["content"])

# Root-level share surface (/s/{slug}) — same module, no /content prefix so
# links stay short enough for a WhatsApp caption. Also hosts the public app feed.
share_router = APIRouter(tags=["content"])

_service = ContentService()


@share_router.get("/feed", response_model=list[FeedItemOut])
async def app_feed(
    temple_id: str | None = Query(default=None, description="filter to one temple"),
    cat: str | None = Query(default=None, description="Festival | Darshan | AstroTalk"),
) -> list[dict]:
    """The curated notices/articles feed for the app home + feed sheet."""
    from app.modules.content.feed import list_feed

    return list_feed(temple_id, cat)


_identity = IdentityService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# The feed is editorial content, so a content_reviewer edits it alongside the
# owner — the same pairing that gates a temple's `reviewed` flag in Part 5.
FeedEditorDep = Annotated[
    Operator, Depends(require_operator("owner", "content_reviewer"))
]
# The same pairing as a `dependencies=[...]` entry, for the routes that have no
# use for the Operator object itself.
#
# These were `AdminGuard` — "any authenticated operator" — which was accurate
# when the only credential was the owner's shared token and is not any more. A
# support account exists to answer devotees' questions; publishing to the
# product's public channels is not part of that job, and the console's own IA
# has never claimed it was.
ReviewerGuard = Depends(require_operator("owner", "content_reviewer"))
CronOrReviewerGuard = Depends(require_cron_or_operator("owner", "content_reviewer"))


# ---- App feed CRUD (console plan Part 8) ----
# feed.py's own docstring said "admin CRUD layer on later". This is it: the
# three cards were a Python literal, so correcting a festival notice meant a
# code change and a redeploy — the opposite of what a notices feed is for.
#
# Every write ends in _publish_feed, which commits and rebuilds the in-memory
# snapshot GET /feed serves; without it an edit would not appear until restart.


async def _publish_feed(session: AsyncSession) -> None:
    await session.commit()
    await feed.load(session)


def _feed_error(exc: feed_admin.FeedAdminError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, feed_admin.NotFound)
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(code, detail=str(exc))


def _feed_out(row) -> dict:  # noqa: ANN001
    return {
        "id": row.id,
        "cat": row.cat,
        "image": row.image,
        "glyph": row.glyph,
        "live": row.live,
        "title_en": row.title_en,
        "title_ml": row.title_ml,
        "body_en": row.body_en,
        "body_ml": row.body_ml,
        "who_en": row.who_en,
        "who_ml": row.who_ml,
        "temple_id": row.temple_id,
        "published": row.published,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
    }


@router.get("/feed/manage", summary="Every feed card, drafts included")
async def manage_feed(session: SessionDep, operator: FeedEditorDep) -> list[dict]:
    return [_feed_out(r) for r in await feed_admin.listing(session)]


@router.post(
    "/feed",
    status_code=status.HTTP_201_CREATED,
    summary="Write a new feed card",
)
async def create_feed_item(
    payload: FeedItemIn, session: SessionDep, operator: FeedEditorDep
) -> dict:
    fields = payload.model_dump()
    try:
        row = await feed_admin.create(session, item_id=fields.pop("id"), **fields)
    except feed_admin.FeedAdminError as exc:
        raise _feed_error(exc) from exc
    await _publish_feed(session)
    return _feed_out(row)


@router.patch("/feed/{item_id}", summary="Edit a feed card")
async def update_feed_item(
    item_id: str, payload: FeedItemPatch, session: SessionDep, operator: FeedEditorDep
) -> dict:
    try:
        row = await feed_admin.update(
            session, item_id=item_id, changes=payload.model_dump(exclude_unset=True)
        )
    except feed_admin.FeedAdminError as exc:
        raise _feed_error(exc) from exc
    await _publish_feed(session)
    return _feed_out(row)


@router.post("/feed/{item_id}/published", summary="Publish or withdraw a card")
async def set_feed_published(
    item_id: str, payload: PublishedIn, session: SessionDep, operator: FeedEditorDep
) -> dict:
    """Withdrawing is the only removal on offer. Pulling a wrong notice off the
    app should not destroy the text that then has to be corrected."""
    try:
        row = await feed_admin.update(
            session, item_id=item_id, changes={"published": payload.published}
        )
    except feed_admin.FeedAdminError as exc:
        raise _feed_error(exc) from exc
    await _publish_feed(session)
    return _feed_out(row)


def _public_base(request: Request) -> str:
    configured = get_settings().public_base_url.rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def _card_out(card: ShareCard, request: Request) -> ShareCardOut:
    base = _public_base(request)
    return ShareCardOut(
        slug=card.slug,
        kind=card.kind,
        title=card.title,
        media_url=get_storage().url(card.media_key),
        share_url=f"{base}/s/{card.slug}",
        hits=card.hits,
    )


@router.post(
    "/run-daily",
    response_model=RunDailySummary,
    dependencies=[CronOrReviewerGuard],
    summary="Draft today's content pack (scheduled or admin-triggered; idempotent)",
)
async def run_daily(
    session: SessionDep,
    day: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> dict:
    return await _service.run_daily(session, day)


@router.get("/posts", response_model=list[ContentPostOut], dependencies=[ReviewerGuard])
async def list_posts(
    session: SessionDep,
    day: Annotated[date | None, Query(description="Filter to one day")] = None,
) -> list[ContentPostOut]:
    return await _service.list_posts(session, day)


@router.post(
    "/posts/{post_id}/approve",
    response_model=ContentPostOut,
    dependencies=[ReviewerGuard],
    summary="Approve a draft (optionally with an inline text edit)",
)
async def approve_post(
    session: SessionDep, post_id: int, payload: ApprovePayload | None = None
) -> ContentPostOut:
    try:
        return await _service.approve(session, post_id, (payload or ApprovePayload()).body)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/posts/{post_id}/publish",
    response_model=ContentPostOut,
    dependencies=[ReviewerGuard],
    summary="Publish an approved post to its platform",
)
async def publish_post(session: SessionDep, post_id: int) -> ContentPostOut:
    try:
        return await _service.publish(session, post_id)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/posts/{post_id}/mark-published",
    response_model=ContentPostOut,
    dependencies=[ReviewerGuard],
    summary="Mark a daily post published-by-hand (paste the post URL)",
)
async def mark_post_published(
    session: SessionDep, post_id: int, payload: MarkPublishedPayload
) -> ContentPostOut:
    try:
        return await _service.mark_post_published(session, post_id, payload.external_url)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


# ---- Content Studio (ENGAGEMENT_PLAN.md Part B) ----


@router.post(
    "/generate",
    response_model=StudioDraftOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ReviewerGuard],
    summary="Generate one creative studio draft (reel/weekly/festival/nakshatra/myth)",
)
async def generate_studio(session: SessionDep, payload: StudioGeneratePayload) -> StudioDraftOut:
    if payload.kind not in STUDIO_KINDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown kind. Choose one of: {', '.join(STUDIO_KINDS)}",
        )
    return await _service.generate_studio(session, payload.kind, payload.topic, payload.day)


@router.get(
    "/studio",
    response_model=list[StudioDraftOut],
    dependencies=[ReviewerGuard],
    summary="List studio drafts (newest first)",
)
async def list_studio(session: SessionDep) -> list[StudioDraftOut]:
    return await _service.list_studio(session)


@router.post(
    "/studio/{draft_id}/approve",
    response_model=StudioDraftOut,
    dependencies=[ReviewerGuard],
    summary="Approve a studio draft (optionally with an inline edit)",
)
async def approve_studio(
    session: SessionDep, draft_id: int, payload: ApprovePayload | None = None
) -> StudioDraftOut:
    try:
        return await _service.approve_studio(session, draft_id, (payload or ApprovePayload()).body)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Draft not found")


@router.post(
    "/studio/{draft_id}/mark-published",
    response_model=StudioDraftOut,
    dependencies=[ReviewerGuard],
    summary="Mark a studio draft posted-by-hand (paste the YouTube/Instagram URL)",
)
async def mark_studio_published(
    session: SessionDep, draft_id: int, payload: MarkPublishedPayload
) -> StudioDraftOut:
    try:
        return await _service.mark_studio_published(session, draft_id, payload.external_url)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Draft not found")


@router.delete(
    "/studio/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[ReviewerGuard],
    summary="Delete a studio draft",
)
async def delete_studio(session: SessionDep, draft_id: int) -> None:
    try:
        await _service.delete_studio(session, draft_id)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Draft not found")


# ---- Share cards (GROWTH_PLAN.md Part 2) ----


@router.post(
    "/cards",
    response_model=ShareCardOut,
    status_code=status.HTTP_201_CREATED,
    summary="Render a personal share card for the logged-in user",
)
async def create_card(
    payload: ShareCardCreate, user: CurrentUser, session: SessionDep, request: Request
) -> ShareCardOut:
    """The insight → a branded PNG + a /s link whose CTA carries the user's
    referral code (sharing IS the referral loop's top of funnel)."""
    if payload.template not in ("feed", "story"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown template")
    if not payload.body.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty card body")
    ref = await _identity.get_or_create_referral_code(session, user.id)
    try:
        card = await share_cards.create_personal_card(
            session,
            user_id=user.id,
            ref_code=ref.code,
            title=payload.title,
            body=payload.body,
            template=payload.template,
        )
    except share_cards.ToneViolation:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This text cannot be turned into a public card",
        )
    await session.commit()
    return _card_out(card, request)


@router.get(
    "/cards/daily/{nakshatra}",
    response_model=ShareCardOut,
    summary="Public daily card for one nakshatra (name or index 0-26)",
)
async def daily_card(nakshatra: str, session: SessionDep, request: Request) -> ShareCardOut:
    try:
        card = await share_cards.get_or_create_daily_card(session, nakshatra)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    await session.commit()
    return _card_out(card, request)


_LANDING_HTML = """<!doctype html>
<html lang="ml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Tara</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="Tara">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary_large_image">
<style>
  body {{ margin:0; background:#0b0f2a; color:#f5f1e8; font-family:system-ui,sans-serif;
         min-height:100vh; display:flex; flex-direction:column; align-items:center;
         justify-content:center; gap:24px; padding:24px; box-sizing:border-box; }}
  img {{ max-width:min(420px,92vw); border-radius:16px; box-shadow:0 12px 48px rgba(0,0,0,.5); }}
  a.cta {{ background:#e8b64c; color:#0b0f2a; font-weight:700; text-decoration:none;
           padding:14px 28px; border-radius:999px; font-size:16px; }}
  p {{ color:#9aa3c4; font-size:13px; margin:0; }}
</style>
</head>
<body>
  <img src="{image}" alt="{title}">
  <a class="cta" href="{cta}">നിങ്ങളുടെ സ്വന്തം reading നേടൂ ✨</a>
  <p>Tara · AI ജ്യോതിഷ സഹായി</p>
</body>
</html>"""


@share_router.get("/s/{slug}", include_in_schema=False, response_class=HTMLResponse)
async def share_landing(slug: str, session: SessionDep, request: Request) -> HTMLResponse:
    """The link a shared card unfurls to: OG image + a get-your-own CTA.

    Every view bumps the card's durable hit counter — the plan's
    "shares clicked" metric.
    """
    card = await share_cards.get_card(session, slug)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Card not found")
    await share_cards.record_hit(session, card)
    await session.commit()

    base = _public_base(request)
    media_url = get_storage().url(card.media_key)
    image = media_url if media_url.startswith("http") else f"{base}{media_url}"
    cta = f"{base}/ui/login?ref={card.ref_code}" if card.ref_code else f"{base}/ui"
    description = " ".join(card.body.split())[:140]
    page = _LANDING_HTML.format(
        title=html_lib.escape(card.title),
        description=html_lib.escape(description),
        image=html_lib.escape(image),
        url=html_lib.escape(f"{base}/s/{card.slug}"),
        cta=html_lib.escape(cta),
    )
    return HTMLResponse(page, headers={"Cache-Control": "no-cache"})
