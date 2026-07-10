"""Curiosity engine — personalized follow-up chips (internal to chat).

After every non-crisis reply the chat service builds up to three short Malayalam
follow-up questions from the person's OWN computed chart (running dasha, doshas,
janma nakshatram, current transits) plus a rotating "untouched topic" so the
conversation stays curious instead of repeating what was just asked.

These are deterministic strings, NOT LLM output: zero extra tokens/latency, and
they can never violate the reply guardrails (GUARDRAILS.md §1) the way generated
text might. They complement — do not replace — the single caring question the
persona already ends each reply with. The frontend renders them as tappable
chips and falls back to its own ``grounded_in``-derived chips when this list is
empty.
"""

from __future__ import annotations

_GRAHA_ML = {
    "surya": "സൂര്യൻ",
    "chandra": "ചന്ദ്രൻ",
    "chevvai": "ചൊവ്വ",
    "budhan": "ബുധൻ",
    "guru": "വ്യാഴം",
    "shukran": "ശുക്രൻ",
    "shani": "ശനി",
    "rahu": "രാഹു",
    "ketu": "കേതു",
}

# Life-concern key → a curious chart question. Keys match temples.CONCERN_DEITIES
# so a concern just asked about is excluded from the rotation.
_TOPIC_QUESTIONS = {
    "career": "എന്റെ ജാതകത്തിൽ തൊഴിൽ യോഗം എങ്ങനെയുണ്ട്?",
    "marriage": "വിവാഹ യോഗം ജാതകം എന്ത് പറയുന്നു?",
    "wealth": "സാമ്പത്തിക കാര്യങ്ങൾ ജാതകം എന്ത് സൂചിപ്പിക്കുന്നു?",
    "health": "ആരോഗ്യം സംബന്ധിച്ച് ജാതകം എന്ത് പറയുന്നു?",
    "children": "സന്താനഭാഗ്യം ജാതകത്തിൽ എങ്ങനെയുണ്ട്?",
    "education": "വിദ്യാഭ്യാസ യോഗം എങ്ങനെയുണ്ട്?",
    "peace": "മനസ്സമാധാനത്തിന് ജാതകം എന്ത് വഴി കാണിക്കുന്നു?",
}

# Chart-independent curiosities, always safe to offer.
_GENERIC_TOPICS = [
    "എന്റെ ലഗ്നം എന്നെക്കുറിച്ച് എന്ത് പറയുന്നു?",
    "ഈ വർഷത്തെ പ്രധാന ഗ്രഹസഞ്ചാരങ്ങൾ എന്തൊക്കെ?",
    "എന്റെ ഇന്നത്തെ നക്ഷത്രഫലം പറയൂ",
]


def build_suggestions(
    *,
    latest: str,
    chart: dict | None,
    transits: dict | None,
    grounded_in: list[str],
    concern: str | None,
    astrologer: dict | None = None,
    limit: int = 3,
) -> list[str]:
    """Up to ``limit`` Malayalam follow-up chips, most personal first."""
    out: list[str] = []

    def _add(text: str | None) -> None:
        if text and text not in out:
            out.append(text)

    # 1) Human-astrologer CTA when the escalation step picked one.
    if astrologer and astrologer.get("name"):
        _add(f"📿 {astrologer['name']}-നെ കാണാൻ സമയം ബുക്ക് ചെയ്യാം")

    chart = chart if isinstance(chart, dict) else {}
    transits = transits if isinstance(transits, dict) else {}

    # 2) Current mahadasha.
    maha = ((chart.get("dasha") or {}).get("current") or {}).get("mahadasha") or {}
    lord_ml = maha.get("lord_ml") or _GRAHA_ML.get(maha.get("lord", ""))
    if lord_ml:
        _add(f"എന്റെ {lord_ml} ദശാകാലം എങ്ങനെ പോകുന്നു?")

    # 3) Doshas (uses the parihara-aware fields; a cancelled dosha reads
    #    differently from a live one).
    chovva = (chart.get("doshas") or {}).get("chovva_dosha") or {}
    if chovva.get("present"):
        if chovva.get("effective", True):
            _add("ചൊവ്വാ ദോഷത്തിന്റെ പരിഹാരങ്ങൾ എന്തൊക്കെയാണ്?")
        else:
            _add("എന്റെ ചൊവ്വാ ദോഷം എങ്ങനെ പരിഹരിക്കപ്പെട്ടു?")
    if (transits.get("sade_sati") or {}).get("active"):
        _add("ഏഴര ശനിയിൽ ഞാൻ എന്ത് ശ്രദ്ധിക്കണം?")

    # 4) Janma nakshatram.
    if chart.get("nakshatram"):
        _add(f"എന്റെ {chart['nakshatram']} നക്ഷത്രത്തിന്റെ ഈ ആഴ്ചയിലെ ഫലം?")

    # 5) A retrograde transit (skip the nodes, which are always retrograde).
    for name, entry in (transits.get("transits") or {}).items():
        if name in ("rahu", "ketu"):
            continue
        if isinstance(entry, dict) and entry.get("retrograde"):
            _add(f"{_GRAHA_ML.get(name, name)} വക്രഗതിയിൽ ഞാൻ എന്ത് ശ്രദ്ധിക്കണം?")
            break

    # 6) Rotating untouched topic — the curiosity driver. Exclude the concern
    #    just asked about; rotate by the message hash so consecutive turns vary.
    pool = [q for key, q in _TOPIC_QUESTIONS.items() if key != concern]
    pool += _GENERIC_TOPICS
    if pool:
        _add(pool[hash(latest) % len(pool)])

    return out[:limit]
