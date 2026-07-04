"""Pydantic schemas (DTOs) for the whatsapp module's public boundary."""

from pydantic import BaseModel


class ConsentRequest(BaseModel):
    phone: str


class ConsentResponse(BaseModel):
    phone: str
    opted_in: bool
