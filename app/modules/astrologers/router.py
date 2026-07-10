"""HTTP routes for the astrologers module — directory + free consult booking.

Browsing the directory is public (like temple suggestions). Booking and reading
one's own bookings require a login session; the owner is DERIVED from the bearer
token, never trusted from the payload (GUARDRAILS.md §4).
"""

from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrologers.schemas import (
    AstrologerOut,
    BookingCreate,
    BookingOut,
    OpenSlot,
)
from app.modules.astrologers.service import (
    AstroBookingError,
    AstroBookingNotFound,
    AstrologersService,
)
from app.modules.identity.auth import CurrentUser
from app.platform.db import get_session

router = APIRouter(prefix="/astrologers", tags=["astrologers"])

_service = AstrologersService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
