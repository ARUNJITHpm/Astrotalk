"""HTTP routes for the notifications module.

POST /notifications/run-festivals is a scheduled "cron endpoint" — an
external scheduler (the same one that fires /content/run-daily) calls it
each morning with the X-Cron-Token; admins can trigger it manually too.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.service import NotificationsService
from app.platform.cron_auth import CronOrAdminGuard
from app.platform.db import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])

_service = NotificationsService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/run-festivals",
    dependencies=[CronOrAdminGuard],
    summary="Send T-3-day festival updates to subscribers (scheduled; idempotent)",
)
async def run_festivals(
    session: SessionDep,
    today: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> dict:
    summary = await _service.run_festivals(session, today)
    await session.commit()
    return summary
