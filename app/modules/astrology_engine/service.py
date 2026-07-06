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

    async def compute_porutham(
        self,
        female_chart: dict,
        male_chart: dict,
        *,
        female_name: str = "",
        male_name: str = "",
    ) -> dict:
        """The ten Kerala poruthams for a (female, male) pair of natal charts.

        Deterministic — the janma nakshatram / rasi in each chart drive the
        classical grading (see ``porutham.py``). Directional poruthams count
        from the bride's star to the groom's, so the caller must pass the
        charts in the right roles. Raises ``ValueError`` if either chart lacks a
        real moon placement (mock / pending), so the caller can degrade instead
        of scoring a placeholder.
        """
        from app.modules.astrology_engine.porutham import (
            compute_porutham,
            star_from_chart,
        )

        female = star_from_chart(female_chart, "female", female_name)
        male = star_from_chart(male_chart, "male", male_name)
        return compute_porutham(female, male)

    async def get_panchangam(self, day: date | None = None) -> dict:
        """Panchangam for the day: nakshatram, nalla neram, tithi."""
        return await self._client.panchangam(day or date.today())

    def nakshatra_names(self) -> list[str]:
        """The 27 Malayalam nakshatra names, in canonical order.

        Public so other modules (content's daily nakshatra cards) can validate
        and enumerate stars without importing this module's internals.
        """
        from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS

        return list(NAKSHATRAS)

    async def get_prashna_chart(
        self,
        when: datetime | None = None,
        lat: float = 9.9312,
        lng: float = 76.2673,
    ) -> dict:
        """Horary (prashna) chart for the moment a question is asked.

        Defaults: now (tz-aware) at Kochi — pass the user's stored location
        when known, since the udaya lagna is location-sensitive.
        """
        from datetime import timezone

        return await self._client.prashna_chart(
            when or datetime.now(timezone.utc), lat, lng
        )

    async def get_prashnam_reading(
        self,
        mode: str,
        *,
        leaf_count: int | None = None,
        arudha_rasi_index: int | None = None,
        number: int | None = None,
        when: datetime | None = None,
        lat: float = 9.9312,
        lng: float = 76.2673,
    ) -> dict:
        """A full prashnam reading: prashna chart of the moment + mode rules.

        ``mode`` is ``"thamboola"`` (requires ``leaf_count``), ``"swarna"``
        (requires ``arudha_rasi_index`` 0–11), or ``"sankhya"`` (requires
        ``number`` 1–108). Returns deterministic facts and retrieval cues —
        the traditional meanings live in the knowledge corpus.
        """
        from app.modules.astrology_engine.prashnam import (
            sankhya_prashnam,
            swarna_prashnam,
            thamboola_prashnam,
        )

        chart = await self.get_prashna_chart(when, lat, lng)
        if mode == "thamboola":
            if leaf_count is None:
                raise ValueError("thamboola prashnam requires leaf_count")
            reading = thamboola_prashnam(leaf_count, chart)
        elif mode == "swarna":
            if arudha_rasi_index is None:
                raise ValueError("swarna prashnam requires arudha_rasi_index")
            reading = swarna_prashnam(arudha_rasi_index, chart)
        elif mode == "sankhya":
            if number is None:
                raise ValueError("sankhya prashnam requires number")
            reading = sankhya_prashnam(number, chart)
        else:
            raise ValueError(f"Unknown prashnam mode {mode!r}")
        return {**reading, "prashna_chart": chart}
