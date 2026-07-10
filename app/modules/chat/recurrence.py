"""Recurring-concern detection (internal to chat).

When the same life concern (marriage, career, health, …) keeps coming up across
a user's recent chats, the chat service may gently offer a human astrologer and
a temple visit as OPTIONAL extra support (framed by the persona, never as a
demand or out of fear — GUARDRAILS.md §1). A direct ask ("suggest an astrologer
near me") triggers the same offer immediately, regardless of history.

Pure helper: it takes the temples module's ``detect_concern`` classifier so the
chat service keeps its single dependency surface, reads recent turns via the
chat history, and degrades to "no fire" whenever history is unavailable.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat import history

# Keywords that ask for a human astrologer outright (English + Manglish + ML).
_ASTRO_INTENT = (
    "astrologer", "jyolsyan", "jyotsyan", "jyothishi", "jyotish",
    "consult", "in person", "directly meet",
    "ജ്യോത്സ്യ", "ജ്യോതിഷി", "ജ്യോതിഷൻ", "ജ്യോതിഷം",
    "നേരിട്ട് കാണ", "നേരില്‍ കാണ", "ആളെ കാണ",
)

# Same concern must appear in at least this many of the recent turns (including
# the current one) before we treat it as "persisting".
_RECURRENCE_THRESHOLD = 3
_HISTORY_WINDOW = 10
# Don't re-suggest if a very recent reply already named an astrologer (the dummy
# ids all contain "astro-", which appears verbatim in any reply that named one).
_COOLDOWN_TURNS = 5
_SUGGESTED_SENTINEL = "astro-"


async def detect_recurring_concern(
    session: AsyncSession | None,
    user_id: str,
    latest: str,
    detect_concern: Callable[[str], str | None],
) -> tuple[str | None, bool]:
    """Return ``(recurring_concern | None, direct_ask)``.

    ``recurring_concern`` is set only when the current message maps to a concern
    that appears ≥ threshold times in the recent window AND no recent reply
    already offered an astrologer. ``direct_ask`` is independent of history.
    """
    direct_ask = any(kw in latest.lower() for kw in _ASTRO_INTENT)

    current = detect_concern(latest)
    if session is None or current is None:
        return None, direct_ask

    turns = await history.get_history(session, user_id, limit=_HISTORY_WINDOW)

    counts: Counter[str] = Counter([current])
    recently_suggested = False
    for i, turn in enumerate(turns):
        for msg in turn.get("messages", []):
            if msg.get("role") not in (None, "user"):
                continue
            concern = detect_concern(msg.get("content", ""))
            if concern:
                counts[concern] += 1
        if i < _COOLDOWN_TURNS and _SUGGESTED_SENTINEL in (turn.get("reply") or ""):
            recently_suggested = True

    if recently_suggested or counts[current] < _RECURRENCE_THRESHOLD:
        return None, direct_ask
    return current, direct_ask
