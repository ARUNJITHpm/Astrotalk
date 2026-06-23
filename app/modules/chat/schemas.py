"""Pydantic schemas (DTOs) for the chat module's public boundary."""

from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: str = "demo"
    messages: list[ChatMessage]
