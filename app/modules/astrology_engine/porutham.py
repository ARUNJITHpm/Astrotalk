"""Kerala ``pathu porutham`` (ten-fold marriage compatibility) — pure engine.

This is deterministic astrology: given two people's janma nakshatram and rasi,
it computes the classical ten Kerala poruthams and grades each one. Like
``doshas.py`` and ``prashnam.py``, the FACTS are computed here in Python; the
LLM only narrates them (and never as a decree — see the honesty note the chat
service attaches).

The ten poruthams (ദശപൊരുത്തം), in the order Kerala almanacs list them:

  1. ദിനം      Dina        — health / longevity of the union
  2. ഗണം       Gana        — temperament (deva / manushya / rakshasa)
  3. മഹേന്ദ്രം   Mahendra    — progeny and wellbeing
  4. സ്ത്രീദീർഘം Stree-Deergha— prosperity and the wife's longevity
  5. യോനി      Yoni        — physical / instinctual compatibility
  6. രാശി      Rasi        — general harmony of the moon signs
  7. രാശ്യാധിപൻ Rasyadhipathi— friendship of the two sign lords
  8. വശ്യം      Vasya       — mutual attraction / influence
  9. രജ്ജു      Rajju       — longevity of the married state (the weightiest)
 10. വേധം      Vedha       — mutual affliction

Every porutham is graded ``uthamam`` (best) / ``madhyamam`` (middling) /
``adhamam`` (unfavourable), each worth 1 / 0.5 / 0 point, so a match scores out
of 10. Directional poruthams (dina, mahendra, stree-deergha) count *from the
bride's (female) star to the groom's (male) star*, which is why the caller must
say which chart is the woman's.

Reference tables are the standard ones published in Kerala jyotisha manuals;
they are indexed to :data:`NAKSHATRAS` / :data:`RASIS` in ``swiss_ephemeris`` so
a computed chart's ``nakshatram`` / ``rasi`` strings resolve straight to a row.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS, RASIS

# --- Nakshatra attribute tables (indexed 0..26, aligned to NAKSHATRAS) --------

# Gana: 0 = deva (divine), 1 = manushya (human), 2 = rakshasa (demonic).
_DEVA, _MANUSHYA, _RAKSHASA = "deva", "manushya", "rakshasa"
_GANA_ML = {_DEVA: "ദേവഗണം", _MANUSHYA: "മനുഷ്യഗണം", _RAKSHASA: "രാക്ഷസഗണം"}
_GANA: list[str] = [
    _DEVA,      # 0  അശ്വതി   Ashwini
    _MANUSHYA,  # 1  ഭരണി     Bharani
    _RAKSHASA,  # 2  കാർത്തിക  Karthika
    _MANUSHYA,  # 3  രോഹിണി   Rohini
    _DEVA,      # 4  മകയിരം   Makayiram
    _MANUSHYA,  # 5  തിരുവാതിര Thiruvathira
    _DEVA,      # 6  പുണർതം   Punartham
    _DEVA,      # 7  പൂയം     Pooyam
    _RAKSHASA,  # 8  ആയില്യം  Ayilyam
    _RAKSHASA,  # 9  മകം      Makam
    _MANUSHYA,  # 10 പൂരം     Pooram
    _MANUSHYA,  # 11 ഉത്രം     Uthram
    _DEVA,      # 12 അത്തം     Attam
    _RAKSHASA,  # 13 ചിത്തിര   Chithira
    _DEVA,      # 14 ചോതി     Chothi
    _RAKSHASA,  # 15 വിശാഖം   Vishakham
    _DEVA,      # 16 അനിഴം    Anizham
    _RAKSHASA,  # 17 തൃക്കേട്ട   Thrikketta
    _RAKSHASA,  # 18 മൂലം     Moolam
    _MANUSHYA,  # 19 പൂരാടം   Pooradam
    _MANUSHYA,  # 20 ഉത്രാടം   Uthradam
    _DEVA,      # 21 തിരുവോണം Thiruvonam
    _RAKSHASA,  # 22 അവിട്ടം   Avittam
    _RAKSHASA,  # 23 ചതയം    Chathayam
    _MANUSHYA,  # 24 പൂരുരുട്ടാതി Pururuttathi
    _MANUSHYA,  # 25 ഉത്രട്ടാതി  Uthrattathi
    _DEVA,      # 26 രേവതി    Revathi
]

# Yoni (animal symbol) per nakshatra, with the animal's sex. Two nakshatras
# share each of the 14 animals (one male, one female). Names are the Malayalam
# terms almanacs use.
_YONI: list[str] = [
    "കുതിര",   # 0  Ashwini      horse
    "ആന",     # 1  Bharani      elephant
    "ആട്",     # 2  Karthika     goat/sheep
    "പാമ്പ്",   # 3  Rohini       serpent
    "പാമ്പ്",   # 4  Makayiram    serpent
    "പട്ടി",    # 5  Thiruvathira dog
    "പൂച്ച",   # 6  Punartham    cat
    "ആട്",     # 7  Pooyam       goat/sheep
    "പൂച്ച",   # 8  Ayilyam      cat
    "എലി",    # 9  Makam        rat
    "എലി",    # 10 Pooram       rat
    "പശു",    # 11 Uthram       cow
    "പോത്ത്",  # 12 Attam        buffalo
    "പുലി",    # 13 Chithira     tiger
    "പോത്ത്",  # 14 Chothi       buffalo
    "പുലി",    # 15 Vishakham    tiger
    "മാൻ",    # 16 Anizham      deer
    "മാൻ",    # 17 Thrikketta    deer
    "പട്ടി",    # 18 Moolam       dog
    "കുരങ്ങ്",  # 19 Pooradam     monkey
    "കീരി",    # 20 Uthradam     mongoose
    "കുരങ്ങ്",  # 21 Thiruvonam   monkey
    "സിംഹം",  # 22 Avittam      lion
    "കുതിര",   # 23 Chathayam    horse
    "സിംഹം",  # 24 Pururuttathi  lion
    "പശു",    # 25 Uthrattathi   cow
    "ആന",     # 26 Revathi      elephant
]

# Enemy (mrityu) yoni pairs — natural predators. Any other pairing is neutral or
# (same animal) friendly. Stored as a set of frozensets for O(1) lookup.
_YONI_ENEMIES: set[frozenset[str]] = {
    frozenset({"പശു", "പുലി"}),      # cow / tiger
    frozenset({"ആന", "സിംഹം"}),      # elephant / lion
    frozenset({"കുതിര", "പോത്ത്"}),   # horse / buffalo
    frozenset({"പട്ടി", "മാൻ"}),      # dog / deer
    frozenset({"പാമ്പ്", "കീരി"}),     # serpent / mongoose
    frozenset({"പൂച്ച", "എലി"}),      # cat / rat
    frozenset({"കുരങ്ങ്", "ആട്"}),     # monkey / goat
}

# Rajju: the body-part group a nakshatra belongs to. Sharing a rajju is the
# classic rajju dosha (it threatens the mangalya / longevity of the marriage),
# so this is the single most important porutham. 6/6/6/6/3 split of the 27.
_PADA, _KATI, _NABHI, _KANTA, _SIRA = "pada", "kati", "nabhi", "kanta", "sira"
_RAJJU: list[str] = [
    _PADA,   # 0  Ashwini
    _KATI,   # 1  Bharani
    _NABHI,  # 2  Karthika
    _KANTA,  # 3  Rohini
    _SIRA,   # 4  Makayiram
    _KANTA,  # 5  Thiruvathira
    _NABHI,  # 6  Punartham
    _KATI,   # 7  Pooyam
    _PADA,   # 8  Ayilyam
    _PADA,   # 9  Makam
    _KATI,   # 10 Pooram
    _NABHI,  # 11 Uthram
    _KANTA,  # 12 Attam
    _SIRA,   # 13 Chithira
    _KANTA,  # 14 Chothi
    _NABHI,  # 15 Vishakham
    _KATI,   # 16 Anizham
    _PADA,   # 17 Thrikketta
    _PADA,   # 18 Moolam
    _KATI,   # 19 Pooradam
    _NABHI,  # 20 Uthradam
    _KANTA,  # 21 Thiruvonam
    _SIRA,   # 22 Avittam
    _KANTA,  # 23 Chathayam
    _NABHI,  # 24 Pururuttathi
    _KATI,   # 25 Uthrattathi
    _PADA,   # 26 Revathi
]

# Malayalam label for each rajju group (for the reason strings).
_RAJJU_ML = {
    _PADA: "പാദ", _KATI: "കടി", _NABHI: "നാഭി", _KANTA: "കണ്ഠ", _SIRA: "ശിരോ",
}

# Vedha (mutual affliction) nakshatra pairs. If the couple's two stars form a
# pair here, the vedha porutham fails. Chithira (13) has no vedha partner.
_VEDHA_PAIRS: set[frozenset[int]] = {
    frozenset({0, 17}),   # Ashwini    / Thrikketta
    frozenset({1, 16}),   # Bharani    / Anizham
    frozenset({2, 15}),   # Karthika   / Vishakham
    frozenset({3, 14}),   # Rohini     / Chothi
    frozenset({4, 22}),   # Makayiram  / Avittam
    frozenset({5, 21}),   # Thiruvathira/ Thiruvonam
    frozenset({6, 20}),   # Punartham  / Uthradam
    frozenset({7, 19}),   # Pooyam     / Pooradam
    frozenset({8, 18}),   # Ayilyam    / Moolam
    frozenset({9, 26}),   # Makam      / Revathi
    frozenset({10, 25}),  # Pooram     / Uthrattathi
    frozenset({11, 24}),  # Uthram     / Pururuttathi
    frozenset({12, 23}),  # Attam      / Chathayam
}

# --- Rasi (moon-sign) attribute tables (indexed 0..11, aligned to RASIS) ------

# The lord (adhipan) of each rasi, by the same graha ids swiss_ephemeris uses.
_RASI_LORD: list[str] = [
    "chevvai",   # 0  മേടം    Mesha    — Mars
    "shukran",   # 1  ഇടവം    Vrishabha— Venus
    "budhan",    # 2  മിഥുനം   Mithuna  — Mercury
    "chandra",   # 3  കർക്കടകം Karka    — Moon
    "surya",     # 4  ചിങ്ങം   Simha    — Sun
    "budhan",    # 5  കന്നി     Kanya    — Mercury
    "shukran",   # 6  തുലാം    Tula     — Venus
    "chevvai",   # 7  വൃശ്ചികം Vrischika— Mars
    "guru",      # 8  ധനു      Dhanu    — Jupiter
    "shani",     # 9  മകരം    Makara   — Saturn
    "shani",     # 10 കുംഭം    Kumbha   — Saturn
    "guru",      # 11 മീനം     Meena    — Jupiter
]

# Naisargika (natural) planetary friendship. friends[a] holds the grahas that
# planet ``a`` regards as a friend; enemies[a] its enemies. Anything in neither
# set is neutral. The relation is not always symmetric (e.g. Sun befriends
# Jupiter, Jupiter befriends Sun; but Venus's and the Moon's differ).
_FRIENDS: dict[str, set[str]] = {
    "surya":   {"chandra", "chevvai", "guru"},
    "chandra": {"surya", "budhan"},
    "chevvai": {"surya", "chandra", "guru"},
    "budhan":  {"surya", "shukran"},
    "guru":    {"surya", "chandra", "chevvai"},
    "shukran": {"budhan", "shani"},
    "shani":   {"budhan", "shukran"},
}
_ENEMIES: dict[str, set[str]] = {
    "surya":   {"shukran", "shani"},
    "chandra": set(),
    "chevvai": {"budhan"},
    "budhan":  {"chandra"},
    "guru":    {"budhan", "shukran"},
    "shukran": {"surya", "chandra"},
    "shani":   {"surya", "chandra", "chevvai"},
}

# Malayalam graha labels for the reason strings.
_GRAHA_ML = {
    "surya": "സൂര്യൻ", "chandra": "ചന്ദ്രൻ", "chevvai": "ചൊവ്വ",
    "budhan": "ബുധൻ", "guru": "വ്യാഴം", "shukran": "ശുക്രൻ", "shani": "ശനി",
}

# Vasya (mutual influence): the set of rasis that each rasi holds sway over.
# male's rasi ∈ vasya[female's rasi] → the wife draws the husband, and so on.
_VASYA: list[set[int]] = [
    {4, 7},    # 0  Mesha    -> Simha, Vrischika
    {3, 6},    # 1  Vrishabha-> Karka, Tula
    {5},       # 2  Mithuna  -> Kanya
    {7, 8},    # 3  Karka    -> Vrischika, Dhanu
    {6},       # 4  Simha    -> Tula
    {2, 11},   # 5  Kanya    -> Mithuna, Meena
    {9, 5},    # 6  Tula     -> Makara, Kanya
    {3},       # 7  Vrischika-> Karka
    {11},      # 8  Dhanu    -> Meena
    {0, 10},   # 9  Makara   -> Mesha, Kumbha
    {0},       # 10 Kumbha   -> Mesha
    {9},       # 11 Meena    -> Makara
]

# Grades and their point value out of 1.
UTHAMAM, MADHYAMAM, ADHAMAM = "uthamam", "madhyamam", "adhamam"
_POINTS = {UTHAMAM: 1.0, MADHYAMAM: 0.5, ADHAMAM: 0.0}


@dataclass(frozen=True)
class Star:
    """One person's porutham inputs, resolved to table indices.

    ``nakshatra`` / ``rasi`` are 0-based indices into
    :data:`NAKSHATRAS` / :data:`RASIS`. ``sex`` is ``"female"`` or ``"male"`` —
    the directional poruthams count from the female's star to the male's.
    """

    nakshatra: int
    rasi: int
    sex: str
    name: str = ""

    @property
    def nakshatra_ml(self) -> str:
        return NAKSHATRAS[self.nakshatra]

    @property
    def rasi_ml(self) -> str:
        return RASIS[self.rasi]


def star_from_chart(natal: dict, sex: str, name: str = "") -> Star:
    """Build a :class:`Star` from a computed natal chart dict.

    Resolves the chart's ``nakshatram`` / ``rasi`` Malayalam strings back to
    their table indices. Raises ``ValueError`` if the chart lacks a real moon
    placement (e.g. a mock or ``pending`` chart) so the caller can degrade
    gracefully instead of scoring garbage.
    """
    nak = natal.get("nakshatram")
    rasi = natal.get("rasi")
    if nak not in NAKSHATRAS or rasi not in RASIS:
        raise ValueError(
            f"chart has no usable moon placement (nakshatram={nak!r}, rasi={rasi!r})"
        )
    return Star(
        nakshatra=NAKSHATRAS.index(nak),
        rasi=RASIS.index(rasi),
        sex=sex,
        name=name,
    )


def _count(from_idx: int, to_idx: int, span: int) -> int:
    """Inclusive forward count from ``from_idx`` to ``to_idx`` on a wheel of
    ``span`` positions (so the count is always 1..span)."""
    return (to_idx - from_idx) % span + 1


def _graded(grade: str, points_label: str, reason: str) -> dict:
    return {
        "grade": grade,
        "points": _POINTS[grade],
        "label": points_label,
        "reason": reason,
    }


# --- The ten poruthams. Each takes (female, male) and returns a graded dict. --

def _dina(female: Star, male: Star) -> dict:
    """Dina (tara) — count from the bride's star to the groom's, remainder mod 9.
    Even remainders (and 0) are auspicious for health and longevity."""
    n = _count(female.nakshatra, male.nakshatra, 27)
    rem = n % 9
    good = rem % 2 == 0  # 0, 2, 4, 6, 8
    grade = UTHAMAM if good else ADHAMAM
    return _graded(
        grade, "ദിനപ്പൊരുത്തം",
        f"വധുവിന്റെ {female.nakshatra_ml} മുതൽ വരന്റെ {male.nakshatra_ml} വരെ "
        f"എണ്ണം {n} (9-ന്റെ ശിഷ്ടം {rem}) — "
        + ("ശുഭം." if good else "അനുകൂലമല്ല."),
    )


def _gana(female: Star, male: Star) -> dict:
    """Gana — temperament. Same gana is best; deva+manushya workable; the
    rakshasa+deva pairing is the hardest."""
    gf, gm = _GANA[female.nakshatra], _GANA[male.nakshatra]
    if gf == gm:
        grade = UTHAMAM
    elif {gf, gm} == {_DEVA, _RAKSHASA}:
        grade = ADHAMAM
    else:
        grade = MADHYAMAM
    return _graded(
        grade, "ഗണപ്പൊരുത്തം",
        f"വധു {_GANA_ML[gf]}, വരൻ {_GANA_ML[gm]}.",
    )


def _mahendra(female: Star, male: Star) -> dict:
    """Mahendra — progeny and wellbeing. The count from the bride's star to the
    groom's landing on 4, 7, 10, 13, 16, 19, 22 or 25 is auspicious."""
    n = _count(female.nakshatra, male.nakshatra, 27)
    good = n in {4, 7, 10, 13, 16, 19, 22, 25}
    grade = UTHAMAM if good else ADHAMAM
    return _graded(
        grade, "മഹേന്ദ്രപ്പൊരുത്തം",
        f"വധുവിൽ നിന്ന് വരനിലേക്കുള്ള എണ്ണം {n} — "
        + ("മഹേന്ദ്രസ്ഥാനം; ശുഭം." if good else "മഹേന്ദ്രസ്ഥാനമല്ല."),
    )


