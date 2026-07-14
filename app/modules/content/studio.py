"""Content Studio (internal): on-demand creative drafts (ENGAGEMENT_PLAN Part B).

The owner opens the /admin Content Studio, picks a kind (reel script, weekly
astro-news, festival special, nakshatra episode, myth-buster), optionally types
a topic, and gets ONE screened draft + a ready-to-paste caption. They review it,
then post it BY HAND to YouTube/Instagram and paste the link back (mark
published). Auto-publishing to those platforms stays mocked (publishers.py).

Every draft is screened by tone_safety exactly like the daily pipeline — one
corrective retry, then the hand-written compliant fallback. Public copy is never
stored unscreened.
"""

from datetime import date as date_type
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.content import llm, templates
from app.modules.content.models import STUDIO_KINDS, StudioDraft
from app.modules.tone_safety.service import ToneSafetyService
from app.platform import metrics
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

_tone = ToneSafetyService()


class UnknownStudioKind(ValueError):
    """The requested kind is not one of STUDIO_KINDS."""


async def _gather_context(kind: str, day: date_type) -> tuple[dict, str]:
    """(panchangam, extra facts) grounding for the draft. Weekly news scans 7 days."""
    engine = AstrologyEngineService()
    panchangam = await engine.get_panchangam(day)
    extra = ""
    if kind == "weekly_astro_news":
        names: list[str] = []
        for offset in range(7):
            try:
                p = await engine.get_panchangam(day + timedelta(days=offset))
                nak = p.get("nakshatram", "")
                if nak:
                    names.append(nak)
            except Exception:  # a single day's hiccup must not block the script
                logger.warning("studio: panchangam unavailable for +%d", offset, exc_info=True)
        if names:
            extra = "week_nakshatrams=" + ", ".join(names)
    return panchangam, extra


async def _draft(kind: str, topic: str, panchangam: dict, extra: str) -> str:
    """One screened script (LLM → corrective retry → compliant fallback)."""
    system = templates.studio_prompt(kind)
    facts = templates.build_studio_input(kind, topic, panchangam, extra)

    body = await llm.generate(system, facts)
    if body and not _tone.screen_reply(body):
        return body
    if body:  # violations found — one corrective retry (mirrors chat/pipeline)
        logger.warning("studio: %s draft violated tone rules; retrying.", kind)
        body = await llm.generate(system + "\n" + _tone.corrective_note(), facts)
        if body and not _tone.screen_reply(body):
            return body
        logger.warning("studio: %s retry still violated; using fallback.", kind)
    return templates.studio_fallback(kind, topic, panchangam)


async def generate(
    session: AsyncSession, kind: str, topic: str = "", day: date_type | None = None
) -> StudioDraft:
    """Generate ONE studio draft and persist it as ``draft``."""
    if kind not in STUDIO_KINDS:
        raise UnknownStudioKind(f"unknown studio kind {kind!r}")
    day = day or date_type.today()
    topic = (topic or "").strip()

    panchangam, extra = await _gather_context(kind, day)
    body = await _draft(kind, topic, panchangam, extra)
    title = topic or kind.replace("_", " ").title()

    draft = StudioDraft(
        kind=kind,
        topic=topic or None,
        title=title,
        body=body,
        caption=templates.studio_caption(kind, topic),
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    metrics.increment("content.studio_generated")
    logger.info("studio: generated %s (id=%s)", kind, draft.id)
    return draft


async def list_drafts(session: AsyncSession, limit: int = 100) -> list[StudioDraft]:
    query = select(StudioDraft).order_by(StudioDraft.created_at.desc()).limit(limit)
    return list((await session.execute(query)).scalars().all())
