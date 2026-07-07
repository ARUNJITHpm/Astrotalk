"""Booking internals for white-label orgs (GROWTH_PLAN.md Part 4b).

Weekly availability windows → concrete open start times → a booking that is
``pending`` until its payment captures (free consults confirm instantly).
Payment rides commerce's order flow (Part 5a); confirmation is reconciled
lazily against the payment status, so no webhook coupling between modules.
Times are the org's local wall clock (IST audience) stored naive.
"""

from datetime import UTC, date as date_type, datetime, time as time_type, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs.models import AvailabilitySlot, Booking, Org
from app.platform import metrics
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


class BookingError(ValueError):
    pass


async def add_slot(
    session: AsyncSession,
    *,
    org_id: int,
    weekday: int,
    start: str,
    end: str,
    duration_min: int = 30,
    price_paise: int = 0,
) -> AvailabilitySlot:
    """One weekly window, e.g. weekday=5, 10:00–13:00, 30-minute consults."""
    try:
        start_t = time_type.fromisoformat(start)
        end_t = time_type.fromisoformat(end)
    except ValueError:
        raise BookingError("start/end must be HH:MM")
    start_min = start_t.hour * 60 + start_t.minute
    end_min = end_t.hour * 60 + end_t.minute
    if not 0 <= weekday <= 6:
        raise BookingError("weekday is 0 (Mon) … 6 (Sun)")
    if end_min - start_min < duration_min or duration_min < 10:
        raise BookingError("window shorter than one appointment")
    if price_paise < 0:
        raise BookingError("price cannot be negative")
    slot = AvailabilitySlot(
        org_id=org_id,
        weekday=weekday,
        start_min=start_min,
        end_min=end_min,
        duration_min=duration_min,
        price_paise=price_paise,
    )
    session.add(slot)
    await session.flush()
    return slot


async def list_slots(session: AsyncSession, org_id: int) -> list[AvailabilitySlot]:
    return list(
        (
            await session.execute(
                select(AvailabilitySlot)
                .where(AvailabilitySlot.org_id == org_id, AvailabilitySlot.active.is_(True))
                .order_by(AvailabilitySlot.weekday, AvailabilitySlot.start_min)
            )
        ).scalars().all()
    )


async def availability(
    session: AsyncSession, org_id: int, day: date_type
) -> list[dict]:
    """Open appointment start times for one calendar day."""
    slots = [s for s in await list_slots(session, org_id) if s.weekday == day.weekday()]
    if not slots:
        return []
    day_start = datetime.combine(day, time_type.min)
    day_end = day_start + timedelta(days=1)
    taken = {
        b.starts_at
        for b in (
            await session.execute(
                select(Booking).where(
                    Booking.org_id == org_id,
                    Booking.starts_at >= day_start,
                    Booking.starts_at < day_end,
                    Booking.status != "cancelled",
                )
            )
        ).scalars()
    }
    open_times: list[dict] = []
    for slot in slots:
        cursor = slot.start_min
        while cursor + slot.duration_min <= slot.end_min:
            starts_at = day_start + timedelta(minutes=cursor)
            if starts_at not in taken:
                open_times.append(
                    {
                        "starts_at": starts_at.isoformat(),
                        "duration_min": slot.duration_min,
                        "price_paise": slot.price_paise,
                    }
                )
            cursor += slot.duration_min
    return sorted(open_times, key=lambda o: o["starts_at"])


async def book(
    session: AsyncSession, *, org: Org, user_id: int, starts_at: datetime
) -> tuple[Booking, dict | None]:
    """Reserve one open time. Returns (booking, checkout order | None).

    Paid slots come back ``pending`` with a commerce order for the client
    checkout; free slots confirm instantly.
    """
    if starts_at.tzinfo is not None:  # normalize to the naive local convention
        starts_at = starts_at.astimezone(UTC).replace(tzinfo=None)
    day_open = await availability(session, org.id, starts_at.date())
    match = next((o for o in day_open if o["starts_at"] == starts_at.isoformat()), None)
    if match is None:
        raise BookingError("that time is not available")

    order = None
    booking = Booking(
        org_id=org.id,
        user_id=user_id,
        starts_at=starts_at,
        duration_min=match["duration_min"],
        price_paise=match["price_paise"],
        status="confirmed" if match["price_paise"] == 0 else "pending",
    )
    if match["price_paise"] > 0:
        from app.modules.commerce.service import CommerceService

        order = await CommerceService().create_custom_order(
            session,
            user_id=user_id,
            product=f"booking:{org.handle}",
            amount_paise=match["price_paise"],
            org_id=org.id,
        )
        booking.razorpay_order_id = order["order_id"]
    session.add(booking)
    await session.flush()
    metrics.increment("orgs.bookings_created")
    if booking.status == "confirmed":
        await _notify_confirmation(session, org, booking)
    return booking, order


async def reconcile(session: AsyncSession, org: Org, booking: Booking) -> Booking:
    """Confirm a pending booking once its payment captured (lazy, idempotent)."""
    if booking.status == "pending" and booking.razorpay_order_id:
        from app.modules.commerce.service import CommerceService

        status = await CommerceService().get_payment_status(
            session, booking.razorpay_order_id
        )
        if status == "paid":
            booking.status = "confirmed"
            await session.flush()
            metrics.increment("orgs.bookings_confirmed")
            await _notify_confirmation(session, org, booking)
        elif status == "failed":
            booking.status = "cancelled"
            await session.flush()
    return booking


async def _notify_confirmation(session: AsyncSession, org: Org, booking: Booking) -> None:
    """Best-effort WhatsApp confirmation — consent + cap enforced by whatsapp."""
    try:
        from app.modules.identity.service import IdentityService
        from app.modules.whatsapp.service import WhatsappService

        user = await IdentityService().get_user(session, booking.user_id)
        if user is None:
            return
        when = booking.starts_at.strftime("%d-%m-%Y %H:%M")
        await WhatsappService().send_template(
            session,
            user.phone,
            f"✅ {org.name}: നിങ്ങളുടെ കൺസൾട്ടേഷൻ ബുക്ക് ചെയ്തു — {when}. "
            "മാറ്റം വേണമെങ്കിൽ ഈ പേജിൽ നിന്ന് cancel ചെയ്യാം.",
        )
    except Exception:  # pragma: no cover - notification must never block booking
        logger.warning("orgs: booking confirmation notify failed", exc_info=True)


async def get_booking(session: AsyncSession, org_id: int, booking_id: int) -> Booking | None:
    booking = await session.get(Booking, booking_id)
    if booking is None or booking.org_id != org_id:
        return None
    return booking


async def cancel(session: AsyncSession, booking: Booking) -> Booking:
    if booking.status in ("completed", "cancelled"):
        raise BookingError(f"cannot cancel a {booking.status} booking")
    booking.status = "cancelled"
    await session.flush()
    metrics.increment("orgs.bookings_cancelled")
    return booking


async def bookings_for_org(session: AsyncSession, org_id: int) -> list[Booking]:
    return list(
        (
            await session.execute(
                select(Booking)
                .where(Booking.org_id == org_id)
                .order_by(Booking.starts_at.desc())
            )
        ).scalars().all()
    )


async def bookings_for_user(
    session: AsyncSession, org_id: int, user_id: int
) -> list[Booking]:
    return list(
        (
            await session.execute(
                select(Booking)
                .where(Booking.org_id == org_id, Booking.user_id == user_id)
                .order_by(Booking.starts_at.desc())
            )
        ).scalars().all()
    )