def _stree_deergha(female: Star, male: Star) -> dict:
    """Stree-deergha — the wife's longevity and the couple's prosperity. The
    groom's star counted from the bride's should be well beyond the 9th; 8-9 is
    middling, nearer than that is weak."""
    n = _count(female.nakshatra, male.nakshatra, 27)
    if n > 9:
        grade = UTHAMAM
    elif n >= 7:
        grade = MADHYAMAM
    else:
        grade = ADHAMAM
    return _graded(
        grade, "സ്ത്രീദീർഘപ്പൊരുത്തം",
        f"വധുവിൽ നിന്ന് വരനിലേക്കുള്ള എണ്ണം {n} — "
        + ("ദീർഘമുണ്ട്; ശുഭം." if n > 9 else
           "മധ്യമം." if n >= 7 else "ദീർഘം കുറവ്."),
    )


def _yoni(female: Star, male: Star) -> dict:
    """Yoni — instinctual compatibility by animal symbol. Same animal is best,
    enemy animals the worst, everything else neutral."""
    yf, ym = _YONI[female.nakshatra], _YONI[male.nakshatra]
    if yf == ym:
        grade = UTHAMAM
        note = "ഒരേ യോനി."
    elif frozenset({yf, ym}) in _YONI_ENEMIES:
        grade = ADHAMAM
        note = "ശത്രുയോനി."
    else:
        grade = MADHYAMAM
        note = "മധ്യമയോനി."
    return _graded(
        grade, "യോനിപ്പൊരുത്തം",
        f"വധു {yf}, വരൻ {ym} — {note}",
    )


