"""In-memory snapshot of the astrologer directory, sourced from the database.

Same shape and the same reasoning as ``temples/registry.py``:
``AstrologersService`` is synchronous on the read path and is called
synchronously from inside the chat turn (``suggest_for``), so the directory is
cached at startup rather than queried per call. An empty table falls back to
``SEED_ASTROLOGERS`` so a fresh test database behaves exactly as it did before
the directory moved.

The fallback keys on the table being EMPTY, not on there being no active rows —
deactivating every astrologer is a deliberate operator act (and a likely one
here, since all 28 seeded entries are generated placeholders), so it must not
resurrect them.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrologers.models import Astrologer
from app.modules.astrologers.seed_data import SEED_ASTROLOGERS

_snapshot: list[dict[str, Any]] | None = None


def row_to_dict(a: Astrologer) -> dict[str, Any]:
    """An Astrologer row in the exact shape ``seed_data.AstrologerSeed`` gives."""
    return {
        "id": a.id,
        "name": a.name,
        "name_ml": a.name_ml,
        "district": a.district,
        "town": a.town,
        "lat": a.lat,
        "lng": a.lng,
        "specialties": list(a.specialties or []),
        "experience_years": a.experience_years,
        "languages": list(a.languages or []),
        "rating": a.rating,
        "bio_ml": a.bio_ml,
        "availability": list(a.availability or []),
        "price_paise_per_min": a.price_paise_per_min,
    }


async def load(session: AsyncSession) -> int:
    """Refresh the snapshot from the database. Returns the active row count."""
    global _snapshot
    total = (await session.execute(select(func.count()).select_from(Astrologer))).scalar_one()
    if not total:
        _snapshot = None  # never imported → serve the seed
        return 0

    rows = (
        await session.execute(
            select(Astrologer)
            .where(Astrologer.active.is_(True))
            .order_by(Astrologer.sort_order, Astrologer.id)
        )
    ).scalars().all()
    _snapshot = [row_to_dict(a) for a in rows]
    return len(rows)


def current() -> list[dict[str, Any]]:
    """The directory the service should read right now."""
    return _snapshot if _snapshot is not None else list(SEED_ASTROLOGERS)


def reset() -> None:
    """Drop the snapshot (tests, and after a destructive operator edit)."""
    global _snapshot
    _snapshot = None
