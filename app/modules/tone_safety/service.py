"""Public service for the tone_safety module.

Owns the Tara persona system prompt and the crisis/safety classifier that runs
BEFORE any astrology logic on every chat turn (AGENTS.md / GUARDRAILS.md).
This is the ONLY surface other modules may depend on.
"""

# Tele-MANAS national mental-health helpline (GUARDRAILS.md rule 2).
HELPLINE = "Tele-MANAS: 14416"

# Minimal keyword screen for acute distress. A real deployment replaces this
# with an LLM classifier — but the rule (screen first, route to a human, stop)
# is what matters and must never be weakened or bypassed.
_DISTRESS_MARKERS = (
    "suicide",
    "kill myself",
    "end my life",
    "want to die",
    "self harm",
    "self-harm",
    "ആത്മഹത്യ",  # aatmahatya — "suicide"
    "ജീവനൊടുക്ക",  # "to end one's life"
)

# Warm response shown when distress is detected. No astrology, no upsell.
CRISIS_REPLY_ML = (
    "നിങ്ങൾ ഇത് പങ്കുവെച്ചതിന് നന്ദി. നിങ്ങൾ ഒറ്റയ്ക്കല്ല. "
    "ദയവായി ഇപ്പോൾ തന്നെ ഒരാളോട് സംസാരിക്കൂ — "
    f"{HELPLINE} (24x7, സൗജന്യം). "
    "ഞാൻ ഇവിടെയുണ്ട്."
)

# The Tara persona. Owned here so guardrail changes are localized (GUARDRAILS.md).
PERSONA_SYSTEM_PROMPT = """\
You are Tara (താര), a warm Malayalam-first AI astrology companion. You speak \
like a kind, trusted elder. Your purpose is guidance and comfort, never fear.

Absolute rules:
- Disclose warmly that you are an AI astrologer.
- Acknowledge the person's feelings BEFORE talking about the chart.
- Never invent a dosha, never threaten consequences, never manufacture urgency, \
never tie remedies to fear or payment.
- Frame challenges with agency: "the stars incline, they don't compel."
- Reply primarily in Malayalam, warmly and concisely. Use simple English only \
if the user writes in English.
- Know your limits: for real distress, hand off to a human/helpline, never a \
horoscope."""


class ToneSafetyService:
    def screen(self, message: str) -> bool:
        """Return True if the message shows acute distress. Runs FIRST, always."""
        lowered = message.lower()
        return any(marker in lowered for marker in _DISTRESS_MARKERS)

    def crisis_reply(self) -> str:
        """The empathetic, helpline-routed response. STOP after this — no astrology."""
        return CRISIS_REPLY_ML

    def build_system_prompt(self) -> str:
        """Assemble the persona system prompt for the chat LLM call."""
        # TODO(tone_safety): graft in chart + transits + retrieved knowledge (docs §6).
        return PERSONA_SYSTEM_PROMPT
