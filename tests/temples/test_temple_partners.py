"""Tests for GROWTH_PLAN.md Part 3: temple partnerships.

Covers the admin partner console (create, festivals, QR), the public
microsite + subscribe flow (which IS the WhatsApp opt-in), the embeddable
panchangam widget, and the festival notification cron: T-3 targeting,
consent + 24h-cap enforcement via the whatsapp module, and idempotency
via the notification log.
"""

from datetime import date, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.notifications.service import FESTIVAL_LEAD_DAYS, NotificationsService
from app.modules.temples import partners
from app.modules.whatsapp import consent
from app.platform.config import get_settings
from app.platform.db import Base, get_session

_TEMPLE_ID = "tvm-padmanabhaswamy"
_TODAY = date(2026, 7, 7)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
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


_notifications = NotificationsService()


async def _partner(session, slug="padmanabha"):
    return await partners.create_partner(session, temple_id=_TEMPLE_ID, slug=slug)


# ---- partner + subscription rules ----


async def test_partner_slug_and_duplicate_rules(session):
    await _partner(session)
    with pytest.raises(partners.PartnerError):  # same temple twice
        await partners.create_partner(session, temple_id=_TEMPLE_ID, slug="other")
    with pytest.raises(partners.PartnerError):  # bad slug
        await partners.create_partner(session, temple_id="x", slug="Bad Slug!")


async def test_subscribe_is_the_whatsapp_opt_in(session):
    await _partner(session)
    sub = await partners.subscribe(session, phone="+91 98765 43210", temple_id=_TEMPLE_ID)
    assert sub.phone == "+919876543210"  # normalized like identity
    assert await consent.is_opted_in(session, "+919876543210")

    # Idempotent per (phone, temple).
    again = await partners.subscribe(session, phone="+919876543210", temple_id=_TEMPLE_ID)
    assert again.id == sub.id

    with pytest.raises(partners.PartnerError):
        await partners.subscribe(session, phone="12", temple_id=_TEMPLE_ID)


# ---- festival notification cron ----


async def test_festival_run_sends_once_with_consent_and_cap(session):
    await _partner(session)
    festival_day = _TODAY + timedelta(days=FESTIVAL_LEAD_DAYS)
    await partners.add_festival(
        session, temple_id=_TEMPLE_ID, name="Alpashi Utsavam",
        name_ml="അൽപ്പശി ഉത്സവം", day=festival_day,
    )
    # One festival NOT in the window — must not trigger.
    await partners.add_festival(
        session, temple_id=_TEMPLE_ID, name="Later", day=festival_day + timedelta(days=10),
    )

    subscribed = "+919000000001"
    await partners.subscribe(session, phone=subscribed, temple_id=_TEMPLE_ID)
    # An opted-OUT subscriber: subscribed, then replied STOP.
    stopped = "+919000000002"
    await partners.subscribe(session, phone=stopped, temple_id=_TEMPLE_ID)
    await consent.opt_out(session, stopped)
    # A capped subscriber: already got 3 messages today.
    capped = "+919000000003"
    await partners.subscribe(session, phone=capped, temple_id=_TEMPLE_ID)
    for _ in range(3):
        await consent.record_send(session, capped)

    summary = await _notifications.run_festivals(session, _TODAY)
    assert summary["festivals"] == 1
    assert summary["sent"] == 1  # only the consenting, un-capped subscriber
    assert summary["skipped"] == 2

    # Re-run: the log makes it a no-op (scheduler retries are safe).
    second = await _notifications.run_festivals(session, _TODAY)
    assert second["sent"] == 0
    # The send was logged against the throttle counter too.
    assert await consent.sends_in_last_24h(session, subscribed) == 1


# ---- HTTP surface ----


@pytest.mark.asyncio
async def test_partner_console_and_public_pages(session):
    main_app.dependency_overrides[get_session] = lambda: session
    admin = {"X-Admin-Token": "chargemod"}
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Console is admin-gated.
            assert (await client.get("/temples/partners")).status_code == 401
            assert (
                await client.post("/temples/partners", json={"temple_id": "x", "slug": "x"})
            ).status_code == 401

            # Unknown temple id refused; real one registers.
            bad = await client.post(
                "/temples/partners", headers=admin,
                json={"temple_id": "nope", "slug": "nope"},
            )
            assert bad.status_code == 404
            created = await client.post(
                "/temples/partners", headers=admin,
                json={"temple_id": _TEMPLE_ID, "slug": "padmanabha", "tier": "partner"},
            )
            assert created.status_code == 201

            fest = await client.post(
                "/temples/partners/padmanabha/festivals", headers=admin,
                json={"name": "Painkuni Utsavam", "name_ml": "പൈങ്കുനി ഉത്സവം",
                      "day": "2026-08-01"},
            )
            assert fest.status_code == 201

            qr = await client.get("/temples/partners/padmanabha/qr.png", headers=admin)
            assert qr.status_code == 200
            assert qr.headers["content-type"] == "image/png"
            assert qr.content.startswith(b"\x89PNG")

            # Public microsite: temple name, panchangam, festival, vazhipadu.
            page = await client.get("/t/padmanabha?src=qr")
            assert page.status_code == 200
            assert "പത്മനാഭസ്വാമി" in page.text
            assert "പൈങ്കുനി ഉത്സവം" in page.text
            assert "നല്ല നേരം" in page.text
            assert "thulabharam" in page.text
            assert (await client.get("/t/unknown")).status_code == 404

            # Subscribe from the page.
            sub = await client.post("/t/padmanabha/subscribe", json={"phone": "+919111111111"})
            assert sub.status_code == 200
            assert (
                await client.post("/t/padmanabha/subscribe", json={"phone": "1"})
            ).status_code == 422

            # Widget: public, embeddable, branded when ?temple= is given.
            widget = await client.get("/widget/panchangam?temple=padmanabha")
            assert widget.status_code == 200
            assert "പത്മനാഭസ്വാമി" in widget.text
            assert "x-frame-options" not in {k.lower() for k in widget.headers}

            # Cron endpoint is token-gated like the content one.
            monkey_settings = get_settings()
            monkey_settings.cron_token = "cron-secret"
            try:
                assert (await client.post("/notifications/run-festivals")).status_code == 401
                run = await client.post(
                    "/notifications/run-festivals",
                    headers={"X-Cron-Token": "cron-secret"},
                )
                assert run.status_code == 200
                assert "target_day" in run.json()
            finally:
                monkey_settings.cron_token = ""
    finally:
        main_app.dependency_overrides.pop(get_session, None)
