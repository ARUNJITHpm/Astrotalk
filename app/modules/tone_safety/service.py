"""Public service for the tone_safety module.

Owns the Tara persona system prompt and the crisis/safety classifier that runs
BEFORE any astrology logic on every chat turn (AGENTS.md / GUARDRAILS.md §2).
This is the ONLY surface other modules may depend on.

Usage contract (GUARDRAILS.md §2 — must never be weakened for engagement):
    if tone_safety.screen(message):
        respond with tone_safety.crisis_reply()  # empathetic + helpline
        STOP — no astrology, no RAG, no upsell this turn
    else:
        proceed to the astrology pipeline

A request to loosen the crisis routing or the persona's no-fear rules is a
guardrail violation (GUARDRAILS.md §1/§2), not a feature — refuse it.
"""

from typing import Any

from app.modules.tone_safety import crisis_classifier, persona, reply_screen


class ToneSafetyService:
    def screen(self, message: str) -> bool:
        """Return True if the message shows acute distress. Runs FIRST, always."""
        return crisis_classifier.screen(message)

    def crisis_reply(self) -> str:
        """The empathetic, helpline-routed response. STOP after this — no astrology."""
        return persona.SAFETY_RESPONSE

    def screen_reply(self, reply: str) -> list[str]:
        """Violation categories in a GENERATED reply ([] = clean).

        The output-side guardrail (GUARDRAILS.md §1): fear-mongering,
        payment-linked remedies, manufactured urgency. Chat retries once with
        ``corrective_note()`` and falls back to ``safe_reply()`` if needed.
        """
        return reply_screen.screen_reply(reply)

    def corrective_note(self) -> str:
        """System-prompt addendum for the one corrective retry."""
        return reply_screen.CORRECTIVE_NOTE

    def safe_reply(self) -> str:
        """On-persona fallback when the retry still violates."""
        return reply_screen.SAFE_FALLBACK_REPLY

    def build_system_prompt(
        self,
        chart: Any | None = None,
        transits: Any | None = None,
        retrieved: Any | None = None,
        memory: Any | None = None,
    ) -> str:
        """Assemble the persona system prompt for the chat LLM call."""
        return persona.build_system_prompt(chart, transits, retrieved, memory)


# Module-level convenience surface (PROJECT_DOCS.md §6 references tone_safety.screen).
def screen(message: str) -> bool:
    return crisis_classifier.screen(message)


def build_system_prompt(
    chart: Any | None = None,
    transits: Any | None = None,
    retrieved: Any | None = None,
    memory: Any | None = None,
) -> str:
    return persona.build_system_prompt(chart, transits, retrieved, memory)
