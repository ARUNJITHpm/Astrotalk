"""HTTP routes for the astrologers module — directory + free consult booking.

Browsing the directory is public (like temple suggestions). Booking and reading
one's own bookings require a login session; the owner is DERIVED from the bearer
token, never trusted from the payload (GUARDRAILS.md §4).
"""

from datetime import date as date_type
from functools import partial
from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrologers import admin as astro_admin
from app.modules.astrologers import registry
from app.modules.astrologers.schemas import (
    AstrologerActiveIn,
    AstrologerAdminIn,
    AstrologerAdminOut,
    AstrologerAdminPatch,
    AstrologerOut,
    AstrologerPhotoOut,
    AvailabilityIn,
    BookingCreate,
    BookingOut,
    BookingStatusIn,
    OpenSlot,
    OperatorBookingOut,
)
from app.modules.astrologers.service import (
    AstroBookingError,
    AstroBookingNotFound,
    AstrologersService,
)
from app.modules.identity.auth import CurrentUser
from app.platform.admin_auth import Operator, require_operator
from app.platform.db import get_session
from app.platform.storage import ImageRejected, get_storage, sniff_image

router = APIRouter(prefix="/astrologers", tags=["astrologers"])

_service = AstrologersService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# The whole directory is one editorial surface, so there is no scoped role here
# the way there is for temples — an operator either curates it or does not.
OwnerDep = Annotated[Operator, Depends(require_operator("owner"))]


# ---- directory (public). Literal paths declared before /{astrologer_id}. ----


@router.get("", response_model=list[AstrologerOut])
async def list_astrologers(
    district: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
) -> list[AstrologerOut]:
    return [AstrologerOut(**a) for a in _service.list_astrologers(district, specialty)]


@router.get(
    "/bookings/me",
    response_model=list[BookingOut],
    summary="The logged-in user's astrologer bookings",
)
async def my_bookings(user: CurrentUser, session: SessionDep) -> list[BookingOut]:
    rows = await _service.bookings_for_user(session, user.phone)
    return [BookingOut.model_validate(b) for b in rows]


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingOut,
    summary="Cancel one of your bookings",
)
async def cancel_booking(
    booking_id: int, user: CurrentUser, session: SessionDep
) -> BookingOut:
    try:
        booking = await _service.cancel(session, booking_id, user.phone)
    except AstroBookingNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AstroBookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return BookingOut.model_validate(booking)


# ---- Directory administration (console plan Part 6) ----
# Owner-only. A temple_admin runs a temple, not the astrologer directory, and
# there is no per-astrologer role: this is one editorial surface.
#
# Registered BEFORE `/{astrologer_id}` so the catch-all never claims "/manage".
# Every write ends in `_publish`, which commits and rebuilds the in-memory
# snapshot the (synchronous) readers serve — without it an operator's edit
# would not appear until the next restart.


async def _publish(session: AsyncSession) -> None:
    await session.commit()
    await registry.load(session)


def _admin_error(exc: astro_admin.AstrologerAdminError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, astro_admin.NotFound)
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(code, detail=str(exc))


@router.get(
    "/manage",
    response_model=list[AstrologerAdminOut],
    summary="Directory rows for the console (includes hidden entries)",
)
async def manage_astrologers(
    session: SessionDep,
    operator: OwnerDep,
    include_inactive: bool = Query(default=True),
) -> list[AstrologerAdminOut]:
    rows = await astro_admin.listing(session, include_inactive=include_inactive)
    return [AstrologerAdminOut.model_validate(a) for a in rows]


@router.post(
    "",
    response_model=AstrologerAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard an astrologer (owner)",
)
async def create_astrologer(
    payload: AstrologerAdminIn, session: SessionDep, operator: OwnerDep
) -> AstrologerAdminOut:
    fields = payload.model_dump()
    try:
        row = await astro_admin.create(session, astrologer_id=fields.pop("id"), **fields)
    except astro_admin.AstrologerAdminError as exc:
        raise _admin_error(exc) from exc
    await _publish(session)
    return AstrologerAdminOut.model_validate(row)


