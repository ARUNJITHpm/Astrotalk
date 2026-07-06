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


async def test_authenticate_checks_the_password(session):
    service = IdentityService()
    await service.create_user(session, _SAMPLE)

    # Correct password logs in; equivalent phone formats resolve to one user.
    ok = await service.authenticate(session, "+91-98765-43210", "secret123")
    assert ok is not None and ok.phone == "+919876543210"

    # Wrong password fails, and an unregistered number fails regardless.
    assert await service.authenticate(session, "+919876543210", "wrong") is None
    assert await service.authenticate(session, "+910000000000", "secret123") is None


async def test_verify_identity_matches_birth_details(session):
    service = IdentityService()
    await service.create_user(session, _SAMPLE)

    # Name matches case-/whitespace-insensitively; dob must match exactly.
    ok = await service.verify_identity(
        session, "+91-98765-43210", "  arya  ", date(1995, 4, 12)
    )
    assert ok is not None and ok.phone == "+919876543210"

    # Wrong name, wrong dob, or unknown number all fail.
    assert await service.verify_identity(
        session, "+919876543210", "Someone", date(1995, 4, 12)
    ) is None
    assert await service.verify_identity(
        session, "+919876543210", "Arya", date(1990, 1, 1)
    ) is None
    assert await service.verify_identity(
        session, "+910000000000", "Arya", date(1995, 4, 12)
    ) is None


async def test_reset_password_rehashes_and_revokes_sessions(session):
    service = IdentityService()
    user = await service.create_user(session, _SAMPLE)

    # An outstanding session exists; the old password authenticates.
    login = await service.create_session(session, user)
    assert await service.get_session_user(session, login.token) is not None
    assert await service.authenticate(session, user.phone, "secret123") is not None

    await service.reset_password(session, user, "brandnew")

    # New password works, old one no longer does, old session is revoked.
    assert await service.authenticate(session, user.phone, "brandnew") is not None
    assert await service.authenticate(session, user.phone, "secret123") is None
    assert await service.get_session_user(session, login.token) is None


