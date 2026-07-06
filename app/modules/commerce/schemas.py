"""Pydantic schemas (DTOs) for the commerce module's public boundary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    """A purchase intent. The product key selects the price server-side —
    the client never supplies an amount."""

    product: str


class OrderOut(BaseModel):
    """What the client-side checkout needs to open Razorpay."""

    order_id: str
    product: str
    amount_paise: int
    currency: str
    razorpay_key_id: str
    mock: bool


class EntitlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_key: str
    granted_by: str
    expires_at: datetime | None
    created_at: datetime
