"""Pydantic schemas (DTOs) for the chat module's public boundary."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: str = "demo"
    messages: list[ChatMessage]
    # Groups turns into one conversation for the history sidebar. The client
    # generates it per chat session; None falls back to an ungrouped turn.
    conversation_id: str | None = None
    # Developer flag: when true (and not in production), the response carries a
    # `debug` trace of the whole orchestration. Off by default.
    debug: bool = False


class ChatResponse(BaseModel):
    reply: str
    # True when the crisis safety path fired: reply is the helpline message and
    # NO astrology ran (GUARDRAILS.md §2).
    is_safety_response: bool
    # What grounded the reply, e.g. ["chart", "transits", "knowledge:retrograde-mercury"].
    grounded_in: list[str] = []
    # Per-turn orchestration trace (params, tools, timings, LLM config). Present
    # only when debug was requested in a non-production environment.
    debug: dict[str, Any] | None = None


class ChatHistoryEntry(BaseModel):
    """One stored conversation turn from the MongoDB chat_history collection."""

    user_id: str
    conversation_id: str | None = None
    messages: list[ChatMessage]
    reply: str
    created_at: datetime


class MemoryFact(BaseModel):
    """A single distilled fact in a user's memory profile."""

    text: str
    kind: str = "fact"
    created_at: datetime | None = None


class UserMemoryProfile(BaseModel):
    """The user's durable memory profile from the MongoDB user_memory collection."""

    user_id: str
    summary: str | None = None
    facts: list[MemoryFact] = []
    updated_at: datetime | None = None