async def test_session_tokens_expire_and_revoke(session, monkeypatch):
    service = IdentityService()
    user = await service.create_user(session, _SAMPLE)

    login = await service.create_session(session, user)
    assert login.token and len(login.token) > 30
    found = await service.get_session_user(session, login.token)
    assert found is not None and found.id == user.id

    # Unknown/empty tokens resolve to no one.
    assert await service.get_session_user(session, "not-a-token") is None
    assert await service.get_session_user(session, "") is None

    # Logout revokes immediately (and is idempotent).
    await service.revoke_session(session, login.token)
    assert await service.get_session_user(session, login.token) is None
    await service.revoke_session(session, login.token)

    # An expired session is dead even though the row existed.
    monkeypatch.setattr(get_settings(), "session_ttl_hours", -1)
    stale = await service.create_session(session, user)
    assert await service.get_session_user(session, stale.token) is None


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
            auth = resp.json()  # AuthResponse: {user, token, expires_at}
            user_id = auth["user"]["id"]
            token = auth["token"]
            assert token and auth["expires_at"]
            assert auth["user"]["phone"] == "+919876543210"
            assert auth["user"]["tz"] == "Asia/Kolkata"
            # Password hash is never exposed in the API response.
            assert "password" not in auth["user"]
            assert "password_hash" not in auth["user"]

            # Same mobile again → 409, not a duplicate user.
            dup = await client.post("/identity/users", json=body)
            assert dup.status_code == 409, dup.text

            # Login needs the REAL password now.
            wrong = await client.post(
                "/identity/login",
                json={"phone": "+91 98765 43210", "password": "anything"},
            )
            assert wrong.status_code == 401, wrong.text
            ok = await client.post(
                "/identity/login",
                json={"phone": "+91 98765 43210", "password": "secret123"},
            )
            assert ok.status_code == 200, ok.text
            assert ok.json()["user"]["id"] == user_id

            # An unregistered number still gets 401.
            bad = await client.post(
                "/identity/login",
                json={"phone": "+910000000000", "password": "secret123"},
            )
            assert bad.status_code == 401, bad.text

            # The chart is private: no token → 401; another user's id → 403.
            headers = {"Authorization": f"Bearer {token}"}
            assert (await client.get(f"/identity/users/{user_id}/chart")).status_code == 401
            assert (
                await client.get(f"/identity/users/{user_id + 1}/chart", headers=headers)
            ).status_code == 403

            chart = await client.get(f"/identity/users/{user_id}/chart", headers=headers)
            assert chart.status_code == 200, chart.text
            # astrology_engine now computes a (mock) natal chart at onboarding.
            natal = chart.json()["natal_json"]
            assert natal["mock"] is True
            assert natal["nakshatram"]
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_forgot_password_reset_flow_via_api():
    """End-to-end: verify birth details, reset the password, and log in with it.
    Wrong details are rejected; the old password stops working afterward."""
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
            assert (await client.post("/identity/users", json=body)).status_code == 201

            proof = {"phone": "+91 98765 43210", "name": "arya", "dob": "1995-04-12"}

            # Wrong birth date → 401 on both verify and reset.
            bad = {**proof, "dob": "1990-01-01"}
            assert (
                await client.post("/identity/password/verify", json=bad)
            ).status_code == 401
            assert (
                await client.post(
                    "/identity/password/reset", json={**bad, "new_password": "hacker"}
                )
            ).status_code == 401

            # Too-short new password is rejected (422) even with correct details.
            short = await client.post(
                "/identity/password/reset", json={**proof, "new_password": "no"}
            )
            assert short.status_code == 422, short.text

            # Correct details → verify passes (204), then reset logs in (200).
            assert (
                await client.post("/identity/password/verify", json=proof)
            ).status_code == 204
            done = await client.post(
                "/identity/password/reset", json={**proof, "new_password": "freshpass"}
            )
            assert done.status_code == 200, done.text
            assert done.json()["token"] and done.json()["user"]["phone"] == "+919876543210"

            # New password logs in; the old one no longer does.
            assert (
                await client.post(
                    "/identity/login",
                    json={"phone": "+919876543210", "password": "freshpass"},
                )
            ).status_code == 200
            assert (
                await client.post(
                    "/identity/login",
                    json={"phone": "+919876543210", "password": "secret123"},
                )
            ).status_code == 401
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
            auth = resp.json()
            user_id = auth["user"]["id"]
            headers = {"Authorization": f"Bearer {auth['token']}"}

            # Onboarded under the pinned mock → chart is a mock.
            first = await client.get(f"/identity/users/{user_id}/chart", headers=headers)
            assert first.json()["natal_json"]["mock"] is True

            # Recompute is for the logged-in account only: no token → 401.
            anon = await client.post("/identity/recompute-chart")
            assert anon.status_code == 401, anon.text

            # Turn the real engine on (overrides the autouse mock pin).
            monkeypatch.setattr(get_settings(), "mock_ephemeris", False)

            # Manual recompute → a real Swiss Ephemeris chart is stored.
            redo = await client.post("/identity/recompute-chart", headers=headers)
            assert redo.status_code == 200, redo.text
            natal = redo.json()["natal_json"]
            assert natal["mock"] is False
            assert natal["source"] == "swiss-ephemeris"
            assert natal["dasha"]["system"] == "vimshottari"

            # The newest chart is now the real one.
            newest = await client.get(f"/identity/users/{user_id}/chart", headers=headers)
            assert newest.json()["natal_json"]["mock"] is False

            # Login self-heal: with a real chart already stored it's a no-op,
            # and login still succeeds normally.
            ok = await client.post(
                "/identity/login",
                json={"phone": "+919876543210", "password": "secret123"},
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
            auth = resp.json()
            user_id = auth["user"]["id"]
            headers = {"Authorization": f"Bearer {auth['token']}"}
            before = await client.get(f"/identity/users/{user_id}/chart", headers=headers)
            assert before.json()["natal_json"]["mock"] is True

            # Real engine on → the next login recomputes the stale chart.
            monkeypatch.setattr(get_settings(), "mock_ephemeris", False)
            ok = await client.post(
                "/identity/login",
                json={"phone": "+918888877777", "password": "secret123"},
            )
            assert ok.status_code == 200, ok.text

            after = await client.get(f"/identity/users/{user_id}/chart", headers=headers)
            natal = after.json()["natal_json"]
            assert natal["mock"] is False
            assert natal["source"] == "swiss-ephemeris"
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
