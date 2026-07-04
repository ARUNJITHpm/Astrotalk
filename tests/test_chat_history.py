"""Tests for chat history + durable memory persistence (MongoDB layer).

These verify the graceful-degradation contract: when the document store is
unavailable, get_db() returns None and every persistence call must degrade to a
safe no-op. The `_force_mongo_off` fixture pins that "disabled" state regardless
of the local `.env` (which may point at a real mongod), so the suite is hermetic.
"""

import pytest

import app.platform.mongo as mongo_mod
from app.modules.chat import history, memory, user_memory
from app.platform.mongo import get_db


class _MockOffSettings:
    """Minimal stand-in: get_db() only reads `mock_mongo` on the disabled path."""

    mock_mongo = True


@pytest.fixture(autouse=True)
def _force_mongo_off(monkeypatch):
    # Reset the lazy client cache and force the mock branch so get_db() -> None,
    # independent of the environment's .env / any running mongod.
    monkeypatch.setattr(mongo_mod, "get_settings", lambda: _MockOffSettings())
    monkeypatch.setattr(mongo_mod, "_initialized", False)
    monkeypatch.setattr(mongo_mod, "_db", None)
    monkeypatch.setattr(mongo_mod, "_client", None)
    # history.py / user_memory.py bound `get_db` at import — point them at None too.
    monkeypatch.setattr("app.modules.chat.history.get_db", lambda: None)
    monkeypatch.setattr("app.modules.chat.user_memory.get_db", lambda: None)


def test_mongo_disabled_by_default():
    # With the disabled/mock branch forced, there is no live document store.
    assert get_db() is None


async def test_save_turn_is_noop_when_disabled():
    # Must not raise even though no Mongo is available.
    await history.save_turn("demo", [{"role": "user", "content": "hi"}], "hello")


async def test_get_history_returns_empty_when_disabled():
    assert await history.get_history("demo") == []


async def test_extract_memory_is_noop_when_disabled():
    await memory.extract_memory("demo", [{"role": "user", "content": "hi"}])


async def test_get_profile_none_when_disabled():
    assert await user_memory.get_profile("demo") is None


async def test_upsert_facts_is_noop_when_disabled():
    await user_memory.upsert_facts("demo", [{"text": "likes tea", "kind": "fact"}])


def test_format_for_prompt_renders_summary_and_facts():
    profile = {
        "summary": "Cautious about a job change.",
        "facts": [{"text": "married"}, {"text": "one child"}],
    }
    out = user_memory.format_for_prompt(profile)
    assert "Cautious about a job change." in out
    assert "- married" in out
    assert "- one child" in out


def test_format_for_prompt_none_for_empty():
    assert user_memory.format_for_prompt(None) is None
    assert user_memory.format_for_prompt({}) is None
