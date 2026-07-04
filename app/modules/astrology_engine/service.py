"""Public service for the astrology_engine module.

This is the ONLY surface other modules may depend on (AGENTS.md):
  - identity calls compute_natal_chart() at onboarding
  - chat calls get_transits(now, chart)
  - content calls get_panchangam(today)

All functions return plain JSON-serializable dicts (so identity can store a chart
directly in a JSON column). They are async because the real provider is network
I/O (AGENTS.md: don't block the event loop on the ephemeris API). The actual
provider call is isolated in ephemeris_client.py.
"""

from datetime import date, datetime, time

from app.modules.astrology_engine.ephemeris_client import EphemerisClient


class AstrologyEngineService:
    def __init__(self, client: EphemerisClient | None = None) -> None:
        self._client = client or EphemerisClient()

    async def compute_natal_chart(
        self,
        dob: date,
        birth_time: time | None = None,
        lat: float = 0.0,
        lng: float = 0.0,
        tz: str = "Asia/Kolkata",
    ) -> dict:
        """Compute (or fetch cached) natal chart for a birth event."""
        return await self._client.natal_chart(dob, birth_time, lat, lng, tz)

    async def get_transits(
        self, now: datetime | None = None, chart: dict | None = None
    ) -> dict:
        """Current planetary transits, optionally relative to a natal chart."""
        return await self._client.transits(now or datetime.now(), chart)

    async def get_panchangam(self, day: date | None = None) -> dict:
        """Panchangam for the day: nakshatram, nalla neram, tithi."""
        return await self._client.panchangam(day or date.today())
