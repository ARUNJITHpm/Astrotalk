"""Pydantic schemas (DTOs) for the knowledge module's public boundary."""

from pydantic import BaseModel


class KnowledgeChunk(BaseModel):
    """A retrieved interpretation chunk. ``score`` is higher = more relevant."""

    id: str
    topic: str
    text: str
    score: float
    reviewed: bool
