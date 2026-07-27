"""Curated notices/articles feed for the Nithara app (NITHARA-BUILD-PLAN Part 4).

The consumer feed (festival notices, darshan info, panchangam explainers) is
editorial content — a curated bilingual seed, read-only, like the temple
directory. Content is honest: notices come from the temple as source, and the
educational card speaks in Nithara's own disclosed voice — no fabricated named
authority making predictions, and no invented engagement counts (GUARDRAILS §1/§4).
Real reactions (community already reacts to content posts) and admin CRUD layer
on later; until then like/comment counts are 0.

Categories match the app: Festival · Darshan · AstroTalk. ``temple_id`` (when
set) points at a real seed temple so the card's "View temple" opens it.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import FeedItem

CATEGORIES = ("Festival", "Darshan", "AstroTalk")

FEED_ITEMS: list[dict] = [
    {
        "id": "pooram-ilanjithara",
        "cat": "Festival",
        "image": "i-fest", "glyph": "i-parasol", "live": False,
        "title_en": "Thrissur Pooram — Ilanjithara Melam",
        "title_ml": "തൃശ്ശൂർ പൂരം — ഇലഞ്ഞിത്തറ മേളം",
        "body_en": "The Ilanjithara Melam gathers percussion artists on the eastern "
        "maidan; the Kudamattam parasol exchange follows in the evening.",
        "body_ml": "ഇലഞ്ഞിത്തറ മേളം കിഴക്കേ മൈതാനത്ത് വാദ്യകലാകാരന്മാരെ ഒരുമിച്ചു "
        "ചേർക്കുന്നു; വൈകുന്നേരം കുടമാറ്റം നടക്കുന്നു.",
        "who_en": "Vadakkunnathan Temple",
        "who_ml": "വടക്കുന്നാഥൻ ക്ഷേത്രം",
        "likes": 0, "comments": 0,
        "temple_id": "tsr-vadakkunnathan",
    },
    {
        "id": "guruvayur-nirmalyam",
        "cat": "Darshan",
        "image": "i-dars", "glyph": "i-lamp", "live": False,
        "title_en": "Nirmalya darshanam at Guruvayur",
        "title_ml": "ഗുരുവായൂരിൽ നിർമാല്യ ദർശനം",
        "body_en": "The first darshan of the day begins around 3 AM; queues form well "
        "before the nada opens.",
        "body_ml": "ദിവസത്തിലെ ആദ്യ ദർശനം പുലർച്ചെ 3 മണിയോടെ ആരംഭിക്കുന്നു; നട "
        "തുറക്കുന്നതിന് മുൻപേ ക്യൂ തുടങ്ങും.",
        "who_en": "Guruvayur Sri Krishna Temple",
        "who_ml": "ഗുരുവായൂർ ശ്രീകൃഷ്ണ ക്ഷേത്രം",
        "likes": 0, "comments": 0,
        "temple_id": "tsr-guruvayur",
    },
    {
        "id": "what-is-pradosham",
        "cat": "AstroTalk",
        "image": "i-astr", "glyph": "i-sparkle", "live": False,
        "title_en": "What is Pradosham?",
        "title_ml": "പ്രദോഷം എന്നാൽ എന്ത്?",
        "body_en": "Pradosham falls on the thirteenth lunar day — traditionally a time "
        "many set aside for Shiva worship in the twilight hour. Guidance only.",
        "body_ml": "ത്രയോദശി തിഥിയിലാണ് പ്രദോഷം — സന്ധ്യാവേളയിൽ ശിവാരാധനയ്ക്കായി "
        "പലരും മാറ്റിവയ്ക്കുന്ന സമയം. മാർഗനിർദേശം മാത്രം.",
        "who_en": "Nithara",
        "who_ml": "നിതാര",
        "likes": 0, "comments": 0,
        "temple_id": None,
    },
]


def current() -> list[dict]:
    """The feed the app should be served right now.

    ``None`` snapshot = the table was never imported, so serve the curated seed.
    Same fallback as the temple and astrologer registries, and for the same
    reason: every test builds a fresh database and seeds no feed, so they keep
    exercising exactly the behaviour this had when it *was* a literal.
    """
    return list(FEED_ITEMS) if _snapshot is None else _snapshot


def list_feed(temple_id: str | None = None, cat: str | None = None) -> list[dict]:
    """The curated feed, optionally filtered by temple or category."""
    items = current()
    if temple_id:
        items = [a for a in items if a["temple_id"] == temple_id]
    if cat:
        items = [a for a in items if a["cat"].lower() == cat.lower()]
    return list(items)


# ---- database-backed feed (console plan Part 8) ----
# The list above is now the import fixture and the empty-table fallback; the
# live feed is a snapshot of `feed_items`, refreshed at startup and after every
# operator write. `list_feed` is synchronous and called from a route with no
# session, so a snapshot keeps that signature rather than rippling async out.

_snapshot: list[dict] | None = None


def row_to_dict(item: "FeedItem") -> dict:
    """A FeedItem row in the exact shape the seed literal produces."""
    return {
        "id": item.id,
        "cat": item.cat,
        "image": item.image,
        "glyph": item.glyph,
        "live": item.live,
        "title_en": item.title_en,
        "title_ml": item.title_ml,
        "body_en": item.body_en,
        "body_ml": item.body_ml,
        "who_en": item.who_en,
        "who_ml": item.who_ml,
        # Always zero, never stored: real reactions do not exist yet, and an
        # invented engagement count is exactly what GUARDRAILS §4 forbids.
        "likes": 0,
        "comments": 0,
        "temple_id": item.temple_id,
    }


async def load(session: "AsyncSession") -> int:
    """Refresh the snapshot from the database. Returns the published count."""
    global _snapshot
    total = (await session.execute(select(func.count()).select_from(FeedItem))).scalar_one()
    if not total:
        _snapshot = None  # never imported → serve the curated seed
        return 0
    rows = (
        await session.execute(
            select(FeedItem)
            .where(FeedItem.published.is_(True))
            .order_by(FeedItem.sort_order, FeedItem.id)
        )
    ).scalars().all()
    _snapshot = [row_to_dict(r) for r in rows]
    return len(rows)


def reset() -> None:
    """Drop the snapshot (tests, and after a destructive operator edit)."""
    global _snapshot
    _snapshot = None
