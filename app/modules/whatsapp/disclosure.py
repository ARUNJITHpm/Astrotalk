"""The AI disclosure and opt-out footer — GUARDRAILS.md §3, in one place.

These strings are compliance, not transport. They lived inside
``waha_client.py`` because that was the only sender when they were written, and
``service.py`` kept its own second copy of the same Malayalam sentence for
proactive messages. Removing WAHA (console plan Part 15) would therefore have
deleted the disclosure the Cloud API path imports — so it moved here first,
which is where it should have been all along: a rule every sender obeys, owned
by none of them.

Two footers, because they answer different questions:

  ``with_disclosure`` — a REPLY to something the person just sent. They know
  they are in a conversation; they need to know it is answered by an AI.

  ``with_footer`` — a PROACTIVE message they did not ask for right now. It
  carries the disclosure *and* the way out, because a message that arrives
  unbidden must always show how to stop the next one.

Both append in code rather than in a prompt, so no model, template or new caller
can forget them. There is a deliberate third case — ``send_text_raw`` — for
system messages where the disclosure would be absurd ("you have been
unsubscribed" does not need telling that an AI helped write it).

Change these words only with the same care as any other GUARDRAILS text.
"""

AI_DISCLOSURE = "🤖 ഈ സന്ദേശം AI സഹായത്തോടെ തയ്യാറാക്കിയതാണ്."
OPT_OUT = "ഈ സന്ദേശങ്ങൾ വേണ്ടെങ്കിൽ 'STOP' എന്ന് മറുപടി അയക്കൂ."

# Proactive footer: disclosure, then the way out.
FOOTER = f"\n\n{AI_DISCLOSURE}\n{OPT_OUT}"


def with_disclosure(text: str) -> str:
    """A reply, plus the AI disclosure."""
    return f"{text}\n\n{AI_DISCLOSURE}"


def with_footer(message: str) -> str:
    """A proactive message, plus the disclosure and the opt-out line."""
    return f"{message}{FOOTER}"
