"""Output guardrail screen for GENERATED replies (internal to tone_safety).

The persona prompt asks the LLM to never use fear, payment-linked remedies, or
manufactured urgency (GUARDRAILS.md §1) — but a prompt is a request, not a
guarantee. This screen deterministically checks what the model actually said,
so chat can retry or fall back instead of shipping a violation.

Design: small, high-precision lexicons. A miss (false negative) costs one bad
reply; a false positive costs a needless retry — so every pattern here should
be something Tara must NEVER say, not merely something gloomy. Normal astrology
vocabulary (dosha, shani, ഏഴര ശനി…) is NOT flagged; doshas discussed with
agency are the product working as designed.

Owned by tone_safety because this file is guardrail-bearing copy (AGENTS.md):
loosening these lexicons is a guardrail change and needs review.
"""

import re

# --- Fear / doom: catastrophe declared AT the person. -----------------------
# Plain nouns ("ദോഷം", "ശനി") are fine; these patterns assert doom or curse.
_FEAR_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"വലിയ\s*(ആപത്ത്|അപകടം|ദോഷം|ദുരന്തം)",   # "a great danger/calamity (awaits)"
        r"(ആപത്ത്|അപകടം|ദുരന്തം|മരണം)\s*(വരും|ഉണ്ടാകും|സംഭവിക്കും)",
        r"ശാപം",                                        # curse
        r"നാശം\s*(വരും|ഉണ്ടാകും)",
        r"കഷ്ടകാലം\s*(തീരില്ല|മാറില്ല)",              # "your bad period will never end"
        r"ഒരിക്കലും\s*(നന്നാവില്ല|രക്ഷപ്പെടില്ല|ശരിയാവില്ല)",
        r"\bcursed\b",
        r"\bdoom(ed)?\b",
        r"(terrible|grave)\s+(danger|misfortune)\s+(awaits|will)",
    )
)

# --- Payment-linked remedies: money tied to a ritual/outcome. ----------------
# A price near a remedy word is the violation; prices alone (e.g. a temple's
# well-known vazhipadu fee mentioned neutrally) are left to review, not code.
_REMEDY_WORDS = (
    r"(പരിഹാര|പൂജ|വഴിപാട|ഹോമം|യന്ത്ര|രത്ന|മന്ത്ര|pooja|puja|homam|remedy|ritual|yantra|gemstone)"
)
_PAYMENT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"{_REMEDY_WORDS}[^.。\n]{{0,60}}(₹|രൂപ|\brs\.?\b|\bfee\b|\bpay\b|പണം\s*അട|ഫീസ്)",
        rf"(₹|രൂപ|\brs\.?\b|\bfee\b|\bpay\b|പണം\s*അട|ഫീസ്)[^.。\n]{{0,60}}{_REMEDY_WORDS}",
        rf"{_REMEDY_WORDS}[^.。\n]{{0,60}}(ചെയ്തില്ലെങ്കിൽ|ചെയ്യാതിരുന്നാൽ)",  # remedy-or-else
    )
)

# --- Manufactured urgency: act NOW or suffer. --------------------------------
_URGENCY_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(ഉടനെ|ഉടൻ|ഇപ്പോൾ\s*തന്നെ)[^.。\n]{0,40}(ചെയ്തില്ലെങ്കിൽ|ഇല്ലെങ്കിൽ)",
        r"(ചെയ്തില്ലെങ്കിൽ|ഇല്ലെങ്കിൽ)[^.。\n]{0,40}(ആപത്ത്|അപകടം|ദോഷം|നഷ്ടം|നാശം)",
        r"(last\s+chance|act\s+now\s+or|before\s+it'?s\s+too\s+late)",
    )
)

_CATEGORIES: tuple[tuple[str, tuple[re.Pattern, ...]], ...] = (
    ("fear", _FEAR_PATTERNS),
    ("payment_remedy", _PAYMENT_PATTERNS),
    ("urgency", _URGENCY_PATTERNS),
)


def screen_reply(reply: str) -> list[str]:
    """Violation categories found in a generated reply ([] = clean).

    Categories: "fear", "payment_remedy", "urgency" — each maps 1:1 to a
    GUARDRAILS.md §1 rule.
    """
    if not reply:
        return []
    found = []
    for name, patterns in _CATEGORIES:
        if any(p.search(reply) for p in patterns):
            found.append(name)
    return found


# Injected into the system prompt for the single corrective retry after a
# violation. States the failure plainly so the model fixes THAT, not the style.
CORRECTIVE_NOTE = (
    "IMPORTANT CORRECTION: your previous draft violated a hard rule "
    "(fear-mongering, payment-linked remedy, or manufactured urgency). "
    "Rewrite the reply keeping the same substance but with guidance and "
    "agency: no threats of misfortune, no money tied to any remedy, no "
    "act-now-or-else pressure. The stars incline, they never compel."
)

# Served when even the corrective retry violates — warm, safe, on-persona.
SAFE_FALLBACK_REPLY = (
    "ക്ഷമിക്കണം, ഈ ചോദ്യത്തിന് ഇപ്പോൾ നല്ലൊരു ഉത്തരം പറയാൻ എനിക്ക് കഴിയുന്നില്ല. "
    "ഒന്ന് വ്യത്യസ്തമായി ചോദിച്ചു നോക്കാമോ? ഓർക്കുക — നക്ഷത്രങ്ങൾ വഴി കാട്ടുന്നു, "
    "അവ ഒന്നും അടിച്ചേൽപ്പിക്കുന്നില്ല; തിരഞ്ഞെടുപ്പ് എപ്പോഴും നിങ്ങളുടേതാണ്. 🙏"
)
