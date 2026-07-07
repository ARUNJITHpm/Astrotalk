"""Tests for GROWTH_PLAN.md Part 5c: white-label SaaS subscriptions.

Covers subscribe (mock) → active, dunning via the subscription webhook
(halted → past_due soft-lock: bookings refused, new customers degrade to
Tara-direct, data still readable), recovery (charged → active), the
customer cap, and owner/admin gating of the billing surfaces.
"""

import json
from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.identity.service import IdentityService
from app.modules.orgs.service import OrgsService
from app.platform.config import get_settings
from app.platform.db import Base, get_session

_MONDAY = date(2026, 7, 13)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_razorpay", True)
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", "")


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


def _sub_event(sub_id: str, event: str) -> bytes:
    return json.dumps(
        {"event": event, "payload": {"subscription": {"entity": {"id": sub_id}}}}
    ).encode()


async def test_customer_cap_gates_new_attachments(session, monkeypatch):
    orgs = OrgsService()
    org = await orgs.create_org(session, handle="tiny", name="Tiny")
    monkeypatch.setitem(OrgsService.PLAN_LIMITS, "starter", {"customer_cap": 1, "booking": True})

    from app.modules.identity.schemas import UserCreate

    identity = IdentityService()
    first = await identity.create_user(
        session, UserCreate(phone="+911", password="p", name="A", dob="1990-01-01",
                            birth_place="Kochi", org="tiny"),
    )
    assert first.org_id == org.id
    # Cap hit → second signup still succeeds, but Tara-direct.
    second = await identity.create_user(
        session, UserCreate(phone="+912", password="p", name="B", dob="1990-01-01",
                            birth_place="Kochi", org="tiny"),
    )
    assert second.org_id is None


@pytest.mark.asyncio
async def test_subscription_lifecycle_and_dunning(session):
    main_app.dependency_overrides[get_session] = lambda: session
    admin = {"X-Admin-Token": "chargemod"}
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            reg = await client.post("/identity/users", json={
                "phone": "+913000000001", "password": "p", "name": "Owner",
                "dob": "1980-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            owner = {"Authorization": f"Bearer {reg.json()['token']}"}
            await client.post("/orgs", headers=admin, json={
                "handle": "guru", "name": "Guru", "owner_phone": "+913000000001",
            })
            cust = await client.post("/identity/users", json={
                "phone": "+913000000002", "password": "p", "name": "C",
                "dob": "1995-01-01", "birth_time": None, "birth_place": "Kochi",
                "org": "guru",
            })
            customer = {"Authorization": f"Bearer {cust.json()['token']}"}

            # Billing panel is owner-only; trial by default.
            assert (await client.get("/orgs/guru/billing", headers=customer)).status_code == 403
            trial = (await client.get("/orgs/guru/billing", headers=owner)).json()
            assert trial["billing_status"] == "trial"
            assert trial["growth_locked"] is False

            # Subscribe (mock) → active pro.
            sub = await client.post(
                "/orgs/guru/billing/subscribe", json={"plan": "pro"}, headers=owner
            )
            assert sub.status_code == 200
            sub_id = sub.json()["subscription_id"]
            assert sub.json()["billing_status"] == "active"
            assert sub_id.startswith("sub_mock_")

            # A bookable slot while healthy.
            await client.post("/orgs/guru/booking/slots", headers=owner, json={
                "weekday": 0, "start": "10:00", "end": "10:30",
                "duration_min": 30, "price_paise": 0,
            })
            ok = await client.post(
                "/orgs/guru/booking", json={"starts_at": f"{_MONDAY}T10:00:00"},
                headers=customer,
            )
            assert ok.status_code == 201

            # Renewal fails → Razorpay sends subscription.halted → soft-lock.
            halted = await client.post(
                "/commerce/webhook/razorpay",
                content=_sub_event(sub_id, "subscription.halted"),
            )
            assert halted.status_code == 200
            locked = (await client.get("/orgs/guru/billing", headers=owner)).json()
            assert locked["billing_status"] == "past_due"
            assert locked["growth_locked"] is True

            # Growth features lock: no new bookings, signups degrade to direct…
            await client.post(
                f"/orgs/guru/booking/{ok.json()['booking']['id']}/cancel", headers=customer
            )
            blocked = await client.post(
                "/orgs/guru/booking", json={"starts_at": f"{_MONDAY}T10:00:00"},
                headers=customer,
            )
            assert blocked.status_code == 409
            reg2 = await client.post("/identity/users", json={
                "phone": "+913000000003", "password": "p", "name": "D",
                "dob": "1996-01-01", "birth_time": None, "birth_place": "Kochi",
                "org": "guru",
            })
            assert reg2.status_code == 201  # never bounced
            direct = await IdentityService().get_user_by_phone(session, "+913000000003")
            assert direct.org_id is None

            # …but data is never deleted: CRM still reads.
            crm = await client.get("/orgs/guru/crm/customers", headers=owner)
            assert crm.status_code == 200 and len(crm.json()) == 1

            # Payment recovers → active again, booking unlocked.
            await client.post(
                "/commerce/webhook/razorpay",
                content=_sub_event(sub_id, "subscription.charged"),
            )
            recovered = (await client.get("/orgs/guru/billing", headers=owner)).json()
            assert recovered["billing_status"] == "active"
            again = await client.post(
                "/orgs/guru/booking", json={"starts_at": f"{_MONDAY}T10:00:00"},
                headers=customer,
            )
            assert again.status_code == 201

            # Unknown subscription id is acknowledged, not retried.
            unknown = await client.post(
                "/commerce/webhook/razorpay",
                content=_sub_event("sub_elsewhere", "subscription.halted"),
            )
            assert unknown.status_code == 200

            # Admin ops lever.
            ops = await client.post(
                "/orgs/guru/plan", headers=admin,
                json={"plan": "starter", "billing_status": "trial"},
            )
            assert ops.json()["plan"] == "starter"
            assert ops.json()["billing_status"] == "trial"
    finally:
        main_app.dependency_overrides.pop(get_session, None)
