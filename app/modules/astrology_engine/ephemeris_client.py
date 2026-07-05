"""Client wrapping an external ephemeris/astrology API (internal to astrology_engine).

When ``MOCK_EPHEMERIS`` is true (the default), every method returns a
**deterministic** mock derived only from its inputs, so the rest of the app works
end-to-end with no API key. Determinism uses ``zlib.crc32`` over a stable string —
NOT the salted built-in ``hash()`` — so results are identical across processes.

Swapping in a real provider later should require touching ONLY this file: fill in
the ``_real_*`` methods (httpx calls to ``settings.ephemeris_api_url``) and the
public service keeps the same shape.
"""

from datetime import date, datetime, time
from zlib import crc32

from app.platform.config import get_settings

# Malayalam nakshatra names (27), in order.
_NAKSHATRAS = [
    "അശ്വതി", "ഭരണി", "കാർത്തിക", "രോഹിണി", "മകയിരം", "തിരുവാതിര",
    "പുണർതം", "പൂയം", "ആയില്യം", "മകം", "പൂരം", "ഉത്രം",
    "അത്തം", "ചിത്തിര", "ചോതി", "വിശാഖം", "അനിഴം", "തൃക്കേട്ട",
    "മൂലം", "പൂരാടം", "ഉത്രാടം", "തിരുവോണം", "അവിട്ടം", "ചതയം",
    "പൂരുരുട്ടാതി", "ഉത്രട്ടാതി", "രേവതി",
]

# 12 rasis (zodiac signs), Malayalam transliteration.
_RASIS = [
    "മേടം", "ഇടവം", "മിഥുനം", "കർക്കടകം", "ചിങ്ങം", "കന്നി",
    "തുലാം", "വൃശ്ചികം", "ധനു", "മകരം", "കുംഭം", "മീനം",
]

# Navagraha (nine planets), keyed by stable English ids.
_PLANETS = [
    "surya", "chandra", "chevvai", "budhan", "guru",
    "shukran", "shani", "rahu", "ketu",
]

# 30 tithis: Shukla (waxing) 1-15 then Krishna (waning) 1-15.
_TITHI_NAMES = [
    "പ്രതിപദം", "ദ്വിതീയ", "തൃതീയ", "ചതുർത്ഥി", "പഞ്ചമി",
    "ഷഷ്ഠി", "സപ്തമി", "അഷ്ടമി", "നവമി", "ദശമി",
    "ഏകാദശി", "ദ്വാദശി", "ത്രയോദശി", "ചതുർദശി", "പൗർണമി/അമാവാസി",
]


def _seed(*parts: object) -> int:
    """Stable, cross-process integer seed from arbitrary inputs."""
    raw = "|".join(str(p) for p in parts)
    return crc32(raw.encode("utf-8"))


def _pick(items: list[str], seed: int) -> str:
    return items[seed % len(items)]


