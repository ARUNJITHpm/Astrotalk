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


# ---- Content Studio: on-demand creative pieces (ENGAGEMENT_PLAN.md Part B) ----
# Same hard rules as the daily pack; every draft still passes the tone_safety
# screen. Each prompt is a single-shot drafter — output is the script text only.

STUDIO_PROMPTS: dict[str, str] = {
    "reel_script": f"""\
You write a 45-60 second SPOKEN Malayalam script for an Instagram Reel /
YouTube Short for a calm, honest astrology app called Tara.
{_COMMON_RULES}
- Structure clearly: a HOOK (one line, ~3 seconds, a gentle question or
  surprise), a BODY (3-4 short speakable beats on the topic), and a CTA
  (invite the viewer to ask Tara). ~90-120 spoken words.
- Plain speakable lines only — no camera directions, no emoji, no headings.
TOPIC/CONTEXT: {{facts}}
OUTPUT: the script lines only.""",
    "weekly_astro_news": f"""\
You write a 3-5 minute SPOKEN Malayalam script for a WEEKLY astrology-news
video ("ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങൾ") for the Tara app.
{_COMMON_RULES}
- Warm host voice. Cover: the week's nakshatram highlights, any notable
  day, and one calming reflection for the week ahead. Informative, never
  fearful — no "bad days", only gentle guidance.
- Speakable paragraphs a host reads aloud. No stage directions, no emoji.
TOPIC/CONTEXT: {{facts}}
OUTPUT: the script lines only.""",
    "festival_special": f"""\
You write a warm SPOKEN Malayalam script (about 60-90 seconds) for a festival
special video for the Tara astrology app.
{_COMMON_RULES}
- Explain the festival's meaning and spirit, one simple way to observe it with
  a calm heart, and a warm blessing. Devotional and kind; promise nothing,
  threaten nothing.
- Speakable lines only — no stage directions, no emoji.
TOPIC/CONTEXT: {{facts}}
OUTPUT: the script lines only.""",
    "nakshatra_episode": f"""\
You write an evergreen SPOKEN Malayalam script (about 60-90 seconds) for a
"know your nakshatram" episode for the Tara astrology app.
{_COMMON_RULES}
- Describe the nakshatram's gentle qualities and strengths, one kind piece of
  everyday guidance for people born under it, and a warm closing. Traits as
  encouragement, never as fixed fate or warning.
- Speakable lines only — no stage directions, no emoji.
TOPIC/CONTEXT: {{facts}}
OUTPUT: the script lines only.""",
    "myth_buster": f"""\
You write a gentle SPOKEN Malayalam script (about 45-70 seconds) that calmly
CORRECTS a common fear-based astrology myth, for the Tara app. This is Tara's
signature "no fear" voice.
{_COMMON_RULES}
- Name the myth kindly (do NOT amplify the fear), explain the calmer truth,
  and reassure the viewer. The whole point is to REDUCE fear, never create it.
- Speakable lines only — no stage directions, no emoji.
TOPIC/CONTEXT: {{facts}}
OUTPUT: the script lines only.""",
}

# Per-kind Malayalam caption + hashtags for the manual post (deterministic, so
# it never needs the LLM and always stays compliant).
_STUDIO_HASHTAGS = {
    "reel_script": "#ജ്യോതിഷം #Tara #മലയാളം #പഞ്ചാംഗം",
    "weekly_astro_news": "#ജ്യോതിഷവാർത്ത #Tara #മലയാളം #ഈആഴ്ച",
    "festival_special": "#ഉത്സവം #Tara #മലയാളം #ജ്യോതിഷം",
    "nakshatra_episode": "#നക്ഷത്രം #Tara #മലയാളം #ജ്യോതിഷം",
    "myth_buster": "#ഭയമില്ലാജ്യോതിഷം #Tara #മലയാളം #സത്യം",
}


def studio_prompt(kind: str) -> str:
    """The studio prompt for a kind, with the app link resolved."""
    return STUDIO_PROMPTS[kind].replace("{app_link}", APP_LINK)


