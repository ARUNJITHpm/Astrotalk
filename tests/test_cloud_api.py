"""Tests for the official Meta WhatsApp Cloud API transport.

Covers the pieces that make "cloud" a drop-in replacement for WAHA:
  - CloudAPIClient: recipient formatting, mock send, AI-disclosure footer.
  - _make_transport: config selects cloud vs waha.
  - Cloud webhook: GET verification handshake, X-Hub-Signature-256 verification,
    and POST routing an inbound text through the SAME brain as WAHA.
"""

import hashlib
import hmac
import json

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.whatsapp import onboarding as ob
from app.modules.whatsapp.cloud_api_client import CloudAPIClient, _phone_to_wa_id
from app.modules.whatsapp.router import _verify_meta_signature
from app.modules.whatsapp.service import _make_transport
from app.modules.whatsapp.waha_client import WAHAClient, _AI_DISCLOSURE
from app.platform.config import get_settings
from app.platform.db import Base

_PHONE = "919400621156"


# ---- recipient formatting ----


def test_phone_to_wa_id_strips_plus_and_chat_suffix():
    assert _phone_to_wa_id("+919400621156") == "919400621156"
    assert _phone_to_wa_id("919400621156") == "919400621156"
    assert _phone_to_wa_id("919400621156@c.us") == "919400621156"
    assert _phone_to_wa_id("919400621156:12@s.whatsapp.net") == "919400621156"


# ---- mock send + disclosure ----


async def test_cloud_send_text_is_mocked_and_carries_disclosure(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    client = CloudAPIClient()
    # send_text must append the AI disclosure in code (GUARDRAILS §3). We assert
    # via _send by capturing the composed text through a monkeypatched _send.
    captured = {}

    async def _capture(phone, text):
        captured["phone"] = phone
        captured["text"] = text
        return {"mock": True}

    monkeypatch.setattr(client, "_send", _capture)
    await client.send_text(_PHONE, "നമസ്കാരം")
    assert _AI_DISCLOSURE in captured["text"]
    assert captured["text"].startswith("നമസ്കാരം")

    # send_text_raw must NOT append it.
    captured.clear()
    await client.send_text_raw(_PHONE, "STOP confirmed")
    assert _AI_DISCLOSURE not in captured["text"]


async def test_cloud_send_mock_returns_placeholder_without_network(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    client = CloudAPIClient()
    result = await client._send(_PHONE, "hello")
    assert result == {"mock": True, "to": _PHONE}


# ---- transport selection ----


def test_make_transport_selects_cloud(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_transport", "cloud")
    assert isinstance(_make_transport(), CloudAPIClient)


def test_make_transport_defaults_to_waha(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_transport", "waha")
    assert isinstance(_make_transport(), WAHAClient)


# ---- signature verification ----


def test_verify_meta_signature():
    secret = "app-secret-123"
    body = b'{"hello":"world"}'
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_meta_signature(body, good, secret) is True
    assert _verify_meta_signature(body, good, "") is True  # no secret → skip
    assert _verify_meta_signature(body, "sha256=deadbeef", secret) is False
    assert _verify_meta_signature(body, "", secret) is False  # missing header
    assert _verify_meta_signature(b'{"tampered":1}', good, secret) is False


# ---- webhook (GET verification + POST routing) ----


@pytest_asyncio.fixture
async def api(monkeypatch):
    """httpx client bound to the app with an in-memory DB, transport=cloud,
    WhatsApp mocked, and a known verify token."""
    monkeypatch.setattr(get_settings(), "whatsapp_transport", "cloud")
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    monkeypatch.setattr(get_settings(), "meta_webhook_verify_token", "verify-me")
    monkeypatch.setattr(get_settings(), "meta_app_secret", "")  # skip HMAC in test

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


async def test_cloud_webhook_verification_echoes_challenge(api):
    resp = await api.get(
        "/whatsapp/cloud-webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "1234567890",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "1234567890"


async def test_cloud_webhook_verification_rejects_bad_token(api):
    resp = await api.get(
        "/whatsapp/cloud-webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "1234567890",
        },
    )
    assert resp.status_code == 403


def _inbound(text: str, from_digits: str = _PHONE, msg_id: str = "wamid.TEST1") -> dict:
    """A minimal Cloud API inbound-text webhook body."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PNID",
                            },
                            "contacts": [
                                {"profile": {"name": "Tester"}, "wa_id": from_digits}
                            ],
                            "messages": [
                                {
                                    "from": from_digits,
                                    "id": msg_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def test_cloud_webhook_routes_text_through_brain(api):
    # A first greeting from an unknown number → the feature-showcase welcome path
    # runs (state persists), and the endpoint reports it handled one message.
    resp = await api.post("/whatsapp/cloud-webhook", json=_inbound("hi"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "handled": "1"}


async def test_cloud_webhook_ignores_delivery_statuses(api):
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.X", "status": "delivered"}
                            ],
                        },
                    }
                ]
            }
        ],
    }
    resp = await api.post("/whatsapp/cloud-webhook", json=body)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "handled": "0"}
