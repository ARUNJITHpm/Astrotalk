"""Integration-style tests for the chat orchestrator (PROJECT_DOCS.md §6).

Drives the real HTTP endpoint via httpx ASGITransport. MOCK_LLM / mock_openai is
on by default, so no API key is needed.

These tests are hermetic w.r.t. the document store: the `_no_mongo` fixture forces
the Mongo layer to "disabled" regardless of the local `.env` (which may point at a
real mongod), so history/memory behaviour is deterministic on any machine.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.modules.chat import history
from app.modules.chat.models import ChatTurn  # noqa: F401
from app.platform.db import Base, get_session

# Astrology terms that must NEVER appear in a crisis safety response (GUARDRAILS §2).
_ASTROLOGY_TERMS = ("ജാതക", "നക്ഷത്ര", "രാശി", "ഗ്രഹ", "dosha", "horoscope", "transit")


@pytest_asyncio.fixture(autouse=True)
async def test_db(monkeypatch):
    """In-memory SQLite DB for tests.

    Overrides DB session dependencies & background session factory.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(history, "async_session_factory", factory)

    async def _override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_session, None)
        await engine.dispose()


@pytest.fixture(autouse=True)
def _no_mongo(monkeypatch):
    """Pin the document store off so tests don't depend on a local mongod / .env.

    user_memory.py does `from app.platform.mongo import get_db`, so we patch
    its bound name to return None — exactly the "Mongo unavailable" path the
    code already degrades through. Chat history now persists in Postgres.
    """
    monkeypatch.setattr("app.modules.chat.user_memory.get_db", lambda: None)
    # Pin the LLM to the mock regardless of the local .env (which points at
    # real providers) — pytest must never spend API money; evals/ is the only
    # place real LLM calls belong.
    monkeypatch.setenv("MOCK_LLM", "1")


class _FakeUser:
    """Stand-in for the authenticated identity.User require_user resolves."""

    def __init__(self, phone: str, name: str = "Demo", dob=None):
        self.phone = phone
        self.name = name
        self.dob = dob
        self.id = 0


def _login_as(phone: str) -> None:
    """Override the auth dependency: requests act as this logged-in user.

    Chat derives the user from the session token, so tests inject the identity
    here instead of registering + logging in for every case.
    """
    from app.modules.identity.auth import require_user

    app.dependency_overrides[require_user] = lambda: _FakeUser(phone)


@pytest.fixture(autouse=True)
def _as_demo_user():
    _login_as("demo")
    yield
    from app.modules.identity.auth import require_user

    app.dependency_overrides.pop(require_user, None)


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_crisis_message_returns_safety_response_with_no_astrology(client):
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [
                    {"role": "user", "content": "എനിക്ക് ജീവിക്കാൻ വയ്യ, ആത്മഹത്യ ചെയ്യണം"}
                ],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_safety_response"] is True
    assert "14416" in body["reply"]
    assert body["grounded_in"] == []
    for term in _ASTROLOGY_TERMS:
        assert term not in body["reply"], f"crisis reply leaked astrology: {term}"


async def test_normal_message_runs_astrology_pipeline(client):
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [
                    {"role": "user", "content": "ഈ വർഷം ജോലിയിൽ എന്ത് മാറ്റം വരും?"}
                ],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_safety_response"] is False
    assert body["reply"].strip()
    # Step 2-3 grounding ran: transits always present, plus any retrieved chunks.
    assert "transits" in body["grounded_in"]


async def test_normal_reply_carries_curious_suggestions(client):
    async with client:
        resp = await client.post(
            "/chat/message",
            json={"messages": [{"role": "user", "content": "ഇന്ന് എങ്ങനെ ഉണ്ടാകും?"}]},
        )
    body = resp.json()
    # Even without a chart, the rotating topics give at least one curious chip.
    assert isinstance(body["suggestions"], list)
    assert body["suggestions"]


async def test_crisis_reply_has_no_suggestions(client):
    async with client:
        resp = await client.post(
            "/chat/message",
            json={"messages": [{"role": "user", "content": "എനിക്ക് ജീവിക്കാൻ വയ്യ, ആത്മഹത്യ ചെയ്യണം"}]},
        )
    body = resp.json()
    assert body["is_safety_response"] is True
    assert body["suggestions"] == []


