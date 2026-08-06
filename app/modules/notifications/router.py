"""HTTP routes for the notifications module.

POST /notifications/run-festivals is a scheduled "cron endpoint" — an
external scheduler (the same one that fires /content/run-daily) calls it
each morning with the X-Cron-Token; the owner can trigger it manually from
the console's Channels → Notifications screen.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.auth import CurrentUser
from app.modules.notifications.schemas import (
    DeviceOut,
    DeviceRegister,
    NakshatramReminderSummary,
)
from app.modules.notifications.service import NotificationsService
from app.platform.cron_auth import require_cron_or_operator
from app.platform.db import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Owner, not "any operator". Both runs put messages on real devotees' phones,
# and GUARDRAILS §3 makes the first live WhatsApp send a human-approval gate —
# a decision that belongs to the person who owns the number, not to whoever
# happens to be signed in. The cron branch is untouched: the scheduler holds a
# secret, not a role.
CronOrOwnerGuard = Depends(require_cron_or_operator("owner"))

_service = NotificationsService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/devices",
    response_model=DeviceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register this install's FCM token for push",
)
async def register_device(
    payload: DeviceRegister, user: CurrentUser, session: SessionDep
) -> DeviceOut:
    device = await _service.register_device(
        session, user.id, payload.token, payload.platform
    )
    await session.commit()
    return DeviceOut.model_validate(device)


@router.post(
    "/run-nakshatram-reminders",
    response_model=NakshatramReminderSummary,
    dependencies=[CronOrOwnerGuard],
    summary="Push star-day reminders T-3 days out (scheduled; idempotent)",
)
async def run_nakshatram_reminders(
    session: SessionDep,
    today: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> dict:
    summary = await _service.run_nakshatram_reminders(session, today)
    await session.commit()
    return summary


@router.post(
    "/run-festivals",
    dependencies=[CronOrOwnerGuard],
    summary="Send T-3-day festival updates to subscribers (scheduled; idempotent)",
)
async def run_festivals(
    session: SessionDep,
    today: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> dict:
    summary = await _service.run_festivals(session, today)
    await session.commit()
    return summary
