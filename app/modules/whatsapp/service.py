"""Public service for the whatsapp module — compliant Channel broadcast + 1:1 cap.

This is the ONLY surface other modules may depend on (AGENTS.md).

HARD GUARDRAILS (GUARDRAILS.md §3 — enforced here, never weakened):
  - Every proactive message carries an AI disclosure + opt-out footer. We append
    it IN CODE, so it cannot be lost by a prompt forgetting it.
  - Business-initiated 1:1 sends are capped at MAX_WA_MESSAGES_PER_DAY per phone
    per 24h, enforced by a counter (see consent.WAMessageLog), not by hand.
  - Opt-in is required before any 1:1 send (see consent.is_opted_in).

This module deliberately exposes NO open-ended AI chat surface on WhatsApp, and
NO function that joins or adds a bot to a WhatsApp group. Those are prohibited
(GUARDRAILS.md §3) — do not add them.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp import consent
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# GUARDRAILS.md §3 hard cap; default 3, overridable per environment.
MAX_WA_MESSAGES_PER_DAY = int(os.getenv("MAX_WA_MESSAGES_PER_DAY", "3"))

# Appended to EVERY proactive message. AI disclosure + friction-free opt-out.
_AI_DISCLOSURE = "🤖 ഈ സന്ദേശം AI സഹായത്തോടെ തയ്യാറാക്കിയതാണ്."
_OPT_OUT = "ഈ സന്ദേശങ്ങൾ വേണ്ടെങ്കിൽ 'STOP' എന്ന് മറുപടി അയക്കൂ."
_FOOTER = f"\n\n{_AI_DISCLOSURE}\n{_OPT_OUT}"


def _with_footer(message: str) -> str:
    return f"{message}{_FOOTER}"


class WhatsappService:
    async def publish_to_channel(self, message: str) -> str:
        """Publish ONE message to the WhatsApp Channel, with the compliance footer
        appended automatically. Returns the composed message that was sent/logged.

        MOCK_WHATSAPP=true (default) logs instead of calling the BSP, so the daily
        pipeline runs with no credentials. The first live send needs human
        approval (AGENTS.md).
        """
        composed = _with_footer(message)
        if get_settings().mock_whatsapp:
            logger.info("whatsapp(mock): would publish to Channel:\n%s", composed)
            return composed
        return await self._send_via_bsp(composed)

    async def should_throttle(self, session: AsyncSession, phone: str) -> bool:
        """True if this phone has hit the 24h cap (for future 1:1 sends)."""
        count = await consent.sends_in_last_24h(session, phone)
        return count >= MAX_WA_MESSAGES_PER_DAY

    async def send_template(
        self, session: AsyncSession, phone: str, message: str
    ) -> bool:
        """One business-initiated 1:1 template send, guardrails enforced HERE:

          1. opt-in required (consent ledger) — else silently skipped;
          2. 24h cap respected — else silently skipped;
          3. AI disclosure + opt-out footer appended in code;
          4. the send is logged so the cap keeps counting.

        Returns True only when the message was actually sent (or mock-sent).
        Callers (festival notifications, booking confirmations) NEVER bypass
        this path (GUARDRAILS.md §3).
        """
        if not await consent.is_opted_in(session, phone):
            logger.info("whatsapp: skipped 1:1 send — no opt-in.")
            return False
        if await self.should_throttle(session, phone):
            logger.info("whatsapp: skipped 1:1 send — 24h cap reached.")
            return False
        composed = _with_footer(message)
        if get_settings().mock_whatsapp:
            logger.info("whatsapp(mock): would send 1:1 template:\n%s", composed)
        else:  # pragma: no cover - needs live BSP + human approval
            await self._send_via_bsp(composed)
        await consent.record_send(session, phone)
        return True

    async def _send_via_bsp(self, composed: str) -> str:  # pragma: no cover
        raise NotImplementedError(
            "Live WhatsApp send not wired. Set MOCK_WHATSAPP=false and implement "
            "the BSP call here — the FIRST live send requires human approval "
            "(AGENTS.md / GUARDRAILS.md §3)."
        )


# Module-level convenience surface.
async def publish_to_channel(message: str) -> str:
    return await WhatsappService().publish_to_channel(message)
