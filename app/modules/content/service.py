"""Public service for the content module.

Generates the daily Malayalam reading from a panchangam (PROJECT_DOCS.md §5).
This is the ONLY surface other modules may depend on (AGENTS.md).

Uses OpenAI gpt-4o-mini with the exact §5 system prompt; when the LLM is mocked
(MOCK_LLM env / mock_openai / no API key) it returns a calm, compliant fallback
template so the daily pipeline works with zero API key.
"""

import os

from app.modules.content import templates
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _should_mock() -> bool:
    settings = get_settings()
    env = os.getenv("MOCK_LLM")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    return settings.mock_openai or not settings.openai_api_key


class ContentService:
    async def generate_daily_message(self, panchangam: dict) -> str:
        """Draft ONE short Malayalam WhatsApp Channel message from the panchangam."""
        if _should_mock():
            logger.info("content: mock daily message (no live OpenAI call).")
            return templates.fallback_message(panchangam)

        from openai import AsyncOpenAI

        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.chat_model,
            max_tokens=300,
            messages=[
                {"role": "system", "content": templates.system_prompt()},
                {"role": "user", "content": templates.build_input(panchangam)},
            ],
        )
        return (response.choices[0].message.content or "").strip()


# Module-level convenience surface.
async def generate_daily_message(panchangam: dict) -> str:
    return await ContentService().generate_daily_message(panchangam)
