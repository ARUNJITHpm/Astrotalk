"""Tests for the Meta WhatsApp Cloud API transport — the only one, since Part 15.

  - CloudAPIClient: recipient formatting, mock send, AI-disclosure footer.
  - Cloud webhook: GET verification handshake, X-Hub-Signature-256 verification,
    and POST routing an inbound text through the brain.

The disclosure assertions matter more than they look. The string they check used
to live inside ``waha_client.py``, which Part 15 deleted — the Cloud client
imported it from there, so a careless removal would have taken GUARDRAILS §3's
AI disclosure off every outbound message with nothing failing. It now lives in
``whatsapp/disclosure.py``, which belongs to no transport.
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
from app.modules.whatsapp.disclosure import AI_DISCLOSURE, OPT_OUT, with_footer
from app.modules.whatsapp.router import _verify_meta_signature
from app.modules.whatsapp.service import _make_transport
from app.platform.config import get_settings, warn_about_removed_settings
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
    assert AI_DISCLOSURE in captured["text"]
    assert captured["text"].startswith("നമസ്കാരം")

    # send_text_raw must NOT append it.
    captured.clear()
    await client.send_text_raw(_PHONE, "STOP confirmed")
    assert AI_DISCLOSURE not in captured["text"]


async def test_cloud_send_mock_returns_placeholder_without_network(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    client = CloudAPIClient()
    result = await client._send(_PHONE, "hello")
    assert result == {"mock": True, "to": _PHONE}


# ---- the compliance footers ----


def test_a_proactive_message_carries_the_disclosure_and_the_way_out():
    """GUARDRAILS §3. A message somebody did not ask for right now must say it
    is AI-assisted AND how to stop the next one; a reply only needs the first."""
    body = with_footer("നാളെ ഉത്സവം")
    assert body.startswith("നാളെ ഉത്സവം")
    assert AI_DISCLOSURE in body
    assert OPT_OUT in body


# ---- transport selection ----


def test_there_is_one_transport_and_it_is_the_cloud_api():
    # Part 15 removed the self-hosted WAHA stack. The selector is gone with it;
    # what remains is a seam, so the next swap is a one-file change again.
    assert isinstance(_make_transport(), CloudAPIClient)


def test_a_stale_waha_setting_warns_instead_of_being_ignored(monkeypatch):
    """A Space whose env still says WHATSAPP_TRANSPORT=waha keeps working — its
    messages go out over the Cloud API — but quietly doing something other than
    what was configured is how an operator comes to believe a channel is wired
    the way they set it up. It boots, and it complains."""
    monkeypatch.setattr(get_settings(), "whatsapp_transport", "waha")
    problems = warn_about_removed_settings()
    assert len(problems) == 1
    assert "waha" in problems[0].lower()
    assert "cloud" in problems[0].lower()

    monkeypatch.setattr(get_settings(), "whatsapp_transport", "cloud")
    assert warn_about_removed_settings() == []


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


# ---- the transport health probe ----


async def test_status_reports_mock_mode_without_touching_the_network(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
    result = await CloudAPIClient().is_healthy()
    assert result == {"healthy": True, "mock": True, "transport": "cloud"}


async def test_status_names_the_missing_credential(monkeypatch):
    """"Live" on the console's Integrations page only means "not mocked". An
    expired token or a wrong phone-number id looks identical from there until a
    devotee's reply fails to arrive, which is why this probe exists at all."""
    monkeypatch.setattr(get_settings(), "mock_whatsapp", False)
    monkeypatch.setattr(get_settings(), "meta_access_token", "")
    monkeypatch.setattr(get_settings(), "meta_phone_number_id", "")
    result = await CloudAPIClient().is_healthy()
    assert result["healthy"] is False
    assert "meta_access_token" in result["error"]


async def test_status_is_owner_only(api):
    # It returns the sending number's display name and Meta quality rating.
    assert (await api.get("/whatsapp/status")).status_code == 401
