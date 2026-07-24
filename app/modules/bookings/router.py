"""HTTP routes for the bookings module (NITHARA-BUILD-PLAN Part 1).

  - POST /bookings  — book a pooja (opens a Razorpay order; ₹15 service fee).
  - GET  /bookings  — the caller's bookings, state reconciled to ok|wait.

Payment capture reuses commerce: the returned ``order_id`` goes to Razorpay
checkout on device, or to POST /commerce/orders/{id}/mock-pay in dev.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.schemas import BookingCreate, BookingOut
from app.modules.bookings.service import (
    BookingsService,
    UnknownPooja,
    UnknownTemple,
)
from app.modules.identity.auth import CurrentUser
from app.platform.db import get_session

router = APIRouter(prefix="/bookings", tags=["bookings"])

_service = BookingsService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate, user: CurrentUser, session: SessionDep
) -> dict:
    try:
        out = await _service.create(session, user_id=user.id, payload=payload)
    except UnknownTemple:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown temple")
    except UnknownPooja:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown pooja")
    await session.commit()
    return out


@router.get("", response_model=list[BookingOut])
async def list_bookings(user: CurrentUser, session: SessionDep) -> list[dict]:
    out = await _service.list_for_user(session, user.id)
    await session.commit()  # persist any states reconciled to ok
    return out
