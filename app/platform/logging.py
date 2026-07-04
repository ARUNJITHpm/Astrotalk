"""Backwards-compatible shim — logging now lives in ``logging_config``.

HARD RULE (AGENTS.md): never log raw birth data or secrets.
"""

from app.platform.logging_config import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
