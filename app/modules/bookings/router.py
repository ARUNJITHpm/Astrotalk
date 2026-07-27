"""HTTP routes for the bookings module (NITHARA-BUILD-PLAN Part 1).

  - POST /bookings        — book a pooja (Razorpay order; ₹15 service fee).
  - GET  /bookings        — the caller's bookings, state reconciled to ok|wait.
  - /bookings/queue/…     — the OPERATOR surface (console plan Part 7): the
    queue, one booking's detail, status and notes, the temple worklist and the
    settlement export. Scoped: a temple_admin sees only their own temples.

Payment capture reuses commerce: the returned ``order_id`` goes to Razorpay
checkout on device, or to POST /commerce/orders/{id}/mock-pay in dev.
"""

import csv
import io
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings import admin as booking_admin
from app.modules.bookings.models import PoojaBooking
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingNoteIn,
    BookingOut,
    BookingSettingsIn,
    BookingStatusIn,
    OperatorBookingDetail,
    OperatorBookingPage,
    OperatorBookingRow,
    Worklist,
    WorklistGroup,
    WorklistItem,
)
from app.modules.bookings.service import (
    BookingsService,
    UnknownPooja,
    UnknownTemple,
    service_fee_paise,
)
from app.modules.commerce.service import CommerceService
from app.modules.identity.auth import CurrentUser
from app.modules.identity.service import IdentityService
from app.platform.admin_auth import Operator, require_operator
from app.platform.db import get_session

router = APIRouter(prefix="/bookings", tags=["bookings"])

_service = BookingsService()
_commerce = CommerceService()
_identity = IdentityService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# Query filters are declared Annotated rather than as call-in-default values —
# same behaviour, and it keeps `Query(...)` out of function signatures' defaults.
OptStr = Annotated[str | None, Query()]
OptDate = Annotated[date_type | None, Query()]
# Owners and temple admins both work the queue; the scope filter is what makes
# that safe, and it is applied in the query rather than after it.
QueueDep = Annotated[Operator, Depends(require_operator("owner", "temple_admin"))]
OwnerDep = Annotated[Operator, Depends(require_operator("owner"))]


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate, user: CurrentUser, session: SessionDep
) -> dict:
    try:
        out = await _service.create(session, user_id=user.id, payload=payload)
    except UnknownTemple as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Unknown temple"
        ) from exc
    except UnknownPooja as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown pooja") from exc
    await session.commit()
    return out


@router.get("", response_model=list[BookingOut])
async def list_bookings(user: CurrentUser, session: SessionDep) -> list[dict]:
    out = await _service.list_for_user(session, user.id)
    await session.commit()  # persist any states reconciled to ok
    return out


# ---- Operator queue (console plan Part 7) ----
# Everything below is under /bookings/queue rather than /bookings/{id}, so no
# operator path can ever be mistaken for a devotee-facing one, and there is no
# catch-all to order around.


def _admin_error(exc: booking_admin.BookingAdminError) -> HTTPException:
    if isinstance(exc, booking_admin.NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, booking_admin.TransitionRefused):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


async def _resolve_user_filter(session: AsyncSession, phone: str | None) -> int | None:
    """A phone filter, turned into a user id through identity's public service.

    Returns ``-1`` for a phone nobody owns rather than ``None``: None means "no
    filter", and an unmatched search must return nothing, not everything.
    """
    if not phone:
        return None
    user = await _identity.get_user_by_phone(session, phone)
    return user.id if user else -1


