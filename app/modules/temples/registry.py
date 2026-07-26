"""In-memory snapshot of the temple directory, sourced from the database.

Why a snapshot rather than a query per call: ``TemplesService`` is entirely
synchronous and is called synchronously from inside the chat orchestrator's
turn. Making its readers async to fetch a directory that changes a few times a
month would ripple through every caller for no benefit. So the table is read
once at startup (and again after any operator write) into the same
``list[dict]`` shape the service has always used.

The fallback matters as much as the snapshot: when the table is empty we serve
``SEED_TEMPLES`` unchanged. That covers a fresh test database — every existing
test builds one with ``Base.metadata.create_all`` and seeds no temples — and a
process that boots before the import migration has run. Behaviour in both cases
is byte-identical to how the directory worked when it *was* the seed literal.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.temples.models import Temple
from app.modules.temples.seed_data import SEED_TEMPLES

# None = "not loaded, or loaded and empty" → fall back to the seed. A loaded,
# non-empty directory replaces it wholesale.
_snapshot: list[dict[str, Any]] | None = None

# Keys the service reads with a default (``t.get("hours", DEFAULT_HOURS)``).
# They must be ABSENT from the dict when unset, not present-and-None, or the
# default never applies and the temple loses its fallback hours/catalogue.
_OPTIONAL = ("hours", "timings", "poojas")


def row_to_dict(t: Temple) -> dict[str, Any]:
    """A Temple row in the exact shape ``seed_data.TempleSeed`` produces."""
    out: dict[str, Any] = {
        "id": t.id,
        "name": t.name,
        "name_ml": t.name_ml,
        "deity": t.deity,
        "district": t.district,
        "town": t.town,
        "town_ml": t.town_ml,
        "lat": t.lat,
        "lng": t.lng,
        "famous_for": t.famous_for,
        "vazhipadu": list(t.vazhipadu or []),
        "reviewed": t.reviewed,
        "story": t.story,
        "story_ml": t.story_ml,
        "rating": t.rating,
        "reviews": t.reviews,
    }
    for key in _OPTIONAL:
        value = getattr(t, key)
        if value is not None:
            out[key] = value
    return out


async def load(session: AsyncSession) -> int:
    """Refresh the snapshot from the database. Returns the active row count.

    The fallback keys on the TABLE being empty, not on there being no active
    rows. An operator who retires every temple means it — resurrecting the seed
    directory underneath them would be the opposite of what they asked for.
    """
    global _snapshot
    total = (await session.execute(select(func.count()).select_from(Temple))).scalar_one()
    if not total:
        _snapshot = None  # never imported → serve the curated seed
        return 0

    rows = (
        await session.execute(
            select(Temple).where(Temple.active.is_(True)).order_by(Temple.sort_order, Temple.id)
        )
    ).scalars().all()
    _snapshot = [row_to_dict(t) for t in rows]
    return len(rows)


def current() -> list[dict[str, Any]]:
    """The directory the service should read right now."""
    return _snapshot if _snapshot is not None else list(SEED_TEMPLES)


def reset() -> None:
    """Drop the snapshot (tests, and after a destructive operator edit)."""
    global _snapshot
    _snapshot = None
