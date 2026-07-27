"""Operator writes against the astrologer directory (console plan Part 6).

Data access and validation; the routes live in router.py.

All 28 seeded entries are generated placeholders — `id == name ==
"{district}-astro-{n}"`, deterministic experience and rating — and the app
already refuses to render them. This module is how a real practitioner gets
onboarded, which until Part 2 was impossible without a code change.

Owner-only at the route layer. A `temple_admin` runs a temple, not the
astrologer directory, and there is no per-astrologer role: the directory is a
single editorial surface.
"""

import re
from datetime import time as time_type
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrologers.models import TERMINAL_STATES, AstroBooking, Astrologer

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")

# Fields an operator may set. Listed explicitly rather than accepting **changes
# so a payload cannot reach a column nobody meant to expose.
ASTROLOGER_FIELDS = frozenset({
    "name", "name_ml", "district", "town", "lat", "lng", "specialties",
    "experience_years", "languages", "rating", "bio_ml", "availability",
    "active", "price_paise_per_min", "photo_key", "sort_order",
})


class AstrologerAdminError(ValueError):
    """A rejected write — unknown id, malformed window, out-of-range number."""


class NotFound(AstrologerAdminError):
    """The row the operator addressed does not exist."""


class TransitionRefused(AstrologerAdminError):
    """The requested booking status change is not one the state machine allows."""


def _validate_availability(windows: Any) -> None:
    """Weekly consult windows: ``{weekday, start, end, duration_min}``.

    ``_open_slots_utc`` (service.py) walks these to generate bookable slots, so
    a malformed entry does not fail here — it fails inside every availability
    and booking call for that astrologer. Validate at the write.
    """
    if not isinstance(windows, list):
        raise AstrologerAdminError("availability must be a list of windows")
    for w in windows:
        if not isinstance(w, dict):
            raise AstrologerAdminError("each window must be an object")
        missing = {"weekday", "start", "end", "duration_min"} - set(w)
        if missing:
            raise AstrologerAdminError(f"window is missing: {', '.join(sorted(missing))}")
        if not isinstance(w["weekday"], int) or not 0 <= w["weekday"] <= 6:
            raise AstrologerAdminError("weekday must be 0 (Mon) to 6 (Sun)")
        try:
            start = time_type.fromisoformat(w["start"])
            end = time_type.fromisoformat(w["end"])
        except (TypeError, ValueError) as exc:
            raise AstrologerAdminError("start and end must be HH:MM") from exc
        duration = w["duration_min"]
        if not isinstance(duration, int) or duration <= 0:
            raise AstrologerAdminError("duration_min must be a positive whole number")
        span = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
        if span <= 0:
            raise AstrologerAdminError("a window must end after it starts")
        if span < duration:
            # Otherwise the window silently yields zero slots and the astrologer
            # looks fully booked forever.
            raise AstrologerAdminError("the window is shorter than one consult")


def _validate_fields(changes: dict[str, Any]) -> None:
    unknown = set(changes) - ASTROLOGER_FIELDS
    if unknown:
        raise AstrologerAdminError(f"cannot set: {', '.join(sorted(unknown))}")
    if "lat" in changes and not (-90 <= changes["lat"] <= 90):
        raise AstrologerAdminError("lat must be between -90 and 90")
    if "lng" in changes and not (-180 <= changes["lng"] <= 180):
        raise AstrologerAdminError("lng must be between -180 and 180")
    if "rating" in changes and not (0 <= changes["rating"] <= 5):
        raise AstrologerAdminError("rating must be between 0 and 5")
    if "experience_years" in changes and changes["experience_years"] < 0:
        raise AstrologerAdminError("experience_years cannot be negative")
    if "price_paise_per_min" in changes and changes["price_paise_per_min"] < 0:
        raise AstrologerAdminError("price_paise_per_min cannot be negative")
    if changes.get("availability") is not None:
        _validate_availability(changes["availability"])


# ---- directory ----


async def get(session: AsyncSession, astrologer_id: str) -> Astrologer | None:
    """The raw row, active or not — the console edits hidden entries too."""
    return await session.get(Astrologer, astrologer_id)


async def listing(
    session: AsyncSession, *, include_inactive: bool = True
) -> list[Astrologer]:
    query = select(Astrologer).order_by(Astrologer.sort_order, Astrologer.id)
    if not include_inactive:
        query = query.where(Astrologer.active.is_(True))
    return list((await session.execute(query)).scalars().all())


async def create(
    session: AsyncSession, *, astrologer_id: str, **fields: Any
) -> Astrologer:
    if not _ID_RE.match(astrologer_id or ""):
        raise AstrologerAdminError("id must be lowercase letters/digits/hyphens")
    if await session.get(Astrologer, astrologer_id) is not None:
        raise AstrologerAdminError(f"astrologer {astrologer_id!r} already exists")
    for required in ("name", "district", "lat", "lng"):
        if fields.get(required) is None:
            raise AstrologerAdminError(f"{required} is required")
    _validate_fields(fields)

    row = Astrologer(id=astrologer_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def update(
    session: AsyncSession, *, astrologer_id: str, changes: dict[str, Any]
) -> Astrologer:
    row = await session.get(Astrologer, astrologer_id)
    if row is None:
        raise NotFound(f"unknown astrologer {astrologer_id!r}")
    _validate_fields(changes)
    for key, value in changes.items():
        setattr(row, key, value)
    await session.flush()
    return row


# ---- the diary ----


async def bookings_for(
    session: AsyncSession,
    astrologer_id: str,
    *,
    include_cancelled: bool = True,
) -> list[AstroBooking]:
    """One astrologer's consult diary. Nothing could read this before Part 6 —
    bookings were only ever queryable by the user who made them."""
    query = (
        select(AstroBooking)
        .where(AstroBooking.astrologer_id == astrologer_id)
        .order_by(AstroBooking.starts_at.desc())
    )
    if not include_cancelled:
        query = query.where(AstroBooking.status != "cancelled")
    return list((await session.execute(query)).scalars().all())


async def set_booking_status(
    session: AsyncSession, *, booking_id: int, new_status: str
) -> AstroBooking:
    """Move a consult to a terminal state, or correct which terminal it is.

    Nothing may return to ``confirmed``. ``astro_bookings`` has a unique
    constraint on (astrologer_id, starts_at) and a cancelled row keeps holding
    that slot, so reviving one would re-seat a consult that somebody else may
    have booked in the meantime — the user booking path revives deliberately,
    through ``service.book``, which checks the slot is still open first.
    """
    if new_status not in TERMINAL_STATES:
        raise TransitionRefused(
            f"an operator may only set: {', '.join(sorted(TERMINAL_STATES))}"
        )
    booking = await session.get(AstroBooking, booking_id)
    if booking is None:
        raise NotFound("unknown booking")
    if booking.status == new_status:
        return booking  # idempotent
    booking.status = new_status
    await session.flush()
    return booking