async def test_recurring_concern_offers_astrologer(client, test_db):
    # Seed two prior marriage turns; the third (this request) crosses the
    # 3-of-10 recurrence threshold, so the reply grounds in an astrologer.
    factory = test_db
    async with factory() as s:
        for _ in range(2):
            s.add(
                ChatTurn(
                    user_id="demo",
                    messages=[{"role": "user", "content": "വിവാഹം എപ്പോൾ നടക്കും?"}],
                    reply="ശുഭം.",
                )
            )
        await s.commit()
    async with client:
        resp = await client.post(
            "/chat/message",
            json={"messages": [{"role": "user", "content": "എന്റെ വിവാഹ കാര്യം ഒന്ന് നോക്കാമോ?"}]},
        )
    body = resp.json()
    assert any(t.startswith("astrologer:") for t in body["grounded_in"])
    assert any(t.startswith("recurring:") for t in body["grounded_in"])
    # And a booking CTA chip is offered.
    assert any(s.startswith("📿") for s in body["suggestions"])


def test_select_varga_maps_topics_to_divisional_charts():
    from app.modules.chat.service import ChatService

    pick = ChatService._select_varga
    assert pick("എനിക്ക് ജോലി മാറ്റം വരുമോ?") == "D10"  # career → dashamsa
    assert pick("When will I get a promotion at work?") == "D10"
    assert pick("വിവാഹം എപ്പോൾ നടക്കും?") == "D9"  # marriage → navamsa
    assert pick("Is my relationship going to last?") == "D9"
    assert pick("കുട്ടികൾ ഉണ്ടാകുമോ?") == "D7"  # children → saptamsa
    assert pick("എന്റെ അമ്മയുടെ ആരോഗ്യം?") == "D12"  # parents → dwadasamsa
    assert pick("hello, how are you?") is None  # no topic → D1 only
    # Manglish (romanized Malayalam) forms pick the same vargas.
    assert pick("ente joli sheriyakumo?") == "D10"
    assert pick("kalyanam eppol nadakkum?") == "D9"
    assert pick("kutti undakumo?") == "D7"


def test_retrieval_query_grounds_in_computed_chart_facts():
    from app.modules.chat.service import ChatService

    chart = {
        "nakshatram": "ചോതി",
        "lagnam": "തുലാം",
        "dasha": {"current": {"mahadasha": {"lord": "shani"}}},
        "doshas": {
            "chovva_dosha": {"present": True},
            "kala_sarpa_dosha": {"present": False},
        },
    }
    transits = {
        "transits": {"budhan": {"retrograde": True}},
        "sade_sati": {"active": True, "phase": "peak"},
    }
    q = ChatService._retrieval_query("വിവാഹം എപ്പോൾ?", transits, chart)
    # Every cue is a computed fact — the query pulls chunks for THIS chart.
    assert "budhan retrograde" in q
    assert "sade sati" in q
    assert "ചോതി" in q
    assert "തുലാം lagna" in q
    assert "shani mahadasha" in q
    assert "chovva dosha" in q
    assert "kala sarpa" not in q  # absent dosha adds no cue


def test_retrieval_query_degrades_without_chart():
    from app.modules.chat.service import ChatService

    q = ChatService._retrieval_query("hello", {"transits": {}}, None)
    assert q == "hello"


async def test_temple_question_grounds_reply_in_a_temple(client):
    # Explicit temple ask ("ക്ഷേത്രത്തിൽ" → remedy intent) with a career concern
    # ("ജോലി") and a district ("തിരുവനന്തപുരം"): step 3c must graft a suggestion
    # and tag it in grounded_in as "temple:<id>".
    _login_as("demo1")  # digits → the chart/location DB path runs (and degrades)
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo1",
                "messages": [
                    {
                        "role": "user",
                        "content": "ജോലി കിട്ടാൻ ഏത് ക്ഷേത്രത്തിൽ പോകണം? ഞാൻ തിരുവനന്തപുരം ആണ്.",
                    }
                ],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_safety_response"] is False
    temple_refs = [g for g in body["grounded_in"] if g.startswith("temple:")]
    assert (
        temple_refs
    ), f"expected a temple:<id> in grounded_in, got {body['grounded_in']}"


