"""Pydantic DTOs for the bookings module's HTTP boundary."""

from datetime import datetime

from pydantic import BaseModel


class BookingCreate(BaseModel):
    """Book a pooja. The price is the server's truth — the client never sends an
    amount; it only names the temple + offering and who it's for."""

    temple_id: str
    pooja_key: str
    when: str = ""  # display label for the chosen day, e.g. "28 Jul, 6:00 AM"
    member_id: int | None = None
    member_name: str = ""
    member_nak: int | None = None


class BookingOut(BaseModel):
    """A booking as the app renders it. ``order_id`` + ``mock`` +
    ``razorpay_key_id`` drive checkout on create; ``state`` is ``wait`` until the
    payment is captured, then ``ok`` (confirmed)."""

    id: int
    ref: str
    temple_id: str
    pooja_key: str
    pooja_name: str
    amount_paise: int
    service_fee_paise: int
    total_paise: int
    member_id: int | None
    member_name: str
    member_nak: int | None
    when: str
    state: str
    order_id: str | None
    mock: bool
    razorpay_key_id: str = ""
    created_at: datetime
