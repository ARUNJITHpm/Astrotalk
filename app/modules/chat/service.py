"""Public service for the chat module — the AI astrologer orchestrator.

Request flow (Tara-Project-Documentation.md §6):
  tone_safety.screen()  → distress? helpline + STOP
  else                  → persona system prompt → stream OpenAI reply

This is the ONLY surface other modules may depend on (AGENTS.md).
"""

from collections.abc import AsyncIterator

from app.modules.tone_safety.service import ToneSafetyService
from app.platform.config import get_settings

# A calm demo reply streamed when no OPENAI_API_KEY is configured, so the UI
# works end-to-end out of the box.
_DEMO_REPLY_ML = (
    "നമസ്കാരം 🙏 ഞാൻ താര, നിങ്ങളുടെ AI ജ്യോതിഷ കൂട്ടുകാരി. "
    "(ഇത് ഒരു demo മറുപടിയാണ് — യഥാർത്ഥ മറുപടികൾക്ക് OPENAI_API_KEY "
    "സജ്ജമാക്കൂ.) ഇന്ന് നിങ്ങളുടെ മനസ്സിൽ എന്താണ്?"
)


class ChatService:
    def __init__(self, tone_safety: ToneSafetyService | None = None) -> None:
        self._tone_safety = tone_safety or ToneSafetyService()

    async def stream_reply(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Yield the assistant reply token-by-token.

        `messages` is the full conversation history: [{"role", "content"}, ...].
        """
        latest = messages[-1]["content"] if messages else ""

        # GUARDRAIL 2: crisis screen runs FIRST, before any astrology logic.
        if self._tone_safety.screen(latest):
            yield self._tone_safety.crisis_reply()
            return

        settings = get_settings()
        if not settings.openai_api_key:
            yield _DEMO_REPLY_ML
            return

        async for chunk in self._stream_from_openai(settings, messages):
            yield chunk

    async def _stream_from_openai(
        self, settings, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        system_prompt = self._tone_safety.build_system_prompt()

        # OpenAI takes the system prompt as the first message in the list.
        payload = [{"role": "system", "content": system_prompt}, *messages]

        stream = await client.chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=payload,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
