"""LLM client for the chat module (internal).

Two real providers behind one OpenAI-compatible client:
  - "sarvam"  — Sarvam AI (Malayalam/Indic-first; settings.sarvam_*). DEFAULT.
  - "openai"  — OpenAI (settings.openai_api_key + chat_model).

The UI may request a provider per message; a provider with no key falls back
to the other, then to a canned mock reply so the app always answers offline.

Mock decision (the platform config flag is `mock_openai`; the task refers to it
as MOCK_LLM). We honor an explicit `MOCK_LLM` env var if set, else fall back to
`settings.mock_openai`, else to "no API key at all". Default config mocks, so
this works offline out of the box.
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

# Per-provider completion budget. Sarvam models write long-form Malayalam and
# truncate mid-sentence at 1024 (seen live); give them the API's own default.
_MAX_TOKENS = {"sarvam": 2048, "sarvam-fast": 2048, "openai": 1024}
_DEFAULT_MAX_TOKENS = 1024

# "sarvam-fast" is the same account/endpoint with the lower-latency 30B model.
PROVIDERS = ("sarvam", "sarvam-fast", "openai")


class LLMClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        # Last LIVE call's resolution + token usage (None when mocked/never
        # called). Surfaced by the developer debug panel.
        self.last_usage: dict | None = None
        self.last_provider: str | None = None
        self.last_model: str | None = None

    def _forced_mock(self) -> bool:
        env = os.getenv("MOCK_LLM")
        if env is not None:
            return env.strip().lower() in {"1", "true", "yes", "on"}
        return self._settings.mock_openai

    def _resolve(
        self, requested: str | None = None
    ) -> tuple[str, str | None, str | None, str | None]:
        """(provider, api_key, base_url, model) for this call.

        Order: the requested provider (or the configured default), then the
        other real provider if the first has no key, then the mock. A bad
        `requested` value is treated as "use the default", not an error.
        """
        if self._forced_mock():
            return "mock", None, None, None
        s = self._settings
        creds = {
            "sarvam": (s.sarvam_api_key, s.sarvam_base_url, s.sarvam_model),
            "sarvam-fast": (s.sarvam_api_key, s.sarvam_base_url, s.sarvam_fast_model),
            "openai": (s.openai_api_key, None, s.chat_model),
        }
        first = requested if requested in PROVIDERS else s.chat_provider
        if first not in PROVIDERS:
            first = "sarvam"
        # Fallback chain: the pick, then the flagship providers in order.
        for name in dict.fromkeys((first, "sarvam", "openai")):
            key, base_url, model = creds[name]
            if key:
                return name, key, base_url, model
        return "mock", None, None, None

    def debug_meta(self) -> dict:
        """Config snapshot for the debug panel — how the LLM step is wired.

        No secrets: reports only whether keys are present, never the keys.
        """
        provider, _key, _url, model = self._resolve(self.last_provider)
        return {
            "mocked": provider == "mock",
            "provider": self.last_provider or provider,
            "model": self.last_model or model,
            "max_tokens": _MAX_TOKENS.get(
                self.last_provider or provider, _DEFAULT_MAX_TOKENS
            ),
            "api_key_set": bool(
                self._settings.openai_api_key or self._settings.sarvam_api_key
            ),
            "usage": self.last_usage,
        }

    async def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        provider: str | None = None,
    ) -> str:
        """Return the assistant reply for `system_prompt` + conversation history.

        ``provider`` optionally picks "sarvam" or "openai" for this call; the
        default is settings.chat_provider (with key-based fallback).
        """
        name, api_key, base_url, model = self._resolve(provider)
        if name == "mock":
            logger.info("chat.llm: mock reply (no live provider call).")
            self.last_usage = None
            self.last_provider, self.last_model = "mock", None
            return _MOCK_REPLY_ML

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        payload = [{"role": "system", "content": system_prompt}, *messages]
        extra: dict = {}
        if name.startswith("sarvam"):
            # Sarvam models reason before answering (default effort "medium");
            # the thinking eats the completion budget and truncates long
            # Malayalam replies mid-sentence (seen in evals). Chat is
            # conversational — low effort is faster and leaves room to speak.
            extra["extra_body"] = {"reasoning_effort": "low"}
        response = await client.chat.completions.create(
            model=model,
            max_tokens=_MAX_TOKENS.get(name, _DEFAULT_MAX_TOKENS),
            messages=payload,
            **extra,
        )
        # Capture what actually served the reply for the debug panel.
        self.last_provider, self.last_model = name, model
        self.last_usage = response.usage.model_dump() if response.usage else None
        return response.choices[0].message.content or ""
