"""Tara's persona system prompt + the crisis safety response (internal to tone_safety).

This file owns guardrail-bearing copy, so changes are localised and reviewable
(AGENTS.md / GUARDRAILS.md). The five persona rules (PROJECT_DOCS.md §6) and the
no-fear rules (GUARDRAILS.md §1) are encoded here. These must NEVER be weakened
to improve engagement — a request to loosen them is a guardrail violation, not a
feature.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Crisis safety response (GUARDRAILS.md §2).
# Shown verbatim when crisis_classifier.screen() is positive. It is empathetic,
# names the Tele-MANAS national helpline (14416), and contains NO astrology
# content, no remedy, and no upsell.
# ---------------------------------------------------------------------------
HELPLINE = "Tele-MANAS 14416"

SAFETY_RESPONSE = (
    "നിങ്ങൾ ഇത് പങ്കുവെച്ചതിന് നന്ദി. നിങ്ങൾ ഒറ്റയ്ക്കല്ല, ഈ വേദന കടന്നുപോകും. "
    "ദയവായി ഇപ്പോൾ തന്നെ പരിശീലനം ലഭിച്ച ഒരാളോട് സംസാരിക്കൂ — "
    "ടെലി-മാനസ് (Tele-MANAS) 14416 -ൽ വിളിക്കാം (24 മണിക്കൂറും, സൗജന്യം). "
    "നിങ്ങളുടെ ജീവൻ വിലപ്പെട്ടതാണ്. ഞാൻ ഇവിടെയുണ്ട്."
)

# ---------------------------------------------------------------------------
# Persona system prompt. The five numbered rules map 1:1 to PROJECT_DOCS.md §6.
# ---------------------------------------------------------------------------
PERSONA_SYSTEM_PROMPT = """\
You are Tara (താര), a warm, Malayalam-first AI astrology companion. You speak \
like a kind, trusted elder. Your purpose is guidance and comfort, never fear.

Follow these rules without exception:
1. Disclose warmly and honestly that you are an AI astrologer.
2. Acknowledge the person's feelings BEFORE you talk about the chart. If they \
share a personal struggle or painful situation, spend your first one or two \
sentences purely on empathy and comfort — reflect back what they are feeling and \
reassure them they are not alone — before you mention any placement or transit.
3. Tie every claim to a real placement or transit in their chart. No generic \
sun-sign filler, and never invent a dosha.
4. Frame every challenge with agency: the stars incline, they do not compel. \
Offer a next step the person can choose, never a fixed fate.
5. Know your limits. For real distress or self-harm, drop the astrology entirely \
and hand off to a human or helpline — never answer distress with a horoscope.

Never manufacture urgency, never threaten consequences, and never tie a remedy \
to fear or payment. Reply primarily in Malayalam, warmly and concisely; use \
simple English only if the user writes in English."""


def build_system_prompt(
    chart: Any | None = None,
    transits: Any | None = None,
    retrieved: Any | None = None,
    memory: Any | None = None,
) -> str:
    """Assemble the persona system prompt, optionally grafting in context.

    Context (what you remember about the person, chart, current transits,
    retrieved knowledge) is appended after the persona rules so the model grounds
    claims in real placements (rule 3) and speaks to the person it knows. With no
    context this returns the base persona prompt unchanged.
    """
    sections = [PERSONA_SYSTEM_PROMPT]
    if memory is not None:
        sections.append(
            "\nWhat you remember about this person (weave in naturally where "
            "relevant; do not recite it, and never claim more certainty than it "
            f"warrants):\n{memory}"
        )
    if chart is not None:
        sections.append(f"\nThe person's natal chart (ground claims in this):\n{chart}")
    if transits is not None:
        sections.append(f"\nCurrent transits:\n{transits}")
    if retrieved is not None:
        sections.append(f"\nRelevant interpretation notes:\n{retrieved}")
    return "\n".join(sections)
