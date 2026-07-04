"""Application logging setup.

HARD RULE (AGENTS.md #4 / GUARDRAILS.md #4): never log raw birth data, secrets,
or PII. Log *that* something happened (e.g. a crisis route fired) — not the
sensitive content itself.
"""

import logging
from logging.config import dictConfig

from app.platform.config import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s :: %(message)s"


# Third-party libraries that spam DEBUG/INFO noise we almost never want. Pinned
# to WARNING so our own DEBUG logs stay readable in development.
_NOISY_LOGGERS = (
    "asyncio",
    "watchfiles",
    "watchfiles.main",
    "httpx",
    "httpcore",
    "openai",
    "chromadb",
    "urllib3",
    "asyncpg",
    "multipart",
    "python_multipart",
)


def configure_logging() -> None:
    """Idempotently configure logging. Call once at app startup.

    Our own ``app.*`` loggers are verbose (DEBUG) in development and INFO in
    production. The root stays at INFO and noisy third-party libraries are pinned
    to WARNING, so ``python main.py`` doesn't drown in library DEBUG chatter.
    """
    settings = get_settings()
    app_level = "DEBUG" if settings.app_env == "development" else "INFO"
    loggers = {"app": {"level": app_level}}
    loggers.update({name: {"level": "WARNING"} for name in _NOISY_LOGGERS})
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": _LOG_FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "loggers": loggers,
            "root": {"level": "INFO", "handlers": ["console"]},
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
