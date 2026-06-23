"""App logging setup.

HARD RULE (AGENTS.md): never log raw birth data or secrets.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
