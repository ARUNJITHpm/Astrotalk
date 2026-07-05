"""Pydantic schemas (DTOs) for the chat module's public boundary."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PrashnamPick(BaseModel):
    """A prashnam (Kerala horary) interaction attached to a chat turn.

    ``thamboola`` carries the betel-leaf count the user offered; ``swarna``
    carries which of the 12 unlabeled rasi squares they touched (the arudha);
    ``sankhya`` carries a number from the sacred 1–108. The engine computes
    the question-moment chart and the deterministic rules; the LLM only
    narrates, under the honesty guardrail.
    """

    mode: Literal["thamboola", "swarna", "sankhya"]
    leaf_count: int | None = Field(None, ge=1, le=108)
    arudha_rasi_index: int | None = Field(None, ge=0, le=11)
    number: int | None = Field(None, ge=1, le=108)

    @model_validator(mode="after")
    def _mode_has_its_pick(self):
        if self.mode == "thamboola" and self.leaf_count is None:
            raise ValueError("thamboola prashnam requires leaf_count")
        if self.mode == "swarna" and self.arudha_rasi_index is None:
            raise ValueError("swarna prashnam requires arudha_rasi_index")
        if self.mode == "sankhya" and self.number is None:
            raise ValueError("sankhya prashnam requires number")
        return self


class ChatRequest(BaseModel):
    user_id: str = "demo"
    messages: list[ChatMessage]
    # Groups turns into one conversation for the history sidebar. The client
    # generates it per chat session; None falls back to an ungrouped turn.
    conversation_id: str | None = None
    # Set when this turn is a prashnam interaction (the "പ്രശ്നം ചോദിക്കൂ" flow).
    prashnam: PrashnamPick | None = None
    # Optional per-message LLM provider pick (the UI's model selector).
    # None = the configured default (sarvam). Keyless providers fall back.
    provider: Literal["sarvam", "sarvam-fast", "openai"] | None = None
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
