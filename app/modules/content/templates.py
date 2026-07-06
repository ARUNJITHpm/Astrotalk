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


# ---- Per-platform prompts for the daily content pack (GROWTH_PLAN.md Part 1) ----
# Every prompt repeats the §5 hard rules (no doom, no remedies/payments, no
# urgency) because generated output is public-facing; the tone_safety reply
# screen still runs on every draft as the enforcement backstop.

_COMMON_RULES = """\
STRICT RULES (never break these):
- Warm, calm Malayalam — like a kind elder. Simple words.
- NEVER predict doom, never mention remedies/payments, never create urgency.
- Ground every claim in the INPUT facts; invent nothing."""

PLATFORM_PROMPTS: dict[str, str] = {
    "wa_channel": DAILY_SYSTEM_PROMPT,  # the original §5 prompt
    "fb_post": f"""\
You write ONE Malayalam Facebook post for an astrology app's page.
{_COMMON_RULES}
- 80–120 words: today's panchangam facts, one thought about the day's
  nakshatram, one gentle actionable tip anyone can do today.
- End with: "കൂടുതൽ അറിയാൻ 👉 {{app_link}}" then 2–3 relevant Malayalam hashtags.
INPUT: {{facts}}
OUTPUT: the post text only.""",
    "ig_reel": f"""\
You write a 30-second SPOKEN Malayalam script for an Instagram Reel for an
astrology app. It will be read aloud over a calm background.
{_COMMON_RULES}
- Structure: one hook line (a question or gentle surprise), three short
  spoken beats about today (nakshatram, nalla neram, one tip), one closing
  line inviting viewers to the app. ~60-70 spoken words total.
- Plain lines of speakable text only — no camera directions, no emoji.
INPUT: {{facts}}
OUTPUT: the script lines only.""",
    "yt_short": f"""\
You write a 30-40 second SPOKEN Malayalam script for a YouTube Short for an
astrology app.
{_COMMON_RULES}
- Structure: hook, today's panchangam in two sentences, one thought for
  people born under today's nakshatram, one closing invite to the app.
- Plain speakable lines only — no stage directions, no emoji.
INPUT: {{facts}}
OUTPUT: the script lines only.""",
}


def build_platform_input(panchangam: dict, nugget: str = "") -> str:
    """The INPUT facts line shared by every platform prompt."""
    facts = build_input(panchangam)
    tithi = panchangam.get("tithi", "")
    if tithi:
        facts += f", tithi={tithi}"
    if nugget:
        facts += f"\nknowledge_note: {nugget}"
    return facts


def platform_prompt(platform: str) -> str:
    """The platform's system prompt with the app link resolved."""
    return PLATFORM_PROMPTS[platform].replace("{app_link}", APP_LINK)


def platform_fallback(platform: str, panchangam: dict) -> str:
    """Compliant grounded copy per platform when the LLM is mocked/empty."""
    nakshatram = panchangam.get("nakshatram", "")
    nalla_neram = panchangam.get("nalla_neram", "")
    day = panchangam.get("date", "")
    if platform == "wa_channel":
        return fallback_message(panchangam)
    if platform == "fb_post":
        return (
            f"ഇന്ന് ({day}) നക്ഷത്രം {nakshatram}; നല്ല നേരം {nalla_neram}. "
            "പുതിയ കാര്യങ്ങൾ പതിയെ തുടങ്ങാൻ നല്ല ദിവസം. "
            "ഇന്ന് ഒരാളോട് ഒരു നല്ല വാക്ക് പറയൂ — അതാണ് ഏറ്റവും വലിയ വഴിപാട്. "
            f"കൂടുതൽ അറിയാൻ 👉 {APP_LINK}\n"
            "#ജ്യോതിഷം #പഞ്ചാംഗം #മലയാളം"
        )
    # Spoken scripts (ig_reel / yt_short) share one calm structure.
    return (
        f"ഇന്നത്തെ നക്ഷത്രം ഏതാണെന്ന് അറിയാമോ? {nakshatram}.\n"
        f"നല്ല നേരം {nalla_neram} — പ്രധാന കാര്യങ്ങൾ അപ്പോൾ ചെയ്യാം.\n"
        "മനസ്സ് ശാന്തമാക്കി ഒരു ചെറിയ നന്മയോടെ ദിവസം തുടങ്ങൂ.\n"
        "നിങ്ങളുടെ നക്ഷത്രത്തെക്കുറിച്ച് കൂടുതൽ അറിയാൻ താര ആപ്പിൽ വരൂ."
    )
