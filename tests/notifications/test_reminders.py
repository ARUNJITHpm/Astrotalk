"""Tests for NITHARA-BUILD-PLAN Part 4: FCM nakshatram reminders.

Hermetic: SQLite in-memory + mock ephemeris + mock FCM, so the reminder flow
(register device → run job → idempotent re-run) needs no external services.
"""

from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.identity.models import FamilyMember
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
from app.modules.notifications.service import NotificationsService
from app.platform.config import get_settings
from app.platform.db import Base, get_session

_NAK = 3  # Rohini


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_fcm", True)


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


async def _make_user(session, phone="+915551230000") -> int:
    user = await IdentityService().create_user(session, UserCreate(
        phone=phone, password="p", name="Devotee",
        dob=date(1990, 1, 1), birth_time=None, birth_place="Thrissur",
    ))
    return user.id


async def test_reminder_fires_at_lead_and_is_idempotent(session):
    svc = NotificationsService()
    user_id = await _make_user(session)
    await svc.register_device(session, user_id, "tok-1", "android")
    session.add(FamilyMember(user_id=user_id, name="Amma", rel="rMother", nak=_NAK))
    await session.flush()

    today = date(2026, 7, 25)
    star = await AstrologyEngineService().next_nakshatram_day(_NAK, from_day=today)
    lead = (star - today).days

    first = await svc.run_nakshatram_reminders(session, today=today, lead_days=lead)
    assert first["reminders_sent"] == 1

    # Re-running the same day must not double-send (idempotent via the log).
    again = await svc.run_nakshatram_reminders(session, today=today, lead_days=lead)
    assert again["reminders_sent"] == 0

    # A different lead window doesn't match this member's star.
    off = await svc.run_nakshatram_reminders(session, today=today, lead_days=lead + 99)
    assert off["reminders_sent"] == 0


async def test_no_devices_means_no_reminders(session):
    svc = NotificationsService()
    user_id = await _make_user(session, phone="+915551230001")
    # Member exists but no device registered → nobody to push.
    session.add(FamilyMember(user_id=user_id, name="Achan", rel="rFather", nak=_NAK))
    await session.flush()
    result = await svc.run_nakshatram_reminders(session, today=date(2026, 7, 25))
    assert result["reminders_sent"] == 0


async def test_register_device_upserts(session):
    svc = NotificationsService()
    user_id = await _make_user(session, phone="+915551230002")
    d1 = await svc.register_device(session, user_id, "same-token", "android")
    d2 = await svc.register_device(session, user_id, "same-token", "ios")
    assert d1.id == d2.id and d2.platform == "ios"  # re-point, not duplicate


@pytest.mark.asyncio
async def test_device_endpoint_requires_auth(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            anon = await client.post("/notifications/devices", json={"token": "t"})
            assert anon.status_code == 401

            reg = await client.post("/identity/users", json={
                "phone": "+915551230003", "password": "p", "name": "D",
                "dob": "1990-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            auth = {"Authorization": f"Bearer {reg.json()['token']}"}
            ok = await client.post(
                "/notifications/devices", json={"token": "tok", "platform": "web"}, headers=auth
            )
            assert ok.status_code == 201 and ok.json()["platform"] == "web"
    finally:
        main_app.dependency_overrides.pop(get_session, None)
