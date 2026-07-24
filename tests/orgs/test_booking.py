"""Tests for GROWTH_PLAN.md Part 4b: the org booking system.

Covers slot rules, availability slicing (window → appointment times, minus
booked), the paid flow (pending → order → mock-pay → confirmed on
reconcile), the free flow (instant confirm), double-booking prevention,
owner-only surfaces, and cancellation rights.
"""

from datetime import date, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.orgs import booking as booking_svc
from app.modules.orgs.service import OrgsService
from app.platform.config import get_settings
from app.platform.db import Base, get_session

# A Monday (weekday 0) well in the future.
_MONDAY = date(2026, 7, 13)
assert _MONDAY.weekday() == 0


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_razorpay", True)
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)


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


async def test_slot_rules(session):
    org = await OrgsService().create_org(session, handle="guru", name="Guru")
    with pytest.raises(booking_svc.BookingError):
        await booking_svc.add_slot(session, org_id=org.id, weekday=9, start="10:00", end="11:00")
    with pytest.raises(booking_svc.BookingError):
        await booking_svc.add_slot(session, org_id=org.id, weekday=0, start="10:00", end="10:15")
    with pytest.raises(booking_svc.BookingError):
        await booking_svc.add_slot(session, org_id=org.id, weekday=0, start="ten", end="11:00")


async def test_availability_slices_window(session):
    org = await OrgsService().create_org(session, handle="guru", name="Guru")
    await booking_svc.add_slot(
        session, org_id=org.id, weekday=0, start="10:00", end="11:30",
        duration_min=30, price_paise=50000,
    )
    open_times = await booking_svc.availability(session, org.id, _MONDAY)
    assert [o["starts_at"][-8:] for o in open_times] == ["10:00:00", "10:30:00", "11:00:00"]
    # A different weekday has none.
    assert await booking_svc.availability(session, org.id, _MONDAY + timedelta(days=1)) == []


@pytest.mark.asyncio
async def test_booking_flow_over_http(session):
    main_app.dependency_overrides[get_session] = lambda: session
    admin = {"X-Admin-Token": "chargemod"}
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Owner + org.
            owner_reg = await client.post("/identity/users", json={
                "phone": "+911000000001", "password": "p", "name": "Owner",
                "dob": "1980-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            owner = {"Authorization": f"Bearer {owner_reg.json()['token']}"}
            await client.post("/orgs", headers=admin, json={
                "handle": "guru", "name": "Guru", "owner_phone": "+911000000001",
            })

            # A customer.
            cust_reg = await client.post("/identity/users", json={
                "phone": "+911000000002", "password": "p", "name": "Customer",
                "dob": "1995-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            customer = {"Authorization": f"Bearer {cust_reg.json()['token']}"}

            # Only the owner may add slots.
            slot_payload = {"weekday": 0, "start": "10:00", "end": "11:00",
                            "duration_min": 30, "price_paise": 50000}
            assert (
                await client.post("/orgs/guru/booking/slots", json=slot_payload, headers=customer)
            ).status_code == 403
            assert (
                await client.post("/orgs/guru/booking/slots", json=slot_payload, headers=owner)
            ).status_code == 201
            # A free evening slot too.
            free_payload = {"weekday": 0, "start": "18:00", "end": "18:30",
                            "duration_min": 30, "price_paise": 0}
            await client.post("/orgs/guru/booking/slots", json=free_payload, headers=owner)

            # Public availability.
            avail = (await client.get(f"/orgs/guru/booking/availability?day={_MONDAY}")).json()
            assert len(avail) == 3  # 10:00, 10:30 paid + 18:00 free

            # Paid booking → pending + a checkout order.
            paid_time = f"{_MONDAY}T10:00:00"
            created = await client.post(
                "/orgs/guru/booking", json={"starts_at": paid_time}, headers=customer
            )
            assert created.status_code == 201
            body = created.json()
            assert body["booking"]["status"] == "pending"
            order_id = body["order"]["order_id"]

            # The slot is gone; double-booking refused.
            avail2 = (await client.get(f"/orgs/guru/booking/availability?day={_MONDAY}")).json()
            assert all(o["starts_at"] != paid_time for o in avail2)
            dup = await client.post(
                "/orgs/guru/booking", json={"starts_at": paid_time}, headers=customer
            )
            assert dup.status_code == 409

            # Pay → reconcile on next read → confirmed.
            await client.post(f"/commerce/orders/{order_id}/mock-pay", headers=customer)
            mine = (await client.get("/orgs/guru/booking/mine", headers=customer)).json()
            assert mine[0]["status"] == "confirmed"

            # Free slot confirms instantly.
            free = await client.post(
                "/orgs/guru/booking", json={"starts_at": f"{_MONDAY}T18:00:00"},
                headers=customer,
            )
            assert free.json()["booking"]["status"] == "confirmed"
            assert free.json()["order"] is None

            # Owner sees both; a stranger can't cancel; the customer can.
            all_bookings = (
                await client.get("/orgs/guru/booking/bookings", headers=owner)
            ).json()
            assert len(all_bookings) == 2
            assert (
                await client.get("/orgs/guru/booking/bookings", headers=customer)
            ).status_code == 403

            booking_id = free.json()["booking"]["id"]
            stranger_reg = await client.post("/identity/users", json={
                "phone": "+911000000003", "password": "p", "name": "S",
                "dob": "1999-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            stranger = {"Authorization": f"Bearer {stranger_reg.json()['token']}"}
            assert (
                await client.post(f"/orgs/guru/booking/{booking_id}/cancel", headers=stranger)
            ).status_code == 403
            cancelled = await client.post(
                f"/orgs/guru/booking/{booking_id}/cancel", headers=customer
            )
            assert cancelled.json()["status"] == "cancelled"
            # Cancelling frees the time again.
            avail3 = (await client.get(f"/orgs/guru/booking/availability?day={_MONDAY}")).json()
            assert any(o["starts_at"] == f"{_MONDAY}T18:00:00" for o in avail3)
    finally:
        main_app.dependency_overrides.pop(get_session, None)
