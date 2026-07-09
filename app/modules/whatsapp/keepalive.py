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


# Statuses we auto-restart. SCAN_QR_CODE means a real logout that needs a fresh
# QR/pairing code (a human) — restarting it just loops, so we leave it alone.
_RECOVERABLE = {"FAILED", "STOPPED"}


async def _recover_session_once(settings) -> None:
    """If the WAHA session has dropped to FAILED/STOPPED, restart it.

    A transient drop reconnects from the persisted creds and returns to WORKING
    with no re-pair. Best-effort: any error is logged, never raised.
    """
    base = settings.waha_api_url.strip().rstrip("/")
    sess = settings.waha_session
    headers = {"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base}/sessions/{sess}", headers=headers)
            if resp.status_code != 200:
                logger.warning("waha keepalive: session check HTTP %s", resp.status_code)
                return
            status = (resp.json() or {}).get("status")
            if status in _RECOVERABLE:
                logger.warning(
                    "waha keepalive: session '%s' is %s — auto-restarting", sess, status
                )
                r = await client.post(f"{base}/sessions/{sess}/restart", headers=headers)
                logger.info("waha keepalive: auto-restart -> %s", r.status_code)
    except Exception as exc:  # must never kill the loop
        logger.warning("waha keepalive: session recovery failed (%s)", exc)


async def _loop(url: str, interval: int, settings) -> None:
    logger.info("waha keepalive: started (every %ss -> %s)", interval, url)
    try:
        while True:
            await _ping_once(url)
            if settings.waha_autorecover_enabled:
                await _recover_session_once(settings)
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
    return asyncio.create_task(_loop(url, interval, settings), name="waha-keepalive")
