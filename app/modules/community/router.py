"""HTTP routes for the community module (ENGAGEMENT_PLAN.md Part A).

The user-facing engagement surface:
  - GET  /community/feed      — public feed (personalised + streak when logged in)
  - POST /community/posts/{id}/react — toggle an emoji reaction (login)
  - GET  /community/streak    — the caller's daily check-in streak (login)
  - GET  /community/polls     — active polls with results
  - POST /community/polls/{id}/vote — cast/change a vote (login)
  - POST /community/polls     — create a poll (admin)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.community.schemas import (
    FeedOut,
    PollCreate,
    PollOut,
    PollVotePayload,
    ReactionOut,
    ReactionPayload,
    StreakOut,
)
from app.modules.community.service import (
    CommunityService,
    InvalidOption,
    InvalidReaction,
    PollNotFound,
)
from app.modules.identity.auth import CurrentUser
from app.modules.identity.models import User
from app.modules.identity.service import IdentityService
from app.platform.admin_auth import AdminGuard
from app.platform.db import get_session

router = APIRouter(prefix="/community", tags=["community"])

_service = CommunityService()
_identity = IdentityService()
_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> User | None:
    """Resolve the caller if a valid token is present, else None (feed is public)."""
    token = credentials.credentials if credentials else ""
    if not token:
        return None
    return await _identity.get_session_user(session, token)


OptionalUser = Annotated[User | None, Depends(optional_user)]


@router.get(
    "/feed", response_model=FeedOut, summary="The user feed (public; richer when logged in)"
)
async def get_feed(session: SessionDep, user: OptionalUser) -> FeedOut:
    return await _service.get_feed(session, user.id if user else None)


@router.post(
    "/posts/{post_id}/react",
    response_model=ReactionOut,
    summary="Toggle an emoji reaction on a feed post",
)
async def react(
    session: SessionDep, post_id: int, payload: ReactionPayload, user: CurrentUser
) -> ReactionOut:
    try:
        return await _service.react(session, user.id, post_id, payload.emoji)
    except InvalidReaction as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/streak", response_model=StreakOut, summary="The caller's check-in streak")
async def get_streak(session: SessionDep, user: CurrentUser) -> StreakOut:
    return await _service.get_streak(session, user.id)


@router.get("/polls", response_model=list[PollOut], summary="Active polls with live results")
async def list_polls(session: SessionDep, user: OptionalUser) -> list[PollOut]:
    return await _service.list_polls(session, user.id if user else None)


@router.post(
    "/polls/{poll_id}/vote",
    response_model=PollOut,
    summary="Cast or change a vote on a poll",
)
async def vote(
    session: SessionDep, poll_id: int, payload: PollVotePayload, user: CurrentUser
) -> PollOut:
    try:
        return await _service.vote(session, poll_id, user.id, payload.option_index)
    except PollNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Poll not found")
    except InvalidOption as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post(
    "/polls",
    response_model=PollOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminGuard],
    summary="Create a poll (admin)",
)
async def create_poll(session: SessionDep, payload: PollCreate) -> PollOut:
    if not payload.question.strip() or len([o for o in payload.options if o.strip()]) < 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A poll needs a question and at least two options",
        )
    return await _service.create_poll(session, payload.question, payload.options)
