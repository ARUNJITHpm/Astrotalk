"""Who may reach the panels the console carried over in Part 13.

Every endpoint here already existed and every one of them was behind
``AdminGuard``. That guard means **any authenticated operator**, which was an
accurate description of the world when the only credential was the owner's
shared token. Part 4 gave operators real accounts with granted roles, and from
that moment the same declaration meant something quite different: a support
account could publish to the product's public channels, a temple_admin could
open any devotee's chat transcript, and either could type a stranger's mobile
into the WhatsApp simulator and read back that person's personalised reading.

Nothing in the console's IA ever claimed those things were allowed. The gap was
invisible because the sidebar hid the pages — and hiding a nav item is not
access control.

So these tests are about the *negative* case. A 200 for the right role proves
the screen works; only a 403 for the wrong one proves the door is shut. They
pin each carried-over surface to the role the sidebar advertises:

  content (daily pack, studio)   → owner or content_reviewer
  notification runs              → owner only (GUARDRAILS §3: real sends)
  WhatsApp simulator             → owner only (acts as ANY phone)
  chat explorer                  → owner or support
  org tenants + the plan lever   → owner only
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin.models import Operator as OperatorRow
from app.modules.admin.models import OperatorRole, OperatorSession
from app.platform.config import get_settings
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}  # tests/conftest.py configures this


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


@pytest_asyncio.fixture
async def api(session, monkeypatch):
    settings = get_settings()
    # A configured cron token, so the cron branch of the notification guard is
    # closed and the role branch is the one under test. Without this the dev
    # fallback ("no token configured + development = open") would let every
    # request through and the assertions below would prove nothing.
    monkeypatch.setattr(settings, "cron_token", "cron-secret")
    # Hermetic. These are guard tests: the two runs that reach past the door
    # (drafting a pack, firing a notification run) exist here only to prove the
    # door opened. The developer .env has MOCK_OPENAI=false and
    # MOCK_WHATSAPP=false, so without this the suite would bill a real LLM for
    # twelve drafts and try to send real messages to prove a 200.
    monkeypatch.setattr(settings, "mock_openai", True)
    monkeypatch.setattr(settings, "mock_whatsapp", True)
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        main_app.dependency_overrides.clear()


async def _auth(session, *roles, email="staff@example.com") -> dict[str, str]:
    """Sign-in headers for an operator holding exactly ``roles``."""
    row = OperatorRow(email=email, name="Staff", active=True)
    session.add(row)
    await session.flush()
    for role in roles:
        session.add(
            OperatorRole(
                operator_id=row.id,
                role=role,
                temple_id="tsr-guruvayur" if role == "temple_admin" else None,
            )
        )
    token = f"tok-{row.id}-{'-'.join(roles)}"
    session.add(
        OperatorSession(
            token=token,
            operator_id=row.id,
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


# ---- content: the daily pack and the studio ----


async def test_a_content_reviewer_may_read_the_daily_pack(api, session):
    auth = await _auth(session, "content_reviewer")
    assert (await api.get("/content/posts", headers=auth)).status_code == 200
    assert (await api.get("/content/studio", headers=auth)).status_code == 200


async def test_support_may_not_touch_the_daily_pack(api, session):
    """Answering a devotee's question does not extend to publishing on the
    product's Facebook page."""
    auth = await _auth(session, "support")
    assert (await api.get("/content/posts", headers=auth)).status_code == 403
    assert (await api.get("/content/studio", headers=auth)).status_code == 403
    assert (await api.post("/content/posts/1/approve", headers=auth)).status_code == 403


async def test_a_temple_admin_may_not_publish_content(api, session):
    auth = await _auth(session, "temple_admin")
    assert (await api.post("/content/posts/1/publish", headers=auth)).status_code == 403
    assert (await api.delete("/content/studio/1", headers=auth)).status_code == 403


