"""Tests for the content module's daily-message generation (mock path)."""

from app.modules.content import templates
from app.modules.content.service import ContentService

_PANCHANGAM = {
    "date": "2026-06-25",
    "nakshatram": "രോഹിണി",
    "nalla_neram": "07:30–08:30",
    "tithi": "ദശമി",
}


async def test_generate_daily_message_is_compliant_and_grounded():
    msg = await ContentService().generate_daily_message(_PANCHANGAM)

    # Grounded in the panchangam, ends with the soft CTA + app link (§5).
    assert "രോഹിണി" in msg
    assert "👉" in msg
    assert templates.APP_LINK in msg
    # GUARDRAILS §1: no payment/urgency language in the daily copy.
    for forbidden in ("₹", "pay", "urgent", "ഇപ്പോൾ തന്നെ വാങ്ങ"):
        assert forbidden not in msg


def test_system_prompt_matches_doc_and_substitutes_link():
    prompt = templates.system_prompt()
    # Exact §5 rules are present.
    assert "ONE short Malayalam WhatsApp Channel message" in prompt
    assert "NEVER predict doom" in prompt
    # The {app_link} placeholder is resolved before the LLM sees it.
    assert "{app_link}" not in prompt
    assert templates.APP_LINK in prompt
