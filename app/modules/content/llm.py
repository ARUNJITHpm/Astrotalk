"""LLM call for content generation (internal to the content module).

Mirrors the provider resolution of the chat module's client (sarvam →
openai → mock) without importing it — AGENTS.md forbids reaching into
another module's internals, and chat's client is tuned for conversation
(history, debug panel) while this one is a single-shot drafter.

Carries over the two Sarvam quirks learned in chat/evals:
  - reasoning_effort=low, or thinking eats the completion budget;
  - one retry with a doubled budget when the reply comes back empty.
"""

import os

from app.platform import metrics
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

_MAX_TOKENS = 700


def _forced_mock() -> bool:
    env = os.getenv("MOCK_LLM")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    return get_settings().mock_openai


def _resolve() -> tuple[str, str | None, str | None, str | None]:
    """(provider, api_key, base_url, model): sarvam first, openai fallback, mock."""
    if _forced_mock():
        return "mock", None, None, None
    s = get_settings()
    if s.sarvam_api_key:
        return "sarvam", s.sarvam_api_key, s.sarvam_base_url, s.sarvam_model
    if s.openai_api_key:
        return "openai", s.openai_api_key, None, s.chat_model
    return "mock", None, None, None


async def generate(system_prompt: str, user_input: str) -> str | None:
    """One drafting call. Returns None when mocked or empty after retry —
    the caller substitutes its platform-specific fallback template."""
    name, api_key, base_url, model = _resolve()
    if name == "mock":
        logger.info("content.llm: mock draft (no live provider call).")
        metrics.record_llm_usage("mock", None, None, mock=True)
        return None

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    payload = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    extra: dict = {}
    if name == "sarvam":
        extra["extra_body"] = {"reasoning_effort": "low"}

    async def call(max_tokens: int) -> str:
        response = await client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=payload, **extra
        )
        usage = getattr(response, "usage", None)
        metrics.record_llm_usage(name, model, usage.model_dump() if usage else None)
        return (response.choices[0].message.content or "").strip()

    draft = await call(_MAX_TOKENS)
    if not draft:
        logger.warning("content.llm: %s returned empty draft — retrying with doubled budget.", name)
        draft = await call(_MAX_TOKENS * 2)
    return draft or None
