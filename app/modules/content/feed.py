"""Curated notices/articles feed for the Nithara app (NITHARA-BUILD-PLAN Part 4).

The consumer feed (festival notices, darshan posts, astro talks) is editorial
content — kept as a curated bilingual seed here, read-only, exactly like the
temple directory. Real like/comment counts and admin CRUD can layer on later
(community already has a reaction mechanism keyed to content posts); for now the
counts are display seed values.

Categories match the app: Festival · Darshan · AstroTalk. ``temple_id`` (when
set) points at a real seed temple so the card's "View temple" opens it.
"""

CATEGORIES = ("Festival", "Darshan", "AstroTalk")

FEED_ITEMS: list[dict] = [
    {
        "id": "pooram-ilanjithara",
        "cat": "Festival",
        "image": "i-fest", "glyph": "i-parasol", "live": True,
        "title_en": "Thrissur Pooram — Ilanjithara Melam",
        "title_ml": "തൃശ്ശൂർ പൂരം — ഇലഞ്ഞിത്തറ മേളം",
        "body_en": "250 artists, one rhythm. Kudamattam begins at 5 PM on the eastern side.",
        "body_ml": "250 കലാകാരന്മാർ, ഒരേ താളം. കുടമാറ്റം വൈകുന്നേരം 5 മണിക്ക്, കിഴക്കേ ഭാഗത്ത്.",
        "who_en": "Vadakkunnathan Temple",
        "who_ml": "വടക്കുന്നാഥൻ ക്ഷേത്രം",
        "likes": 18400, "comments": 1200,
        "temple_id": "tsr-vadakkunnathan",
    },
    {
        "id": "guruvayur-nirmalyam",
        "cat": "Darshan",
        "image": "i-dars", "glyph": "i-lamp", "live": False,
        "title_en": "Nirmalya darshanam at Guruvayur",
        "title_ml": "ഗുരുവായൂരിൽ നിർമാല്യ ദർശനം",
        "body_en": "The 3 AM darshan. The queue was already a kilometre — worth every minute.",
        "body_ml": "പുലർച്ചെ 3 മണിയുടെ ദർശനം. ക്യൂ ഒരു കിലോമീറ്റർ — എന്നിട്ടും വിലപ്പെട്ടത്.",
        "who_en": "arjun_k",
        "who_ml": "അർജുൻ",
        "likes": 2100, "comments": 184,
        "temple_id": "tsr-guruvayur",
    },
    {
        "id": "guru-transit-chothi",
        "cat": "AstroTalk",
        "image": "i-astr", "glyph": "i-sparkle", "live": False,
        "title_en": "Guru transit — for Chothi natives",
        "title_ml": "ഗുരു സംക്രമം — ചോതി നക്ഷത്രക്കാർക്ക്",
        "body_en": "Jupiter enters Mithunam this week and sits on your seventh house.",
        "body_ml": "ഈ ആഴ്ച വ്യാഴം മിഥുനത്തിലേക്ക്, നിങ്ങളുടെ ഏഴാം ഭാവത്തിൽ.",
        "who_en": "Dr. Nandakumar",
        "who_ml": "ഡോ. നന്ദകുമാർ",
        "likes": 890, "comments": 212,
        "temple_id": None,
    },
]


def list_feed(temple_id: str | None = None, cat: str | None = None) -> list[dict]:
    """The curated feed, optionally filtered by temple or category."""
    items = FEED_ITEMS
    if temple_id:
        items = [a for a in items if a["temple_id"] == temple_id]
    if cat:
        items = [a for a in items if a["cat"].lower() == cat.lower()]
    return list(items)
