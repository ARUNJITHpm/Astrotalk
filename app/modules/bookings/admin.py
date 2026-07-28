"""The operator view of pooja bookings (console plan Part 7).

The biggest gap in the back office: before this, operators could see **nothing**.
The module had exactly two routes and both were hard-scoped to the caller, so
the only way to answer "what are we performing tomorrow" was to open the
database.

Scope is the load-bearing part of this file. A ``temple_admin`` must see only
their own temples' bookings, and every query here takes a ``temple_ids``
argument that is threaded from ``Operator.visible_temple_ids()``. ``None`` means
unrestricted; an **empty set** means this operator manages nothing and must see
nothing. Collapsing the two would hand a scoped operator the whole queue, which
is the single most damaging mistake available in this module.

Cross-module rule (AGENTS.md): commerce and identity are reached through their
public services, never their tables.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta, timezone
from datetime import date as date_type
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import (
    BOOKING_STATES,
    OPERATOR_TRANSITIONS,
    BookingSettings,
    PoojaBooking,
)

MAX_PAGE = 200
# The settlement export is not a page of a list — an accountant reconciling a
# month wants every row the filter matched, and a CSV silently cut off at the
# page size would be worse than no export at all. Still bounded, because an
# unbounded query against a growing table eventually takes the process with it.
MAX_EXPORT = 5000

# India Standard Time, fixed +05:30 and no DST, so a constant offset is exact.
IST = timezone(timedelta(hours=5, minutes=30))


def _ist_day_bounds(day: date_type) -> tuple[datetime, datetime]:
    """The UTC instants that bracket one IST calendar day.

    Date filters are compared against these rather than against the stored
    timestamp's own date. `created_at` is UTC, and an operator in Kerala asking
    for "the 21st" means the 21st in IST — a booking made at 03:00 IST on the
    21st is 21:30 UTC on the *20th*, and a naive comparison files it under the
    wrong day. Doing the conversion in Python also keeps the SQL portable:
    tests run on SQLite, production is Postgres.
    """
    start = datetime.combine(day, time.min, IST)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


class BookingAdminError(ValueError):
    """A rejected operator action."""


class NotFound(BookingAdminError):
    """No booking with that id or ref — or none this operator may see."""


class TransitionRefused(BookingAdminError):
    """The state machine does not allow that move."""


def _scoped(query: Any, temple_ids: frozenset[str] | None) -> Any:
    """Restrict a query to the temples this operator manages."""
    if temple_ids is None:
        return query
    if not temple_ids:
        # A false query, not an unfiltered one. `in_(())` is valid SQL and this
        # is the branch that matters most: an operator with no grants sees zero
        # rows rather than every row.
        return query.where(PoojaBooking.temple_id.in_(()))
    return query.where(PoojaBooking.temple_id.in_(temple_ids))


async def queue(
    session: AsyncSession,
    *,
    temple_ids: frozenset[str] | None,
    temple_id: str | None = None,
    state: str | None = None,
    pooja_key: str | None = None,
    ref: str | None = None,
    user_id: int | None = None,
    booked_from: date_type | None = None,
    booked_to: date_type | None = None,
    perform_from: date_type | None = None,
    perform_to: date_type | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[PoojaBooking]]:
    """A filtered, paged slice of the queue plus the total before paging."""
    if state is not None and state not in BOOKING_STATES:
        raise BookingAdminError(f"unknown state: {state}")
    limit = max(1, min(limit, MAX_EXPORT))
    offset = max(0, offset)

    conditions = []
    if temple_id:
        conditions.append(PoojaBooking.temple_id == temple_id)
    if state:
        conditions.append(PoojaBooking.state == state)
    if pooja_key:
        conditions.append(PoojaBooking.pooja_key == pooja_key)
    if ref:
        conditions.append(PoojaBooking.ref == ref.strip().upper())
    if user_id is not None:
        conditions.append(PoojaBooking.user_id == user_id)
    if booked_from:
        conditions.append(PoojaBooking.created_at >= _ist_day_bounds(booked_from)[0])
    if booked_to:
        # Inclusive of the whole day: everything before IST midnight after it.
        conditions.append(PoojaBooking.created_at < _ist_day_bounds(booked_to)[1])
    if perform_from:
        conditions.append(PoojaBooking.perform_on >= perform_from)
    if perform_to:
        conditions.append(PoojaBooking.perform_on <= perform_to)

    base = _scoped(select(PoojaBooking), temple_ids)
    for condition in conditions:
        base = base.where(condition)

    total = (
        await session.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(PoojaBooking.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return total, list(rows)


async def get_one(
    session: AsyncSession,
    *,
    temple_ids: frozenset[str] | None,
    booking_id: int | None = None,
    ref: str | None = None,
) -> PoojaBooking:
    """One booking by id or by human ref, within this operator's scope.

    A booking outside the scope raises ``NotFound``, not a permission error:
    the operator has no way to know it exists, and telling them a ref is
    "forbidden rather than unknown" is itself a leak — refs are short and
    guessable (``NT`` + six digits).
    """
    query = _scoped(select(PoojaBooking), temple_ids)
    if booking_id is not None:
        query = query.where(PoojaBooking.id == booking_id)
    elif ref:
        query = query.where(PoojaBooking.ref == ref.strip().upper())
    else:
        raise BookingAdminError("a booking id or ref is required")

    row = (await session.execute(query)).scalars().first()
    if row is None:
        raise NotFound("booking not found")
    return row


async def set_state(
    session: AsyncSession,
    *,
    booking: PoojaBooking,
    new_state: str,
    note: str = "",
) -> PoojaBooking:
    """Move a booking through the operator state machine.

    ``refunded`` records that a refund was issued **in the Razorpay dashboard**;
    nothing here moves money. Wiring an actual refund call touches payments and
    is gated on human approval (AGENTS.md), so this deliberately stops at
    bookkeeping rather than pretending.
    """
    if new_state not in BOOKING_STATES:
        raise BookingAdminError(f"unknown state: {new_state}")
    if new_state == booking.state:
        if note:
            booking.operator_note = note
            await session.flush()
        return booking  # idempotent
    allowed = OPERATOR_TRANSITIONS.get(booking.state, frozenset())
    if new_state not in allowed:
        raise TransitionRefused(
            f"a {booking.state} booking cannot become {new_state}"
            + (f"; allowed: {', '.join(sorted(allowed))}" if allowed else "")
        )
    booking.state = new_state
    if note:
        booking.operator_note = note
    await session.flush()
    return booking


async def set_note(
    session: AsyncSession, *, booking: PoojaBooking, note: str
) -> PoojaBooking:
    booking.operator_note = note
    await session.flush()
    return booking


async def set_perform_on(
    session: AsyncSession, *, booking: PoojaBooking, perform_on: date_type | None
) -> PoojaBooking:
    """Give a booking the date it is to be performed on, or take it away.

    ``worklist`` reports how many bookings carry no date, because they appear on
    no sheet at any date and a silently omitted booking is a pooja nobody
    performs. Until console plan Part 11 nothing could act on that count: the
    field is set by the app at booking time and ``perform_on`` was optional, so
    every booking made before it existed was permanently unschedulable.

    ``when_label`` is deliberately left alone. It is the free text the devotee
    was shown, and rewriting it here would make the console's record disagree
    with the confirmation they are holding.
    """
    booking.perform_on = perform_on
    await session.flush()
    return booking


async def worklist(
    session: AsyncSession,
    *,
    temple_ids: frozenset[str] | None,
    temple_id: str | None = None,
    day: date_type | None = None,
) -> tuple[list[PoojaBooking], int]:
    """What the temple performs on ``day``, plus how many bookings have no date.

    Only paid and performed bookings appear: an abandoned `wait` order is not
    work, and a cancelled one is the opposite of work.

    The undated count is reported rather than hidden. `when_label` is free
    display text the client composes, so bookings made before `perform_on`
    existed cannot be placed on any day — a sheet that quietly omitted them
    would be worse than one that says how many it is missing.
    """
    performable = PoojaBooking.state.in_(("ok", "completed"))
    base = _scoped(select(PoojaBooking), temple_ids).where(performable)
    if temple_id:
        base = base.where(PoojaBooking.temple_id == temple_id)

    dated = base.where(PoojaBooking.perform_on == day) if day else base.where(
        PoojaBooking.perform_on.is_not(None)
    )
    rows = (
        await session.execute(dated.order_by(PoojaBooking.member_nak, PoojaBooking.ref))
    ).scalars().all()

    undated = (
        await session.execute(
            select(func.count()).select_from(
                base.where(PoojaBooking.perform_on.is_(None)).subquery()
            )
        )
    ).scalar_one()
    return list(rows), undated


def group_by_nakshatram(
    rows: Sequence[PoojaBooking],
) -> list[tuple[int | None, list[PoojaBooking]]]:
    """Group a worklist by star, with the unnamed ones last."""
    groups: dict[int | None, list[PoojaBooking]] = {}
    for row in rows:
        groups.setdefault(row.member_nak, []).append(row)
    return sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))


async def set_service_fee(session: AsyncSession, *, paise: int) -> int:
    """The ₹15 fee was a Python constant until Part 3 gave it a row; this is the
    first thing that can actually write it."""
    if paise < 0:
        raise BookingAdminError("the service fee cannot be negative")
    row = await session.get(BookingSettings, 1)
    if row is None:
        row = BookingSettings(id=1, service_fee_paise=paise)
        session.add(row)
    else:
        row.service_fee_paise = paise
    await session.flush()
    return row.service_fee_paise


def csv_rows(bookings: Sequence[PoojaBooking]) -> list[list[str]]:
    """Settlement export. Money is emitted in **paise**, the stored figure —
    a rupee rendering here would be the one place a reconciliation is done
    against a rounded number.
    """
    header = [
        "ref", "created_at", "perform_on", "temple_id", "pooja_key", "pooja_name",
        "member_name", "member_nak", "amount_paise", "service_fee_paise",
        "total_paise", "state", "razorpay_order_id", "operator_note",
    ]
    out = [header]
    for b in bookings:
        out.append([
            b.ref,
            b.created_at.isoformat() if b.created_at else "",
            b.perform_on.isoformat() if b.perform_on else "",
            b.temple_id,
            b.pooja_key,
            b.pooja_name,
            b.member_name,
            "" if b.member_nak is None else str(b.member_nak),
            str(b.amount_paise),
            str(b.service_fee_paise),
            str(b.amount_paise + b.service_fee_paise),
            b.state,
            b.razorpay_order_id or "",
            b.operator_note or "",
        ])
    return out