def build_studio_input(kind: str, topic: str, panchangam: dict, extra: str = "") -> str:
    """The CONTEXT line for a studio prompt: the owner's topic + grounding facts."""
    lines = [f"kind={kind}"]
    if topic:
        lines.append(f"topic={topic}")
    if panchangam:
        lines.append(build_input(panchangam))
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def studio_caption(kind: str, topic: str = "") -> str:
    """A ready-to-paste Malayalam caption + hashtags for the manual post."""
    lead = {
        "reel_script": "ഇന്നത്തെ ചിന്ത 🌸",
        "weekly_astro_news": "ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങൾ ✨",
        "festival_special": f"{topic or 'ഉത്സവം'} ആശംസകൾ 🪔",
        "nakshatra_episode": f"{topic or 'നിങ്ങളുടെ നക്ഷത്രം'} 🌟",
        "myth_buster": "ഭയപ്പെടേണ്ട — ശാന്തമായി അറിയാം 🕊️",
    }.get(kind, "Tara")
    hashtags = _STUDIO_HASHTAGS.get(kind, "#Tara #ജ്യോതിഷം")
    return f"{lead}\n\nകൂടുതൽ അറിയാൻ 👉 {APP_LINK}\n{hashtags}"


def studio_fallback(kind: str, topic: str, panchangam: dict) -> str:
    """Compliant grounded script per studio kind when the LLM is mocked/empty."""
    nakshatram = panchangam.get("nakshatram", "") if panchangam else ""
    subject = topic or nakshatram or "ഇന്നത്തെ ദിവസം"
    if kind == "weekly_astro_news":
        return (
            "എല്ലാവർക്കും സ്വാഗതം. ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങളിലേക്ക്.\n"
            f"ഈ ദിവസങ്ങളിൽ നക്ഷത്രം {nakshatram} പോലുള്ളവ കടന്നുപോകുന്നു.\n"
            "ഓരോ ദിവസവും ചെറിയ നന്മകൾ ചെയ്ത്, മനസ്സ് ശാന്തമായി സൂക്ഷിക്കാം.\n"
            "ഭയമല്ല, സൗമ്യമായ മാർഗനിർദേശമാണ് നമ്മുടെ വഴി.\n"
            "നിങ്ങളുടെ നക്ഷത്രത്തെക്കുറിച്ച് കൂടുതൽ അറിയാൻ താര ആപ്പിൽ ചോദിക്കൂ."
        )
    if kind == "myth_buster":
        return (
            f"'{subject}' എന്ന പേടി പലരും കേട്ടിട്ടുണ്ട്. പക്ഷേ പേടിക്കേണ്ട കാര്യമില്ല.\n"
            "ജ്യോതിഷം ഭയപ്പെടുത്താനുള്ളതല്ല — അത് ശാന്തമായ മാർഗനിർദേശമാണ്.\n"
            "ഏതൊരു ദിവസവും നല്ല മനസ്സോടെ തുടങ്ങിയാൽ അതു നല്ല ദിവസമാകും.\n"
            "സംശയങ്ങൾ ഉണ്ടെങ്കിൽ താരയോട് ശാന്തമായി ചോദിക്കൂ."
        )
    # reel_script / festival_special / nakshatra_episode share a calm structure.
    return (
        f"{subject} — ഒരു ചെറിയ ചിന്ത നിങ്ങൾക്കായി.\n"
        "ഇന്ന് സ്വയം ഒരു നല്ല വാക്ക് പറയൂ; മനസ്സിന് ശാന്തമായ ഒരു ശ്വാസം നൽകൂ.\n"
        "ഓരോ നക്ഷത്രത്തിനും അതിന്റേതായ നന്മകളുണ്ട് — അവയെ വിശ്വസിക്കൂ.\n"
        "നിങ്ങളുടെ നക്ഷത്രത്തെക്കുറിച്ച് കൂടുതൽ അറിയാൻ താരയോട് ചോദിക്കൂ."
    )


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
