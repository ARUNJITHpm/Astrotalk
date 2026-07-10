"""Dummy astrologer directory (internal to the astrologers module).

⚠️ DUMMY DATA — every entry is placeholder. Names are intentionally generic
(``kozhikode-astro-1`` …) so nobody mistakes them for real practitioners; the
coordinates are each district's headquarters town, not a real office. When real
experienced astrologers come on board, replace this list (same shape) and the
``suggest_for`` / booking flow keeps working unchanged.

Two astrologers per each of Kerala's 14 districts (28 total). The canonical
district keys come from ``temples.remedy_map.DISTRICTS`` so the directory, the
temple directory, and the chat district detector all agree on spelling.

Fields:
  - ``id`` / ``name`` — the ``<district>-astro-N`` slug (also the booking key).
  - ``specialties`` — life-concern keys from ``temples.remedy_map`` (career,
    marriage, children, education, health, wealth, obstacles, peace, ancestors).
  - ``availability`` — weekly consult windows; ``weekday`` is 0 (Mon) … 6 (Sun),
    matching ``date.weekday()``. ``-astro-1`` sits mornings, ``-astro-2``
    evenings, so the booking page shows variety.

Tone (GUARDRAILS.md §1): a human consultation is optional support the person may
choose — never a demand, never sold through fear. Consults here are free.
"""

from typing import TypedDict

from app.modules.temples.remedy_map import DISTRICTS


class AstrologerSeed(TypedDict):
    id: str
    name: str
    district: str
    town: str
    lat: float
    lng: float
    specialties: list[str]
    experience_years: int
    languages: list[str]
    rating: float
    bio_ml: str
    availability: list[dict]


# District HQ town + coordinates (public knowledge). Order matches DISTRICTS.
_DISTRICT_SEATS: dict[str, tuple[str, float, float]] = {
    "Thiruvananthapuram": ("Thiruvananthapuram", 8.5241, 76.9366),
    "Kollam": ("Kollam", 8.8932, 76.6141),
    "Pathanamthitta": ("Pathanamthitta", 9.2648, 76.7870),
    "Alappuzha": ("Alappuzha", 9.4981, 76.3388),
    "Kottayam": ("Kottayam", 9.5916, 76.5222),
    "Idukki": ("Painavu", 9.8497, 76.9560),
    "Ernakulam": ("Kochi", 9.9312, 76.2673),
    "Thrissur": ("Thrissur", 10.5276, 76.2144),
    "Palakkad": ("Palakkad", 10.7867, 76.6548),
    "Malappuram": ("Malappuram", 11.0510, 76.0711),
    "Kozhikode": ("Kozhikode", 11.2588, 75.7804),
    "Wayanad": ("Kalpetta", 11.6054, 76.0862),
    "Kannur": ("Kannur", 11.8745, 75.3704),
    "Kasaragod": ("Kasaragod", 12.4996, 74.9869),
}

# Rotating specialty pairs so every concern is covered by several astrologers
# statewide and no two neighbours look identical.
_SPECIALTY_ROTATION: list[list[str]] = [
    ["marriage", "career", "peace"],
    ["health", "children", "wealth"],
    ["education", "obstacles", "career"],
    ["marriage", "children", "peace"],
    ["wealth", "career", "obstacles"],
    ["health", "peace", "ancestors"],
    ["marriage", "education", "wealth"],
]

_BIO_TEMPLATE = (
    "പരമ്പരാഗത കേരള ജ്യോതിഷത്തിൽ {years} വർഷത്തെ പരിചയം. "
    "{focus} സംബന്ധമായ സംശയങ്ങൾക്ക് ശാന്തമായി വഴികാട്ടുന്നു."
)

_FOCUS_ML: dict[str, str] = {
    "marriage": "വിവാഹം, പൊരുത്തം",
    "career": "തൊഴിൽ, ഉദ്യോഗം",
    "children": "സന്താനഭാഗ്യം",
    "education": "വിദ്യാഭ്യാസം",
    "health": "ആരോഗ്യം",
    "wealth": "സാമ്പത്തികം",
    "obstacles": "തടസ്സങ്ങൾ, കോടതി കാര്യങ്ങൾ",
    "peace": "മനസ്സമാധാനം",
    "ancestors": "പിതൃകർമ്മം",
}


def _slug(district: str) -> str:
    return district.lower().replace(" ", "")


def _morning_windows() -> list[dict]:
    # Tue/Thu/Sat mornings, 30-min consults.
    return [
        {"weekday": 1, "start": "09:30", "end": "12:30", "duration_min": 30},
        {"weekday": 3, "start": "09:30", "end": "12:30", "duration_min": 30},
        {"weekday": 5, "start": "10:00", "end": "13:00", "duration_min": 30},
    ]


def _evening_windows() -> list[dict]:
    # Mon/Wed/Fri evenings, 30-min consults.
    return [
        {"weekday": 0, "start": "17:00", "end": "20:00", "duration_min": 30},
        {"weekday": 2, "start": "17:00", "end": "20:00", "duration_min": 30},
        {"weekday": 4, "start": "18:00", "end": "20:30", "duration_min": 30},
    ]


def _build() -> list[AstrologerSeed]:
    out: list[AstrologerSeed] = []
    for i, district in enumerate(DISTRICTS):
        town, lat, lng = _DISTRICT_SEATS[district]
        slug = _slug(district)
        for n in (1, 2):
            specialties = _SPECIALTY_ROTATION[(2 * i + n) % len(_SPECIALTY_ROTATION)]
            years = 8 + ((i * 2 + n) % 22)  # 8–29 years, deterministic spread
            rating = round(4.2 + ((i + n) % 8) * 0.1, 1)  # 4.2–4.9
            focus = ", ".join(_FOCUS_ML[s] for s in specialties[:2])
            out.append(
                AstrologerSeed(
                    id=f"{slug}-astro-{n}",
                    name=f"{slug}-astro-{n}",
                    district=district,
                    town=town,
                    lat=lat,
                    lng=lng,
                    specialties=specialties,
                    experience_years=years,
                    languages=["Malayalam", "English"] if n == 1 else ["Malayalam", "Tamil"],
                    rating=rating,
                    bio_ml=_BIO_TEMPLATE.format(years=years, focus=focus),
                    availability=_morning_windows() if n == 1 else _evening_windows(),
                )
            )
    return out


SEED_ASTROLOGERS: list[AstrologerSeed] = _build()