def _rasi(female: Star, male: Star) -> dict:
    """Rasi (bhakoot) — harmony of the moon signs. The 6/8 (shashtashtaka)
    placement is the classic dosha; 2/12 (dwirdwadasha) is a milder blemish;
    anything else (including the same sign) is favourable."""
    fwd = _count(female.rasi, male.rasi, 12)   # female -> male, 1..12
    rev = _count(male.rasi, female.rasi, 12)   # male -> female, 1..12
    pair = {fwd, rev}
    if pair == {6, 8}:
        grade, note = ADHAMAM, "ഷഷ്ടാഷ്ടകം (6/8) — ദോഷം."
    elif pair == {2, 12}:
        grade, note = MADHYAMAM, "ദ്വിർദ്വാദശം (2/12) — മധ്യമം."
    else:
        grade, note = UTHAMAM, "രാശിപ്പൊരുത്തം ശുഭം."
    return _graded(
        grade, "രാശിപ്പൊരുത്തം",
        f"വധു {female.rasi_ml}, വരൻ {male.rasi_ml} — {note}",
    )


def _relation(a_lord: str, b_lord: str) -> str:
    """How planet ``a_lord`` regards ``b_lord``: friend / enemy / neutral."""
    if a_lord == b_lord:
        return "friend"
    if b_lord in _FRIENDS.get(a_lord, set()):
        return "friend"
    if b_lord in _ENEMIES.get(a_lord, set()):
        return "enemy"
    return "neutral"


