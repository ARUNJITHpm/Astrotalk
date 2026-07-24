"""Tests for the community module (ENGAGEMENT_PLAN.md Part A).

Covers the engagement layer that shipped without tests: emoji reactions
(toggle + validation), the daily check-in streak, and weekly polls
(create / vote / change vote / validation). Exercised at the public service
level with a hermetic in-memory SQLite DB — no card rendering, no HTTP auth —
so it runs anywhere regardless of the local font/libraqm situation.
"""

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.community.models import REACTIONS, UserCheckin
from app.modules.community.schemas import FeedOut
from app.modules.community.service import (
    CommunityService,
    InvalidOption,
    InvalidReaction,
    PollNotFound,
)
from app.platform.db import Base


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


_USER = 101
_POST = 7


# ---- Reactions ----

@pytest.mark.asyncio
async def test_react_toggles_and_counts(session):
    svc = CommunityService()

    added = await svc.react(session, _USER, _POST, "🙏")
    assert added.reactions == {"🙏": 1}
    assert added.my_reactions == ["🙏"]

    # A second user reacting with the same emoji bumps the count, not the toggle.
    other = await svc.react(session, 202, _POST, "🙏")
    assert other.reactions == {"🙏": 2}
    assert other.my_reactions == ["🙏"]

    # Same user + same emoji again removes their reaction (toggle off).
    removed = await svc.react(session, _USER, _POST, "🙏")
    assert removed.reactions == {"🙏": 1}
    assert removed.my_reactions == []


@pytest.mark.asyncio
async def test_react_rejects_unknown_emoji(session):
    with pytest.raises(InvalidReaction):
        await CommunityService().react(session, _USER, _POST, "👎")


# ---- Streak ----

@pytest.mark.asyncio
async def test_streak_counts_consecutive_days_ending_today(session):
    svc = CommunityService()
    today = date.today()
    # Seed three consecutive days ending today, plus an older gap that must not count.
    for delta in (0, 1, 2, 5):
        session.add(UserCheckin(user_id=_USER, day=today - timedelta(days=delta)))
    await session.commit()

    out = await svc.get_streak(session, _USER)
    assert out.streak == 3
    assert out.checked_in_today is True


@pytest.mark.asyncio
async def test_streak_zero_when_no_checkins(session):
    out = await CommunityService().get_streak(session, _USER)
    assert out.streak == 0
    assert out.checked_in_today is False


@pytest.mark.asyncio
async def test_feed_records_checkin_and_exposes_reactions(session):
    svc = CommunityService()
    feed = await svc.get_feed(session, user_id=_USER)
    assert isinstance(feed, FeedOut)
    assert feed.available_reactions == list(REACTIONS)
    # A logged-in feed visit is a check-in, so the streak starts at 1.
    assert feed.streak == 1


# ---- Polls ----

@pytest.mark.asyncio
async def test_poll_create_vote_and_change_vote(session):
    svc = CommunityService()
    poll = await svc.create_poll(session, "ഇന്ന് ക്ഷേത്രം സന്ദർശിക്കുമോ?", ["ഉവ്വ്", "ഇല്ല"])
    assert poll.total_votes == 0
    assert [r.text for r in poll.results] == ["ഉവ്വ്", "ഇല്ല"]

    voted = await svc.vote(session, poll.id, _USER, 0)
    assert voted.total_votes == 1
    assert voted.results[0].votes == 1
    assert voted.my_vote == 0

    # Re-voting changes the choice rather than adding a second vote.
    changed = await svc.vote(session, poll.id, _USER, 1)
    assert changed.total_votes == 1
    assert changed.results[0].votes == 0
    assert changed.results[1].votes == 1
    assert changed.my_vote == 1

    # It appears in the active-poll listing.
    listed = await svc.list_polls(session, _USER)
    assert any(p.id == poll.id for p in listed)


@pytest.mark.asyncio
async def test_vote_rejects_missing_poll_and_bad_option(session):
    svc = CommunityService()
    with pytest.raises(PollNotFound):
        await svc.vote(session, 9999, _USER, 0)

    poll = await svc.create_poll(session, "Q", ["a", "b"])
    with pytest.raises(InvalidOption):
        await svc.vote(session, poll.id, _USER, 5)
