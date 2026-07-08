"""HTTP routes for the chat module — the in-app AI astrologer.

Every route requires a login session (Authorization: Bearer). The user's
identity is DERIVED from the token — the payload's user_id is ignored — so one
account can never chat as, or read, another (GUARDRAILS.md §4).
"""

import time as _time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat import history, memory, user_memory
from app.modules.chat.schemas import (
    ChatHistoryEntry,
    ChatRequest,
    ChatResponse,
    UserMemoryProfile,
)
from app.modules.chat.service import ChatService
from app.modules.identity.auth import CurrentUser
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/chat", tags=["chat"])

_service = ChatService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Sliding-window rate limit on chat turns (LLM cost / abuse guard). In-process
# only — good for the current single-worker deployment; move the window to
# Redis when the app runs multiple workers.
_RATE_WINDOW_S = 3600.0
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(key: str) -> None:
    limit = get_settings().chat_rate_limit_per_hour
    if limit <= 0:  # 0/negative = disabled (e.g. load tests)
        return
    now = _time.monotonic()
    hits = _rate_hits[key]
    while hits and now - hits[0] > _RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages this hour — please take a short break.",
        )
    hits.append(now)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    user: CurrentUser,
) -> ChatResponse:
    """Run the §6 orchestrator: crisis screen FIRST, then chart + transits + RAG
    + persona + LLM. Memory extraction is scheduled after the reply, never
    blocking it."""
    _check_rate_limit(user.phone)
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    # Debug trace is a dev tool only — never expose the system prompt/internals in
    # production, even if a client asks for it.
    debug = payload.debug and get_settings().app_env != "production"
    result = await _service.handle_message(
        user.phone,
        messages,
        session,
        debug=debug,
        prashnam=payload.prashnam,
        porutham=payload.porutham,
        provider=payload.provider,
    )

    # Persist history + schedule durable-memory extraction only on the normal
    # path — never on a crisis turn (GUARDRAILS.md §2: no processing/persisting of
    # distress content downstream). Both run after the reply, never blocking it.
    if not result.is_safety_response:
        background_tasks.add_task(
            history.save_turn,
            user.phone,
            messages,
            result.reply,
            payload.conversation_id,
            llm_provider=result.llm_provider,
            llm_model=result.llm_model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            price_inr=result.price_inr,
            price_usd=result.price_usd,
        )
        background_tasks.add_task(memory.extract_memory, user.phone, messages)

    return result


@router.get("/history/{user_id}", response_model=list[ChatHistoryEntry])
async def get_chat_history(
    user_id: str, user: CurrentUser, session: SessionDep, limit: int = 20
) -> list[dict]:
    """Return the LOGGED-IN user's stored conversation turns, newest first.

    403 unless the path user_id is the caller's own.
    """
    if user_id != user.phone:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your history")
    return await history.get_history(session, user_id, limit=limit)


@router.get("/memory/{user_id}", response_model=UserMemoryProfile)
async def get_user_memory(user_id: str, user: CurrentUser) -> dict:
    """Return the LOGGED-IN user's durable memory profile.

    403 unless the path user_id is the caller's own. 404 when there is no
    profile yet, or when MongoDB is disabled (MOCK_MONGO) / unavailable — the
    lookup degrades to None rather than erroring.
    """
    if user_id != user.phone:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your memory")
    profile = await user_memory.get_profile(user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No memory profile")
    return profile
