"""Pydantic schemas (DTOs) for the whatsapp module's public boundary."""

from pydantic import BaseModel


class ConsentRequest(BaseModel):
    phone: str


class ConsentResponse(BaseModel):
    phone: str
    opted_in: bool


# ---- WhatsApp simulator (the /whatsapp demo page) ----


class SimulateRequest(BaseModel):
    """One inbound message from the simulator page, acting as ``phone``."""

    phone: str
    text: str


class SimulateResponse(BaseModel):
    reply: str