async def test_plain_question_suggests_no_temple(client):
    # No remedy intent and no classic concern+dosha pairing → step 3c stays
    # silent; temple suggestions must not spam ordinary questions.
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [{"role": "user", "content": "ഇന്ന് എന്റെ ദിവസം എങ്ങനെ?"}],
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    temple_refs = [g for g in body["grounded_in"] if g.startswith("temple:")]
    assert temple_refs == [], f"unexpected temple suggestions: {temple_refs}"


def test_detect_current_district_needs_first_person_residence_cue():
    # Deterministic capture of "where I live now" for the memory profile:
    # district name + first-person cue, so other people's places don't stick.
    from app.modules.chat.memory import _detect_current_district

    assert _detect_current_district("ഞാൻ തിരുവനന്തപുരം ആണ്") == "Thiruvananthapuram"
    assert _detect_current_district("I live in Kochi now") == "Ernakulam"
    assert _detect_current_district("njan thrissur aanu") == "Thrissur"  # Manglish
    # District present but it's the mother's place → not stored.
    assert _detect_current_district("എന്റെ അമ്മ കോഴിക്കോട് ആണ്") is None
    assert _detect_current_district("ഇന്ന് നല്ല ദിവസമാണോ?") is None


async def test_temple_guidance_falls_back_to_stored_district():
    # When the message names no place, the profile's stored district (current
    # residence from memory extraction) localizes the temple suggestion.
    from app.modules.chat.service import ChatService

    class _SpyTemples:
        def __init__(self):
            self.kwargs = None

        def detect_concern(self, text):
            return "career"

        def detect_district(self, text):
            return None

        def suggest(self, **kwargs):
            self.kwargs = kwargs
            return []

    spy = _SpyTemples()
    svc = ChatService(temples=spy)
    await svc._temple_guidance(
        "ഒരു വഴിപാട് പറയാമോ?", None, {}, None, "demo", stored_district="Kollam"
    )
    assert spy.kwargs["district"] == "Kollam"


async def test_swarna_prashnam_turn_grounds_in_prashnam(client):
    # A swarna pick rides the normal /chat/message flow: the engine computes
    # the question-moment chart + arudha rules, grounded_in records it.
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [
                    {"role": "user", "content": "എന്റെ പുതിയ സംരംഭം വിജയിക്കുമോ?"}
                ],
                "prashnam": {"mode": "swarna", "arudha_rasi_index": 4},
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_safety_response"] is False
    assert "prashnam:swarna" in body["grounded_in"]


async def test_thamboola_prashnam_requires_leaf_count(client):
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [{"role": "user", "content": "വിജയിക്കുമോ?"}],
                "prashnam": {"mode": "thamboola"},  # no leaf_count → 422
            },
        )
    assert resp.status_code == 422, resp.text


