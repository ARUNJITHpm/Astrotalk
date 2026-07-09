"""Tests for whatsapp compliance: footer, consent ledger, 24h cap, daily pipeline."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.whatsapp import consent, onboarding as ob, service
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


# ---- First-contact welcome (feature showcase) ----


async def test_first_greeting_gets_feature_showcase(session):
    svc = WhatsappService()
    reply = await svc.handle_inbound_message(session, _PHONE, "hi")
    assert reply == ob.WELCOME_MSG
    # The showcase advertises the real feature surface.
    for feature in ("ജാതകം", "പൊരുത്ത", "ദോഷം", "പ്രശ്നം", "പഞ്ചാംഗം"):
        assert feature in reply


async def test_repeat_greeting_gets_short_welcome(session):
    svc = WhatsappService()
    await svc.handle_inbound_message(session, _PHONE, "hi")
    reply = await svc.handle_inbound_message(session, _PHONE, "hello")
    assert reply == ob.WELCOME_BACK_MSG
    assert reply != ob.WELCOME_MSG  # no menu spam on every "hi"


async def test_greeting_never_starts_details_collection(session):
    svc = WhatsappService()
    await svc.handle_inbound_message(session, _PHONE, "hi")
    wa = await ob.get_session(session, _PHONE)
    # Welcome advertises chart features, but details are only collected once a
    # personal chart question is asked (needs_personal_chart).
    assert wa.state == "casual"


async def test_personal_question_starts_collection_after_welcome(session):
    svc = WhatsappService()
    await svc.handle_inbound_message(session, _PHONE, "hi")
    reply = await svc.handle_inbound_message(
        session, _PHONE, "when will i get married?"
    )
    assert reply == ob.COLLECT_INTRO_NAME
    wa = await ob.get_session(session, _PHONE)
    assert wa.state == "collect_name"
    assert wa.onboarding_data["pending_question"] == "when will i get married?"