def _rasyadhipathi(female: Star, male: Star) -> dict:
    """Rasyadhipathi — friendship of the two sign lords. Mutual friends (or the
    same lord) is best; a friend-neutral mix is middling; mutual enmity fails."""
    lf, lm = _RASI_LORD[female.rasi], _RASI_LORD[male.rasi]
    rel_fm = _relation(lf, lm)
    rel_mf = _relation(lm, lf)
    rels = {rel_fm, rel_mf}
    if lf == lm or rels == {"friend"}:
        grade = UTHAMAM
    elif "enemy" in rels and "friend" not in rels:
        grade = ADHAMAM
    elif "enemy" in rels:
        grade = MADHYAMAM       # one friend, one enemy — mixed
    else:
        grade = MADHYAMAM       # friend/neutral or neutral/neutral
    return _graded(
        grade, "രാശ്യാധിപപ്പൊരുത്തം",
        f"വധുവിന്റെ അധിപൻ {_GRAHA_ML[lf]}, വരന്റെ അധിപൻ {_GRAHA_ML[lm]} — "
        f"({rel_fm}/{rel_mf}).",
    )


def _vasya(female: Star, male: Star) -> dict:
    """Vasya — mutual attraction. Best when each sign holds sway over the other;
    one-way is middling; neither is weak."""
    fm = male.rasi in _VASYA[female.rasi]     # wife draws husband
    mf = female.rasi in _VASYA[male.rasi]     # husband draws wife
    if fm and mf:
        grade, note = UTHAMAM, "പരസ്പര വശ്യം."
    elif fm or mf:
        grade, note = MADHYAMAM, "ഏകപക്ഷ വശ്യം."
    else:
        grade, note = ADHAMAM, "വശ്യമില്ല."
    return _graded(
        grade, "വശ്യപ്പൊരുത്തം",
        f"വധു {female.rasi_ml}, വരൻ {male.rasi_ml} — {note}",
    )


