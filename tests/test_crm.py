"""Tests for GROWTH_PLAN.md Part 4c: the astrologer CRM.

Covers owner-only access, org-scoping (another org's customer is invisible),
customer list + chart + notes, and the transcript consent rule: 403 until
the CUSTOMER flips /identity/transcript-consent themselves.
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


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_mongo", True)


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


async def _register(client, phone, name, org=None):
    res = await client.post("/identity/users", json={
        "phone": phone, "password": "p", "name": name,
        "dob": "1990-01-01", "birth_time": None, "birth_place": "Kochi", "org": org,
    })
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['token']}"}


@pytest.mark.asyncio
async def test_crm_access_scoping_and_consent(session):
    main_app.dependency_overrides[get_session] = lambda: session
    admin = {"X-Admin-Token": "chargemod"}
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            _owner_id, owner = await _register(client, "+912000000001", "Owner")
            await client.post("/orgs", headers=admin, json={
                "handle": "guru", "name": "Guru", "owner_phone": "+912000000001",
            })
            cust_id, customer = await _register(client, "+912000000002", "Cust", org="guru")
            # A customer of a DIFFERENT org.
            await client.post("/orgs", headers=admin, json={"handle": "other", "name": "O"})
            other_id, _ = await _register(client, "+912000000003", "Other", org="other")

            # Owner-only: the customer's own token is refused.
            assert (
                await client.get("/orgs/guru/crm/customers", headers=customer)
            ).status_code == 403

            customers = (await client.get("/orgs/guru/crm/customers", headers=owner)).json()
            assert [c["user_id"] for c in customers] == [cust_id]

            # Another org's customer is a 404, not a leak.
            assert (
                await client.get(f"/orgs/guru/crm/customers/{other_id}/chart", headers=owner)
            ).status_code == 404

            # Chart prep is available (registration computed it).
            chart = await client.get(
                f"/orgs/guru/crm/customers/{cust_id}/chart", headers=owner
            )
            assert chart.status_code == 200
            assert "natal_json" in chart.json()

            # Notes round-trip; customers never see this surface.
            note = await client.post(
                f"/orgs/guru/crm/customers/{cust_id}/notes", headers=owner,
                json={"note": "prefers evening calls"},
            )
            assert note.status_code == 201
            notes = (
                await client.get(f"/orgs/guru/crm/customers/{cust_id}/notes", headers=owner)
            ).json()
            assert notes[0]["note"] == "prefers evening calls"

            # Transcript: locked until the CUSTOMER consents.
            locked = await client.get(
                f"/orgs/guru/crm/customers/{cust_id}/transcript", headers=owner
            )
            assert locked.status_code == 403
            await client.post(
                "/identity/transcript-consent", headers=customer, json={"allow": True}
            )
            opened = await client.get(
                f"/orgs/guru/crm/customers/{cust_id}/transcript", headers=owner
            )
            assert opened.status_code == 200  # empty list — mongo mocked
            assert opened.json() == []

            # Dashboard page serves with branding for the org.
            page = await client.get("/a/guru/dashboard")
            assert page.status_code == 200
            assert "window.TARA_ORG" in page.text
            assert "Dashboard" in page.text
    finally:
        main_app.dependency_overrides.pop(get_session, None)
