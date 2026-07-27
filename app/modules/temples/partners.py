"""Temple partnership internals (GROWTH_PLAN.md Part 3).

Partner CRUD, festival calendar, subscriptions, and QR generation. The
public pages themselves live in router.py; this file owns the data access.

Consent rule (GUARDRAILS.md §3): subscribing here IS the WhatsApp opt-in —
a user-initiated action on the temple's page — recorded through the whatsapp
module's consent ledger, never around it.
"""

import io
import re
from datetime import UTC, datetime, timedelta
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.temples.models import (
    TIERS,
    TempleFestival,
    TemplePartner,
    TempleSubscription,
)
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


async def update_festival(
    session: AsyncSession,
    *,
    festival_id: int,
    name: str | None = None,
    name_ml: str | None = None,
    day: date_type | None = None,
) -> TempleFestival | None:
    """Correct a festival entry. Festivals were append-only until console plan
    Part 5, so a wrong date could never be fixed — and a wrong date is exactly
    the thing subscribers get notified about three days early."""
    festival = await session.get(TempleFestival, festival_id)
    if festival is None:
        return None
    if name is not None:
        festival.name = name
    if name_ml is not None:
        festival.name_ml = name_ml
    if day is not None:
        festival.day = day
    await session.flush()
    return festival


async def delete_festival(session: AsyncSession, *, festival_id: int) -> bool:
    """Remove a festival outright. Unlike a temple or a partner this is a hard
    delete: nothing references a festival row, and a cancelled festival should
    disappear from the microsite rather than linger as an inactive entry."""
    festival = await session.get(TempleFestival, festival_id)
    if festival is None:
        return False
    await session.delete(festival)
    return True


async def update_partner(
    session: AsyncSession,
    *,
    slug: str,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    tier: str | None = None,
    active: bool | None = None,
) -> TemplePartner | None:
    """Edit a partner record. ``active`` had no route that could write it, so a
    partnership could be created but never ended; setting it False takes the
    microsite and QR poster offline without dropping the festival history."""
    partner = (
        await session.execute(select(TemplePartner).where(TemplePartner.slug == slug))
    ).scalars().first()
    if partner is None:
        return None
    if tier is not None:
        if tier not in TIERS:
            raise PartnerError(f"tier must be one of: {', '.join(TIERS)}")
        partner.tier = tier
    if contact_name is not None:
        partner.contact_name = contact_name
    if contact_phone is not None:
        partner.contact_phone = contact_phone
    if active is not None:
        partner.active = active
    await session.flush()
    return partner


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
