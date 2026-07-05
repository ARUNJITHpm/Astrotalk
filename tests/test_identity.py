"""Tests for the identity module: onboarding (create_user) and chart persistence.

Uses an in-memory SQLite engine (StaticPool keeps the single connection so the
schema/data persist across sessions). No Postgres or migrations required.
"""

from datetime import date, time

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.identity.models import User  # noqa: F401  (registers tables on Base)
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import _PLACEHOLDER_GEOCODE, IdentityService
from app.platform.config import get_settings
from app.platform.db import Base


@pytest.fixture(autouse=True)
def _force_mock_ephemeris(monkeypatch):
    # Onboarding computes a natal chart AND geocodes the birth place; pin both
    # mocks so tests are independent of the local .env (which runs the real
    # Swiss Ephemeris + Open-Meteo geocoder) and never touch the network.
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)

_SAMPLE = UserCreate(
    phone="+91 98765 43210",
    password="secret123",
    name="Arya",
    dob=date(1995, 4, 12),
    birth_time=time(6, 30),
    birth_place="Thrissur, Kerala",
)


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


async def test_create_user_assigns_id_and_placeholder_geocode(session):
    service = IdentityService()

    user = await service.create_user(session, _SAMPLE)

    assert user.id is not None
    assert user.name == "Arya"
    assert user.birth_place == "Thrissur, Kerala"
    # Phone is stored normalized (digits + leading country '+').
    assert user.phone == "+919876543210"
    # _geocode stub fills lat/lng/tz so onboarding works with no API key.
    assert (user.lat, user.lng, user.tz) == _PLACEHOLDER_GEOCODE
    # Password is stored hashed, never in the clear.
    assert user.password_hash and user.password_hash != "secret123"


async def test_authenticate_registered_number(session):
    service = IdentityService()
    await service.create_user(session, _SAMPLE)

    # TESTING STAGE: any password logs in a registered number; equivalent phone
    # formats resolve to the same user.
    ok = await service.authenticate(session, "+91-98765-43210", "secret123")
    assert ok is not None and ok.phone == "+919876543210"
    assert await service.authenticate(session, "+919876543210", "wrong") is not None

    # An UNregistered number still fails regardless of password.
    assert await service.authenticate(session, "+910000000000", "secret123") is None


async def test_lookup_and_chart_by_phone(session):
    service = IdentityService()
    user = await service.create_user(session, _SAMPLE)
    await service.save_chart(session, user.id, {"sun": "Aries"})

    # Any equivalent formatting of the same number resolves to the same user.
    found = await service.get_user_by_phone(session, "+91-98765-43210")
    assert found is not None and found.id == user.id

    chart = await service.get_chart_by_phone(session, "+919876543210")
    assert chart is not None and chart.natal_json == {"sun": "Aries"}

    assert await service.get_user_by_phone(session, "+910000000000") is None


async def test_get_chart_after_create(session):
    service = IdentityService()

    user = await service.create_user(session, _SAMPLE)
    saved = await service.save_chart(session, user.id, {"sun": "Aries", "moon": "Karka"})

    fetched = await service.get_chart(session, user.id)

    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.user_id == user.id
    assert fetched.natal_json == {"sun": "Aries", "moon": "Karka"}


async def test_get_chart_none_when_user_has_no_chart(session):
    service = IdentityService()
    user = await service.create_user(session, _SAMPLE)

    assert await service.get_chart(session, user.id) is None


async def test_geocode_real_mode_uses_fetched_result_and_caches(monkeypatch):
    """With mock_geocoding off, _geocode returns the provider's result and
    caches it — a later provider outage must not lose a known place."""
    from app.modules.identity import service as identity_service

    monkeypatch.setattr(get_settings(), "mock_geocoding", False)
    monkeypatch.setattr(identity_service, "_GEOCODE_CACHE", {})

    thrissur = (10.5276, 76.2144, "Asia/Kolkata")

    async def fake_fetch(place):
        return thrissur

    monkeypatch.setattr(identity_service, "_fetch_geocode", fake_fetch)
    assert await identity_service._geocode("Thrissur, Kerala") == thrissur

    async def broken_fetch(place):
        raise RuntimeError("provider down")

    monkeypatch.setattr(identity_service, "_fetch_geocode", broken_fetch)
    # Same place (any spacing/case) → served from cache, no network needed.
    assert await identity_service._geocode("  thrissur,   kerala ") == thrissur


async def test_geocode_degrades_to_placeholder(monkeypatch):
    """Provider errors and no-match results both fall back to the placeholder —
    onboarding never blocks on the geocoder."""
    from app.modules.identity import service as identity_service

    monkeypatch.setattr(get_settings(), "mock_geocoding", False)
    monkeypatch.setattr(identity_service, "_GEOCODE_CACHE", {})

    async def broken_fetch(place):
        raise RuntimeError("provider down")

    monkeypatch.setattr(identity_service, "_fetch_geocode", broken_fetch)
    assert await identity_service._geocode("Thrissur") == _PLACEHOLDER_GEOCODE

    async def no_match(place):
        return None

    monkeypatch.setattr(identity_service, "_fetch_geocode", no_match)
    assert await identity_service._geocode("Atlantis") == _PLACEHOLDER_GEOCODE
    # Failures are never cached — a later fixed lookup can still succeed.
    assert identity_service._GEOCODE_CACHE == {}


