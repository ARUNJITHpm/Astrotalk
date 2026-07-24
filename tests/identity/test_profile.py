"""Tests for NITHARA-BUILD-PLAN Part 2: family board, check-in, stats, milestones.

Hermetic: SQLite in-memory + mocked ephemeris/geocoding/razorpay, so the whole
profile flow (members CRUD, darshan check-in, stats/badges) runs with no keys.
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
_TEMPLE2 = "tvm-attukal-devi"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_razorpay", True)


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


async def _register(client, phone="+915550000001", name="Devotee") -> dict:
    reg = await client.post("/identity/users", json={
        "phone": phone, "password": "p", "name": name,
        "dob": "1990-01-01", "birth_time": None, "birth_place": "Thrissur",
    })
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=main_app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_self_member_autocreated_then_crud(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        async with _client() as client:
            auth = await _register(client)

            # First read lazily creates the self row.
            members = (await client.get("/identity/me/members", headers=auth)).json()
            assert len(members) == 1
            assert members[0]["self"] is True
            assert members[0]["name"] == "Devotee" and members[0]["rel"] == "rSelf"

            # Add a relative.
            added = await client.post(
                "/identity/me/members",
                json={"name": "Amma", "rel": "rMother", "nak": 3}, headers=auth,
            )
            assert added.status_code == 201
            mid = added.json()["id"]
            assert added.json()["self"] is False and added.json()["nak"] == 3

            # Self sorts first, relative second.
            listing = (await client.get("/identity/me/members", headers=auth)).json()
            assert [m["self"] for m in listing] == [True, False]

            # Edit the relative.
            patched = await client.patch(
                f"/identity/me/members/{mid}", json={"nak": 10}, headers=auth
            )
            assert patched.json()["nak"] == 10

            # Delete it; the self row cannot be deleted.
            assert (await client.delete(f"/identity/me/members/{mid}", headers=auth)).status_code == 204
            assert len((await client.get("/identity/me/members", headers=auth)).json()) == 1
            self_id = listing[0]["id"]
            no_self = await client.delete(f"/identity/me/members/{self_id}", headers=auth)
            assert no_self.status_code == 400
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_checkin_advances_stats_and_is_idempotent(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        async with _client() as client:
            auth = await _register(client)

            zero = (await client.get("/identity/me/stats", headers=auth)).json()
            assert zero == {"temples_visited": 0, "poojas": 0, "streak": 0, "badges": 0}

            first = await client.post(f"/temples/{_TEMPLE}/checkin", headers=auth)
            assert first.status_code == 200
            assert first.json() == {"fresh": True, "temple_id": _TEMPLE, "temples_visited": 1}

            # Same temple, same day → not fresh, count unchanged.
            again = await client.post(f"/temples/{_TEMPLE}/checkin", headers=auth)
            assert again.json()["fresh"] is False
            assert again.json()["temples_visited"] == 1

            # A darshan also advanced the daily streak.
            stats = (await client.get("/identity/me/stats", headers=auth)).json()
            assert stats["temples_visited"] == 1 and stats["streak"] == 1
            assert stats["badges"] >= 1  # first_temple unlocked

            # A second temple bumps the distinct count.
            await client.post(f"/temples/{_TEMPLE2}/checkin", headers=auth)
            assert (await client.get("/identity/me/stats", headers=auth)).json()["temples_visited"] == 2

            bad = await client.post("/temples/nope/checkin", headers=auth)
            assert bad.status_code == 404
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_milestones_track_real_activity(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        async with _client() as client:
            auth = await _register(client)

            before = {m["key"]: m for m in (await client.get("/identity/me/milestones", headers=auth)).json()}
            assert before["first_temple"]["got"] is False
            assert before["ten_temples"]["target"] == 10

            await client.post(f"/temples/{_TEMPLE}/checkin", headers=auth)
            # An UNPAID booking must not light the badge yet.
            created = await client.post(
                "/bookings", json={"temple_id": _TEMPLE, "pooja_key": "pushpanjali"}, headers=auth
            )
            unpaid = {m["key"]: m for m in (await client.get("/identity/me/milestones", headers=auth)).json()}
            assert unpaid["first_pooja"]["got"] is False and unpaid["first_pooja"]["current"] == 0

            # Only a captured payment counts as a pooja.
            await client.post(f"/commerce/orders/{created.json()['order_id']}/mock-pay", headers=auth)
            after = {m["key"]: m for m in (await client.get("/identity/me/milestones", headers=auth)).json()}
            assert after["first_temple"]["got"] is True
            assert after["first_pooja"]["got"] is True and after["first_pooja"]["current"] == 1
            assert after["ten_temples"]["got"] is False
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_members_scoped_to_caller(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        async with _client() as client:
            auth = await _register(client, phone="+915550000002", name="A")
            await client.post(
                "/identity/me/members", json={"name": "Kin", "rel": "rSpouse"}, headers=auth
            )
            other = await _register(client, phone="+915550000003", name="B")
            mine = (await client.get("/identity/me/members", headers=other)).json()
            # Only their own auto-created self row — none of A's members.
            assert len(mine) == 1 and mine[0]["name"] == "B"
    finally:
        main_app.dependency_overrides.pop(get_session, None)
