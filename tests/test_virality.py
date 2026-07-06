"""Tests for GROWTH_PLAN.md Part 2 (virality): share cards + referral loop.

Covers the referral service (code mint, credit rules, reward threshold),
registration with a ``ref`` code over HTTP, personal card rendering with the
tone screen, the cached public daily nakshatra cards, and the /s/{slug}
landing page (OG tags, CTA carrying the referral code, durable hit counter).
"""

from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.content import share_cards
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
from app.platform.config import get_settings
from app.platform.db import Base, get_session
from app.platform.storage import reset_storage


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_storage", True)
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "referral_reward_threshold", 2)
    monkeypatch.setattr(get_settings(), "public_base_url", "")
    reset_storage()
    yield
    reset_storage()


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


_identity = IdentityService()


def _user_payload(n: int) -> dict:
    return {
        "phone": f"+9198765432{n:02d}",
        "password": "pass",
        "name": f"Test User {n}",
        "dob": "1995-05-05",
        "birth_time": None,
        "birth_place": "Kochi",
    }


async def _make_user(session, n: int):
    return await _identity.create_user(session, UserCreate(**_user_payload(n)))


# ---- referral service rules ----


async def test_referral_code_minted_once(session):
    user = await _make_user(session, 1)
    first = await _identity.get_or_create_referral_code(session, user.id)
    second = await _identity.get_or_create_referral_code(session, user.id)
    assert first.code == second.code
    assert len(first.code) == 8


async def test_record_referral_rules(session):
    referrer = await _make_user(session, 1)
    friend = await _make_user(session, 2)
    code = (await _identity.get_or_create_referral_code(session, referrer.id)).code

    # Unknown code and self-referral are silently ignored.
    assert await _identity.record_referral(session, "NOPE1234", friend.id) is None
    assert await _identity.record_referral(session, code, referrer.id) is None

    # A real credit lands as activated; the same user can't be credited twice.
    referral = await _identity.record_referral(session, code, friend.id)
    assert referral is not None and referral.status == "activated"
    assert await _identity.record_referral(session, code, friend.id) is None

    summary = await _identity.referral_summary(session, referrer.id)
    assert summary["activated"] == 1
    assert summary["reward_granted"] is False  # threshold is 2 in tests


async def test_reward_unlocks_at_threshold(session):
    referrer = await _make_user(session, 1)
    code = (await _identity.get_or_create_referral_code(session, referrer.id)).code
    for n in (2, 3):
        friend = await _make_user(session, n)
        await _identity.record_referral(session, code, friend.id)

    summary = await _identity.referral_summary(session, referrer.id)
    assert summary["activated"] == 2
    assert summary["reward_granted"] is True

    # Funnel shows up in the admin metrics payload.
    metrics = await _identity.admin_metrics(session)
    assert metrics["referrals"]["referred_signups"] == 2
    assert metrics["referrals"]["rewards_granted"] == 1


# ---- share cards ----


async def test_personal_card_screens_tone(session):
    user = await _make_user(session, 1)
    with pytest.raises(share_cards.ToneViolation):
        await share_cards.create_personal_card(
            session, user_id=user.id, ref_code=None,
            title="Tara", body="നിങ്ങളുടെ മേൽ ഒരു ശാപം ഉണ്ട്",
        )


async def test_daily_card_is_cached_per_day_and_star(session):
    first = await share_cards.get_or_create_daily_card(session, "0", date(2026, 7, 7))
    again = await share_cards.get_or_create_daily_card(session, "അശ്വതി", date(2026, 7, 7))
    assert first.id == again.id  # index and name resolve to the SAME cached card
    assert first.slug == "daily-2026-07-07-0"
    assert first.kind == "daily"

    with pytest.raises(ValueError):
        await share_cards.get_or_create_daily_card(session, "27", date(2026, 7, 7))


# ---- HTTP surface: the full loop ----


@pytest.mark.asyncio
async def test_share_and_referral_loop_over_http(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Register the sharer and open their referral panel.
            reg = await client.post("/identity/users", json=_user_payload(1))
            assert reg.status_code == 201
            token = reg.json()["token"]
            auth = {"Authorization": f"Bearer {token}"}

            panel = (await client.get("/identity/referral", headers=auth)).json()
            assert panel["activated"] == 0
            assert f"/ui/login?ref={panel['code']}" in panel["share_link"]

            # Cards require login.
            assert (await client.post("/content/cards", json={"body": "x"})).status_code == 401

            # Render a personal card; its landing page carries the ref code.
            card = await client.post(
                "/content/cards",
                headers=auth,
                json={"title": "ഇന്നത്തെ ചിന്ത", "body": "ശാന്തമായ മനസ്സ് ഏറ്റവും വലിയ കൂട്ട്."},
            )
            assert card.status_code == 201
            body = card.json()
            assert body["media_url"].startswith("/media/cards/")
            assert f"/s/{body['slug']}" in body["share_url"]

            png = await client.get(body["media_url"])
            assert png.status_code == 200
            assert png.headers["content-type"] == "image/png"

            landing = await client.get(f"/s/{body['slug']}")
            assert landing.status_code == 200
            assert 'property="og:image"' in landing.text
            assert f"ref={panel['code']}" in landing.text

            # The hit was recorded durably.
            await session.commit()
            hit_card = await share_cards.get_card(session, body["slug"])
            assert hit_card.hits == 1

            assert (await client.get("/s/not-a-card")).status_code == 404

            # A friend registers through the shared link → referral credited.
            friend_payload = _user_payload(2) | {"ref": panel["code"]}
            reg2 = await client.post("/identity/users", json=friend_payload)
            assert reg2.status_code == 201
            panel2 = (await client.get("/identity/referral", headers=auth)).json()
            assert panel2["activated"] == 1

            # Public daily card needs no auth and is stable across calls.
            daily1 = (await client.get("/content/cards/daily/0")).json()
            daily2 = (await client.get("/content/cards/daily/0")).json()
            assert daily1["slug"] == daily2["slug"]
            assert (await client.get("/content/cards/daily/99")).status_code == 404
    finally:
        main_app.dependency_overrides.pop(get_session, None)
