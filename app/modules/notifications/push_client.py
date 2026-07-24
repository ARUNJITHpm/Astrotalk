"""FCM push client (internal to notifications).

Mock by default (``mock_fcm``): sends are logged and counted, never dispatched,
so the whole reminder flow runs with no Firebase credentials. Swapping in real
FCM should touch ONLY this file — fill in ``_real_send``; callers keep the shape.
"""

from app.platform import metrics
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _mock_mode() -> bool:
    return get_settings().mock_fcm


class PushClient:
    async def send(
        self, token: str, title: str, body: str, data: dict | None = None
    ) -> bool:
        """Send one push to one device token. Returns True on (mock) success."""
        if _mock_mode():
            logger.info("fcm(mock): push to %s… — %s", token[:10], title)
            metrics.increment("notifications.push_mock")
            return True
        return await self._real_send(token, title, body, data or {})

    async def _real_send(  # pragma: no cover — wired with real Firebase creds
        self, token: str, title: str, body: str, data: dict
    ) -> bool:
        raise NotImplementedError(
            "Real FCM send not wired. Set mock_fcm=false and implement the "
            "Firebase call here."
        )
