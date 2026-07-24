"""Tests for chat history (Postgres layer) + durable memory (MongoDB layer).

Chat history now persists in the ``chat_history`` SQL table. ``save_turn`` opens
its own session from the shared factory (background-task context), so these
tests point that factory at an in-memory SQLite DB. ``get_history`` takes the
caller's session directly. Durable memory still lives in Mongo, so those tests
keep the graceful-degradation (disabled → no-op) contract.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.platform.mongo as mongo_mod
from app.modules.chat import history, memory, user_memory
from app.modules.chat.models import ChatTurn  # noqa: F401  (registers the table)
from app.platform.db import Base


@pytest_asyncio.fixture
async def sql(monkeypatch):
    """In-memory SQLite factory; also patched in as history.save_turn's factory."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # save_turn opens its own session from this module-level factory.
    monkeypatch.setattr(history, "async_session_factory", factory)
    async with factory() as session:
        yield session
    await engine.dispose()


class _MockOffSettings:
    """Minimal stand-in: get_db() only reads `mock_mongo` on the disabled path."""

    mock_mongo = True


@pytest.fixture(autouse=True)
def _force_mongo_off(monkeypatch):
    # Reset the lazy client cache and force the mock branch so get_db() -> None,
    # independent of the environment's .env / any running mongod. Memory still
    # uses Mongo, so this keeps the memory tests hermetic.
    monkeypatch.setattr(mongo_mod, "get_settings", lambda: _MockOffSettings())
    monkeypatch.setattr(mongo_mod, "_initialized", False)
    monkeypatch.setattr(mongo_mod, "_db", None)
    monkeypatch.setattr(mongo_mod, "_client", None)
    monkeypatch.setattr("app.modules.chat.user_memory.get_db", lambda: None)


async def test_save_turn_then_get_history_roundtrips(sql):
    await history.save_turn(
        "demo",
        [{"role": "user", "content": "hi"}],
        "hello there",
        conversation_id="c1",
    )
    rows = await history.get_history(sql, "demo")
    assert len(rows) == 1
    assert rows[0]["reply"] == "hello there"
    assert rows[0]["conversation_id"] == "c1"
    assert rows[0]["messages"] == [{"role": "user", "content": "hi"}]


async def test_get_history_empty_for_unknown_user(sql):
    assert await history.get_history(sql, "nobody") == []


async def test_save_turn_stores_only_latest_user_turn(sql):
    # The client resends the whole transcript; only this turn's user input persists.
    await history.save_turn(
        "demo",
        [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply1"},
            {"role": "user", "content": "second"},
        ],
        "reply2",
    )
    rows = await history.get_history(sql, "demo")
    assert rows[0]["messages"] == [{"role": "user", "content": "second"}]


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
