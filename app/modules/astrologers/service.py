"""Public service for the astrologers module.

This is the ONLY surface other modules may depend on (AGENTS.md). Chat calls
``suggest_for`` to pick a nearby experienced astrologer to (optionally) mention;
the booking page calls ``list_astrologers`` / ``availability`` / ``book``.

Split of responsibilities:
  - WHICH astrologer fits a concern/place: deterministic seed directory + a
    nearest-match rule here.
  - WHETHER to mention one, and HOW: the chat service decides (recurrence /
    direct ask) and the LLM narrates it as OPTIONAL support, never a demand,
    never through fear, never a sales pitch (GUARDRAILS.md §1).

The directory is dummy seed data; only bookings are real DB state. Consults are
free, so a booking confirms immediately. All consult windows are IST wall clock;
we store the absolute instant (UTC) and render times back in IST.
"""

from datetime import (
    UTC,
    date as date_type,
    datetime,
    time as time_type,
    timedelta,
    timezone,
)
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrologers.models import AstroBooking
from app.modules.astrologers.seed_data import SEED_ASTROLOGERS

_EARTH_RADIUS_KM = 6371.0
# India Standard Time — fixed +05:30, no DST, so a constant offset is exact.
IST = timezone(timedelta(hours=5, minutes=30))


class AstroBookingError(ValueError):
    """A booking could not be made (slot taken, unknown astrologer, …) → 409."""


class AstroBookingNotFound(AstroBookingError):
    """The referenced booking does not exist or is not the caller's → 404."""


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — plenty accurate at Kerala scale."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


def _as_utc(dt: datetime) -> datetime:
    """Normalize any datetime to a tz-aware UTC instant.

    Stored values are always written UTC-aware; a naive value (e.g. read back
    from SQLite in tests) is assumed to already be UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class AstrologersService:
    def __init__(self) -> None:
        self._astrologers = SEED_ASTROLOGERS

    # ---- directory ----

    def list_astrologers(
        self, district: str | None = None, specialty: str | None = None
    ) -> list[dict]:
        out = [dict(a) for a in self._astrologers]
        if district:
            out = [a for a in out if a["district"] == district]
        if specialty:
            out = [a for a in out if specialty in a["specialties"]]
        return out

    def get_astrologer(self, astrologer_id: str) -> dict | None:
        for a in self._astrologers:
            if a["id"] == astrologer_id:
                return dict(a)
        return None

    def suggest_for(
        self,
        *,
        concern: str | None = None,
        district: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict | None:
        """Best astrologer for the context: a specialty match narrows first, then
        the person's district, then proximity to their coordinates (else the
        highest-rated of whatever remains)."""
        candidates = list(self._astrologers)
        if concern:
            matches = [a for a in candidates if concern in a["specialties"]]
            if matches:
                candidates = matches
        if district:
            local = [a for a in candidates if a["district"] == district]
            if local:
                candidates = local
        if not candidates:
            return None
        if lat is not None and lng is not None:
            return dict(min(candidates, key=lambda a: _haversine_km(lat, lng, a["lat"], a["lng"])))
        return dict(max(candidates, key=lambda a: a["rating"]))

    # ---- availability + booking ----

    async def availability(
        self, session: AsyncSession, astrologer_id: str, day: date_type
    ) -> list[dict]:
        """Open consult start times on one IST calendar day, rendered in IST."""
        seed = self.get_astrologer(astrologer_id)
        if seed is None:
            return []
        open_slots = await self._open_slots_utc(session, seed, day)
        return sorted(
            (
                {
                    "starts_at": utc.astimezone(IST).isoformat(),
                    "duration_min": dur,
                }
                for utc, dur in open_slots.items()
            ),
            key=lambda o: o["starts_at"],
        )

    async def _open_slots_utc(
        self, session: AsyncSession, seed: dict, day: date_type
    ) -> dict[datetime, int]:
        """Map each open slot's UTC instant → its duration for ``day`` (IST)."""
        windows = [w for w in seed["availability"] if w["weekday"] == day.weekday()]
        if not windows:
            return {}
        day_start = datetime.combine(day, time_type.min, IST)
        start_utc = day_start.astimezone(UTC)
        end_utc = (day_start + timedelta(days=1)).astimezone(UTC)
        rows = (
            await session.execute(
                select(AstroBooking).where(
                    AstroBooking.astrologer_id == seed["id"],
                    AstroBooking.starts_at >= start_utc,
                    AstroBooking.starts_at < end_utc,
                    AstroBooking.status != "cancelled",
                )
            )
        ).scalars()
        taken = {_as_utc(b.starts_at) for b in rows}
        open_slots: dict[datetime, int] = {}
        for w in windows:
            start_min = _minutes(w["start"])
            end_min = _minutes(w["end"])
            dur = int(w["duration_min"])
            cursor = start_min
            while cursor + dur <= end_min:
                utc = (day_start + timedelta(minutes=cursor)).astimezone(UTC)
                if utc not in taken:
                    open_slots[utc] = dur
                cursor += dur
        return open_slots

    async def book(
        self,
        session: AsyncSession,
        *,
        astrologer_id: str,
        user_phone: str,
        starts_at: datetime,
        note: str | None = None,
    ) -> AstroBooking:
        """Reserve one open time. Free consult → confirmed immediately."""
        seed = self.get_astrologer(astrologer_id)
        if seed is None:
            raise AstroBookingNotFound("unknown astrologer")
        requested = _as_utc(starts_at)
        day = requested.astimezone(IST).date()
        open_slots = await self._open_slots_utc(session, seed, day)
        if requested not in open_slots:
            raise AstroBookingError("that time is not available")

        # A cancelled booking still owns the (astrologer, starts_at) unique row —
        # revive it instead of inserting so freed times are genuinely re-bookable.
        existing = (
            await session.execute(
                select(AstroBooking).where(
                    AstroBooking.astrologer_id == astrologer_id,
                    AstroBooking.starts_at == requested,
                )
            )
        ).scalars().first()
        if existing is not None:
            existing.user_phone = user_phone
            existing.duration_min = open_slots[requested]
            existing.status = "confirmed"
            existing.note = note
            booking = existing
        else:
            booking = AstroBooking(
                astrologer_id=astrologer_id,
                user_phone=user_phone,
                starts_at=requested,
                duration_min=open_slots[requested],
                status="confirmed",
                note=note,
            )
            session.add(booking)
        await session.flush()
        return booking

    async def cancel(
        self, session: AsyncSession, booking_id: int, user_phone: str
    ) -> AstroBooking:
        booking = await session.get(AstroBooking, booking_id)
        if booking is None or booking.user_phone != user_phone:
            raise AstroBookingNotFound("booking not found")
        if booking.status == "cancelled":
            raise AstroBookingError("booking is already cancelled")
        booking.status = "cancelled"
        await session.flush()
        return booking

    async def bookings_for_user(
        self, session: AsyncSession, user_phone: str
    ) -> list[AstroBooking]:
        return list(
            (
                await session.execute(
                    select(AstroBooking)
                    .where(AstroBooking.user_phone == user_phone)
                    .order_by(AstroBooking.starts_at.desc())
                )
            ).scalars().all()
        )


def _minutes(hhmm: str) -> int:
    t = time_type.fromisoformat(hhmm)
    return t.hour * 60 + t.minute
