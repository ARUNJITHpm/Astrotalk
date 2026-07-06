"""HTTP routes for the content module.

Two access levels:
  - POST /content/run-daily — the scheduled trigger (X-Cron-Token; an external
    scheduler like GitHub Actions cron fires it each morning).
  - /content/posts...      — the review/approve/publish surface for the /admin
    Content tab (X-Admin-Token).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.admin_auth import AdminGuard
from app.modules.content.schemas import ApprovePayload, ContentPostOut, RunDailySummary
from app.modules.content.service import (
    ContentPostNotFound,
    ContentService,
    InvalidTransition,
)
from app.platform.cron_auth import CronOrAdminGuard
from app.platform.db import get_session

router = APIRouter(prefix="/content", tags=["content"])

_service = ContentService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/run-daily",
    response_model=RunDailySummary,
    dependencies=[CronOrAdminGuard],
    summary="Draft today's content pack (scheduled or admin-triggered; idempotent)",
)
async def run_daily(
    session: SessionDep,
    day: Annotated[date | None, Query(description="Defaults to today")] = None,
) -> dict:
    return await _service.run_daily(session, day)


@router.get("/posts", response_model=list[ContentPostOut], dependencies=[AdminGuard])
async def list_posts(
    session: SessionDep,
    day: Annotated[date | None, Query(description="Filter to one day")] = None,
) -> list[ContentPostOut]:
    return await _service.list_posts(session, day)


@router.post(
    "/posts/{post_id}/approve",
    response_model=ContentPostOut,
    dependencies=[AdminGuard],
    summary="Approve a draft (optionally with an inline text edit)",
)
async def approve_post(
    session: SessionDep, post_id: int, payload: ApprovePayload | None = None
) -> ContentPostOut:
    try:
        return await _service.approve(session, post_id, (payload or ApprovePayload()).body)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/posts/{post_id}/publish",
    response_model=ContentPostOut,
    dependencies=[AdminGuard],
    summary="Publish an approved post to its platform",
)
async def publish_post(session: SessionDep, post_id: int) -> ContentPostOut:
    try:
        return await _service.publish(session, post_id)
    except ContentPostNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
