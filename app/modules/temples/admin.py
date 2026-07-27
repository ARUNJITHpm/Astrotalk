"""Operator writes against the temple directory (console plan Part 5).

Data access and validation only; the routes live in router.py, the same split
partners.py already follows.

Until Part 1 the directory was a Python literal, so *nothing* here was
possible — correcting a temple's coordinates meant a code change and a redeploy.
These are the first writes the table has ever had.

Two rules run through the whole file:

  - **Validate before writing.** The directory feeds the chat orchestrator's
    remedy suggestions, so an unknown deity key or a swapped lat/lng degrades
    replies for everyone, not just one temple's page. Anything the readers
    treat as an enum is checked here.
  - **Retire, never delete.** Bookings, visits, partners and festivals all
    reference ``temples.id`` as a plain string with no foreign key, so a DELETE
    would orphan them silently. ``active=False`` is the only removal.
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.temples.models import Pooja, Temple, TemplePooja
from app.modules.temples.remedy_map import DEITIES

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
_TIMING_KEYS = ("nirmalyam", "morning", "evening")

# Fields an operator may set on a temple. Everything else on the row
# (created_at, updated_at) is the database's business. Listing them explicitly
# rather than accepting **changes is what stops a payload from writing a column
# nobody meant to expose.
TEMPLE_FIELDS = frozenset({
    "name", "name_ml", "deity", "district", "town", "town_ml", "lat", "lng",
    "famous_for", "vazhipadu", "story", "story_ml", "hours", "timings",
    "poojas", "rating", "reviews", "active", "image_key", "sort_order",
})


class TempleAdminError(ValueError):
    """A rejected write — unknown id, bad enum value, out-of-range number."""


class NotFound(TempleAdminError):
    """The row the operator addressed does not exist."""


def _validate_deity(deity: str) -> None:
    if deity not in DEITIES:
        raise TempleAdminError(
            f"unknown deity {deity!r}; one of: {', '.join(sorted(DEITIES))}"
        )


def _validate_coords(changes: dict[str, Any]) -> None:
    """Range-check whichever coordinate was supplied — a PATCH may send one."""
    if "lat" in changes and not (-90 <= changes["lat"] <= 90):
        raise TempleAdminError("lat must be between -90 and 90")
    if "lng" in changes and not (-180 <= changes["lng"] <= 180):
        raise TempleAdminError("lng must be between -180 and 180")


def _validate_hours(hours: Any) -> None:
    """Darshan windows: a list of [open_minute, close_minute] pairs.

    ``_open_state`` iterates these and unpacks two values per entry, so a
    malformed row raises inside every public list call — validate here instead.
    """
    if not isinstance(hours, list) or not hours:
        raise TempleAdminError("hours must be a non-empty list of [open, close]")
    for window in hours:
        if (
            not isinstance(window, list | tuple)
            or len(window) != 2
            or not all(isinstance(m, int) for m in window)
        ):
            raise TempleAdminError("each window must be [open_minute, close_minute]")
        open_m, close_m = window
        if not (0 <= open_m < close_m <= 24 * 60):
            raise TempleAdminError("windows must satisfy 0 <= open < close <= 1440")


def _validate_timings(timings: Any) -> None:
    if not isinstance(timings, dict) or any(k not in timings for k in _TIMING_KEYS):
        raise TempleAdminError(f"timings needs all of: {', '.join(_TIMING_KEYS)}")


def _validate_temple_fields(changes: dict[str, Any]) -> None:
    unknown = set(changes) - TEMPLE_FIELDS
    if unknown:
        raise TempleAdminError(f"cannot set: {', '.join(sorted(unknown))}")
    if "deity" in changes:
        _validate_deity(changes["deity"])
    _validate_coords(changes)
    # None is meaningful for both: it clears the override and restores the
    # module's DEFAULT_HOURS / DEFAULT_TIMINGS, so only a present value is checked.
    if changes.get("hours") is not None:
        _validate_hours(changes["hours"])
    if changes.get("timings") is not None:
        _validate_timings(changes["timings"])


# ---- temples ----


async def get_temple(session: AsyncSession, temple_id: str) -> Temple | None:
    """The raw row, active or not — the console edits retired temples too."""
    return await session.get(Temple, temple_id)


async def list_temples(
    session: AsyncSession,
    *,
    temple_ids: frozenset[str] | None = None,
    include_inactive: bool = True,
) -> list[Temple]:
    """Directory rows for the console.

    ``temple_ids=None`` means unrestricted (an owner). An **empty** set means
    this operator manages nothing and must see nothing — the two are not the
    same, and collapsing them would hand a scoped operator the whole directory.
    """
    if temple_ids is not None and not temple_ids:
        return []
    query = select(Temple).order_by(Temple.sort_order, Temple.id)
    if temple_ids is not None:
        query = query.where(Temple.id.in_(temple_ids))
    if not include_inactive:
        query = query.where(Temple.active.is_(True))
    return list((await session.execute(query)).scalars().all())


async def create_temple(session: AsyncSession, *, temple_id: str, **fields: Any) -> Temple:
    if not _ID_RE.match(temple_id or ""):
        raise TempleAdminError("id must be lowercase letters/digits/hyphens")
    if await session.get(Temple, temple_id) is not None:
        raise TempleAdminError(f"temple {temple_id!r} already exists")
    for required in ("name", "deity", "district", "lat", "lng"):
        if fields.get(required) is None:
            raise TempleAdminError(f"{required} is required")
    _validate_temple_fields(fields)

    row = Temple(id=temple_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def update_temple(
    session: AsyncSession, *, temple_id: str, changes: dict[str, Any]
) -> Temple:
    row = await session.get(Temple, temple_id)
    if row is None:
        raise NotFound(f"unknown temple {temple_id!r}")
    _validate_temple_fields(changes)
    for key, value in changes.items():
        setattr(row, key, value)
    await session.flush()
    return row


async def set_reviewed(session: AsyncSession, *, temple_id: str, reviewed: bool) -> Temple:
    """Flip the astrologer sign-off flag (GUARDRAILS §1).

    Kept out of ``update_temple`` deliberately: the flag says an astrologer
    checked the devotional content, so the route that sets it is gated on a
    different role from the one that edits the content itself. Routing it
    through the generic PATCH would let a temple's own admin certify their own
    copy.
    """
    row = await session.get(Temple, temple_id)
    if row is None:
        raise NotFound(f"unknown temple {temple_id!r}")
    row.reviewed = reviewed
    await session.flush()
    return row


# ---- master offering catalogue ----


async def list_poojas(session: AsyncSession) -> list[Pooja]:
    return list(
        (
            await session.execute(select(Pooja).order_by(Pooja.sort_order, Pooja.key))
        ).scalars().all()
    )


async def upsert_pooja(
    session: AsyncSession, *, key: str, changes: dict[str, Any], create: bool
) -> Pooja:
    """Create or edit one master offering. Amounts are paise, like the column."""
    if "amount_paise" in changes and changes["amount_paise"] is not None:
        if changes["amount_paise"] < 0:
            raise TempleAdminError("amount_paise cannot be negative")
    if changes.get("lead_days") is not None and changes["lead_days"] < 0:
        raise TempleAdminError("lead_days cannot be negative")

    row = await session.get(Pooja, key)
    if row is None:
        if not create:
            raise NotFound(f"unknown offering {key!r}")
        if not _ID_RE.match(key or ""):
            raise TempleAdminError("key must be lowercase letters/digits/hyphens")
        if changes.get("name") is None or changes.get("amount_paise") is None:
            raise TempleAdminError("name and amount_paise are required")
        row = Pooja(key=key, **changes)
        session.add(row)
    elif create:
        raise TempleAdminError(f"offering {key!r} already exists")
    else:
        for field, value in changes.items():
            setattr(row, field, value)
    await session.flush()
    return row


# ---- per-temple overrides ----


async def list_overrides(session: AsyncSession, temple_id: str) -> list[TemplePooja]:
    return list(
        (
            await session.execute(
                select(TemplePooja)
                .where(TemplePooja.temple_id == temple_id)
                .order_by(TemplePooja.pooja_key)
            )
        ).scalars().all()
    )


async def set_override(
    session: AsyncSession,
    *,
    temple_id: str,
    pooja_key: str,
    amount_paise: int | None,
    lead_days: int | None,
    active: bool,
) -> TemplePooja:
    """Set this temple's override of one master offering.

    ``None`` means *inherit the master value* — that is the common case, and it
    must not require copying the price forward, or a later master price change
    would silently skip every temple that once edited its lead time.
    """
    if await session.get(Pooja, pooja_key) is None:
        raise NotFound(f"unknown offering {pooja_key!r}")
    if amount_paise is not None and amount_paise < 0:
        raise TempleAdminError("amount_paise cannot be negative")
    if lead_days is not None and lead_days < 0:
        raise TempleAdminError("lead_days cannot be negative")

    row = (
        await session.execute(
            select(TemplePooja).where(
                TemplePooja.temple_id == temple_id, TemplePooja.pooja_key == pooja_key
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = TemplePooja(temple_id=temple_id, pooja_key=pooja_key)
        session.add(row)
    row.amount_paise = amount_paise
    row.lead_days = lead_days
    row.active = active
    await session.flush()
    return row


async def clear_override(
    session: AsyncSession, *, temple_id: str, pooja_key: str
) -> bool:
    """Drop the override so the temple inherits the master entry again."""
    row = (
        await session.execute(
            select(TemplePooja).where(
                TemplePooja.temple_id == temple_id, TemplePooja.pooja_key == pooja_key
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    return True