class EphemerisClient:
    """Talks to the ephemeris provider, or returns deterministic mocks."""

    def __init__(self) -> None:
        settings = get_settings()
        self._mock = settings.mock_ephemeris
        self._api_url = settings.ephemeris_api_url
        self._api_key = settings.ephemeris_api_key
        self._ayanamsa = settings.ephemeris_ayanamsa

    # ---- public API (all async: the real provider is network I/O) ----

    async def natal_chart(
        self,
        dob: date,
        birth_time: time | None,
        lat: float,
        lng: float,
        tz: str,
    ) -> dict:
        if self._mock:
            return self._mock_natal_chart(dob, birth_time, lat, lng, tz)
        return await self._real_natal_chart(dob, birth_time, lat, lng, tz)

    async def transits(self, when: datetime, chart: dict | None = None) -> dict:
        if self._mock:
            return self._mock_transits(when, chart)
        return await self._real_transits(when, chart)

    async def panchangam(self, day: date) -> dict:
        if self._mock:
            return self._mock_panchangam(day)
        return await self._real_panchangam(day)

    async def prashna_chart(self, when: datetime, lat: float, lng: float) -> dict:
        if self._mock:
            return self._mock_prashna_chart(when, lat, lng)
        return await self._real_prashna_chart(when, lat, lng)

    # ---- deterministic mocks ----

    def _mock_natal_chart(
        self,
        dob: date,
        birth_time: time | None,
        lat: float,
        lng: float,
        tz: str,
    ) -> dict:
        base = _seed(dob.isoformat(), birth_time, round(lat, 2), round(lng, 2))
        planets = {
            name: {
                "rasi": _pick(_RASIS, base + i * 7),
                "house": (base + i * 13) % 12 + 1,
                "retrograde": ((base + i * 17) % 5) == 0,
            }
            for i, name in enumerate(_PLANETS)
        }
        return {
            "system": "vedic",
            "ayanamsa": "lahiri",
            "nakshatram": _pick(_NAKSHATRAS, base),
            "rasi": _pick(_RASIS, base + 3),
            "lagnam": _pick(_RASIS, base + 9),
            "planets": planets,
            "mock": True,
            "source": "mock-ephemeris",
        }

    def _mock_transits(self, when: datetime, chart: dict | None) -> dict:
        base = _seed(when.date().isoformat())
        transits = {
            name: {
                "rasi": _pick(_RASIS, base + i * 5),
                "retrograde": ((base + i * 11) % 4) == 0,
            }
            for i, name in enumerate(_PLANETS)
        }
        return {
            "as_of": when.isoformat(),
            "transits": transits,
            "mock": True,
            "source": "mock-ephemeris",
        }

    def _mock_panchangam(self, day: date) -> dict:
        base = _seed(day.isoformat())
        # Auspicious window: a stable 1-hour slot between 06:00 and 09:00.
        start_hour = 6 + (base % 3)
        nalla_neram = f"{start_hour:02d}:30–{start_hour + 1:02d}:30"
        return {
            "date": day.isoformat(),
            "nakshatram": _pick(_NAKSHATRAS, base),
            "nalla_neram": nalla_neram,
            "tithi": _pick(_TITHI_NAMES, base // 7),
            "mock": True,
            "source": "mock-ephemeris",
        }

    def _mock_prashna_chart(self, when: datetime, lat: float, lng: float) -> dict:
        # Minute-level seed: prashna is about the question MOMENT, so two
        # questions a minute apart may differ (unlike the daily transit mock).
        base = _seed(when.replace(second=0, microsecond=0).isoformat(),
                     round(lat, 2), round(lng, 2))
        lagna_index = base % 12
        moon_index = (base + 4) % 12
        planets = {
            name: {
                "rasi": _pick(_RASIS, base + i * 7),
                "rasi_index": (base + i * 7) % 12,
                "house": ((base + i * 7) % 12 - lagna_index) % 12 + 1,
                "retrograde": ((base + i * 17) % 5) == 0,
            }
            for i, name in enumerate(_PLANETS)
        }
        return {
            "system": "vedic",
            "ayanamsa": "lahiri",
            "as_of": when.isoformat(),
            "udaya_lagnam": _RASIS[lagna_index],
            "udaya_lagna_index": lagna_index,
            "lagna_degree": float(base % 30),
            "moon": {
                "rasi": _RASIS[moon_index],
                "rasi_index": moon_index,
                "nakshatram": _pick(_NAKSHATRAS, base + 2),
                "pada": base % 4 + 1,
                "house": (moon_index - lagna_index) % 12 + 1,
            },
            "tithi": _pick(_TITHI_NAMES, base // 7),
            "tithi_index": base % 30,
            "paksha": "shukla" if base % 30 < 15 else "krishna",
            "planets": planets,
            "mock": True,
            "source": "mock-ephemeris",
        }

    # ---- real provider (fill these in to go live; nothing else changes) ----

    async def _real_natal_chart(
        self,
        dob: date,
        birth_time: time | None,
        lat: float,
        lng: float,
        tz: str,
    ) -> dict:
        # Self-computed via Swiss Ephemeris — no network, no API key. The compute
        # is pure CPU, so run it in a thread to avoid blocking the event loop.
        # Lazy import keeps pyswisseph off the import path when mocking.
        from asyncio import to_thread

        from app.modules.astrology_engine.swiss_ephemeris import compute_natal_chart

        return await to_thread(
            compute_natal_chart, dob, birth_time, lat, lng, tz, self._ayanamsa
        )

    async def _real_transits(self, when: datetime, chart: dict | None = None) -> dict:
        # Self-computed via Swiss Ephemeris (CPU-bound → run off the event loop).
        from asyncio import to_thread

        from app.modules.astrology_engine.swiss_ephemeris import compute_transits

        return await to_thread(compute_transits, when, chart, self._ayanamsa)

    async def _real_panchangam(self, day: date) -> dict:
        from asyncio import to_thread

        from app.modules.astrology_engine.swiss_ephemeris import compute_panchangam

        return await to_thread(compute_panchangam, day, self._ayanamsa)

    async def _real_prashna_chart(self, when: datetime, lat: float, lng: float) -> dict:
        from asyncio import to_thread

        from app.modules.astrology_engine.swiss_ephemeris import compute_prashna_chart

        return await to_thread(compute_prashna_chart, when, lat, lng, self._ayanamsa)
