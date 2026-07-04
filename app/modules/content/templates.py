"""Daily-message templates for the content module (internal).

Holds the exact generation prompt from PROJECT_DOCS.md §5 and a compliant
fallback used when the LLM is mocked. All copy follows GUARDRAILS.md §1: warm,
no doom, no remedies/payments, no urgency.
"""

import os

# The in-app deep-link shown as the soft CTA. Overridable per environment.
APP_LINK = os.getenv("TARA_APP_LINK", "https://tara.app/chat")

# Exact system prompt from PROJECT_DOCS.md §5. {app_link} is filled before the call.
DAILY_SYSTEM_PROMPT = """\
You write ONE short Malayalam WhatsApp Channel message for an astrology app.
Tone: warm, calm, like a kind elder. STRICT RULES:
- Max ~45 words. One useful fact + one gentle thought + one soft CTA.
- NEVER predict doom, never mention remedies/payments, never create urgency.
- End with: "സ്വകാര്യമായി ചോദിക്കണോ? 👉 {app_link}"
INPUT: nakshatram={nakshatram}, nalla_neram={nalla_neram}, date={date}
OUTPUT: the message text only."""

# The soft CTA, kept as a constant so the fallback and the prompt agree.
CTA = f"സ്വകാര്യമായി ചോദിക്കണോ? 👉 {APP_LINK}"


def build_input(panchangam: dict) -> str:
    """Render the INPUT line for the LLM from a panchangam dict."""
    return (
        f"nakshatram={panchangam.get('nakshatram', '')}, "
        f"nalla_neram={panchangam.get('nalla_neram', '')}, "
        f"date={panchangam.get('date', '')}"
    )


def system_prompt() -> str:
    """The §5 system prompt with the real app link substituted in."""
    return DAILY_SYSTEM_PROMPT.replace("{app_link}", APP_LINK)


def fallback_message(panchangam: dict) -> str:
    """A calm, compliant daily message used when the LLM is mocked.

    One fact (today's nakshatram + auspicious window), one gentle thought, one
    soft CTA. Stays within ~45 words; no doom, no remedies, no urgency.
    """
    nakshatram = panchangam.get("nakshatram", "")
    nalla_neram = panchangam.get("nalla_neram", "")
    return (
        f"ഇന്നത്തെ നക്ഷത്രം {nakshatram}. നല്ല നേരം {nalla_neram}. "
        "ഇന്ന് സ്വയം ഒരു ചെറിയ നന്മ ചെയ്യാൻ അൽപ്പം സമയം കണ്ടെത്തൂ — "
        "മനസ്സിന് ശാന്തമായ ഒരു ശ്വാസം നൽകൂ. "
        f"{CTA}"
    )
