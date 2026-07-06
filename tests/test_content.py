"""Tests for the content module: §5 daily message + the Part-1 content pack.

Pack coverage: the run-daily pipeline (drafts per platform, idempotency,
grounded fallbacks, cards in storage), the approve→publish lifecycle with its
status gates, and the HTTP surface's token gating.
"""

from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.content import templates
from app.modules.content.models import PLATFORMS
from app.modules.content.service import ContentService, InvalidTransition
from app.platform.config import get_settings
from app.platform.db import Base, get_session
from app.platform.storage import reset_storage


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    # Pin the mock regardless of the local .env — pytest must never make real
    # LLM calls (this test silently burned API tokens before this pin).
    monkeypatch.setenv("MOCK_LLM", "1")


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    # Pin every external: ephemeris mock, WhatsApp mock, storage to a temp dir.
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_whatsapp", True)
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


_DAY = date(2026, 7, 7)


_PANCHANGAM = {
    "date": "2026-06-25",
    "nakshatram": "രോഹിണി",
    "nalla_neram": "07:30–08:30",
    "tithi": "ദശമി",
}


async def test_generate_daily_message_is_compliant_and_grounded():
    msg = await ContentService().generate_daily_message(_PANCHANGAM)

    # Grounded in the panchangam, ends with the soft CTA + app link (§5).
    assert "രോഹിണി" in msg
    assert "👉" in msg
    assert templates.APP_LINK in msg
    # GUARDRAILS §1: no payment/urgency language in the daily copy.
    for forbidden in ("₹", "pay", "urgent", "ഇപ്പോൾ തന്നെ വാങ്ങ"):
        assert forbidden not in msg


def test_system_prompt_matches_doc_and_substitutes_link():
    prompt = templates.system_prompt()
    # Exact §5 rules are present.
    assert "ONE short Malayalam WhatsApp Channel message" in prompt
    assert "NEVER predict doom" in prompt
    # The {app_link} placeholder is resolved before the LLM sees it.
    assert "{app_link}" not in prompt
    assert templates.APP_LINK in prompt


# ---- Daily content pack (GROWTH_PLAN.md Part 1) ----


async def test_run_daily_drafts_all_platforms_idempotently(session):
    service = ContentService()

    first = await service.run_daily(session, _DAY)
    assert sorted(first["created"]) == sorted(PLATFORMS)
    assert first["skipped"] == []

    # Second run for the same day creates nothing (safe to re-fire the cron).
    second = await service.run_daily(session, _DAY)
    assert second["created"] == []
    assert sorted(second["skipped"]) == sorted(PLATFORMS)

    posts = await service.list_posts(session, _DAY)
    assert len(posts) == len(PLATFORMS)
    for post in posts:
        assert post.status == "draft"
        assert post.body.strip()  # grounded fallback copy (LLM is mocked)
        assert post.media_key and post.media_key.startswith("content/2026-07-07/")
        assert post.media_url and post.media_url.startswith("/media/")
        # GUARDRAILS §1: public copy carries no payment/urgency language.
        for forbidden in ("₹", "pay", "urgent"):
            assert forbidden not in post.body


async def test_approve_applies_inline_edit_and_publish_lifecycle(session):
    service = ContentService()
    await service.run_daily(session, _DAY)
    posts = await service.list_posts(session, _DAY)
    wa = next(p for p in posts if p.platform == "wa_channel")

    # Publishing a draft is refused — human approval is the safety net.
    with pytest.raises(InvalidTransition):
        await service.publish(session, wa.id)

    approved = await service.approve(session, wa.id, body="എഡിറ്റ് ചെയ്ത സന്ദേശം")
    assert approved.status == "approved"
    assert approved.body == "എഡിറ്റ് ചെയ്ത സന്ദേശം"

    published = await service.publish(session, wa.id)
    assert published.status == "published"
    assert published.external_id == "wa_channel:mock"
    assert published.published_at is not None

    # Re-publishing a published post is refused.
    with pytest.raises(InvalidTransition):
        await service.publish(session, wa.id)


@pytest.mark.asyncio
async def test_content_http_surface_gating_and_flow(session, monkeypatch):
    # Admin endpoints demand X-Admin-Token; run-daily takes cron OR admin.
    monkeypatch.setattr(get_settings(), "cron_token", "cron-secret")
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # No token → 401 everywhere.
            assert (await client.get("/content/posts")).status_code == 401
            assert (await client.post(f"/content/run-daily?day={_DAY}")).status_code == 401

            # Cron token fires the pipeline; admin token reviews and ships.
            run = await client.post(
                f"/content/run-daily?day={_DAY}", headers={"X-Cron-Token": "cron-secret"}
            )
            assert run.status_code == 200
            assert sorted(run.json()["created"]) == sorted(PLATFORMS)

            admin = {"X-Admin-Token": "chargemod"}
            posts = (await client.get(f"/content/posts?day={_DAY}", headers=admin)).json()
            post_id = posts[0]["id"]
            ok = await client.post(f"/content/posts/{post_id}/approve", headers=admin)
            assert ok.status_code == 200 and ok.json()["status"] == "approved"
            shipped = await client.post(f"/content/posts/{post_id}/publish", headers=admin)
            assert shipped.status_code == 200 and shipped.json()["status"] == "published"

            # The rendered card is fetchable through /media.
            media_url = posts[0]["media_url"]
            card = await client.get(media_url)
            assert card.status_code == 200
            assert card.headers["content-type"] == "image/png"
    finally:
        main_app.dependency_overrides.pop(get_session, None)
