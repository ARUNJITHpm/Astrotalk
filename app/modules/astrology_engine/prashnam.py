"""Kerala prashnam (horary) rules — deterministic FACTS only (internal).

Prashnam reads the chart of the moment a question is asked (see
``swiss_ephemeris.compute_prashna_chart``). This module adds the two
interactive Kerala forms on top of that chart:

* **Thamboola prashnam (താംബൂല പ്രശ്നം)** — the querent offers a count of
  betel leaves; parity and the remainder mod 8 are read together with the
  prashna chart.
* **Swarna prashnam (സ്വർണ പ്രശ്നം)** — the querent touches one of 12
  unlabeled rasi squares; that square is the arudha (ആരൂഢം), read against the
  udaya lagna and the Moon.
* **Sankhya prashnam (സംഖ്യാ പ്രശ്നം)** — the querent names a number from the
  sacred 1–108; it maps to a rasi (9 numbers each) and a nakshatra (4 numbers
  each), KP-horary style, read against the udaya lagna.

Split of responsibilities (the app-wide rule): this module COMPUTES structured
facts and retrieval cues; what those facts traditionally *mean* lives in the
knowledge corpus (topic "prashnam", curated, reviewed=False pending astrologer
review); the LLM only narrates. The classical arudha-vs-lagna house classes
(kendra/trikona/dusthana/upachaya) follow Prasna Marga conventions; the
thamboola count scheme is a simplified curated draft, NOT a claim to replicate
an ashtamangala prashnam — the honesty guardrail in chat says so explicitly.
"""

from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS, RASIS

# House classes counted from the udaya lagna, in precedence order (a house is
# classified by its first match: 10 is kendra before upachaya, 6 is dusthana).
_HOUSE_CLASSES: tuple[tuple[str, frozenset[int]], ...] = (
    ("kendra", frozenset({1, 4, 7, 10})),      # angles — strength, quick results
    ("trikona", frozenset({5, 9})),            # trines — grace, favourable flow
    ("dusthana", frozenset({6, 8, 12})),       # duhkha houses — obstacles, delay
    ("upachaya", frozenset({3, 11})),          # growth houses — improves with effort
    ("sama", frozenset({2})),                  # neutral
)


def _house_class(house: int) -> str:
    for name, houses in _HOUSE_CLASSES:
        if house in houses:
            return name
    raise ValueError(f"house must be 1–12, got {house}")


def swarna_prashnam(arudha_rasi_index: int, prashna_chart: dict) -> dict:
    """Facts for a swarna prashnam pick: the arudha read against the moment.

    ``arudha_rasi_index`` is the 0–11 rasi square the querent touched. The
    classical combine is the arudha's whole-sign house counted from the udaya
    lagna (mutual kendra → strong/quick, trikona → favourable, dusthana →
    obstacles), plus where the Moon stands from the arudha.
    """
    if not 0 <= arudha_rasi_index <= 11:
        raise ValueError(f"arudha_rasi_index must be 0–11, got {arudha_rasi_index}")

    lagna_index = prashna_chart["udaya_lagna_index"]
    moon_index = prashna_chart["moon"]["rasi_index"]
    house_from_lagna = (arudha_rasi_index - lagna_index) % 12 + 1
    moon_from_arudha = (moon_index - arudha_rasi_index) % 12 + 1

    arudha_rasi = RASIS[arudha_rasi_index]
    relation = _house_class(house_from_lagna)
    return {
        "mode": "swarna",
        "arudha_rasi": arudha_rasi,
        "arudha_rasi_index": arudha_rasi_index,
        "udaya_lagnam": prashna_chart["udaya_lagnam"],
        "arudha_house_from_lagna": house_from_lagna,
        "arudha_lagna_relation": relation,
        "moon_house_from_arudha": moon_from_arudha,
        # BM25 cues — each maps to a curated corpus chunk (topic "prashnam").
        "cues": [
            f"prashnam arudha {arudha_rasi}",
            f"prashnam lagna house {house_from_lagna} {relation}",
        ],
    }


def sankhya_prashnam(number: int, prashna_chart: dict) -> dict:
    """Facts for a sankhya prashnam pick: a number from the sacred 1–108.

    The zodiac splits 108 evenly: 9 numbers per rasi and 4 per nakshatra (the
    108 navamsa padas), so the number lands on one rasi AND one nakshatra —
    KP-horary style. The rasi is read like an arudha against the udaya lagna;
    the nakshatra adds its temperament (its profile chunk lives in the corpus).
    """
    if not 1 <= number <= 108:
        raise ValueError(f"number must be 1–108, got {number}")

    rasi_index = (number - 1) * 12 // 108   # 9 numbers per rasi
    nak_index = (number - 1) * 27 // 108    # 4 numbers per nakshatra
    pada = (number - 1) % 4 + 1

    lagna_index = prashna_chart["udaya_lagna_index"]
    house_from_lagna = (rasi_index - lagna_index) % 12 + 1
    relation = _house_class(house_from_lagna)
    return {
        "mode": "sankhya",
        "number": number,
        "number_rasi": RASIS[rasi_index],
        "number_rasi_index": rasi_index,
        "number_nakshatram": NAKSHATRAS[nak_index],
        "number_pada": pada,
        "udaya_lagnam": prashna_chart["udaya_lagnam"],
        "number_house_from_lagna": house_from_lagna,
        "number_lagna_relation": relation,
        "cues": [
            "prashnam sankhya number",
            f"prashnam lagna house {house_from_lagna} {relation}",
            # The nakshatra name pulls its existing profile chunk.
            NAKSHATRAS[nak_index],
        ],
    }


def thamboola_prashnam(leaf_count: int, prashna_chart: dict) -> dict:
    """Facts for a thamboola prashnam offering of ``leaf_count`` betel leaves.

    Parity (odd = gati/movement, even = sthiti/steadiness) and the remainder
    mod 8 are the count facts; the prashna moment's Moon house from the udaya
    lagna anchors them in the chart. Meanings live in the corpus.
    """
    if leaf_count < 1:
        raise ValueError(f"leaf_count must be positive, got {leaf_count}")

    parity = "odd" if leaf_count % 2 else "even"
    remainder = leaf_count % 8
    moon_house = prashna_chart["moon"]["house"]
    return {
        "mode": "thamboola",
        "leaf_count": leaf_count,
        "parity": parity,
        "remainder": remainder,
        "udaya_lagnam": prashna_chart["udaya_lagnam"],
        "moon_house_from_lagna": moon_house,
        "moon_house_relation": _house_class(moon_house),
        "cues": [
            f"prashnam thamboola {parity} leaves",
            f"prashnam thamboola remainder {remainder}",
            f"prashnam lagna house {moon_house} {_house_class(moon_house)}",
        ],
    }
