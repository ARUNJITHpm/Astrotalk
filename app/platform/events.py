"""In-process event bus — the ONLY sanctioned channel for cross-module side effects.

Modules publish/subscribe here instead of calling into each other (AGENTS.md).
Domain events, e.g. `chat.crisis_detected`, `commerce.report_purchased`.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[Any], Awaitable[None] | None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    async def emit(self, event: str, payload: Any) -> None:
        for handler in self._handlers.get(event, []):
            result = handler(payload)
            if result is not None:
                await result


event_bus = EventBus()