async def test_generating_the_daily_pack_takes_the_cron_token_or_a_reviewer(api, session):
    """The scheduler holds a secret, not a role — that branch must keep working
    or the morning pack silently stops being drafted."""
    cron = {"X-Cron-Token": "cron-secret"}
    assert (await api.post("/content/run-daily?day=2026-01-01", headers=cron)).status_code == 200

    reviewer = await _auth(session, "content_reviewer", email="rev@example.com")
    ok = await api.post("/content/run-daily?day=2026-01-02", headers=reviewer)
    assert ok.status_code == 200

    support = await _auth(session, "support", email="sup@example.com")
    denied = await api.post("/content/run-daily?day=2026-01-03", headers=support)
    assert denied.status_code == 403


async def test_an_unauthenticated_caller_gets_401_not_403(api):
    """The console needs the difference: 401 sends them to the sign-in screen,
    403 tells them to ask the owner. Collapsing them makes a permission wall
    look like an expired session and vice versa."""
    assert (await api.get("/content/posts")).status_code == 401
    assert (await api.post("/content/run-daily")).status_code == 401


async def test_the_flags_are_readable_without_the_analytics(api, session):
    """A content_reviewer needs to know whether Publish really posts.

    That fact only existed on ``/admin/overview``, beside the devotee count, the
    chat volume and the token spend — so the daily-pack screen would have had to
    pull all of it to read one boolean. ``/admin/integrations`` is the same flags
    and nothing else, and notably NOT which credentials are configured.
    """
    auth = await _auth(session, "content_reviewer")
    r = await api.get("/admin/integrations", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"app_env", "integrations"}
    assert isinstance(body["integrations"]["whatsapp"], bool)
    assert "api_keys_present" not in body

    # And it is still a door, not a hole in the wall.
    assert (await api.get("/admin/integrations")).status_code == 401


# ---- notification runs ----


async def test_only_the_owner_may_fire_a_notification_run(api, session):
    """These put messages on real devotees' phones. GUARDRAILS §3 makes the
    first live WhatsApp send a human-approval gate, and the human is the owner
    of the number — not whoever is signed in."""
    for role in ("support", "temple_admin", "content_reviewer"):
        auth = await _auth(session, role, email=f"{role}@example.com")
        r = await api.post("/notifications/run-festivals", headers=auth)
        assert r.status_code == 403, role

    assert (await api.post("/notifications/run-festivals", headers=ADMIN)).status_code == 200


async def test_the_scheduler_still_reaches_the_notification_runs(api):
    cron = {"X-Cron-Token": "cron-secret"}
    assert (await api.post("/notifications/run-festivals", headers=cron)).status_code == 200
    r = await api.post("/notifications/run-nakshatram-reminders", headers=cron)
    assert r.status_code == 200


# ---- the WhatsApp simulator ----


async def test_the_simulator_is_owner_only(api, session):
    """It takes a phone number in the body and replies as that person. A
    temple_admin reaching it is a devotee's private reading handed to a stranger
    who happens to run a temple."""
    payload = {"phone": "+919812345678", "text": "hello"}
    for role in ("support", "temple_admin", "content_reviewer"):
        auth = await _auth(session, role, email=f"{role}@example.com")
        r = await api.post("/whatsapp/simulate", json=payload, headers=auth)
        assert r.status_code == 403, role


# ---- the chat explorer ----


async def test_support_may_read_chat_history(api, session):
    auth = await _auth(session, "support")
    assert (await api.get("/admin/users-chats", headers=auth)).status_code == 200
    r = await api.get("/admin/user-chat/%2B919812345678", headers=auth)
    assert r.status_code == 200


async def test_a_temple_admin_may_not_read_chat_history(api, session):
    auth = await _auth(session, "temple_admin")
    assert (await api.get("/admin/users-chats", headers=auth)).status_code == 403
    r = await api.get("/admin/user-chat/%2B919812345678", headers=auth)
    assert r.status_code == 403


# ---- org tenants ----


async def test_the_tenant_list_and_plan_lever_are_owner_only(api, session):
    """Who our white-label customers are and what they are billed is a
    commercial question, not an operational one."""
    for role in ("support", "temple_admin", "content_reviewer"):
        auth = await _auth(session, role, email=f"{role}@example.com")
        assert (await api.get("/orgs", headers=auth)).status_code == 403, role

    assert (await api.get("/orgs", headers=ADMIN)).status_code == 200