@router.patch(
    "/{astrologer_id}",
    response_model=AstrologerAdminOut,
    summary="Edit an astrologer (owner)",
)
async def update_astrologer(
    astrologer_id: str,
    payload: AstrologerAdminPatch,
    session: SessionDep,
    operator: OwnerDep,
) -> AstrologerAdminOut:
    try:
        row = await astro_admin.update(
            session,
            astrologer_id=astrologer_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except astro_admin.AstrologerAdminError as exc:
        raise _admin_error(exc) from exc
    await _publish(session)
    return AstrologerAdminOut.model_validate(row)


@router.post(
    "/{astrologer_id}/active",
    response_model=AstrologerAdminOut,
    summary="Show or hide an astrologer (owner)",
)
async def set_astrologer_active(
    astrologer_id: str,
    payload: AstrologerActiveIn,
    session: SessionDep,
    operator: OwnerDep,
) -> AstrologerAdminOut:
    """Hiding is the only removal. ``astro_bookings`` references the id as a
    plain string with no foreign key, so a real DELETE would orphan every
    consult ever booked with them. It is also how the 28 generated placeholders
    leave the directory once real practitioners arrive."""
    try:
        row = await astro_admin.update(
            session, astrologer_id=astrologer_id, changes={"active": payload.active}
        )
    except astro_admin.AstrologerAdminError as exc:
        raise _admin_error(exc) from exc
    await _publish(session)
    return AstrologerAdminOut.model_validate(row)


@router.put(
    "/{astrologer_id}/availability",
    response_model=AstrologerAdminOut,
    summary="Replace the weekly consult schedule (owner)",
)
async def replace_availability(
    astrologer_id: str,
    payload: AvailabilityIn,
    session: SessionDep,
    operator: OwnerDep,
) -> AstrologerAdminOut:
    """The windows were baked into ``seed_data._morning_windows()`` /
    ``_evening_windows()`` and could not be changed at all.

    A replacement rather than a merge: "these are my hours" is how a person
    thinks about it, and a partial update makes removing a window awkward.
    Already-booked consults are untouched — they hold an absolute instant, not
    a reference to a window — so narrowing the schedule never cancels anything;
    it only stops new bookings.
    """
    windows = [w.model_dump() for w in payload.windows]
    try:
        row = await astro_admin.update(
            session, astrologer_id=astrologer_id, changes={"availability": windows}
        )
    except astro_admin.AstrologerAdminError as exc:
        raise _admin_error(exc) from exc
    await _publish(session)
    return AstrologerAdminOut.model_validate(row)


@router.post(
    "/{astrologer_id}/photo",
    response_model=AstrologerPhotoOut,
    summary="Upload the astrologer's photo (raw image bytes as the body)",
)
async def upload_astrologer_photo(
    astrologer_id: str, request: Request, session: SessionDep, operator: OwnerDep
) -> AstrologerPhotoOut:
    if await astro_admin.get(session, astrologer_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Astrologer not found")
    data = await request.body()
    try:
        extension, content_type = sniff_image(data)
    except ImageRejected as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    storage = get_storage()
    key = f"astrologers/{astrologer_id}.{extension}"
    await to_thread.run_sync(partial(storage.put, key, data, content_type))
    await astro_admin.update(
        session, astrologer_id=astrologer_id, changes={"photo_key": key}
    )
    await _publish(session)
    return AstrologerPhotoOut(
        astrologer_id=astrologer_id, photo_key=key, url=storage.url(key)
    )


@router.get(
    "/{astrologer_id}/bookings",
    response_model=list[OperatorBookingOut],
    summary="One astrologer's consult diary (owner)",
)
async def astrologer_diary(
    astrologer_id: str,
    session: SessionDep,
    operator: OwnerDep,
    include_cancelled: bool = Query(default=True),
) -> list[OperatorBookingOut]:
    """An astrologer could not see their own diary: bookings were only ever
    queryable by the user who made them (``/bookings/me``)."""
    rows = await astro_admin.bookings_for(
        session, astrologer_id, include_cancelled=include_cancelled
    )
    return [OperatorBookingOut.model_validate(b) for b in rows]


@router.patch(
    "/bookings/{booking_id}",
    response_model=OperatorBookingOut,
    summary="Record how a consult went: cancelled, completed or no_show (owner)",
)
async def set_booking_status(
    booking_id: int,
    payload: BookingStatusIn,
    session: SessionDep,
    operator: OwnerDep,
) -> OperatorBookingOut:
    """Only the booking's own user could change a consult before this, and only
    to ``cancelled`` — so nothing ever recorded that a consult actually
    happened. Nothing may return to ``confirmed``; see ``set_booking_status``.
    """
    try:
        booking = await astro_admin.set_booking_status(
            session, booking_id=booking_id, new_status=payload.status
        )
    except astro_admin.AstrologerAdminError as exc:
        raise _admin_error(exc) from exc
    await session.commit()
    return OperatorBookingOut.model_validate(booking)


@router.get("/{astrologer_id}", response_model=AstrologerOut)
async def get_astrologer(astrologer_id: str) -> AstrologerOut:
    astro = _service.get_astrologer(astrologer_id)
    if astro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Astrologer not found")
    return AstrologerOut(**astro)


@router.get(
    "/{astrologer_id}/availability",
    response_model=list[OpenSlot],
    summary="Open consult times on one day",
)
async def availability(
    astrologer_id: str,
    session: SessionDep,
    date: date_type = Query(..., description="Calendar day (IST), YYYY-MM-DD"),
) -> list[OpenSlot]:
    if _service.get_astrologer(astrologer_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Astrologer not found")
    return [OpenSlot(**o) for o in await _service.availability(session, astrologer_id, date)]


@router.post(
    "/{astrologer_id}/book",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book an open consult time",
)
async def book(
    astrologer_id: str,
    payload: BookingCreate,
    user: CurrentUser,
    session: SessionDep,
) -> BookingOut:
    try:
        booking = await _service.book(
            session,
            astrologer_id=astrologer_id,
            user_phone=user.phone,
            starts_at=payload.starts_at,
            note=payload.note,
        )
    except AstroBookingNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AstroBookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return BookingOut.model_validate(booking)