def _rajju(female: Star, male: Star) -> dict:
    """Rajju — the weightiest porutham, guarding the longevity of the marriage.
    Sharing a rajju group is rajju dosha (unfavourable); different groups pass."""
    rf, rm = _RAJJU[female.nakshatra], _RAJJU[male.nakshatra]
    same = rf == rm
    grade = ADHAMAM if same else UTHAMAM
    if same:
        note = f"ഇരുവരും {_RAJJU_ML[rf]}രജ്ജു — രജ്ജുദോഷം."
    else:
        note = f"വധു {_RAJJU_ML[rf]}രജ്ജു, വരൻ {_RAJJU_ML[rm]}രജ്ജു — ദോഷമില്ല."
    return _graded(grade, "രജ്ജുപ്പൊരുത്തം", note)


def _vedha(female: Star, male: Star) -> dict:
    """Vedha — mutual affliction. A vedha star-pair fails; otherwise passes."""
    afflicted = frozenset({female.nakshatra, male.nakshatra}) in _VEDHA_PAIRS
    grade = ADHAMAM if afflicted else UTHAMAM
    note = "വേധദോഷം." if afflicted else "വേധദോഷമില്ല."
    return _graded(
        grade, "വേധപ്പൊരുത്തം",
        f"വധു {female.nakshatra_ml}, വരൻ {male.nakshatra_ml} — {note}",
    )


