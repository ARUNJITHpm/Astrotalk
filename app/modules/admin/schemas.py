"""Pydantic schemas (DTOs) for the admin module's public boundary.

The nested analytics sections (users / charts / chat / llm) are shaped by the
owning modules and evolve independently, so they're carried as open dicts here
rather than mirrored field-by-field — the admin module composes, it doesn't
redefine each module's metrics.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminOverview(BaseModel):
    """The full analytics payload rendered by the dashboard."""

    generated_at: datetime
    system: dict[str, Any]
    users: dict[str, Any]
    chat: dict[str, Any]
    llm: dict[str, Any]
