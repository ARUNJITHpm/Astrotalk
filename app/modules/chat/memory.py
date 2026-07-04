"""Durable-memory extraction for the chat module (internal).

Runs AFTER the reply is returned (scheduled as a FastAPI BackgroundTask), so it
never blocks the user's response (PROJECT_DOCS.md §6). Distills durable facts
from the conversation and merges them into the user's memory profile
(user_memory), keyed by user_id and shared across all sessions.

When an OpenAI key is configured the LLM does the distillation; otherwise a
lightweight heuristic keeps a note of the latest message so the profile is still
real and demonstrable offline. Later this moves to a Celery task.

PRIVACY (GUARDRAILS.md §4): never log raw conversation content or birth data —
log only that extraction ran.
"""

import json
import os

from app.modules.chat import user_memory
from app.modules.chat.llm_client import LLMClient
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

_DISTILL_SYSTEM = (
    "You extract durable facts about the user from a chat, to help a companion "
    "remember them. Return ONLY a JSON array of short strings — lasting facts, "
    "preferences, relationships, or ongoing situations. No greetings, no chit-chat, "
    "no astrology output. Return [] if there is nothing durable."
)


def _latest_user_text(messages: list[dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return (msg.get("content") or "").strip()
    return ""


def _use_llm() -> bool:
    """Mirror LLMClient's mock decision so distillation matches the chat backend."""
    env = os.getenv("MOCK_LLM")
    if env is not None:
        return env.strip().lower() not in {"1", "true", "yes", "on"}
    settings = get_settings()
    return not settings.mock_openai and bool(settings.openai_api_key)


def _parse_facts(reply: str) -> list[dict] | None:
    try:
        data = json.loads(reply)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    return [{"text": str(item).strip(), "kind": "fact"} for item in data if str(item).strip()]


async def _distill(messages: list[dict[str, str]]) -> list[dict]:
    latest = _latest_user_text(messages)
    if not latest:
        return []
    if not _use_llm():
        # Offline fallback: keep the raw message as a note so memory is non-empty.
        return [{"text": latest, "kind": "note"}]
    try:
        reply = await LLMClient().complete(_DISTILL_SYSTEM, messages)
        facts = _parse_facts(reply)
        if facts is not None:
            return facts
    except Exception as exc:  # pragma: no cover - depends on live LLM
        logger.warning("chat.memory: LLM distillation failed (%s); using note.", exc)
    return [{"text": latest, "kind": "note"}]


async def extract_memory(user_id: str, messages: list[dict[str, str]]) -> None:
    """Distil durable facts from a conversation and merge into the user's profile.

    No-op storage when Mongo is disabled/unavailable (upsert_facts handles that).
    """
    facts = await _distill(messages)
    await user_memory.upsert_facts(user_id, facts)
    logger.info(
        "chat.memory: extraction ran for user=%s (%d fact(s)).", user_id, len(facts)
    )