# The ten, in almanac order. (key, human title, function)
_PORUTHAMS: list[tuple[str, callable]] = [
    ("dina", _dina),
    ("gana", _gana),
    ("mahendra", _mahendra),
    ("stree_deergha", _stree_deergha),
    ("yoni", _yoni),
    ("rasi", _rasi),
    ("rasyadhipathi", _rasyadhipathi),
    ("vasya", _vasya),
    ("rajju", _rajju),
    ("vedha", _vedha),
]


def compute_porutham(female: Star, male: Star) -> dict:
    """Compute all ten Kerala poruthams for a (female, male) pair.

    Returns a plain JSON-serialisable dict::

        {
          "female": {...}, "male": {...},        # echoed inputs (nakshatra/rasi)
          "poruthams": {"dina": {grade, points, label, reason}, ...},
          "score": 7.5, "max_score": 10.0,
          "rajju_dosha": False,                  # the make-or-break flag
          "favourable": [...], "unfavourable": [...],
        }

    No verdict text and no "should they marry" judgement — that framing is the
    chat persona's job, under the honesty rule. This function only reports the
    computed facts.
    """
    results: dict[str, dict] = {}
    score = 0.0
    for key, fn in _PORUTHAMS:
        r = fn(female, male)
        results[key] = r
        score += r["points"]

    favourable = [k for k, r in results.items() if r["grade"] == UTHAMAM]
    unfavourable = [k for k, r in results.items() if r["grade"] == ADHAMAM]

    return {
        "female": {
            "name": female.name,
            "nakshatram": female.nakshatra_ml,
            "rasi": female.rasi_ml,
        },
        "male": {
            "name": male.name,
            "nakshatram": male.nakshatra_ml,
            "rasi": male.rasi_ml,
        },
        "poruthams": results,
        "score": round(score, 1),
        "max_score": float(len(_PORUTHAMS)),
        "rajju_dosha": results["rajju"]["grade"] == ADHAMAM,
        "favourable": favourable,
        "unfavourable": unfavourable,
    }
