"""Background keep-alive pinger for a scale-to-zero WAHA host.

Render's free tier (and similar "scale to zero" hosts) spin the WAHA container
down after ~15 minutes with no inbound HTTP traffic. WhatsApp messages arrive
over Meta's websocket, not HTTP, so they never wake it — the bot silently dies.
This task issues a lightweight HTTP GET on an interval so the host keeps seeing
inbound traffic and stays awake.

IMPORTANT: this runs inside the Tara backend, so it only keeps WAHA awake while
Tara itself is awake. If Tara is also on a scale-to-zero host (e.g. an idle HF
Space), pair this with an external uptime pinger (cron-job.org, UptimeRobot)
hitting Tara's ``/health`` so Tara stays up too.
"""

import asyncio

import httpx

from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _keepalive_url(settings) -> str:
    """The URL to ping — explicit override, or derived from the WAHA API base.

    WAHA exposes an unauthenticated ``GET /ping`` at the host root (outside the
    ``/api`` prefix), which is the cheapest thing to hit. Any HTTP request keeps
    Render awake regardless of status, so an override to some other path is fine.
    """
    if settings.waha_keepalive_url:
        return settings.waha_keepalive_url.strip()
    base = settings.waha_api_url.strip().rstrip("/")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    return f"{base}/ping"


async def _ping_once(url: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
        logger.info("waha keepalive: pinged %s -> %s", url, resp.status_code)
    except Exception as exc:  # network hiccups must never kill the loop
        logger.warning("waha keepalive: ping failed for %s (%s)", url, exc)


async def _loop(url: str, interval: int) -> None:
    logger.info("waha keepalive: started (every %ss -> %s)", interval, url)
    try:
        while True:
            await _ping_once(url)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:  # normal on shutdown
        logger.info("waha keepalive: stopped")
        raise


def start_keepalive() -> "asyncio.Task | None":
    """Start the keep-alive loop as a background task, or return None if off.

    Disabled when ``mock_whatsapp`` is on (dev) or ``waha_keepalive_enabled`` is
    False (the default), so nothing pings anything unless explicitly turned on in
    production. The interval is floored at 60s to avoid hammering the host.
    """
    settings = get_settings()
    if settings.mock_whatsapp or not settings.waha_keepalive_enabled:
        return None
    url = _keepalive_url(settings)
    interval = max(60, settings.waha_keepalive_interval_seconds)
    return asyncio.create_task(_loop(url, interval), name="waha-keepalive")
