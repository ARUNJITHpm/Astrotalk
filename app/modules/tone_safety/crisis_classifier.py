"""Crisis / self-harm screen (internal to tone_safety).

⚠️ PLACEHOLDER HEURISTIC — NOT PRODUCTION-READY. ⚠️
This is a short, pattern-level keyword screen. It WILL miss real distress phrased
in ways not listed here, and it has no understanding of context, negation, or
intent. It MUST be replaced by a reviewed classifier (e.g. an LLM-based or
clinically-reviewed model, evaluated for recall on real Malayalam + English
distress language) BEFORE any real launch.

What is NOT a placeholder, and must NEVER be weakened (GUARDRAILS.md §2):
the ROUTING RULE — screen() runs first on every chat turn; a positive signal
means the caller responds with the safety message and STOPS. No astrology, no
RAG, no upsell on that turn. Improving the word list is welcome; removing or
deprioritising the rule is not.

Design note (precision vs. recall): markers target *explicit self-harm intent*.
We deliberately do NOT flag bare "death"/"die"/"മരണം", because legitimate
astrology questions discuss the 8th house, longevity, ancestors, etc. — flagging
those would break innocent chart questions. A real classifier is needed to catch
the implicit distress this list cannot.
"""

# English markers — explicit self-harm / suicidal intent (phrase-level).
_MARKERS_EN = (
    "suicide",
    "kill myself",
    "killing myself",
    "end my life",
    "ending my life",
    "want to die",
    "don't want to live",
    "dont want to live",
    "no reason to live",
    "no point in living",
    "self harm",
    "self-harm",
    "hurt myself",
    "harm myself",
    "better off dead",
)

# Malayalam markers — explicit self-harm / suicidal intent.
_MARKERS_ML = (
    "ആത്മഹത്യ",        # aatmahatya — "suicide"
    "ജീവനൊടുക്ക",      # "to end one's life"
    "ജീവിക്കാൻ വയ്യ",  # "cannot go on living"
    "മരിക്കണം",         # "want to die"
    "ചാകണം",            # "want to die" (colloquial)
    "ജീവിതം അവസാനിപ്പിക്ക",  # "end (my) life"
    "സ്വയം ഉപദ്രവിക്ക",       # "hurt myself"
    "സ്വയം മുറിവേൽപ്പിക്ക",   # "injure myself"
)

# Manglish (romanized Malayalam) markers — Tara's users often type Malayalam
# in Latin script; the Malayalam-script markers above never match those.
# Spellings vary, so common variants are listed explicitly.
_MARKERS_MANGLISH = (
    "aathmahathya",
    "athmahathya",
    "atmahathya",
    "jeevikkan vayya",
    "jeevikan vayya",
    "jeevikkan pattilla",
    "marikkanam",
    "marikanam",
    "chakanam",
    "chaakanam",
    "jeevanodukk",
    "jeevitham avasanippik",
)

# Full marker set. Kept short on purpose — see the placeholder warning above.
_DISTRESS_MARKERS = _MARKERS_EN + _MARKERS_ML + _MARKERS_MANGLISH


def screen(text: str) -> bool:
    """Return True if ``text`` shows acute distress / self-harm signals.

    Runs FIRST, before any astrology logic, on every chat turn (GUARDRAILS.md §2).
    Errs toward an explicit-intent match; a reviewed classifier must replace this.
    """
    if not text:
        return False
    lowered = text.lower()  # Malayalam has no case; harmless, normalises English.
    return any(marker in lowered for marker in _DISTRESS_MARKERS)
