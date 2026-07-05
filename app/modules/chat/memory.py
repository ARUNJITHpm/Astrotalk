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
from app.modules.temples.service import TemplesService
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# First-person residence cues: a district name alone isn't enough ("എന്റെ അമ്മ
# കോഴിക്കോട് ആണ്" is about the mother), but combined with one of these the
# message is very likely about where the USER is. Detection is deterministic —
# no LLM — so the stored district is always a real Kerala district key.
_RESIDENCE_CUES = (
    "ഞാൻ", "താമസ", "എന്റെ വീട്", "ഇപ്പോൾ",
    "i live", "i am in", "i'm in", "i stay", "based in", "my home",
)

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
    return not settings.mock_openai and bool(
        settings.openai_api_key or settings.sarvam_api_key
    )


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


def _detect_current_district(text: str) -> str | None:
    """The user's current Kerala district, when the message states it.

    Requires BOTH a district name (temples' public detector, en/ml variants)
    and a first-person residence cue, to avoid storing places that belong to
    someone else in the conversation.
    """
    district = TemplesService.detect_district(text)
    if district is None:
        return None
    lower = text.lower()  # no-op for Malayalam, folds the English cues
    if any(cue in lower for cue in _RESIDENCE_CUES):
        return district
    return None


async def extract_memory(user_id: str, messages: list[dict[str, str]]) -> None:
    """Distil durable facts from a conversation and merge into the user's profile.

    No-op storage when Mongo is disabled/unavailable (upsert_facts handles that).
    """
    facts = await _distill(messages)
    district = _detect_current_district(_latest_user_text(messages))
    await user_memory.upsert_facts(user_id, facts, district=district)
    logger.info(
        "chat.memory: extraction ran for user=%s (%d fact(s)).", user_id, len(facts)
    )
