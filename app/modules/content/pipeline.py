"""Daily content pipeline (internal): raw material → drafts → cards.

One run per day (cron endpoint POST /content/run-daily):
  1. Gather the day's facts — panchangam (astrology_engine) + one knowledge
     nugget about the day's nakshatram (knowledge). Public services only.
  2. Draft one piece per platform via the LLM (llm.py); mocked/empty drafts
     fall back to the compliant templates.
  3. Screen EVERY draft with tone_safety.screen_reply — one corrective retry,
     then the hand-written fallback. Public copy is never published unscreened.
  4. Render the day's share cards (feed + story) via platform/cards into
     platform/storage.
  5. Persist rows as ``draft`` — a human approves in /admin before publishing.

Idempotent: a (day, platform) that already has a row is skipped, so the
external scheduler may fire the endpoint more than once safely.
"""

from datetime import date as date_type

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.content import llm, templates
from app.modules.content.models import PLATFORMS, ContentPost
from app.modules.tone_safety.service import ToneSafetyService
from app.platform import metrics
from app.platform.cards import render_card
from app.platform.logging_config import get_logger
from app.platform.storage import get_storage

logger = get_logger(__name__)

_tone = ToneSafetyService()

# Which card format each platform's post links to.
_CARD_FORMAT = {"wa_channel": "feed", "fb_post": "feed", "ig_reel": "story", "yt_short": "story"}


async def _gather(day: date_type) -> tuple[dict, str]:
    """(panchangam, knowledge nugget) — the day's raw material."""
    panchangam = await AstrologyEngineService().get_panchangam(day)
    nugget = ""
    try:
        from app.modules.knowledge.service import KnowledgeService

        nakshatram = panchangam.get("nakshatram", "")
        note = KnowledgeService().nakshatra_relationship(nakshatram)
        if note:
            nugget = note
    except Exception:  # a knowledge hiccup must never block the daily pack
        logger.warning("content.pipeline: knowledge nugget unavailable", exc_info=True)
    return panchangam, nugget


async def _draft(platform: str, panchangam: dict, nugget: str) -> str:
    """One screened draft for the platform (LLM → corrective retry → fallback)."""
    system = templates.platform_prompt(platform)
    facts = templates.build_platform_input(panchangam, nugget)

    body = await llm.generate(system, facts)
    if body and not _tone.screen_reply(body):
        return body
    if body:  # violations found — one corrective retry (mirrors chat's policy)
        logger.warning("content.pipeline: %s draft violated tone rules; retrying.", platform)
        body = await llm.generate(system + "\n" + _tone.corrective_note(), facts)
        if body and not _tone.screen_reply(body):
            return body
        logger.warning("content.pipeline: %s retry still violated; using fallback.", platform)
    return templates.platform_fallback(platform, panchangam)


def _render_cards(day: date_type, panchangam: dict) -> dict[str, str]:
    """Render + store the day's cards; {format: storage_key}. Sync (Pillow)."""
    title = f"{day.isoformat()} · {panchangam.get('nakshatram', '')}"
    body = f"നല്ല നേരം {panchangam.get('nalla_neram', '')}"
    tithi = panchangam.get("tithi", "")
    if tithi:
        body += f"\nതിഥി {tithi}"
    body += "\nശാന്തമായ മനസ്സോടെ നല്ലൊരു ദിവസം ആരംഭിക്കൂ."
    storage = get_storage()
    keys: dict[str, str] = {}
    for fmt in ("feed", "story"):
        png = render_card(title=title, body=body, template=fmt)
        keys[fmt] = storage.put(f"content/{day.isoformat()}/{fmt}.png", png, "image/png")
    return keys


async def run_daily(session: AsyncSession, day: date_type | None = None) -> dict:
    """Generate the day's content pack as drafts. Returns a run summary."""
    day = day or date_type.today()

    existing = set(
        (
            await session.execute(
                select(ContentPost.platform).where(ContentPost.day == day)
            )
        ).scalars()
    )
    todo = [p for p in PLATFORMS if p not in existing]
    summary = {"day": day.isoformat(), "created": [], "skipped": sorted(existing)}
    if not todo:
        return summary

    panchangam, nugget = await _gather(day)
    try:
        card_keys = await to_thread.run_sync(_render_cards, day, panchangam)
    except Exception:  # cards are an enhancement; text drafts must still land
        logger.error("content.pipeline: card rendering failed", exc_info=True)
        card_keys = {}

    for platform in todo:
        body = await _draft(platform, panchangam, nugget)
        session.add(
            ContentPost(
                day=day,
                platform=platform,
                kind="panchangam",
                body=body,
                media_key=card_keys.get(_CARD_FORMAT[platform]),
            )
        )
        summary["created"].append(platform)
        metrics.increment("content.posts_drafted")
    await session.commit()
    logger.info("content.pipeline: %s -> created %s", day, summary["created"])
    return summary
