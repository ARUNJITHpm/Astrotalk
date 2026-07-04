"""Tests for whatsapp compliance: footer, consent ledger, 24h cap, daily pipeline."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.whatsapp import consent, service
from app.modules.whatsapp.service import WhatsappService
from app.modules.whatsapp.tasks import send_daily_message
from app.platform.db import Base

_PHONE = "+919000000000"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_publish_to_channel_always_appends_disclosure_and_optout():
    composed = await WhatsappService().publish_to_channel("ഇന്നത്തെ സന്ദേശം.")
    # AI disclosure + opt-out are appended in code, not left to the prompt.
    assert "AI" in composed
    assert "STOP" in composed
    assert composed.startswith("ഇന്നത്തെ സന്ദേശം.")


async def test_consent_ledger_opt_in_out(session):
    assert await consent.is_opted_in(session, _PHONE) is False
    await consent.opt_in(session, _PHONE)
    assert await consent.is_opted_in(session, _PHONE) is True
    await consent.opt_out(session, _PHONE)
    assert await consent.is_opted_in(session, _PHONE) is False


async def test_should_throttle_enforces_daily_cap(session):
    svc = WhatsappService()
    assert await svc.should_throttle(session, _PHONE) is False
    for _ in range(service.MAX_WA_MESSAGES_PER_DAY):
        await consent.record_send(session, _PHONE)
    # At the cap → throttled.
    assert await svc.should_throttle(session, _PHONE) is True


async def test_daily_pipeline_produces_footered_message():
    msg = await send_daily_message()
    assert "👉" in msg  # content's soft CTA
    assert "AI" in msg and "STOP" in msg  # whatsapp compliance footer
