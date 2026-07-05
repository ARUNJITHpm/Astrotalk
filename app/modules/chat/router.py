"""HTTP routes for the chat module — the in-app AI astrologer."""

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
from app.platform.config import get_settings
from app.platform.db import get_session

router = APIRouter(prefix="/chat", tags=["chat"])

_service = ChatService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/message", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> ChatResponse:
    """Run the §6 orchestrator: crisis screen FIRST, then chart + transits + RAG
    + persona + LLM. Memory extraction is scheduled after the reply, never
    blocking it."""
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    # Debug trace is a dev tool only — never expose the system prompt/internals in
    # production, even if a client asks for it.
    debug = payload.debug and get_settings().app_env != "production"
    result = await _service.handle_message(
        payload.user_id, messages, session, debug=debug, prashnam=payload.prashnam
    )

    # Persist history + schedule durable-memory extraction only on the normal
    # path — never on a crisis turn (GUARDRAILS.md §2: no processing/persisting of
    # distress content downstream). Both run after the reply, never blocking it.
    if not result.is_safety_response:
        background_tasks.add_task(
            history.save_turn,
            payload.user_id,
            messages,
            result.reply,
            payload.conversation_id,
        )
        background_tasks.add_task(memory.extract_memory, payload.user_id, messages)

    return result


@router.get("/history/{user_id}", response_model=list[ChatHistoryEntry])
async def get_chat_history(user_id: str, limit: int = 20) -> list[dict]:
    """Return the user's stored conversation turns, newest first.

    Empty when MongoDB is disabled (MOCK_MONGO) or unavailable — the store
    degrades to a no-op rather than erroring.
    """
    return await history.get_history(user_id, limit=limit)


@router.get("/memory/{user_id}", response_model=UserMemoryProfile)
async def get_user_memory(user_id: str) -> dict:
    """Return the user's durable memory profile (distilled cross-session facts).

    404 when there is no profile yet, or when MongoDB is disabled (MOCK_MONGO) /
    unavailable — the lookup degrades to None rather than erroring.
    """
    profile = await user_memory.get_profile(user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No memory profile")
    return profile
