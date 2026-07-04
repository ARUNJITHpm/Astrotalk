"""Starter knowledge base for RAG retrieval (internal to the knowledge module).

⚠️ PLACEHOLDER CONTENT — NOT astrologer-reviewed. Every chunk below is marked
``reviewed=False``. These exist only so the retrieval pipeline works end-to-end
during development; replace with real astrologer-authored, reviewed interpretation
text before anything ships to users.

Tone follows GUARDRAILS.md §1: guidance and agency, never fear, never doom,
never "pay-or-else". Keep that framing when this content is replaced.
"""

from typing import TypedDict


class SeedChunk(TypedDict):
    id: str
    topic: str
    text: str
    reviewed: bool


SEED_CHUNKS: list[SeedChunk] = [
    {
        "id": "planet-in-house-saturn-10",
        "topic": "planet-in-house",
        "text": (
            "Saturn in the 10th house points to a career built slowly through "
            "patience and responsibility. It rewards steady, honest effort over "
            "shortcuts. The discipline it asks for tends to become a real strength "
            "in midlife — the stars incline toward steady growth here, they do not "
            "compel any single outcome."
        ),
        "reviewed": False,
    },
    {
        "id": "planet-in-house-jupiter-5",
        "topic": "planet-in-house",
        "text": (
            "Jupiter in the 5th house favours learning, creativity, and warmth "
            "with children and students. It is a placement associated with "
            "optimism and good counsel. A gentle reminder: its blessings grow when "
            "you act on them, not by waiting for luck."
        ),
        "reviewed": False,
    },
    {
        "id": "retrograde-mercury",
        "topic": "retrograde",
        "text": (
            "A Mercury retrograde is a season for review, not dread. It tends to "
            "surface miscommunications, delays, and second drafts. Treat it as an "
            "invitation to slow down, re-read, and reconnect with old threads — "
            "there is nothing here to fear, only things worth double-checking."
        ),
        "reviewed": False,
    },
    {
        "id": "retrograde-saturn",
        "topic": "retrograde",
        "text": (
            "Saturn retrograde is a quiet time to revisit commitments and "
            "boundaries. It asks honest questions about where effort is going. It "
            "is reflective rather than punishing — a chance to realign work with "
            "what genuinely matters to you."
        ),
        "reviewed": False,
    },
    {
        "id": "porutham-basics",
        "topic": "porutham",
        "text": (
            "Porutham (Kerala marriage compatibility) traditionally weighs ten "
            "factors, including Dina, Gana, Mahendra, Stree-Deergha, and Rasi "
            "porutham, comparing the couple's birth stars. It is best read as a "
            "balanced conversation starter about compatibility, never as a verdict "
            "or a source of fear. A low score is information to discuss, not doom."
        ),
        "reviewed": False,
    },
    {
        "id": "nakshatra-moon-mind",
        "topic": "nakshatra",
        "text": (
            "In Vedic astrology the Moon's nakshatra (birth star) is linked to the "
            "emotional temperament and instincts. Knowing it helps frame how a "
            "person processes feelings and stress. It describes tendencies and "
            "leanings — it is guidance for self-understanding, not a fixed fate."
        ),
        "reviewed": False,
    },
]
