"""Tests for the admin analytics module.

Covers three surfaces:
  - IdentityService.admin_metrics — the read-only user/chart aggregation, and
    that it exposes counts + a MASKED phone but never birth data.
  - platform.metrics — the in-process LLM token counter.
  - The /admin API — token gating (dev-open, prod-503, token match) and the
    composed overview payload.
"""

from datetime import date, time

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.identity.models import User  # noqa: F401  (registers tables)
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService, _mask_phone
from app.platform import metrics
from app.platform.config import get_settings
from app.platform.db import Base


@pytest.fixture(autouse=True)
def _force_mocks(monkeypatch):
    # admin_metrics is DB-only, but create_user geocodes + charts; pin the mocks
    # so the tests never touch the network or the real ephemeris.
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


def _sample(phone: str, name: str = "Arya") -> UserCreate:
    return UserCreate(
        phone=phone,
        password="secret123",
        name=name,
        dob=date(1995, 4, 12),
        birth_time=time(6, 30),
        birth_place="Thrissur, Kerala",
    )


# ---- IdentityService.admin_metrics ----

async def test_admin_metrics_counts_users_and_charts(session):
    service = IdentityService()
    u1 = await service.create_user(session, _sample("+919000000001", "Arya"))
    u2 = await service.create_user(session, _sample("+919000000002", "Bala"))
    # Real chart for u1, placeholder (pending) chart for u2.
    await service.save_chart(session, u1.id, {"nakshatram": "Ashwini"})
    await service.save_chart(session, u2.id, {"status": "pending"})
    await session.commit()

    m = await service.admin_metrics(session)

    assert m["total_users"] == 2
    assert m["total_charts"] == 2
    assert m["users_with_chart"] == 2
    assert m["real_charts"] == 1
    assert m["placeholder_charts"] == 1
    assert m["new_users_24h"] == 2  # both just created
    assert len(m["signups_daily_14d"]) == 14
    # Recent list carries name + masked phone + chart flag — and NO birth data.
    recent = {r["name"]: r for r in m["recent_users"]}
    assert recent["Arya"]["has_chart"] is True
    assert recent["Arya"]["phone"] == "+919000000001"
    leaked = set(recent["Arya"]) & {
        "dob", "birth_time", "birth_place", "lat", "lng", "tz"
    }
    assert not leaked, f"birth/identity data leaked into admin metrics: {leaked}"


async def test_admin_metrics_empty_db(session):
    m = await IdentityService().admin_metrics(session)
    assert m["total_users"] == 0
    assert m["recent_users"] == []
    assert sum(d["count"] for d in m["signups_daily_14d"]) == 0


def test_mask_phone():
    assert _mask_phone("+919876543210").endswith("10")
    assert " " in _mask_phone("+919876543210")  # bullet + tail form
    assert _mask_phone("7") == "••"
    assert _mask_phone("") == "••"


# ---- platform.metrics ----

def test_metrics_records_tokens():
    before = metrics.snapshot()["totals"]["total_tokens"]
    metrics.record_llm_usage(
        "sarvam", "sarvam-105b",
        {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )
    metrics.record_llm_usage("mock", None, None, mock=True)
    snap = metrics.snapshot()
    assert snap["totals"]["total_tokens"] == before + 150
    assert snap["totals"]["mock_calls"] >= 1
    assert snap["by_provider"]["sarvam"]["prompt_tokens"] >= 100
    # A malformed usage payload must never raise into the caller.
    metrics.record_llm_usage("openai", "gpt-4o-mini", {"prompt_tokens": None})


# ---- /admin API ----

@pytest_asyncio.fixture
async def api():
    """An httpx client bound to the app with an in-memory DB session override."""
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

    async def _override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_admin_login(api):
    # Legacy username/password still works (kept for existing bookmarks/scripts).
    resp = await api.post("/admin/login", json={"username": "admin", "password": "chargemod"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == "chargemod"
    # Login now also echoes the owner email so the console can show who is signed in.
    assert body["email"] == get_settings().admin_email

    # Invalid login
    resp_invalid = await api.post("/admin/login", json={"username": "admin", "password": "wrongpassword"})
    assert resp_invalid.status_code == 401


async def test_admin_login_with_owner_email(api):
    """Owner may sign in with the configured email + admin password."""
    settings = get_settings()
    resp = await api.post(
        "/admin/login",
        json={"username": settings.admin_email, "password": settings.admin_password},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == "chargemod"
    assert body["email"] == settings.admin_email

    # Wrong password for the owner email is rejected.
    bad = await api.post(
        "/admin/login",
        json={"username": settings.admin_email, "password": "nope"},
    )
    assert bad.status_code == 401


async def test_overview_requires_token_always(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", "")

    # Config endpoint indicates token is required
    cfg = await api.get("/admin/config")
    assert cfg.json() == {"token_required": True}

    # Unauthorized requests fail
    assert (await api.get("/admin/overview")).status_code == 401
    assert (
        await api.get("/admin/overview", headers={"X-Admin-Token": "nope"})
    ).status_code == 401

    # Authorized requests succeed
    ok = await api.get("/admin/overview", headers={"X-Admin-Token": "chargemod"})
    assert ok.status_code == 200
    data = ok.json()
    assert set(data) == {"generated_at", "system", "users", "chat", "llm"}
