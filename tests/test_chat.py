"""Integration-style tests for the chat orchestrator (PROJECT_DOCS.md §6).

Drives the real HTTP endpoint via httpx ASGITransport. MOCK_LLM / mock_openai is
on by default, so no API key is needed.

These tests are hermetic w.r.t. the document store: the `_no_mongo` fixture forces
the Mongo layer to "disabled" regardless of the local `.env` (which may point at a
real mongod), so history/memory behaviour is deterministic on any machine.
"""

import httpx
import pytest
from httpx import ASGITransport

from app.main import app

# Astrology terms that must NEVER appear in a crisis safety response (GUARDRAILS §2).
_ASTROLOGY_TERMS = ("ജാതക", "നക്ഷത്ര", "രാശി", "ഗ്രഹ", "dosha", "horoscope", "transit")


@pytest.fixture(autouse=True)
def _no_mongo(monkeypatch):
    """Pin the document store off so tests don't depend on a local mongod / .env.

    history.py and user_memory.py each do `from app.platform.mongo import get_db`,
    so we patch their bound names to return None — exactly the "Mongo unavailable"
    path the code already degrades through.
    """
    monkeypatch.setattr("app.modules.chat.history.get_db", lambda: None)
    monkeypatch.setattr("app.modules.chat.user_memory.get_db", lambda: None)


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


def test_select_varga_maps_topics_to_divisional_charts():
    from app.modules.chat.service import ChatService

    pick = ChatService._select_varga
    assert pick("എനിക്ക് ജോലി മാറ്റം വരുമോ?") == "D10"        # career → dashamsa
    assert pick("When will I get a promotion at work?") == "D10"
    assert pick("വിവാഹം എപ്പോൾ നടക്കും?") == "D9"             # marriage → navamsa
    assert pick("Is my relationship going to last?") == "D9"
    assert pick("കുട്ടികൾ ഉണ്ടാകുമോ?") == "D7"                 # children → saptamsa
    assert pick("എന്റെ അമ്മയുടെ ആരോഗ്യം?") == "D12"           # parents → dwadasamsa
    assert pick("hello, how are you?") is None                  # no topic → D1 only


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