@router.get(
    "/queue",
    response_model=OperatorBookingPage,
    summary="The booking queue — filtered, paged, and scoped to your temples",
)
async def booking_queue(
    session: SessionDep,
    operator: QueueDep,
    temple_id: OptStr = None,
    state: Annotated[
        str | None, Query(description="wait|ok|completed|cancelled|refunded")
    ] = None,
    pooja_key: OptStr = None,
    ref: OptStr = None,
    phone: Annotated[str | None, Query(description="the devotee's mobile")] = None,
    booked_from: OptDate = None,
    booked_to: OptDate = None,
    perform_from: OptDate = None,
    perform_to: OptDate = None,
    limit: Annotated[int, Query(ge=1, le=booking_admin.MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OperatorBookingPage:
    try:
        total, rows = await booking_admin.queue(
            session,
            temple_ids=operator.visible_temple_ids(),
            temple_id=temple_id,
            state=state,
            pooja_key=pooja_key,
            ref=ref,
            user_id=await _resolve_user_filter(session, phone),
            booked_from=booked_from,
            booked_to=booked_to,
            perform_from=perform_from,
            perform_to=perform_to,
            limit=limit,
            offset=offset,
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    return OperatorBookingPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[OperatorBookingRow.model_validate(b) for b in rows],
    )


@router.get(
    "/queue/export.csv",
    summary="Settlement export of the current filter (amounts in paise)",
)
async def export_bookings(
    session: SessionDep,
    operator: QueueDep,
    temple_id: OptStr = None,
    state: OptStr = None,
    booked_from: OptDate = None,
    booked_to: OptDate = None,
) -> Response:
    try:
        _, rows = await booking_admin.queue(
            session,
            temple_ids=operator.visible_temple_ids(),
            temple_id=temple_id,
            state=state,
            booked_from=booked_from,
            booked_to=booked_to,
            # Not a page: an accountant reconciling a month wants every row the
            # filter matched, and a CSV silently cut at 200 would be worse than
            # no export at all.
            limit=booking_admin.MAX_EXPORT,
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(booking_admin.csv_rows(rows))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bookings.csv"'},
    )


@router.get(
    "/queue/worklist",
    response_model=Worklist,
    summary="What the temple performs on a day, grouped by star",
)
async def booking_worklist(
    session: SessionDep,
    operator: QueueDep,
    temple_id: OptStr = None,
    day: Annotated[
        date_type | None, Query(description="defaults to every dated booking")
    ] = None,
) -> Worklist:
    rows, undated = await booking_admin.worklist(
        session,
        temple_ids=operator.visible_temple_ids(),
        temple_id=temple_id,
        day=day,
    )
    return Worklist(
        temple_id=temple_id,
        day=day,
        total=len(rows),
        undated=undated,
        groups=[
            WorklistGroup(nak=nak, items=[WorklistItem.model_validate(b) for b in items])
            for nak, items in booking_admin.group_by_nakshatram(rows)
        ],
    )


async def _detail(session: AsyncSession, booking: PoojaBooking) -> OperatorBookingDetail:
    """Join one booking to its devotee and its payment.

    Both come through the other modules' public services — this module never
    reads their tables (AGENTS.md).
    """
    user = await _identity.get_user(session, booking.user_id)
    payment_status = (
        await _commerce.get_payment_status(session, booking.razorpay_order_id)
        if booking.razorpay_order_id
        else None
    )
    return OperatorBookingDetail(
        **OperatorBookingRow.model_validate(booking).model_dump(),
        user_id=booking.user_id,
        user_name=user.name if user else "",
        user_phone=user.phone if user else "",
        razorpay_order_id=booking.razorpay_order_id,
        payment_status=payment_status,
        total_paise=booking.amount_paise + booking.service_fee_paise,
    )


@router.get(
    "/queue/by-ref/{ref}",
    response_model=OperatorBookingDetail,
    summary="Look a booking up by the ref a devotee reads out",
)
async def booking_by_ref(
    ref: str, session: SessionDep, operator: QueueDep
) -> OperatorBookingDetail:
    try:
        booking = await booking_admin.get_one(
            session, temple_ids=operator.visible_temple_ids(), ref=ref
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    return await _detail(session, booking)


@router.get(
    "/queue/{booking_id}",
    response_model=OperatorBookingDetail,
    summary="One booking, joined to the devotee and the payment",
)
async def booking_detail(
    booking_id: int, session: SessionDep, operator: QueueDep
) -> OperatorBookingDetail:
    try:
        booking = await booking_admin.get_one(
            session, temple_ids=operator.visible_temple_ids(), booking_id=booking_id
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    return await _detail(session, booking)


@router.patch(
    "/queue/{booking_id}/status",
    response_model=OperatorBookingDetail,
    summary="Mark a booking completed, cancelled or refunded",
)
async def set_booking_status(
    booking_id: int, payload: BookingStatusIn, session: SessionDep, operator: QueueDep
) -> OperatorBookingDetail:
    """No cancel path existed for poojas at all — for an operator or a user.

    ``refunded`` is **bookkeeping only**: it records that a refund was issued in
    the Razorpay dashboard. Nothing here moves money. Wiring a real refund call
    touches payments and is gated on human approval (AGENTS.md), so this stops
    at recording the fact rather than pretending to perform it.
    """
    try:
        booking = await booking_admin.get_one(
            session, temple_ids=operator.visible_temple_ids(), booking_id=booking_id
        )
        booking = await booking_admin.set_state(
            session, booking=booking, new_state=payload.status, note=payload.note
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    detail = await _detail(session, booking)
    await session.commit()
    return detail


@router.patch(
    "/queue/{booking_id}/note",
    response_model=OperatorBookingDetail,
    summary="Leave a note on a booking",
)
async def set_booking_note(
    booking_id: int, payload: BookingNoteIn, session: SessionDep, operator: QueueDep
) -> OperatorBookingDetail:
    try:
        booking = await booking_admin.get_one(
            session, temple_ids=operator.visible_temple_ids(), booking_id=booking_id
        )
        booking = await booking_admin.set_note(session, booking=booking, note=payload.note)
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    detail = await _detail(session, booking)
    await session.commit()
    return detail


@router.get("/settings", summary="The booking settings an operator may change")
async def get_booking_settings(session: SessionDep, operator: QueueDep) -> dict:
    return {"service_fee_paise": await service_fee_paise(session)}


@router.put("/settings", summary="Set the service fee (owner)")
async def set_booking_settings(
    payload: BookingSettingsIn, session: SessionDep, operator: OwnerDep
) -> dict:
    """The ₹15 fee was a Python constant until Part 3 gave it a row; this is the
    first thing that can write it. Owner-only — it applies to every temple."""
    try:
        paise = await booking_admin.set_service_fee(
            session, paise=payload.service_fee_paise
        )
    except booking_admin.BookingAdminError as exc:
        raise _admin_error(exc) from exc
    await session.commit()
    return {"service_fee_paise": paise}
