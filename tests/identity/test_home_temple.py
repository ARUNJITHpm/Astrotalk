"""The temple a devotee chose, kept against the account.

Onboarding's whole job is "choose your temple", and the answer lived in
`localStorage` — so clearing site data, reinstalling, or opening the app on a
second phone silently threw it away and sent the person back through onboarding.
The account itself survived, because it is keyed by a server-minted anon id.
That mismatch is what this closes.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.platform.config import get_settings
from app.platform.db import Base, get_session

_TEMPLE = "tvm-padmanabhaswamy"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)


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


@pytest_asyncio.fixture
async def api(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        main_app.dependency_overrides.clear()


async def _anon(api, anon_id=None) -> tuple[dict, str]:
    res = await api.post("/identity/anon", json={"anon_id": anon_id} if anon_id else {})
    body = res.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["anon_id"]


async def test_not_choosing_yet_is_a_normal_answer(api):
    """Onboarding is skippable, so null is a state — not an error."""
    auth, _ = await _anon(api)
    res = await api.get("/identity/me/home-temple", headers=auth)
    assert res.status_code == 200
    assert res.json() == {"temple_id": None}


async def test_the_choice_survives_a_reinstall(api):
    """The point of the whole change. A fresh install has no localStorage; it
    resumes the SAME account with the stored anon key, and the temple has to
    come back with it."""
    auth, anon_id = await _anon(api)
    await api.put("/identity/me/home-temple", json={"temple_id": _TEMPLE}, headers=auth)

    # New install, new session token, same account.
    fresh_auth, _ = await _anon(api, anon_id)
    assert fresh_auth != auth
    res = await api.get("/identity/me/home-temple", headers=fresh_auth)
    assert res.json() == {"temple_id": _TEMPLE}


async def test_changing_it_replaces_rather_than_accumulates(api):
    auth, _ = await _anon(api)
    await api.put("/identity/me/home-temple", json={"temple_id": _TEMPLE}, headers=auth)
    res = await api.put(
        "/identity/me/home-temple", json={"temple_id": "tvm-attukal-devi"}, headers=auth
    )
    assert res.json() == {"temple_id": "tvm-attukal-devi"}


async def test_an_unknown_temple_is_refused(api):
    """Validated here rather than by a foreign key: identity and temples compose
    through services, and a DB constraint would make retiring a temple fail
    against every account that had chosen it."""
    auth, _ = await _anon(api)
    res = await api.put(
        "/identity/me/home-temple", json={"temple_id": "not-a-temple"}, headers=auth
    )
    assert res.status_code == 404
    assert (await api.get("/identity/me/home-temple", headers=auth)).json() == {
        "temple_id": None
    }


async def test_two_accounts_keep_their_own_temples(api):
    auth_a, _ = await _anon(api)
    auth_b, _ = await _anon(api)
    await api.put("/identity/me/home-temple", json={"temple_id": _TEMPLE}, headers=auth_a)
    await api.put(
        "/identity/me/home-temple", json={"temple_id": "tvm-attukal-devi"}, headers=auth_b
    )
    mine = (await api.get("/identity/me/home-temple", headers=auth_a)).json()
    assert mine["temple_id"] == _TEMPLE


async def test_it_needs_a_session(api):
    assert (await api.get("/identity/me/home-temple")).status_code == 401
    assert (
        await api.put("/identity/me/home-temple", json={"temple_id": _TEMPLE})
    ).status_code == 401
