"""Pydantic schemas (DTOs) for the notifications module's public boundary."""

from pydantic import BaseModel, ConfigDict


class DeviceRegister(BaseModel):
    """Register this install's FCM token for push (nakshatram reminders)."""

    token: str
    platform: str = "android"  # android | ios | web


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str


class NakshatramReminderSummary(BaseModel):
    target_lead_days: int
    reminders_sent: int
