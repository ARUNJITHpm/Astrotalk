"""Share cards (internal): every good moment can leave Tara as a branded image.

GROWTH_PLAN.md Part 2. Two kinds:

  - ``personal`` — the logged-in user shares an insight they just got (chat
    reading, porutham, daily nakshatram). Opaque slug (not enumerable — the
    insight text is personal), tone-screened before rendering because the
    image is public the moment it's shared.
  - ``daily``    — 27 public nakshatra cards per day, rendered lazily on first
    request and reused from storage after (deterministic slug), so the cron
    doesn't pay for stars nobody asks for.

Every card gets a ``/s/{slug}`` landing page with OG tags (the card unfurls
in WhatsApp) and a CTA that carries the creator's referral code — this file
is where virality and the referral loop meet.
"""

import secrets
from datetime import date as date_type

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.content.models import ShareCard
from app.modules.tone_safety.service import ToneSafetyService
from app.platform import metrics
from app.platform.cards import render_card
from app.platform.logging_config import get_logger
from app.platform.storage import get_storage

logger = get_logger(__name__)

_tone = ToneSafetyService()
_engine = AstrologyEngineService()

# Personal-card bodies are user-visible insight text; keep them card-sized.
MAX_BODY_CHARS = 600


class ToneViolation(ValueError):
    """The card text failed the tone_safety screen — refuse to render it."""


async def create_personal_card(
    session: AsyncSession,
    *,
    user_id: int,
    ref_code: str | None,
    title: str,
    body: str,
    template: str = "story",
) -> ShareCard:
    """Render + persist one personal share card for the logged-in user.

    The text is screened before any pixel is drawn — a card that violates the
    tone rules (doom, urgency, remedies-for-money) must never exist as an
    image, because images can't be redacted once they leave the app.
    """
    body = body.strip()[:MAX_BODY_CHARS]
    title = title.strip() or "Tara"
    violations = _tone.screen_reply(f"{title}\n{body}")
    if violations:
        raise ToneViolation(", ".join(violations))

    slug = secrets.token_urlsafe(8)
    png = await to_thread.run_sync(
        lambda: render_card(title=title, body=body, template=template)
    )
    media_key = get_storage().put(f"cards/{slug}.png", png, "image/png")
    card = ShareCard(
        slug=slug,
        kind="personal",
        title=title,
        body=body,
        media_key=media_key,
        ref_code=ref_code,
        created_by_user_id=user_id,
    )
    session.add(card)
    await session.flush()
    metrics.increment("content.cards_created")
    return card


async def get_or_create_daily_card(
    session: AsyncSession, nakshatra: str, day: date_type | None = None
) -> ShareCard:
    """The public daily card for one nakshatra — cached per (day, star).

    Raises ValueError for an unknown nakshatra (or index out of 0–26).
    """
    names = _engine.nakshatra_names()
    if nakshatra.isdigit():
        index = int(nakshatra)
        if index >= len(names):
            raise ValueError(f"nakshatra index {index} out of range 0-26")
    else:
        if nakshatra not in names:
            raise ValueError(f"unknown nakshatra {nakshatra!r}")
        index = names.index(nakshatra)
    name = names[index]

    day = day or date_type.today()
    slug = f"daily-{day.isoformat()}-{index}"
    existing = (
        await session.execute(select(ShareCard).where(ShareCard.slug == slug))
    ).scalars().first()
    if existing is not None:
        return existing

    panchangam = await _engine.get_panchangam(day)
    title = f"{day.isoformat()} · {name}"
    body = _daily_body(name, panchangam)
    png = await to_thread.run_sync(
        lambda: render_card(title=title, body=body, template="story")
    )
    media_key = get_storage().put(f"cards/daily/{day.isoformat()}/{index}.png", png, "image/png")
    card = ShareCard(
        slug=slug, kind="daily", title=title, body=body, media_key=media_key
    )
    session.add(card)
    await session.flush()
    metrics.increment("content.cards_created")
    return card


def _daily_body(name: str, panchangam: dict) -> str:
    """Grounded, compliant copy for one star's daily card (no LLM, no doom)."""
    today_star = panchangam.get("nakshatram", "")
    nalla_neram = panchangam.get("nalla_neram", "")
    lines = [f"{name} നക്ഷത്രക്കാർക്ക് ഇന്ന് ശാന്തമായ ഒരു ദിവസം."]
    if today_star:
        lines.append(f"ഇന്നത്തെ നക്ഷത്രം {today_star}.")
    if nalla_neram:
        lines.append(f"നല്ല നേരം {nalla_neram} — പ്രധാന കാര്യങ്ങൾ അപ്പോൾ ചെയ്യാം.")
    lines.append("ഇന്ന് ഒരാളോട് ഒരു നല്ല വാക്ക് പറയൂ.")
    return "\n".join(lines)


async def get_card(session: AsyncSession, slug: str) -> ShareCard | None:
    return (
        await session.execute(select(ShareCard).where(ShareCard.slug == slug))
    ).scalars().first()


async def record_hit(session: AsyncSession, card: ShareCard) -> None:
    """One landing-page view — the durable share-click metric."""
    card.hits += 1
    await session.flush()
    metrics.increment("content.card_share_hits")
