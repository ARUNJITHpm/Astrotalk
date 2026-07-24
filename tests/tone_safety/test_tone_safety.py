"""Tests for the tone_safety crisis screen and persona (GUARDRAILS.md §1/§2).

The crisis screen is the project's most safety-critical path: distress must
route to the helpline, and an ordinary astrology question must NOT be derailed.
"""

from app.modules.tone_safety import persona
from app.modules.tone_safety.service import ToneSafetyService

_svc = ToneSafetyService()


def test_screen_flags_malayalam_distress():
    msg = "എനിക്ക് ഇനി ജീവിക്കാൻ വയ്യ, ആത്മഹത്യ ചെയ്യണം"  # "I can't go on; I want to end my life"
    assert _svc.screen(msg) is True


def test_screen_flags_english_distress():
    msg = "I don't want to live anymore, I want to kill myself"
    assert _svc.screen(msg) is True


def test_screen_does_not_flag_neutral_astrology_question():
    # A normal chart question must reach the astrology pipeline, not the helpline.
    msg = "എന്റെ ജാതകം അനുസരിച്ച് ഈ വർഷം ജോലിയിൽ എന്ത് മാറ്റം വരും?"  # career this year?
    assert _svc.screen(msg) is False


def test_safety_response_has_helpline_and_no_astrology():
    reply = _svc.crisis_reply()
    assert reply == persona.SAFETY_RESPONSE
    assert "14416" in reply
    # No astrology / upsell content in a crisis response (GUARDRAILS.md §2).
    for forbidden in ("ജാതക", "നക്ഷത്ര", "രാശി", "dosha", "horoscope", "₹", "subscribe"):
        assert forbidden not in reply


def test_system_prompt_encodes_all_five_persona_rules():
    prompt = _svc.build_system_prompt()
    # Cues for each of the five §6 rules.
    assert "AI astrologer" in prompt          # 1: disclose AI
    assert "feelings BEFORE" in prompt         # 2: feelings before chart
    assert "real placement or transit" in prompt  # 3: tie claims to placements
    assert "incline, they do not compel" in prompt  # 4: agency
    assert "hand off to a human or helpline" in prompt  # 5: limits / handoff
    assert "never invent a dosha" in prompt    # GUARDRAILS §1 no-fear


def test_system_prompt_injects_user_memory():
    memory = "Cautious about a job change.\n- married\n- one child"
    prompt = _svc.build_system_prompt(memory=memory)
    assert "What you remember about this person" in prompt
    assert "one child" in prompt


def test_system_prompt_omits_memory_section_when_absent():
    assert "What you remember about this person" not in _svc.build_system_prompt()


def test_system_prompt_injects_user_name():
    prompt = _svc.build_system_prompt(name="Arya")
    assert "speaking with is named Arya" in prompt
    assert "if they ask what their name is" in prompt


def test_system_prompt_omits_name_section_when_absent():
    assert "speaking with is named" not in _svc.build_system_prompt()


def test_system_prompt_injects_user_age():
    prompt = _svc.build_system_prompt(age=32)
    assert "32 years old" in prompt
    assert "if they ask their age" in prompt


def test_system_prompt_omits_age_section_when_absent():
    assert "years old" not in _svc.build_system_prompt()


def test_screen_flags_manglish_distress():
    # Romanized Malayalam distress must route to the helpline too — a large
    # share of users type Malayalam in Latin script.
    assert _svc.screen("enikku ini jeevikkan vayya") is True
    assert _svc.screen("marikkanam ennu thonnunnu") is True
    assert _svc.screen("aathmahathya cheyyan thonnunnu") is True
    assert _svc.screen("chakanam ennu thonunnu") is True


def test_screen_does_not_flag_longevity_astrology_talk():
    # 8th-house / longevity questions are legitimate astrology, not distress
    # (the classifier deliberately targets explicit self-harm intent only).
    assert _svc.screen("ayussinte bhavam nokkamo? 8th house entha parayunnathu") is False
    assert _svc.screen("what does my 8th house say about longevity") is False
