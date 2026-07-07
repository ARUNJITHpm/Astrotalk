"""Temple partnership internals (GROWTH_PLAN.md Part 3).

Partner CRUD, festival calendar, subscriptions, and QR generation. The
public pages themselves live in router.py; this file owns the data access.

Consent rule (GUARDRAILS.md §3): subscribing here IS the WhatsApp opt-in —
a user-initiated action on the temple's page — recorded through the whatsapp
module's consent ledger, never around it.
"""

import io
import re
from datetime import UTC, date as date_type, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.temples.models import TempleFestival, TemplePartner, TempleSubscription
from app.platform import metrics
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class PartnerError(ValueError):
    pass


async def create_partner(
    session: AsyncSession,
    *,
    temple_id: str,
    slug: str,
    contact_name: str = "",
    contact_phone: str = "",
    tier: str = "free",
) -> TemplePartner:
    if not _SLUG_RE.match(slug):
        raise PartnerError("slug must be lowercase letters/digits/hyphens")
    if tier not in ("free", "partner"):
        raise PartnerError("tier must be free or partner")
    clash = (
        await session.execute(
            select(TemplePartner).where(
                (TemplePartner.slug == slug) | (TemplePartner.temple_id == temple_id)
            )
        )
    ).scalars().first()
    if clash is not None:
        raise PartnerError("temple or slug already registered")
    partner = TemplePartner(
        temple_id=temple_id,
        slug=slug,
        contact_name=contact_name,
        contact_phone=contact_phone,
        tier=tier,
    )
    session.add(partner)
    await session.flush()
    metrics.increment("temples.partners_created")
    return partner


async def get_partner_by_slug(session: AsyncSession, slug: str) -> TemplePartner | None:
    return (
        await session.execute(
            select(TemplePartner).where(
                TemplePartner.slug == slug, TemplePartner.active.is_(True)
            )
        )
    ).scalars().first()


async def list_partners(session: AsyncSession) -> list[TemplePartner]:
    return list(
        (
            await session.execute(
                select(TemplePartner).order_by(TemplePartner.created_at.desc())
            )
        ).scalars().all()
    )


async def add_festival(
    session: AsyncSession, *, temple_id: str, name: str, day: date_type, name_ml: str = ""
) -> TempleFestival:
    festival = TempleFestival(temple_id=temple_id, name=name, name_ml=name_ml, day=day)
    session.add(festival)
    await session.flush()
    return festival


async def upcoming_festivals(
    session: AsyncSession, temple_id: str, within_days: int = 60,
    today: date_type | None = None,
) -> list[TempleFestival]:
    today = today or datetime.now(UTC).date()
    return list(
        (
            await session.execute(
                select(TempleFestival)
                .where(
                    TempleFestival.temple_id == temple_id,
                    TempleFestival.day >= today,
                    TempleFestival.day <= today + timedelta(days=within_days),
                )
                .order_by(TempleFestival.day)
            )
        ).scalars().all()
    )


async def festivals_on(
    session: AsyncSession, day: date_type
) -> list[TempleFestival]:
    """Every partner temple's festivals falling exactly on ``day``."""
    active_ids = select(TemplePartner.temple_id).where(TemplePartner.active.is_(True))
    return list(
        (
            await session.execute(
                select(TempleFestival).where(
                    TempleFestival.day == day,
                    TempleFestival.temple_id.in_(active_ids),
                )
            )
        ).scalars().all()
    )


async def subscribe(
    session: AsyncSession, *, phone: str, temple_id: str, channel: str = "whatsapp"
) -> TempleSubscription:
    """Subscribe a phone to a temple's festival updates (idempotent).

    Rides the whatsapp consent ledger: the page's subscribe action is the
    user's explicit opt-in, so it's recorded there first.
    """
    from app.modules.identity.service import normalize_phone
    from app.modules.whatsapp import consent

    phone = normalize_phone(phone)
    if not phone or len(phone.lstrip("+")) < 10:
        raise PartnerError("valid mobile number required")
    if channel == "whatsapp":
        await consent.opt_in(session, phone)
    existing = (
        await session.execute(
            select(TempleSubscription).where(
                TempleSubscription.phone == phone,
                TempleSubscription.temple_id == temple_id,
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing
    subscription = TempleSubscription(phone=phone, temple_id=temple_id, channel=channel)
    session.add(subscription)
    await session.flush()
    metrics.increment("temples.subscriptions")
    return subscription


async def subscribers_for(session: AsyncSession, temple_id: str, channel: str = "whatsapp") -> list[str]:
    """Subscriber phone numbers for one temple+channel (notifications job)."""
    return list(
        (
            await session.execute(
                select(TempleSubscription.phone).where(
                    TempleSubscription.temple_id == temple_id,
                    TempleSubscription.channel == channel,
                )
            )
        ).scalars().all()
    )


def qr_png(url: str) -> bytes:
    """A print-sized QR PNG pointing at the temple's microsite."""
    import qrcode

    qr = qrcode.QRCode(box_size=16, border=4)  # ~1000px — sharp at poster size
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
