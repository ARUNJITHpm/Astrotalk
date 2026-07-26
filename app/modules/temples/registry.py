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

from app.modules.temples.models import Pooja, Temple, TemplePooja
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


def _resolve_catalogue(
    masters: list[Pooja], overrides: list[TemplePooja]
) -> list[dict[str, Any]]:
    """Master catalogue + one temple's overrides → the list the app is served.

    ``amount`` is emitted in whole RUPEES: the DB stores paise like every other
    money column, but ``amount`` in rupees is the established API contract
    (PoojaCatalogueItem.amount, and the app's `amount` field).
    """
    by_key = {o.pooja_key: o for o in overrides}
    out: list[dict[str, Any]] = []
    for m in masters:
        o = by_key.get(m.key)
        if o is not None and not o.active:
            continue  # this temple does not offer it
        amount_paise = m.amount_paise if o is None or o.amount_paise is None else o.amount_paise
        lead_days = m.lead_days if o is None or o.lead_days is None else o.lead_days
        out.append({
            "key": m.key,
            "name": m.name,
            "name_ml": m.name_ml,
            "amount": amount_paise // 100,
            # The authoritative figure. `amount` is a lossy rupee rendering for
            # the client (PoojaCatalogueItem.amount is an int), so the booking
            # path must price from this rather than multiplying `amount` back
            # up — otherwise a price that is not a whole rupee undercharges.
            # PoojaCatalogueItem does not declare it, so it never reaches the
            # wire.
            "amount_paise": amount_paise,
            "lead_days": lead_days,
        })
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

    # Resolve the offering catalogue per temple and materialise it into the
    # temple dict under "poojas". That is deliberate: it means
    # TemplesService.pooja_catalogue() and BookingsService._find_pooja() — both
    # of which read t.get("poojas", DEFAULT_POOJAS) — keep working untouched,
    # and pricing stays server-side truth by construction.
    masters = (
        await session.execute(
            select(Pooja).where(Pooja.active.is_(True)).order_by(Pooja.sort_order, Pooja.key)
        )
    ).scalars().all()
    overrides: dict[str, list[TemplePooja]] = {}
    if masters:
        for o in (await session.execute(select(TemplePooja))).scalars().all():
            overrides.setdefault(o.temple_id, []).append(o)

    snapshot = []
    for t in rows:
        row = row_to_dict(t)
        # A temple's own JSON column still wins if set — it is the escape hatch
        # for a catalogue the relational shape cannot express.
        if masters and "poojas" not in row:
            row["poojas"] = _resolve_catalogue(list(masters), overrides.get(t.id, []))
        snapshot.append(row)
    _snapshot = snapshot
    return len(rows)


def current() -> list[dict[str, Any]]:
    """The directory the service should read right now."""
    return _snapshot if _snapshot is not None else list(SEED_TEMPLES)


def reset() -> None:
    """Drop the snapshot (tests, and after a destructive operator edit)."""
    global _snapshot
    _snapshot = None
