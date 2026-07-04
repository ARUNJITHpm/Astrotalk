"""WhatsApp consent ledger + send log (internal to the whatsapp module).

GUARDRAILS.md §3 requires opt-in BEFORE any send, tracked per phone number, and a
hard cap of business-initiated messages per 24h enforced by a counter. Both live
here as real persistence — not convention.

Phone numbers are sensitive; never log them in plaintext or put them in URLs.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WAConsent(Base):
    """Opt-in ledger keyed by phone number (PROJECT_DOCS.md §7)."""

    __tablename__ = "wa_consent"

    phone: Mapped[str] = mapped_column(primary_key=True)
    opted_in: Mapped[bool] = mapped_column(default=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(nullable=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(nullable=True)


class WAMessageLog(Base):
    """One row per business-initiated send, for the per-24h throttle counter."""

    __tablename__ = "wa_message_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(index=True)
    sent_at: Mapped[datetime] = mapped_column(default=_utcnow)


async def opt_in(session: AsyncSession, phone: str) -> WAConsent:
    consent = await session.get(WAConsent, phone)
    if consent is None:
        consent = WAConsent(phone=phone)
        session.add(consent)
    consent.opted_in = True
    consent.opted_in_at = _utcnow()
    consent.opted_out_at = None
    await session.flush()
    return consent


async def opt_out(session: AsyncSession, phone: str) -> WAConsent:
    consent = await session.get(WAConsent, phone)
    if consent is None:
        consent = WAConsent(phone=phone)
        session.add(consent)
    consent.opted_in = False
    consent.opted_out_at = _utcnow()
    await session.flush()
    return consent


async def is_opted_in(session: AsyncSession, phone: str) -> bool:
    consent = await session.get(WAConsent, phone)
    return bool(consent and consent.opted_in)


async def record_send(session: AsyncSession, phone: str) -> None:
    """Log a business-initiated send (feeds should_throttle)."""
    session.add(WAMessageLog(phone=phone))
    await session.flush()


async def sends_in_last_24h(session: AsyncSession, phone: str) -> int:
    since = _utcnow() - timedelta(hours=24)
    result = await session.execute(
        select(func.count())
        .select_from(WAMessageLog)
        .where(WAMessageLog.phone == phone, WAMessageLog.sent_at >= since)
    )
    return int(result.scalar_one())
