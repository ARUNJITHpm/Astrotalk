"""Tests for the curiosity engine (chat.suggestions.build_suggestions).

Pure function over a chart/transits dict — hermetic. Also asserts every chip is
clean under the reply guardrail (tone_safety.screen_reply), since these strings
reach the user without an LLM pass.
"""

from app.modules.chat.suggestions import build_suggestions
from app.modules.tone_safety.service import ToneSafetyService

_CHART = {
    "nakshatram": "അശ്വതി",
    "lagnam": "മേടം",
    "dasha": {"current": {"mahadasha": {"lord": "shani", "lord_ml": "ശനി"}}},
    "doshas": {"chovva_dosha": {"present": True, "effective": True, "severity": "strong"}},
}
_TRANSITS = {
    "transits": {"guru": {"retrograde": True}, "rahu": {"retrograde": True}},
    "sade_sati": {"active": True},
}


def test_capped_at_three():
    out = build_suggestions(
        latest="ഇന്ന് എങ്ങനെ?", chart=_CHART, transits=_TRANSITS,
        grounded_in=["chart"], concern=None,
    )
    assert 1 <= len(out) <= 3
    assert all(isinstance(s, str) and s.strip() for s in out)


def test_dasha_chip_names_the_lord():
    out = build_suggestions(
        latest="x", chart=_CHART, transits={}, grounded_in=[], concern=None,
    )
    assert any("ശനി" in s and "ദശ" in s for s in out)


def test_effective_dosha_asks_for_remedies():
    out = build_suggestions(
        latest="x", chart=_CHART, transits={}, grounded_in=[], concern=None,
    )
    assert any("പരിഹാര" in s for s in out)


def test_cancelled_dosha_asks_how_it_was_cancelled():
    chart = {
        "doshas": {"chovva_dosha": {"present": True, "effective": False, "severity": "cancelled"}},
    }
    out = build_suggestions(
        latest="x", chart=chart, transits={}, grounded_in=[], concern=None,
    )
    assert any("പരിഹരിക്കപ്പെട്ട" in s for s in out)


def test_astrologer_cta_comes_first():
    astro = {"name": "kozhikode-astro-1", "town": "Kozhikode", "district": "Kozhikode"}
    out = build_suggestions(
        latest="x", chart=_CHART, transits=_TRANSITS, grounded_in=[],
        concern="marriage", astrologer=astro,
    )
    assert out[0].startswith("📿")
    assert "kozhikode-astro-1" in out[0]


def test_rotation_excludes_current_concern():
    # No chart → only the rotating topics/generics fill the list; the concern
    # just asked about must not be echoed back.
    out = build_suggestions(
        latest="ജോലി കാര്യം", chart=None, transits={}, grounded_in=[], concern="career",
    )
    assert out  # still gives curious chips without a chart
    career_q = "എന്റെ ജാതകത്തിൽ തൊഴിൽ യോഗം എങ്ങനെയുണ്ട്?"
    assert career_q not in out


def test_all_chips_pass_the_tone_guardrail():
    astro = {"name": "thrissur-astro-2", "town": "Thrissur", "district": "Thrissur"}
    tone = ToneSafetyService()
    out = build_suggestions(
        latest="x", chart=_CHART, transits=_TRANSITS, grounded_in=[],
        concern="health", astrologer=astro,
    )
    for chip in out:
        assert tone.screen_reply(chip) == [], f"chip tripped guardrail: {chip}"
