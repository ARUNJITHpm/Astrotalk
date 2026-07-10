"""Tests for recurring-concern detection (chat.recurrence).

Hermetic: an in-memory SQLite chat_history plus the temples module's real
``detect_concern`` classifier.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.chat.models import ChatTurn
from app.modules.chat.recurrence import detect_recurring_concern
from app.modules.temples.service import TemplesService
from app.platform.db import Base

_detect = TemplesService().detect_concern
_MARRIAGE = "വിവാഹം എപ്പോൾ നടക്കും?"


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


async def _seed(session, count, reply="ശുഭം."):
    for _ in range(count):
        session.add(
            ChatTurn(
                user_id="u1",
                messages=[{"role": "user", "content": _MARRIAGE}],
                reply=reply,
            )
        )
    await session.commit()


async def test_fires_at_three_of_ten(session):
    await _seed(session, 2)  # + the current message = 3
    recurring, direct = await detect_recurring_concern(session, "u1", _MARRIAGE, _detect)
    assert recurring == "marriage"
    assert direct is False


async def test_not_fired_below_threshold(session):
    await _seed(session, 1)  # + current = 2, below 3
    recurring, _ = await detect_recurring_concern(session, "u1", _MARRIAGE, _detect)
    assert recurring is None


async def test_direct_ask_fires_without_history(session):
    recurring, direct = await detect_recurring_concern(
        session, "u1", "Can I consult an astrologer near me?", _detect
    )
    assert direct is True
    assert recurring is None  # no history → not "recurring", but a direct ask


async def test_cooldown_suppresses_when_recent_reply_named_an_astrologer(session):
    await _seed(session, 2, reply="താങ്കൾ kozhikode-astro-1 നെ കാണാം.")
    recurring, _ = await detect_recurring_concern(session, "u1", _MARRIAGE, _detect)
    assert recurring is None


async def test_no_session_degrades_to_no_fire():
    recurring, direct = await detect_recurring_concern(None, "u1", _MARRIAGE, _detect)
    assert recurring is None
    assert direct is False


async def test_empty_history_degrades_to_no_fire(session):
    recurring, _ = await detect_recurring_concern(session, "u1", _MARRIAGE, _detect)
    assert recurring is None  # only the current turn, count 1
