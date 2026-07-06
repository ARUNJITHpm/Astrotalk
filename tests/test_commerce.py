"""Tests for GROWTH_PLAN.md Part 5a: payments core + entitlements.

Covers order creation (server-side prices), the signature-verified webhook
(capture, failure, replay-idempotency, bad signature), the mock capture flow,
the entitlement rules (idempotent grants, expiry), and the Part 2 wiring:
a referral reward now lands as a durable premium_report entitlement.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.commerce.service import CommerceService, SignatureMismatch
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
from app.platform.config import get_settings
from app.platform.db import Base, get_session
from app.platform.storage import reset_storage


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)
    monkeypatch.setattr(get_settings(), "mock_razorpay", True)
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", "")
    monkeypatch.setattr(get_settings(), "referral_reward_threshold", 1)
    monkeypatch.setattr(get_settings(), "mock_storage", True)
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    reset_storage()
    yield
    reset_storage()


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


_service = CommerceService()
_identity = IdentityService()


def _webhook_body(order_id: str, event: str = "payment.captured") -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {"payment": {"entity": {"id": "pay_test1", "order_id": order_id}}},
        }
    ).encode()


async def test_order_capture_grants_entitlement(session):
    order = await _service.create_order(session, user_id=7, product="premium_report")
    assert order["amount_paise"] == 19900
    assert order["mock"] is True
    assert not await _service.has_entitlement(session, 7, "premium_report")

    # Webhook capture (no secret + mock mode → signature optional).
    result = await _service.handle_webhook(session, _webhook_body(order["order_id"]), None)
    assert result["status"] == "ok"
    assert await _service.has_entitlement(session, 7, "premium_report")

    # Replay is idempotent — still exactly one entitlement.
    await _service.handle_webhook(session, _webhook_body(order["order_id"]), None)
    assert len(await _service.list_entitlements(session, 7)) == 1


async def test_webhook_signature_verification(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", "whsec")
    order = await _service.create_order(session, user_id=1, product="premium_report")
    body = _webhook_body(order["order_id"])

    with pytest.raises(SignatureMismatch):
        await _service.handle_webhook(session, body, "wrong")
    with pytest.raises(SignatureMismatch):
        await _service.handle_webhook(session, body, None)

    good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    assert (await _service.handle_webhook(session, body, good))["status"] == "ok"


async def test_payment_failed_webhook(session):
    order = await _service.create_order(session, user_id=2, product="premium_report")
    await _service.handle_webhook(
        session, _webhook_body(order["order_id"], "payment.failed"), None
    )
    assert not await _service.has_entitlement(session, 2, "premium_report")


async def test_entitlement_expiry(session):
    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=1)
    await _service.grant_entitlement(
        session, user_id=3, product_key="x", granted_by="admin", expires_at=past
    )
    assert not await _service.has_entitlement(session, 3, "x")
    await _service.grant_entitlement(
        session, user_id=3, product_key="x", granted_by="admin", expires_at=future
    )
    assert await _service.has_entitlement(session, 3, "x")


async def test_referral_reward_lands_as_entitlement(session):
    """Part 2 → 5a wiring: the reward threshold grants premium_report."""
    referrer = await _identity.create_user(
        session,
        UserCreate(phone="+911111111111", password="p", name="R", dob="1990-01-01",
                   birth_place="Kochi"),
    )
    friend = await _identity.create_user(
        session,
        UserCreate(phone="+912222222222", password="p", name="F", dob="1991-01-01",
                   birth_place="Kochi"),
    )
    code = (await _identity.get_or_create_referral_code(session, referrer.id)).code
    await _identity.record_referral(session, code, friend.id)  # threshold = 1

    assert await _service.has_entitlement(session, referrer.id, "premium_report")
    rows = await _service.list_entitlements(session, referrer.id)
    assert rows[0].granted_by == "referral"


@pytest.mark.asyncio
async def test_commerce_http_flow(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (
                await client.post("/commerce/orders", json={"product": "premium_report"})
            ).status_code == 401

            reg = await client.post("/identity/users", json={
                "phone": "+913333333333", "password": "p", "name": "Buyer",
                "dob": "1992-02-02", "birth_time": None, "birth_place": "Kochi",
            })
            auth = {"Authorization": f"Bearer {reg.json()['token']}"}

            bad = await client.post("/commerce/orders", json={"product": "nope"}, headers=auth)
            assert bad.status_code == 404

            order = await client.post(
                "/commerce/orders", json={"product": "premium_report"}, headers=auth
            )
            assert order.status_code == 201
            order_id = order.json()["order_id"]

            paid = await client.post(f"/commerce/orders/{order_id}/mock-pay", headers=auth)
            assert paid.status_code == 200

            ents = (await client.get("/commerce/entitlements", headers=auth)).json()
            assert [e["product_key"] for e in ents] == ["premium_report"]
            assert ents[0]["granted_by"] == "purchase"

            # Unknown-order webhook is acknowledged, not retried forever.
            resp = await client.post(
                "/commerce/webhook/razorpay", content=_webhook_body("order_elsewhere")
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "unknown-order"
    finally:
        main_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_premium_report_gated_then_delivered(session):
    """Part 5b: 402 until entitled, then a real multi-page PDF via /media."""
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            reg = await client.post("/identity/users", json={
                "phone": "+914444444444", "password": "p", "name": "Reader",
                "dob": "1993-03-03", "birth_time": None, "birth_place": "Kochi",
            })
            auth = {"Authorization": f"Bearer {reg.json()['token']}"}

            locked = await client.post("/commerce/reports/premium", headers=auth)
            assert locked.status_code == 402

            order = (await client.post(
                "/commerce/orders", json={"product": "premium_report"}, headers=auth
            )).json()
            await client.post(f"/commerce/orders/{order['order_id']}/mock-pay", headers=auth)

            report = await client.post("/commerce/reports/premium", headers=auth)
            assert report.status_code == 200
            url = report.json()["download_url"]
            assert url.endswith(".pdf")

            pdf = await client.get(url)
            assert pdf.status_code == 200
            assert pdf.headers["content-type"] == "application/pdf"
            assert pdf.content.startswith(b"%PDF")
            assert pdf.content.count(b"/Type /Page") >= 4  # 4 rendered pages

            # Second request the same day reuses the stored render.
            again = await client.post("/commerce/reports/premium", headers=auth)
            assert again.json()["download_url"] == url
    finally:
        main_app.dependency_overrides.pop(get_session, None)
