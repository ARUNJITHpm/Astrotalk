"""Tests for GROWTH_PLAN.md Part 4a: tenancy core.

Covers org creation rules (handles, reserved names, owner resolution), the
public branding endpoint, the white-label pages (branding injected, same
chat UI), org-tagged registration (users.org_id), and the hard rule that the
persona overlay is wrapped in the immutable-guardrails preamble and reaches
the chat system prompt AFTER the safety persona.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.chat.service import ChatService
from app.modules.identity.service import IdentityService
from app.modules.orgs.service import OrgError, OrgsService
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


_orgs = OrgsService()
_identity = IdentityService()


async def test_org_handle_rules(session):
    await _orgs.create_org(session, handle="guru-jyothisham", name="Guru Jyothisham")
    with pytest.raises(OrgError):  # duplicate
        await _orgs.create_org(session, handle="guru-jyothisham", name="X")
    with pytest.raises(OrgError):  # reserved
        await _orgs.create_org(session, handle="admin", name="X")
    with pytest.raises(OrgError):  # invalid chars
        await _orgs.create_org(session, handle="Bad Handle!", name="X")
    with pytest.raises(OrgError):  # unknown plan
        await _orgs.create_org(session, handle="ok-handle", name="X", plan="gold")


async def test_persona_overlay_is_guardrail_wrapped(session):
    org = await _orgs.create_org(
        session, handle="jyothisham", name="ജ്യോതിഷം LIVE",
        persona_overlay="Speak as Guruji, warm and grandfatherly.",
    )
    overlay = await _orgs.persona_overlay_for(session, org.id)
    assert "can NEVER override" in overlay
    assert "Guruji" in overlay
    assert overlay.index("NEVER override") < overlay.index("Guruji")  # preamble first

    # No overlay text → nothing appended at all.
    plain = await _orgs.create_org(session, handle="plain", name="Plain")
    assert await _orgs.persona_overlay_for(session, plain.id) is None
    assert await _orgs.persona_overlay_for(session, None) is None


async def test_org_overlay_reaches_chat_prompt_after_safety_persona(session):
    org = await _orgs.create_org(
        session, handle="star-guru", name="Star Guru",
        persona_overlay="You are Star Guru's assistant.",
    )
    from app.modules.identity.schemas import UserCreate

    user = await _identity.create_user(
        session,
        UserCreate(phone="+915555555555", password="p", name="U", dob="1990-01-01",
                   birth_place="Kochi", org="star-guru"),
    )
    assert user.org_id == org.id

    response = await ChatService().handle_message(
        "+915555555555", [{"role": "user", "content": "എന്റെ ദിവസം എങ്ങനെ?"}],
        session=session, debug=True,
    )
    prompt = response.debug["system_prompt"]
    assert "Star Guru's assistant" in prompt
    assert "org" in response.grounded_in
    # Overlay comes AFTER the safety persona — the rules read first.
    assert prompt.index("Star Guru's assistant") > 100


@pytest.mark.asyncio
async def test_whitelabel_http_surface(session):
    main_app.dependency_overrides[get_session] = lambda: session
    admin = {"X-Admin-Token": "chargemod"}
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Owner must exist first.
            missing_owner = await client.post("/orgs", headers=admin, json={
                "handle": "guruji", "name": "Guruji", "owner_phone": "+919999999999",
            })
            assert missing_owner.status_code == 404

            reg = await client.post("/identity/users", json={
                "phone": "+919999999999", "password": "p", "name": "Guruji Owner",
                "dob": "1980-01-01", "birth_time": None, "birth_place": "Kochi",
            })
            assert reg.status_code == 201

            created = await client.post("/orgs", headers=admin, json={
                "handle": "guruji", "name": "Guruji ജ്യോതിഷം",
                "persona_overlay": "Warm, grandfatherly.",
                "theme_primary": "#c94f7c", "owner_phone": "+919999999999",
            })
            assert created.status_code == 201
            assert created.json()["owner_user_id"] == reg.json()["user"]["id"]

            # Anyone can fetch branding; unknown org 404s.
            pub = await client.get("/orgs/guruji/public")
            assert pub.status_code == 200
            assert pub.json()["theme_primary"] == "#c94f7c"
            assert (await client.get("/orgs/nope/public")).status_code == 404

            # White-label pages: same UI with branding injected.
            page = await client.get("/a/guruji/ui")
            assert page.status_code == 200
            assert "window.TARA_ORG" in page.text
            assert "Guruji ജ്യോതിഷം" in page.text
            assert 'src="/static/ui/chat.js' in page.text  # the SAME chat app
            login = await client.get("/a/guruji/login")
            assert login.status_code == 200
            assert "window.TARA_ORG" in login.text
            assert (await client.get("/a/nope/ui")).status_code == 404

            # Registering from the white-label page attaches the org; an
            # unknown handle degrades to a Tara-direct account.
            reg2 = await client.post("/identity/users", json={
                "phone": "+918888888888", "password": "p", "name": "Fan",
                "dob": "1995-05-05", "birth_time": None, "birth_place": "Kochi",
                "org": "guruji",
            })
            assert reg2.status_code == 201
            user = await _identity.get_user_by_phone(session, "+918888888888")
            assert user.org_id == created.json()["id"]

            reg3 = await client.post("/identity/users", json={
                "phone": "+917777777777", "password": "p", "name": "Direct",
                "dob": "1996-06-06", "birth_time": None, "birth_place": "Kochi",
                "org": "does-not-exist",
            })
            assert reg3.status_code == 201
            direct = await _identity.get_user_by_phone(session, "+917777777777")
            assert direct.org_id is None
    finally:
        main_app.dependency_overrides.pop(get_session, None)