async def test_crisis_screen_still_wins_over_prashnam(client):
    # GUARDRAILS §2: the crisis screen runs FIRST even on a prashnam turn —
    # no chart, no reading, no astrology in the reply.
    async with client:
        resp = await client.post(
            "/chat/message",
            json={
                "user_id": "demo",
                "messages": [
                    {"role": "user", "content": "എനിക്ക് ജീവിക്കാൻ വയ്യ, ആത്മഹത്യ ചെയ്യണം"}
                ],
                "prashnam": {"mode": "thamboola", "leaf_count": 21},
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_safety_response"] is True
    assert body["grounded_in"] == []
    assert "പ്രശ്ന" not in body["reply"]


async def test_history_endpoint_returns_empty_when_mongo_disabled(client):
    # Mongo forced off (see _no_mongo): history persists nowhere and reads empty
    # (endpoint must degrade to [] rather than error).
    async with client:
        resp = await client.get("/chat/history/demo")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_memory_endpoint_404_when_no_profile(client):
    # Mongo forced off (see _no_mongo) → no profile → 404, not a 500.
    async with client:
        resp = await client.get("/chat/memory/demo")
    assert resp.status_code == 404, resp.text


def test_reply_screen_lexicons():
    # Output guardrail: normal astrology talk (doshas discussed with agency)
    # is clean; fear, payment-linked remedies, and urgency are flagged.
    from app.modules.tone_safety.service import ToneSafetyService

    svc = ToneSafetyService()
    clean = (
        "നിങ്ങളുടെ ജാതകത്തിൽ ചൊവ്വാ ദോഷം ഉണ്ട്, പക്ഷേ ഭയപ്പെടേണ്ടതില്ല — "
        "ഏഴര ശനിയുടെ കാലം ക്ഷമയോടെ കടന്നുപോകാം. ക്ഷേത്രദർശനം നിങ്ങൾക്ക് "
        "തിരഞ്ഞെടുക്കാവുന്ന ഒരു ഭക്തിമാർഗം മാത്രമാണ്. കൂടുതൽ അറിയണോ?"
    )
    assert svc.screen_reply(clean) == []

    assert svc.screen_reply("സൂക്ഷിക്കണം, നിങ്ങൾക്ക് വലിയ ആപത്ത് വരും!") == ["fear"]
    assert svc.screen_reply("You are cursed and doomed.") == ["fear"]
    assert svc.screen_reply("ഈ പൂജ ചെയ്യാൻ ₹5000 അടയ്ക്കണം, എങ്കിലേ ദോഷം മാറൂ.") == [
        "payment_remedy"
    ]
    assert svc.screen_reply("You must pay a fee for this homam.") == ["payment_remedy"]
    assert svc.screen_reply("ഉടനെ വഴിപാട് ചെയ്തില്ലെങ്കിൽ വലിയ നഷ്ടം ഉണ്ടാകും.") == [
        "payment_remedy",
        "urgency",
    ]
    assert svc.screen_reply("") == []


async def test_reply_guardrail_retries_once_then_falls_back():
    # A violating reply must NEVER reach the user: one corrective retry, and if
    # that also violates, the on-persona safe fallback is served.
    from app.modules.chat.service import ChatService
    from app.modules.tone_safety.reply_screen import SAFE_FALLBACK_REPLY

    class _BadThenGood:
        def __init__(self):
            self.calls = 0

        async def complete(self, system_prompt, messages, provider=None):
            self.calls += 1
            if self.calls == 1:
                return "സൂക്ഷിക്കണം! നിങ്ങൾക്ക് വലിയ ആപത്ത് വരും!"
            # The retry must have received the corrective instruction.
            assert "IMPORTANT CORRECTION" in system_prompt
            return "എല്ലാം ശാന്തമായി നോക്കാം. ക്ഷമ വിജയം തരും. കൂടുതൽ ചോദിക്കണോ?"

        def debug_meta(self):
            return {}

    llm = _BadThenGood()
    svc = ChatService(llm=llm)
    resp = await svc.handle_message("demo", [{"role": "user", "content": "എന്റെ ഭാവി?"}])
    assert llm.calls == 2
    assert "ആപത്ത്" not in resp.reply

    class _AlwaysBad:
        async def complete(self, system_prompt, messages, provider=None):
            return "ശാപം! ഉടനെ ചെയ്തില്ലെങ്കിൽ വലിയ ആപത്ത് വരും!"

        def debug_meta(self):
            return {}

    svc2 = ChatService(llm=_AlwaysBad())
    resp2 = await svc2.handle_message("demo", [{"role": "user", "content": "ഭാവി?"}])
    assert resp2.reply == SAFE_FALLBACK_REPLY


async def test_chat_requires_login(client):
    # Without a session token the chat API refuses — identity comes from the
    # token, never from the payload (week-1 security).
    from app.modules.identity.auth import require_user

    app.dependency_overrides.pop(require_user, None)  # drop the test login
    async with client:
        resp = await client.post(
            "/chat/message",
            json={"user_id": "demo", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401, resp.text
        history = await client.get("/chat/history/demo")
        assert history.status_code == 401, history.text


async def test_history_of_another_user_is_forbidden(client):
    # Logged in as "demo" but asking for someone else's transcript → 403.
    async with client:
        resp = await client.get("/chat/history/9999999999")
    assert resp.status_code == 403, resp.text
