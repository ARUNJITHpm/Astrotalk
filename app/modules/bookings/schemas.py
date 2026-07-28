"""Pydantic DTOs for the bookings module's HTTP boundary."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BookingCreate(BaseModel):
    """Book a pooja. The price is the server's truth — the client never sends an
    amount; it only names the temple + offering and who it's for."""

    temple_id: str
    pooja_key: str
    when: str = ""  # display label for the chosen day, e.g. "28 Jul, 6:00 AM"
    # The machine-readable half of `when`. Optional so existing clients keep
    # working; without it the booking cannot appear on a dated worklist, which
    # is the whole point of the operator queue (console plan Part 7).
    perform_on: date | None = None
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
    perform_on: date | None = None
    state: str
    order_id: str | None
    mock: bool
    razorpay_key_id: str = ""
    created_at: datetime


# ---- operator console (console plan Part 7) ----
# Operators could see NOTHING before this: the module had two routes, both hard
# -scoped to the caller. These shapes carry what running a temple needs and the
# app's own BookingOut does not — who booked it, their phone, the payment.


class OperatorBookingRow(BaseModel):
    """One row of the operator queue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ref: str
    temple_id: str
    pooja_key: str
    pooja_name: str
    amount_paise: int
    service_fee_paise: int
    member_name: str
    member_nak: int | None
    when_label: str
    perform_on: date | None
    state: str
    operator_note: str
    created_at: datetime
    updated_at: datetime | None


class OperatorBookingPage(BaseModel):
    """A page of the queue. ``total`` is the count BEFORE paging, so the console
    can show "showing 25 of 480" rather than guessing from a short last page."""

    total: int
    limit: int
    offset: int
    items: list[OperatorBookingRow]


class OperatorBookingDetail(OperatorBookingRow):
    """One booking, joined across modules the way an operator needs to read it.

    ``user_phone`` is the app-wide identity key and the only way to call the
    devotee back. ``payment_status`` and ``razorpay_payment_id`` come from
    commerce through its public service — this module never touches its tables.
    """

    user_id: int
    user_name: str
    user_phone: str
    razorpay_order_id: str | None
    payment_status: str | None
    total_paise: int


class BookingStatusIn(BaseModel):
    status: str
    note: str = ""


class BookingNoteIn(BaseModel):
    note: str


class BookingScheduleIn(BaseModel):
    """The day to perform on. Explicitly nullable — clearing a wrong date has to
    be possible, and it is different from leaving the field out."""

    perform_on: date | None


class BookingSettingsIn(BaseModel):
    """The fee in paise, matching the column. Every other money value in the
    app is stored in paise; a rupee field here would be the one that rounds."""

    service_fee_paise: int


class WorklistItem(BaseModel):
    """One offering to perform, as the temple reads it off the sheet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ref: str
    pooja_key: str
    pooja_name: str
    member_name: str
    member_nak: int | None
    when_label: str
    state: str
    operator_note: str


class WorklistGroup(BaseModel):
    """The bookings for one nakshatram. ``nak`` is None for bookings that name
    no star — the app makes it optional, so the sheet must have a home for
    them rather than dropping them."""

    nak: int | None
    items: list[WorklistItem]


class Worklist(BaseModel):
    temple_id: str | None
    day: date | None
    total: int
    undated: int
    groups: list[WorklistGroup]
