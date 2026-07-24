"""Tests for NITHARA-BUILD-PLAN Part 1: pooja bookings.

Covers pricing (server-side ₹ + ₹15 fee), the create→checkout→confirm flow via
commerce (mock capture), state reconciliation (wait→ok), the member snapshot,
and the auth + not-found boundaries. Hermetic: SQLite in-memory + mocked
Razorpay, so the whole flow runs with zero keys.
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
    monkeypatch.setattr(get_settings(), "mock_razorpay", True)
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


async def _register(client) -> dict:
    reg = await client.post("/identity/users", json={
        "phone": "+915555500000", "password": "p", "name": "Devotee",
        "dob": "1990-01-01", "birth_time": None, "birth_place": "Thrissur",
    })
    return {"Authorization": f"Bearer {reg.json()['token']}"}


@pytest.mark.asyncio
async def test_booking_requires_auth(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/bookings", json={"temple_id": _TEMPLE, "pooja_key": "pushpanjali"}
            )
            assert resp.status_code == 401
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_unknown_temple_and_pooja_404(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            auth = await _register(client)
            bad_temple = await client.post(
                "/bookings", json={"temple_id": "nope", "pooja_key": "pushpanjali"}, headers=auth
            )
            assert bad_temple.status_code == 404
            bad_pooja = await client.post(
                "/bookings", json={"temple_id": _TEMPLE, "pooja_key": "nope"}, headers=auth
            )
            assert bad_pooja.status_code == 404
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_booking_flow_prices_confirms_and_reconciles(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            auth = await _register(client)

            created = await client.post(
                "/bookings",
                json={
                    "temple_id": _TEMPLE, "pooja_key": "pushpanjali",
                    "when": "28 Jul, 6:00 AM",
                    "member_id": 1, "member_name": "Rohini", "member_nak": 3,
                },
                headers=auth,
            )
            assert created.status_code == 201, created.text
            b = created.json()
            # ₹101 offering + ₹15 fee, in paise; server-priced.
            assert b["amount_paise"] == 10100 and b["service_fee_paise"] == 1500
            assert b["total_paise"] == 11600
            assert b["state"] == "wait" and b["ref"].startswith("NT")
            assert b["mock"] is True and b["order_id"]
            assert b["member_name"] == "Rohini" and b["member_nak"] == 3

            # Before payment: still waiting.
            listing = (await client.get("/bookings", headers=auth)).json()
            assert len(listing) == 1 and listing[0]["state"] == "wait"

            # Capture via the commerce mock-pay, then it reconciles to ok.
            paid = await client.post(f"/commerce/orders/{b['order_id']}/mock-pay", headers=auth)
            assert paid.status_code == 200
            after = (await client.get("/bookings", headers=auth)).json()
            assert after[0]["state"] == "ok" and after[0]["when"] == "28 Jul, 6:00 AM"
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_bookings_are_scoped_to_the_caller(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            auth = await _register(client)
            await client.post(
                "/bookings", json={"temple_id": _TEMPLE, "pooja_key": "archana"}, headers=auth
            )
            # A different user sees none of the first user's bookings.
            other = await client.post("/identity/users", json={
                "phone": "+915555511111", "password": "p", "name": "Other",
                "dob": "1991-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
            mine = (await client.get("/bookings", headers=other_auth)).json()
            assert mine == []
    finally:
        main_app.dependency_overrides.pop(get_session, None)
