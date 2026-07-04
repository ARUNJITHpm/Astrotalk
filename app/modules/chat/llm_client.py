"""LLM client for the chat module (internal).

Wraps OpenAI gpt-4o-mini. When mocked, returns a realistic canned Malayalam
reply so the orchestrator works end-to-end with no API key. Swapping providers
stays inside this file.

Mock decision (the platform config flag is `mock_openai`; the task refers to it
as MOCK_LLM). We honor an explicit `MOCK_LLM` env var if set, else fall back to
`settings.mock_openai`, else to "no API key". Default config mocks, so this works
offline out of the box. We do not add a new platform env var (app/platform is a
different ownership domain).
"""

import os

from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Warm, grounded-feeling, no-fear canned reply (GUARDRAILS §1). Acknowledges the
# feeling first, frames with agency, discloses it's an AI. Used when mocked.
_MOCK_REPLY_ML = (
    "നമസ്കാരം 🙏 ഞാൻ താര, നിങ്ങളുടെ AI ജ്യോതിഷ കൂട്ടുകാരി. "
    "നിങ്ങൾ പങ്കുവെച്ച കാര്യം ഞാൻ ശ്രദ്ധയോടെ കേട്ടു — ആ വികാരം സ്വാഭാവികമാണ്. "
    "നിങ്ങളുടെ ജാതകത്തിലെ ഇപ്പോഴത്തെ ഗ്രഹസ്ഥിതി നോക്കുമ്പോൾ, ഇത് "
    "ക്ഷമയോടെ ഓരോ ചുവടും വെക്കാനുള്ള സമയമാണെന്ന് തോന്നുന്നു. "
    "നക്ഷത്രങ്ങൾ വഴികാട്ടുന്നു, അവ നിർബന്ധിക്കുന്നില്ല — തിരഞ്ഞെടുപ്പ് "
    "എപ്പോഴും നിങ്ങളുടേതാണ്. കൂടുതൽ പറയാമോ, എന്താണ് മനസ്സിൽ?"
)


_MAX_TOKENS = 1024


class LLMClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        # Token usage from the most recent LIVE call (None when mocked/never called).
        # Surfaced by the developer debug panel.
        self.last_usage: dict | None = None

    def _should_mock(self) -> bool:
        env = os.getenv("MOCK_LLM")
        if env is not None:
            return env.strip().lower() in {"1", "true", "yes", "on"}
        return self._settings.mock_openai or not self._settings.openai_api_key

    def debug_meta(self) -> dict:
        """Config snapshot for the debug panel — how the LLM step is wired.

        No secrets: reports only whether a key is present, never the key itself.
        """
        mocked = self._should_mock()
        return {
            "mocked": mocked,
            "provider": "mock" if mocked else "openai",
            "model": None if mocked else self._settings.chat_model,
            "max_tokens": _MAX_TOKENS,
            "api_key_set": bool(self._settings.openai_api_key),
            "usage": self.last_usage,
        }

    async def complete(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Return the assistant reply for `system_prompt` + conversation history."""
        if self._should_mock():
            logger.info("chat.llm: mock reply (no live OpenAI call).")
            self.last_usage = None
            return _MOCK_REPLY_ML

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        payload = [{"role": "system", "content": system_prompt}, *messages]
        response = await client.chat.completions.create(
            model=self._settings.chat_model,
            max_tokens=_MAX_TOKENS,
            messages=payload,
        )
        # Capture token usage so the debug panel can show real API cost signals.
        self.last_usage = response.usage.model_dump() if response.usage else None
        return response.choices[0].message.content or ""