async def test_recompute_regeocodes_placeholder_account(monkeypatch, session):
    """regeocode_user upgrades an account onboarded with the placeholder to the
    real coordinates once geocoding is enabled."""
    from app.modules.identity import service as identity_service

    service = IdentityService()
    user = await service.create_user(session, _SAMPLE)  # mocked → placeholder
    assert (user.lat, user.lng) == _PLACEHOLDER_GEOCODE[:2]

    monkeypatch.setattr(get_settings(), "mock_geocoding", False)
    monkeypatch.setattr(identity_service, "_GEOCODE_CACHE", {})

    async def fake_fetch(place):
        return (10.5276, 76.2144, "Asia/Kolkata")

    monkeypatch.setattr(identity_service, "_fetch_geocode", fake_fetch)
    user = await service.regeocode_user(session, user)
    assert (user.lat, user.lng, user.tz) == (10.5276, 76.2144, "Asia/Kolkata")


async def test_onboard_flow_via_api():
    """End-to-end: POST /identity/users creates the user + chart, then the chart
    GET returns it. Exercises the astrology_engine pending fallback. Runs on a
    single event loop via httpx ASGITransport to keep the aiosqlite connection
    bound to one loop."""
    import httpx
    from httpx import ASGITransport

    from app.main import app
    from app.platform.db import get_session

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            body = {
                "phone": "+919876543210",
                "password": "secret123",
                "name": "Arya",
                "dob": "1995-04-12",
                "birth_time": "06:30:00",
                "birth_place": "Thrissur, Kerala",
            }
            resp = await client.post("/identity/users", json=body)
            assert resp.status_code == 201, resp.text
            user_id = resp.json()["id"]
            assert resp.json()["phone"] == "+919876543210"
            assert resp.json()["tz"] == "Asia/Kolkata"
            # Password hash is never exposed in the API response.
            assert "password" not in resp.json()
            assert "password_hash" not in resp.json()

            # Same mobile again → 409, not a duplicate user.
            dup = await client.post("/identity/users", json=body)
            assert dup.status_code == 409, dup.text

            # Login (TESTING STAGE): any password works for a registered number.
            ok = await client.post(
                "/identity/login",
                json={"phone": "+91 98765 43210", "password": "anything"},
            )
            assert ok.status_code == 200, ok.text
            assert ok.json()["id"] == user_id

            # An unregistered number still gets 401.
            bad = await client.post(
                "/identity/login",
                json={"phone": "+910000000000", "password": "secret123"},
            )
            assert bad.status_code == 401, bad.text

            chart = await client.get(f"/identity/users/{user_id}/chart")
            assert chart.status_code == 200, chart.text
            # astrology_engine now computes a (mock) natal chart at onboarding.
            natal = chart.json()["natal_json"]
            assert natal["mock"] is True
            assert natal["nakshatram"]
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_recompute_chart_and_login_self_heal(monkeypatch):
    """A chart stored while the ephemeris was mocked upgrades to a real one:
    explicitly via POST /identity/recompute-chart, and automatically at login."""
    import httpx
    from httpx import ASGITransport

    from app.main import app
    from app.platform.db import get_session

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            body = {
                "phone": "+919876543210",
                "password": "secret123",
                "name": "Arya",
                "dob": "1995-04-12",
                "birth_time": "06:30:00",
                "birth_place": "Thrissur, Kerala",
            }
            resp = await client.post("/identity/users", json=body)
            assert resp.status_code == 201, resp.text
            user_id = resp.json()["id"]

            # Onboarded under the pinned mock → chart is a mock.
            first = await client.get(f"/identity/users/{user_id}/chart")
            assert first.json()["natal_json"]["mock"] is True

            # Unknown number → 404, no chart leak.
            missing = await client.post(
                "/identity/recompute-chart", json={"phone": "+910000000000"}
            )
            assert missing.status_code == 404, missing.text

            # Turn the real engine on (overrides the autouse mock pin).
            monkeypatch.setattr(get_settings(), "mock_ephemeris", False)

            # Manual recompute → a real Swiss Ephemeris chart is stored.
            redo = await client.post(
                "/identity/recompute-chart", json={"phone": "+91 98765 43210"}
            )
            assert redo.status_code == 200, redo.text
            natal = redo.json()["natal_json"]
            assert natal["mock"] is False
            assert natal["source"] == "swiss-ephemeris"
            assert natal["dasha"]["system"] == "vimshottari"

            # The newest chart is now the real one.
            newest = await client.get(f"/identity/users/{user_id}/chart")
            assert newest.json()["natal_json"]["mock"] is False

            # Login self-heal: with a real chart already stored it's a no-op,
            # and login still succeeds normally.
            ok = await client.post(
                "/identity/login",
                json={"phone": "+919876543210", "password": "anything"},
            )
            assert ok.status_code == 200, ok.text
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_login_self_heals_mock_chart(monkeypatch):
    """Login alone (no manual call) upgrades a stale mock chart when the real
    engine is enabled."""
    import httpx
    from httpx import ASGITransport

    from app.main import app
    from app.platform.db import get_session

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            body = {
                "phone": "+918888877777",
                "password": "secret123",
                "name": "Devi",
                "dob": "1992-08-01",
                "birth_time": "05:15:00",
                "birth_place": "Kozhikode, Kerala",
            }
            resp = await client.post("/identity/users", json=body)
            assert resp.status_code == 201, resp.text
            user_id = resp.json()["id"]
            before = await client.get(f"/identity/users/{user_id}/chart")
            assert before.json()["natal_json"]["mock"] is True

            # Real engine on → the next login recomputes the stale chart.
            monkeypatch.setattr(get_settings(), "mock_ephemeris", False)
            ok = await client.post(
                "/identity/login",
                json={"phone": "+918888877777", "password": "anything"},
            )
            assert ok.status_code == 200, ok.text

            after = await client.get(f"/identity/users/{user_id}/chart")
            natal = after.json()["natal_json"]
            assert natal["mock"] is False
            assert natal["source"] == "swiss-ephemeris"
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
