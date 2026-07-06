"""Publishing adapters (internal): one approved post → the platform API.

Rollout order (GROWTH_PLAN.md Part 1): WhatsApp Channel first (rides the
whatsapp module's compliant publish path — AI disclosure + opt-out footer are
appended IN CODE there), then Meta (FB/IG) and YouTube, which stay mocked
stubs until their API apps exist. Every adapter respects the existing
``MOCK_*`` convention, so a "publish" click in dev logs instead of posting.

Returns the platform's external id; raises PublishError on failure so the
caller can mark the row ``failed`` (visible in /admin) instead of losing it.
"""

from app.modules.whatsapp.service import publish_to_channel
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


class PublishError(RuntimeError):
    """A platform send failed; the post should be marked ``failed``."""


async def _publish_wa_channel(body: str) -> str:
    # The whatsapp service handles mock vs live and the compliance footer.
    await publish_to_channel(body)
    prefix = "mock" if get_settings().mock_whatsapp else "live"
    return f"wa_channel:{prefix}"


async def _publish_meta(platform: str, body: str) -> str:
    # Meta Graph API (one app covers FB Page + IG). Not wired yet: the growth
    # plan schedules it after WhatsApp proves the loop. Mock-only until then.
    logger.info("content.publish(mock %s): would post:\n%s", platform, body)
    return f"{platform}:mock"


async def _publish_youtube(body: str) -> str:
    # YouTube Data API v3 needs a video file; blocked on the video pipeline
    # (Part 1 stretch: card + TTS + ffmpeg). Mock-only until then.
    logger.info("content.publish(mock yt_short): would upload script:\n%s", body)
    return "yt_short:mock"


async def publish(platform: str, body: str) -> str:
    """Send one approved post to its platform; returns the external id."""
    try:
        if platform == "wa_channel":
            return await _publish_wa_channel(body)
        if platform in ("fb_post", "ig_reel"):
            return await _publish_meta(platform, body)
        if platform == "yt_short":
            return await _publish_youtube(body)
    except Exception as exc:
        raise PublishError(f"{platform}: {exc}") from exc
    raise PublishError(f"unknown platform {platform!r}")
