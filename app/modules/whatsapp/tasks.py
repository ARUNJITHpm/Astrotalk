"""Daily WhatsApp pipeline (PROJECT_DOCS.md §5).

Wires three public services: astrology_engine → content → whatsapp. Runs on a
schedule (see worker.py). The first live send requires human approval
(AGENTS.md / GUARDRAILS.md §3); until MOCK_WHATSAPP is turned off this only logs.
"""

from datetime import date

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.content.service import ContentService
from app.modules.whatsapp.service import WhatsappService
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


async def send_daily_message(day: date | None = None) -> str:
    """Generate and publish today's calm Malayalam Channel message.

    Returns the composed message (with the compliance footer) that was
    sent/logged, so callers can inspect it.
    """
    panchangam = await AstrologyEngineService().get_panchangam(day)
    message = await ContentService().generate_daily_message(panchangam)
    published = await WhatsappService().publish_to_channel(message)
    logger.info("whatsapp: daily message pipeline complete.")
    return published
