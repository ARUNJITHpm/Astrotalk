"""Starter knowledge base for RAG retrieval (internal to the knowledge module).

⚠️ DRAFT CONTENT — NOT astrologer-reviewed. Every chunk is marked
``reviewed=False``. The corpus follows the production content plan: interpretation
knowledge is *retrieved* (this file), chart facts are *computed* (astrology_engine),
and only the language is *generated* (LLM). Structure:

  - 108 planet-in-house entries (9 grahas × 12 bhavas) — the classic subset is
    hand-written; the rest are composed offline from classical signification
    tables (planet expression × house domain), awaiting astrologer review.
  - 27 nakshatra (birth star) profiles, keyed by the Malayalam names the
    astrology engine emits.
  - 9 Vimshottari mahadasha profiles (one per lord).
  - 12 lagna (ascendant) profiles, keyed by Malayalam rasi names.
  - Dosha framing (chovva/Mangal, Kala Sarpa, Sade Sati) matching the facts
    ``astrology_engine.doshas`` detects, plus remedy framing and Kerala FAQ
    chunks (porutham, muhurtham).

Every text carries the Malayalam term inline (e.g. "Saturn (ശനി)") so the BM25
retriever matches queries written in Malayalam script as well as English.

Tone follows GUARDRAILS.md §1: guidance and agency, never fear, never doom,
never "pay-or-else". Keep that framing when chunks are replaced or reviewed.
"""

from typing import TypedDict


class SeedChunk(TypedDict):
    id: str
    topic: str
    text: str
    reviewed: bool


# ---------------------------------------------------------------------------
# Hand-written chunks: the original six, kept verbatim (ids are referenced by
# tests and possibly by stored traces).
# ---------------------------------------------------------------------------

_ORIGINAL_CHUNKS: list[SeedChunk] = [
    {
        "id": "planet-in-house-saturn-10",
        "topic": "planet-in-house",
        "text": (
            "Saturn in the 10th house points to a career built slowly through "
            "patience and responsibility. It rewards steady, honest effort over "
            "shortcuts. The discipline it asks for tends to become a real strength "
            "in midlife — the stars incline toward steady growth here, they do not "
            "compel any single outcome."
        ),
        "reviewed": False,
    },
    {
        "id": "planet-in-house-jupiter-5",
        "topic": "planet-in-house",
        "text": (
            "Jupiter in the 5th house favours learning, creativity, and warmth "
            "with children and students. It is a placement associated with "
            "optimism and good counsel. A gentle reminder: its blessings grow when "
            "you act on them, not by waiting for luck."
        ),
        "reviewed": False,
    },
    {
        "id": "retrograde-mercury",
        "topic": "retrograde",
        "text": (
            "A Mercury retrograde is a season for review, not dread. It tends to "
            "surface miscommunications, delays, and second drafts. Treat it as an "
            "invitation to slow down, re-read, and reconnect with old threads — "
            "there is nothing here to fear, only things worth double-checking."
        ),
        "reviewed": False,
    },
    {
        "id": "retrograde-saturn",
        "topic": "retrograde",
        "text": (
            "Saturn retrograde is a quiet time to revisit commitments and "
            "boundaries. It asks honest questions about where effort is going. It "
            "is reflective rather than punishing — a chance to realign work with "
            "what genuinely matters to you."
        ),
        "reviewed": False,
    },
    {
        "id": "porutham-basics",
        "topic": "porutham",
        "text": (
            "Porutham (Kerala marriage compatibility) traditionally weighs ten "
            "factors, including Dina, Gana, Mahendra, Stree-Deergha, and Rasi "
            "porutham, comparing the couple's birth stars. It is best read as a "
            "balanced conversation starter about compatibility, never as a verdict "
            "or a source of fear. A low score is information to discuss, not doom."
        ),
        "reviewed": False,
    },
    {
        "id": "nakshatra-moon-mind",
        "topic": "nakshatra",
        "text": (
            "In Vedic astrology the Moon's nakshatra (birth star) is linked to the "
            "emotional temperament and instincts. Knowing it helps frame how a "
            "person processes feelings and stress. It describes tendencies and "
            "leanings — it is guidance for self-understanding, not a fixed fate."
        ),
        "reviewed": False,
    },
]

# ---------------------------------------------------------------------------
# Planet-in-house grid (9 grahas × 12 bhavas), composed from classical
# signification tables. NOTE: the glossary below intentionally duplicates a few
# Malayalam names from astrology_engine — module boundaries (AGENTS.md) forbid
# knowledge importing astrology_engine internals.
# ---------------------------------------------------------------------------

# graha id → (English, Malayalam, "brings … to", growth note)
_PLANETS: dict[str, tuple[str, str, str, str]] = {
    "surya": (
        "Sun", "സൂര്യൻ",
        "brings a strong sense of purpose, dignity, vitality, and leadership to",
        "Watch for pride or a need to dominate here; this gift matures when "
        "authority is carried with humility.",
    ),
    "chandra": (
        "Moon", "ചന്ദ്രൻ",
        "brings emotional sensitivity, care, imagination, and responsiveness to",
        "Moods can colour this area strongly; naming feelings honestly keeps "
        "its gifts steady.",
    ),
    "chevvai": (
        "Mars", "ചൊവ്വ",
        "brings energy, courage, initiative, and a competitive drive to",
        "Impatience or friction can flare here; channelled into disciplined "
        "action, the same fire becomes real achievement.",
    ),
    "budhan": (
        "Mercury", "ബുധൻ",
        "brings quick thinking, communication skill, wit, and adaptability to",
        "Scattered attention is the main risk; focus turns its cleverness "
        "into lasting skill.",
    ),
    "guru": (
        "Jupiter", "വ്യാഴം",
        "brings wisdom, optimism, expansion, and a protective grace to",
        "Its blessings grow through action, not waiting; over-confidence is "
        "the only trap to watch.",
    ),
    "shukran": (
        "Venus", "ശുക്രൻ",
        "brings charm, harmony, artistic taste, and enjoyment to",
        "Indulgence is the risk; balanced enjoyment keeps this a place of "
        "genuine happiness.",
    ),
    "shani": (
        "Saturn", "ശനി",
        "brings discipline, patience, endurance, and slow but lasting results to",
        "Delays here are seasoning, not denial; steady honest effort is "
        "repaid late but in full.",
    ),
    "rahu": (
        "Rahu", "രാഹു",
        "brings intense ambition, unconventional methods, and worldly hunger to",
        "It can exaggerate desire; grounded ethics turn that hunger into "
        "remarkable, self-made achievement.",
    ),
    "ketu": (
        "Ketu", "കേതു",
        "brings detachment, spiritual questioning, and quiet intuition to",
        "It can feel like disinterest in this area; treated as inner freedom, "
        "it becomes deep insight rather than loss.",
    ),
}

# house number → (Malayalam bhava name, domain summary)
_HOUSES: dict[int, tuple[str, str]] = {
    1: ("ലഗ്നം / തനുഭാവം", "the self — body, temperament, and how life is met"),
    2: ("ധനസ്ഥാനം", "wealth, family, food, and the power of speech"),
    3: ("സഹോദരസ്ഥാനം", "siblings, courage, skills, and communication"),
    4: ("സുഖസ്ഥാനം", "home, mother, vehicles, property, and inner peace"),
    5: ("പുത്രസ്ഥാനം / വിദ്യാസ്ഥാനം", "children, education, creativity, and merit of past deeds"),
    6: ("രോഗസ്ഥാനം / ശത്രുസ്ഥാനം", "health challenges, service, debts, and rivals"),
    7: ("കളത്രസ്ഥാനം", "marriage, partnership, and one-to-one relationships"),
    8: ("ആയുസ്സ്ഥാനം", "longevity, transformation, research, and hidden matters"),
    9: ("ഭാഗ്യസ്ഥാനം", "fortune, dharma, father, guru, and long journeys"),
    10: ("കർമ്മസ്ഥാനം", "career, public reputation, and standing in society"),
    11: ("ലാഭസ്ഥാനം", "gains, income, friendships, and aspirations"),
    12: ("വ്യയസ്ഥാനം", "expenditure, foreign lands, rest, and liberation (moksha)"),
}

_ORDINALS = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
    7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
}

# Hand-written overrides for classic placements (id → text). Keyed by the same
# generated id scheme so they replace, not duplicate, the composed entry.
_PLANET_HOUSE_OVERRIDES: dict[str, str] = {
    "planet-in-house-mars-7": (
        "Mars (ചൊവ്വ) in the 7th house (കളത്രസ്ഥാനം — marriage and partnership) "
        "brings passion, honesty, and independence into close relationships. It "
        "is one of the chovva dosha placements, traditionally read as a call for "
        "patience and matched temperaments — not as a barrier to marriage. With "
        "open communication the same intensity becomes deep loyalty; the stars "
        "incline, they never compel."
    ),
    "planet-in-house-rahu-10": (
        "Rahu (രാഹു) in the 10th house (കർമ്മസ്ഥാനം — career and public life) is a "
        "signature of unusual, often self-made professional ambition. It favours "
        "modern fields, foreign connections, and paths no one in the family has "
        "walked. Kept honest, it can lift a person unusually high; the choice of "
        "means always remains yours."
    ),
    "planet-in-house-moon-4": (
        "The Moon (ചന്ദ്രൻ) in the 4th house (സുഖസ്ഥാനം — home and inner peace) is "
        "in its natural domain: a deep bond with the mother, the home, and the "
        "homeland. Emotional security matters more than outward success for this "
        "placement. Tending the home life steadies everything else built upon it."
    ),
    "planet-in-house-venus-7": (
        "Venus (ശുക്രൻ) in the 7th house (കളത്രസ്ഥാനം — marriage) is a classic "
        "indicator of a warm, affectionate partnership and a spouse who brings "
        "beauty and balance into life. Its gift asks for reciprocity: harmony "
        "grows when appreciation is spoken aloud, not assumed."
    ),
    "planet-in-house-sun-10": (
        "The Sun (സൂര്യൻ) in the 10th house (കർമ്മസ്ഥാനം — career and status) is "
        "dig bala — directionally strong. It points to visible achievement, "
        "leadership, and recognition from authority. Its light is brightest when "
        "ambition serves something larger than the self."
    ),
}


def _planet_house_chunks() -> list[SeedChunk]:
    """Compose the 9×12 grid, skipping ids already hand-written above."""
    existing = {c["id"] for c in _ORIGINAL_CHUNKS}
    chunks: list[SeedChunk] = []
    for en_key, (en, ml, gives, note) in _PLANETS.items():
        slug = en.lower()
        for house, (bhava_ml, domain) in _HOUSES.items():
            cid = f"planet-in-house-{slug}-{house}"
            if cid in existing:
                continue
            text = _PLANET_HOUSE_OVERRIDES.get(cid) or (
                f"{en} ({ml}) in the {_ORDINALS[house]} house ({bhava_ml} — "
                f"{domain}) {gives} this area of life. {note} This placement "
                "describes a leaning, not a verdict — the stars incline, they "
                "never compel, and your choices decide how it unfolds."
            )
            chunks.append(
                {"id": cid, "topic": "planet-in-house", "text": text, "reviewed": False}
            )
    return chunks


# ---------------------------------------------------------------------------
# 27 nakshatra profiles, keyed by the Malayalam names the engine emits.
# (name_ml, sanskrit/english alias, profile text)
# ---------------------------------------------------------------------------

_NAKSHATRA_PROFILES: list[tuple[str, str, str]] = [
    ("അശ്വതി", "Ashwathi (Ashwini)",
     "quick, pioneering, and healing by nature — people of this star start things "
     "fast and lift others when they arrive. Their growth lies in finishing what "
     "their enthusiasm begins."),
    ("ഭരണി", "Bharani",
     "born with unusual endurance and the capacity to carry heavy responsibility. "
     "They create, nurture, and transform; life rewards them when they pace "
     "themselves instead of bearing everything alone."),
    ("കാർത്തിക", "Karthika (Krittika)",
     "sharp, purifying, and honest like a flame — natural leaders and critics "
     "with high standards. Warmth spoken alongside truth makes their fire "
     "nourishing rather than scorching."),
    ("രോഹിണി", "Rohini",
     "graced with charm, artistic taste, and a love of comfort and growth — the "
     "Moon's favourite star. Their steadiness builds beautiful things; possessive "
     "attachment is the only weed to watch in that garden."),
    ("മകയിരം", "Makayiram (Mrigashira)",
     "gentle, curious, and always searching — for knowledge, places, and the "
     "perfect answer. The search itself is their gift; contentment comes when "
     "they let good-enough be beautiful."),
    ("തിരുവാതിര", "Thiruvathira (Ardra)",
     "intense and storm-like in feeling, with real power of renewal — after their "
     "rains, everything grows. Emotional honesty, not suppression, is what turns "
     "their storms into fresh starts."),
    ("പുണർതം", "Punartham (Punarvasu)",
     "resilient and optimistic — the star of returning light. However far they "
     "wander or fall, they find the way home and begin again, and they teach "
     "others that recovery is always possible."),
    ("പൂയം", "Pooyam (Pushya)",
     "nourishing, dutiful, and considered among the most auspicious stars — "
     "natural caretakers whom others instinctively trust. Their lesson is to "
     "receive care as gracefully as they give it."),
    ("ആയില്യം", "Ayilyam (Ashlesha)",
     "perceptive and almost mystical in their ability to read people and "
     "situations. Used with kindness, that penetrating insight heals; they "
     "flourish where depth is welcomed, not feared."),
    ("മകം", "Makam (Magha)",
     "dignified and rooted in ancestry and tradition — they carry their family "
     "line with pride and natural authority. Honouring the past while writing "
     "their own chapter is their life's balance."),
    ("പൂരം", "Pooram (Purva Phalguni)",
     "sociable, artistic, and made for celebration — they bring ease, pleasure, "
     "and warmth wherever they go. Their creativity ripens when joy is paired "
     "with a little discipline."),
    ("ഉത്രം", "Uthram (Uttara Phalguni)",
     "generous, reliable, and quietly noble — the friend who actually shows up. "
     "They prosper through partnerships and keeping their word, and they grow by "
     "asking for help as readily as they offer it."),
    ("അത്തം", "Atham (Hasta)",
     "skilled with their hands and quick with their wit — craftspeople, healers, "
     "and problem-solvers. Their cleverness serves them best when it works for "
     "something the heart has chosen."),
    ("ചിത്തിര", "Chithira (Chitra)",
     "brilliant, design-minded, and drawn to beauty in structure — they see the "
     "finished form before others see the parts. Patience with slow materials, "
     "including people, completes their art."),
    ("ചോതി", "Chothi (Swati)",
     "independent and flexible like the wind — they need room to move and think "
     "for themselves. Given freedom they are diplomatic, fair, and quietly "
     "prosperous; fencing them in only scatters their gifts."),
    ("വിശാഖം", "Vishakham (Vishakha)",
     "determined and goal-focused — once the aim is fixed, they rarely stop "
     "before reaching it. Their growth lies in enjoying the road and the "
     "companions on it, not only the arrival."),
    ("അനിഴം", "Anizham (Anuradha)",
     "devoted, cooperative, and gifted at friendship across differences — they "
     "succeed away from home and among strangers. Loyalty is their strength; "
     "choosing wisely whom to give it to is their art."),
    ("തൃക്കേട്ട", "Thrikketta (Jyeshtha)",
     "protective, responsible, and often the eldest in spirit — others lean on "
     "them early in life. Authority sits well on them when it is worn lightly, "
     "with generosity instead of control."),
    ("മൂലം", "Moolam (Mula)",
     "root-seekers — drawn to the bottom of every question, discipline, and "
     "belief. They dismantle to understand, and their honesty about foundations "
     "makes them natural researchers and philosophers."),
    ("പൂരാടം", "Pooradam (Purva Ashadha)",
     "invincibly optimistic and persuasive — they declare their aims aloud and "
     "carry others along on conviction. Backing that confidence with quiet "
     "preparation makes their victories stick."),
    ("ഉത്രാടം", "Uthradam (Uttara Ashadha)",
     "built for lasting victory — integrity, patience, and goals that take years "
     "rather than days. What they finish endures; their only care is choosing "
     "aims worthy of that endurance."),
    ("തിരുവോണം", "Thiruvonam (Shravana)",
     "the star of listening — learners, teachers, and keepers of tradition, "
     "beloved in Kerala as the star of Onam. Knowledge flows to them when they "
     "listen first and speak after, and fame follows usefulness."),
    ("അവിട്ടം", "Avittam (Dhanishta)",
     "rhythmic, musical, and prosperity-minded — good with wealth, groups, and "
     "timing. Their inner music is steadied by belonging somewhere; investing in "
     "community repays them many times over."),
    ("ചതയം", "Chathayam (Shatabhisha)",
     "healers with a hundred remedies — independent, private, and drawn to what "
     "is hidden: medicine, research, the sea, the sky. Solitude restores them; "
     "sharing their findings connects them."),
    ("പൂരുരുട്ടാതി", "Pururuttathi (Purva Bhadrapada)",
     "intense idealists who burn for a cause larger than themselves. Their "
     "passion uplifts when tempered with compassion for those who move slower, "
     "and their words carry unusual power."),
    ("ഉത്രട്ടാതി", "Uthrattathi (Uttara Bhadrapada)",
     "deep, stable, and quietly compassionate — the still water that runs "
     "farthest down. They steady others in crisis, and they flourish when they "
     "also let their own depths be seen."),
    ("രേവതി", "Revathi",
     "gentle, nurturing, and protective of travellers and beginnings-from-"
     "endings — the last nakshatra, holding completion without sorrow. They "
     "prosper by guiding others safely across transitions."),
]


# Relationship / compatibility (പൊരുത്തം) dimension for each nakshatra, keyed by
# the same Malayalam name. This is the "how they love" facet a porutham reading
# leans on — how the star gives and receives affection, its relational strength,
# and its growth edge in a partnership. Folded into the retrievable nakshatra
# chunk AND surfaced by the chat service alongside the ten computed poruthams
# (see chat.service._porutham_note) so a compatibility reading is grounded in
# both people's stars, not the model's guesswork. Phrased as tendencies, never
# fate — GUARDRAILS §1.
_NAKSHATRA_RELATIONSHIP: dict[str, str] = {
    "അശ്വതി":
        "ardent and quick to commit, showing love through action and rescue; "
        "they grow by slowing to let a partner's pace and feelings catch up.",
    "ഭരണി":
        "loving intensely and loyally, carrying a partner's burdens as their "
        "own; harmony comes when they voice their own needs instead of quietly "
        "bearing everything.",
    "കാർത്തിക":
        "honest and protective partners who say what they mean; wrapping that "
        "truth in tenderness keeps their warmth from landing as criticism.",
    "രോഹിണി":
        "deeply affectionate and devoted, making a bond feel beautiful and "
        "secure; loosening possessiveness lets that love breathe.",
    "മകയിരം":
        "playful and curious, they court through conversation and flourish with "
        "a mate who keeps life interesting and reassures the restless mind.",
    "തിരുവാതിര":
        "they feel love as a storm — passionate and renewing; naming feelings "
        "early, before they build, keeps the weather clear between them.",
    "പുണർതം":
        "forgiving and hopeful, always ready to begin again after a quarrel; "
        "they thrive with a partner who values that resilience.",
    "പൂയം":
        "nurturing and steadfast, among the most caring of partners; their "
        "lesson is to let themselves be cared for in return.",
    "ആയില്യം":
        "perceptive and intensely devoted, reading a partner's moods before "
        "words; trust deepens when that insight reassures rather than tests.",
    "മകം":
        "proud and loyal, honouring family and tradition in a union; sharing "
        "authority rather than holding it makes love easy.",
    "പൂരം":
        "warm, romantic, and generous with affection — they make partnership a "
        "celebration; a little steadiness anchors their pleasures.",
    "ഉത്രം":
        "reliable and giving, the partner who keeps every promise; they grow by "
        "asking for support as readily as they offer it.",
    "അത്തം":
        "attentive and clever, showing love through helpful small acts; saying "
        "the feeling in words too completes the care.",
    "ചിത്തിര":
        "drawn to beauty and harmony, they build an elegant shared life; "
        "patience with a partner's rough edges is their finishing art.",
    "ചോതി":
        "independent lovers who need room to breathe; given freedom and trust "
        "they are among the most fair and devoted of mates.",
    "വിശാഖം":
        "devoted and determined once committed; enjoying the relationship as it "
        "is, not only its goals, is where they grow.",
    "അനിഴം":
        "warm and cooperative, gifted at closeness across differences — natural "
        "at partnership, with loyalty freely given as their strength.",
    "തൃക്കേട്ട":
        "protective and responsible, carrying the bond's weight; worn lightly, "
        "that care feels like devotion, not control.",
    "മൂലം":
        "intense and searching in love, wanting depth and honesty; a partner "
        "who welcomes their questions earns lasting devotion.",
    "പൂരാടം":
        "passionate and persuasive, loving wholeheartedly and inspiring a "
        "partner; steadiness behind the warmth keeps promises kept.",
    "ഉത്രാടം":
        "patient and enduring, building love to last; choosing a mate worthy of "
        "that constancy is their one care.",
    "തിരുവോണം":
        "attentive listeners who love by understanding; the bond thrives when "
        "they speak their own heart as well as hearing their partner's.",
    "അവിട്ടം":
        "responsible, providing partners who value home and belonging; softening "
        "leadership into shared decisions keeps harmony.",
    "ചതയം":
        "private and loyal, loving quietly and needing solitude too; a partner "
        "who respects that space is trusted completely.",
    "പൂരുരുട്ടാതി":
        "idealistic and passionate, devoted to a shared purpose; compassion for "
        "a slower-moving partner tempers their fire.",
    "ഉത്രട്ടാതി":
        "calm, faithful, and deeply steadying; letting their own depths be seen "
        "invites the intimacy they give so freely.",
    "രേവതി":
        "tender, selfless, and protective in love; guarding against being taken "
        "for granted keeps their giving joyful.",
}


def relationship_trait(nakshatram_ml: str) -> str | None:
    """The compatibility-facing trait for a nakshatra by its Malayalam name.

    Returns ``None`` for an unknown star so callers degrade gracefully. Used by
    the chat service to ground a porutham reading in each partner's star.
    """
    return _NAKSHATRA_RELATIONSHIP.get(nakshatram_ml)


def _nakshatra_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = []
    for ml, alias, profile in _NAKSHATRA_PROFILES:
        relationship = _NAKSHATRA_RELATIONSHIP.get(ml)
        love = (
            f" In love and marriage (പൊരുത്തം) they are {relationship}"
            if relationship else ""
        )
        chunks.append({
            "id": f"nakshatra-{ml}",
            "topic": "nakshatra",
            "text": (
                f"Those born under {ml} nakshatra ({alias} birth star) are {profile}"
                f"{love} "
                "A birth star describes temperament and leanings — guidance for "
                "self-understanding, never a fixed fate."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# 9 Vimshottari mahadasha profiles. Ids use the engine's dasha lord keys.
# ---------------------------------------------------------------------------

_DASHA_PROFILES: dict[str, tuple[str, str, str]] = {
    "surya": ("Sun", "സൂര്യൻ",
        "a six-year season of visibility, self-definition, and dealings with "
        "authority. Health, confidence, and the father often come into focus. It "
        "rewards standing up straight — taking responsibility for one's own light "
        "rather than waiting for permission."),
    "chandra": ("Moon", "ചന്ദ്രൻ",
        "a ten-year season where the emotional life, home, mother, and the public "
        "come forward. Feelings run closer to the surface, which is a strength "
        "when honoured with rest and honest conversation rather than suppression."),
    "chevvai": ("Mars", "ചൊവ്വ",
        "a seven-year season of energy, ambition, property matters, and decisive "
        "action. Things move fast; the period rewards courage with direction and "
        "asks for patience in conflicts — effort spent on real goals burns clean."),
    "rahu": ("Rahu", "രാഹു",
        "an eighteen-year season of worldly expansion, foreign connections, "
        "technology, and unconventional paths. It can lift a person far beyond "
        "their starting point; the one discipline it demands is honesty about "
        "means, so gains stand on firm ground."),
    "guru": ("Jupiter", "വ്യാഴം",
        "a sixteen-year season traditionally counted among the most supportive: "
        "learning, family growth, children, faith, and recognition tend to "
        "expand. Its grace multiplies when shared — teaching, mentoring, and "
        "generosity are its best investments."),
    "shani": ("Saturn", "ശനി",
        "a nineteen-year season of structure, maturity, and slow compounding. It "
        "prunes what is unnecessary and rewards patient, honest work with results "
        "that outlast the period itself. It is a strict teacher, never a "
        "punisher — what it builds does not fall."),
    "budhan": ("Mercury", "ബുധൻ",
        "a seventeen-year season favouring study, trade, writing, and networks. "
        "The mind quickens and opportunities arrive through communication. It "
        "rewards learning new skills and keeping agreements precise and fair."),
    "ketu": ("Ketu", "കേതു",
        "a seven-year season of simplification and inner turning. Attachments "
        "loosen and priorities clarify; what remains is what matters. Treated as "
        "a spiritual spring-cleaning rather than a loss, it leaves a person "
        "lighter and clearer."),
    "shukran": ("Venus", "ശുക്രൻ",
        "a twenty-year season — the longest — favouring relationships, marriage, "
        "comfort, art, and wealth. Life softens and beautifies; its lesson is "
        "gratitude and moderation, so enjoyment deepens into contentment."),
}


def _dasha_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = []
    for key, (en, ml, profile) in _DASHA_PROFILES.items():
        chunks.append({
            "id": f"mahadasha-{key}",
            "topic": "dasha",
            "text": (
                f"The {en} mahadasha ({ml} ദശ / {key} dasha) in the Vimshottari "
                f"system is {profile} A dasha sets the season's weather, not your "
                "decisions — the stars incline, they never compel."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# 12 lagna (ascendant) profiles, keyed by the engine's Malayalam rasi names.
# ---------------------------------------------------------------------------

_LAGNA_PROFILES: list[tuple[str, str, str]] = [
    ("മേടം", "Medam (Aries) lagna",
     "direct, energetic, and quick to act — pioneers who meet life head-on. "
     "Their courage inspires; pairing it with patience turns bursts of effort "
     "into lasting wins."),
    ("ഇടവം", "Idavam (Taurus) lagna",
     "steady, sensual, and loyal — builders who value comfort, beauty, and "
     "reliability. Change feels costly to them, yet their calm persistence is "
     "exactly what carries others through change."),
    ("മിഥുനം", "Mithunam (Gemini) lagna",
     "curious, articulate, and versatile — minds that light up in conversation "
     "and learning. Depth is their growth edge: choosing a few threads and "
     "weaving them fully."),
    ("കർക്കടകം", "Karkidakam (Cancer) lagna",
     "nurturing, intuitive, and protective — the emotional anchors of their "
     "families. Their sensitivity is strength when they also guard their own "
     "shores, not only everyone else's."),
    ("ചിങ്ങം", "Chingam (Leo) lagna",
     "warm, dignified, and born to be seen — natural leaders with generous "
     "hearts. Their light is steadiest when applause is a byproduct of service, "
     "not the goal."),
    ("കന്നി", "Kanni (Virgo) lagna",
     "precise, helpful, and improvement-minded — they quietly fix what others "
     "overlook. Self-kindness matters: the standards they hold for the world "
     "should soften at their own doorstep."),
    ("തുലാം", "Thulam (Libra) lagna",
     "fair, charming, and partnership-oriented — peacemakers with an eye for "
     "balance and beauty. Decisions come easier when they trust that their own "
     "preference also counts."),
    ("വൃശ്ചികം", "Vrischikam (Scorpio) lagna",
     "intense, private, and transformative — they live few things halfway. "
     "Their depth heals and rebuilds; trusting slowly is fine, as long as they "
     "do eventually trust."),
    ("ധനു", "Dhanu (Sagittarius) lagna",
     "optimistic, principled, and freedom-loving — seekers of meaning, travel, "
     "and truth. Their arrows fly farthest when aimed at one worthy target at "
     "a time."),
    ("മകരം", "Makaram (Capricorn) lagna",
     "disciplined, pragmatic, and quietly ambitious — mountain-climbers who "
     "measure life in decades. Rest and warmth are not detours from their "
     "summit; they are supplies for it."),
    ("കുംഭം", "Kumbham (Aquarius) lagna",
     "original, humanitarian, and future-facing — they think in systems and "
     "care about the many. Their ideas land best when delivered with personal "
     "warmth, one person at a time."),
    ("മീനം", "Meenam (Pisces) lagna",
     "compassionate, imaginative, and porous to others' feelings — artists and "
     "healers by temperament. Boundaries are their life skill: the softer the "
     "heart, the firmer the fence it deserves."),
]


def _lagna_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = []
    for ml, alias, profile in _LAGNA_PROFILES:
        chunks.append({
            "id": f"lagna-{ml}",
            "topic": "lagna",
            "text": (
                f"A person with {ml} lagna ({alias}, the rising sign / ascendant) "
                f"tends to be {profile} The lagna colours the outer temperament — "
                "one lens among many in the chart, never the whole person."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# Dosha framing + remedies + Kerala FAQ. These pair with the FACTS that
# astrology_engine.doshas detects — detection is Python, framing is here.
# ---------------------------------------------------------------------------

_DOSHA_AND_FAQ_CHUNKS: list[SeedChunk] = [
    {
        "id": "dosha-chovva",
        "topic": "dosha",
        "text": (
            "Chovva dosha (ചൊവ്വാ ദോഷം, also called Mangal or Kuja dosha) arises "
            "when Mars (ചൊവ്വ) occupies the 1st, 2nd, 4th, 7th, 8th or 12th house, "
            "counted from the lagna or from the Moon. Tradition reads it as extra "
            "heat in the marriage area — a call for patience and matched "
            "temperaments, not a bar to marriage. Many charts have it, classical "
            "texts list many cancellations (for example both partners having it), "
            "and countless such marriages thrive. It is information for matching, "
            "never a verdict and never a reason for fear."
        ),
        "reviewed": False,
    },
    {
        "id": "dosha-kala-sarpa",
        "topic": "dosha",
        "text": (
            "Kala Sarpa dosha (കാലസർപ്പ ദോഷം) is noted when all seven classical "
            "planets lie on one side of the Rahu–Ketu axis. Tradition associates "
            "it with a life of strong ups and downs and unusually focused karma — "
            "and equally with extraordinary, single-minded achievement; many "
            "celebrated people carry it. It describes intensity of path, not "
            "misfortune. Steady effort and devotion are its classical answers; "
            "fear is not required."
        ),
        "reviewed": False,
    },
    {
        "id": "dosha-sade-sati",
        "topic": "dosha",
        "text": (
            "Sade Sati (ഏഴര ശനി, ezhara shani) is the roughly seven-and-a-half "
            "year period while Saturn (ശനി) transits the 12th, 1st and 2nd houses "
            "from the natal Moon — three phases: rising, peak, and setting. "
            "Tradition treats it as Saturn's classroom: responsibilities pile up, "
            "shortcuts stop working, and honest effort compounds. People routinely "
            "build careers, marry, and prosper during Sade Sati. It asks for "
            "patience and simple living — it is a season of maturing, not a "
            "sentence of misfortune."
        ),
        "reviewed": False,
    },
    {
        "id": "remedies-framing",
        "topic": "remedies",
        "text": (
            "Traditional remedies (പരിഹാരം) — temple worship, chanting, charity, "
            "fasting, or wearing specific colours — are best understood as acts of "
            "devotion and discipline that steady the mind and align daily habits "
            "with an intention. A remedy is chosen freely, never out of fear, and "
            "no genuine tradition ties results to payment. The most classical "
            "remedy of all is conduct: patience, honesty, and consistent effort."
        ),
        "reviewed": False,
    },
    {
        "id": "muhurtham-basics",
        "topic": "muhurtham",
        "text": (
            "A muhurtham (മുഹൂർത്തം) is an auspicious window chosen for beginning "
            "something important — a wedding, a housewarming (griha pravesham), a "
            "first day of work — using the panchangam: the day's nakshatra, tithi, "
            "and weekday, avoiding rahu kalam. Choosing a good muhurtham is an act "
            "of care and auspicious intention; missing one is never a curse, and a "
            "sincere beginning carries its own blessing."
        ),
        "reviewed": False,
    },
    {
        "id": "panchangam-basics",
        "topic": "panchangam",
        "text": (
            "The panchangam (പഞ്ചാംഗം) is the traditional almanac of five limbs: "
            "tithi (lunar day), nakshatra (the Moon's star), yoga, karana, and the "
            "weekday. In Kerala it guides daily timing — nalla neram (good hours) "
            "for starting tasks and rahu kalam to avoid for new beginnings. It is "
            "a rhythm to plan with, like a tide table — practical guidance, not a "
            "source of anxiety."
        ),
        "reviewed": False,
    },
]


# ---------------------------------------------------------------------------
# Prashnam (Kerala horary) — pairs with the FACTS astrology_engine.prashnam
# computes. Chunk texts contain the exact cue tokens the rules module emits
# ("prashnam arudha <rasi>", "prashnam lagna house <n> <class>", "prashnam
# thamboola remainder <n>") so BM25 pulls the matching meanings.
# HONESTY: every framing here presents this as traditional-STYLE guidance —
# never as equivalent to an in-person ashtamangala prashnam with a Daivajna.
# ---------------------------------------------------------------------------

# rasi (Malayalam) → (alias, the flavour an arudha in that rasi lends a question)
_ARUDHA_PROFILES: list[tuple[str, str, str]] = [
    ("മേടം", "Medam/Aries", "urgency and initiative — the matter wants a decision "
     "and quick, brave action; half-measures frustrate it"),
    ("ഇടവം", "Idavam/Taurus", "steadiness and material weight — the matter builds "
     "slowly and rewards patience, saving, and consistency"),
    ("മിഥുനം", "Mithunam/Gemini", "conversation and options — the matter turns on "
     "communication, paperwork, or a choice between two paths"),
    ("കർക്കടകം", "Karkadakam/Cancer", "home and feeling — the matter is close to "
     "the heart, family, or the place one lives; care matters more than speed"),
    ("ചിങ്ങം", "Chingam/Leo", "visibility and dignity — the matter involves "
     "recognition, authority, or standing tall in public"),
    ("കന്നി", "Kanni/Virgo", "detail and service — the matter improves through "
     "careful work, health attention, and fixing small things well"),
    ("തുലാം", "Thulaam/Libra", "balance and partnership — the matter is shared "
     "with another person and asks for fairness and negotiation"),
    ("വൃശ്ചികം", "Vrischikam/Scorpio", "depth and transformation — the matter has "
     "hidden layers; honesty about what is beneath the surface helps"),
    ("ധനു", "Dhanu/Sagittarius", "hope and guidance — the matter grows through "
     "teachers, faith, travel, or taking the long view"),
    ("മകരം", "Makaram/Capricorn", "duty and structure — the matter is a slow "
     "climb that yields to discipline and realistic planning"),
    ("കുംഭം", "Kumbham/Aquarius", "community and rethinking — the matter benefits "
     "from networks, friends, and an unconventional angle"),
    ("മീനം", "Meenam/Pisces", "trust and letting go — the matter asks for "
     "compassion, quiet reflection, and faith in the process"),
]

# house (from the udaya lagna) → (class, what the placement colours the answer with)
_PRASHNA_HOUSE_MEANINGS: list[tuple[int, str, str]] = [
    (1, "kendra", "the querent themselves — self-effort is decisive, and the "
     "matter is in their own hands more than they think"),
    (2, "sama", "resources, savings, and family speech — the matter touches "
     "money or what is said at home; steady stewardship helps"),
    (3, "upachaya", "courage and initiative — the matter improves with effort "
     "over time; boldness is rewarded"),
    (4, "kendra", "home, mother, vehicles, and inner peace — the matter settles "
     "close to home and asks for emotional groundedness"),
    (5, "trikona", "children, learning, and creative merit — a favourable, "
     "blessed placement; sincere intention flows easily here"),
    (6, "dusthana", "obstacles, competition, or health strain — expect "
     "resistance first; the classical counsel is patience, service, and not "
     "forcing the timing"),
    (7, "kendra", "partnership and the other party — the matter depends on "
     "another person; fairness and clear agreement are the way through"),
    (8, "dusthana", "delay and hidden factors — the matter moves slower than "
     "hoped and something is not yet visible; prudence over panic"),
    (9, "trikona", "fortune, elders, and grace — the most favourable placement; "
     "guidance from a teacher or elder blesses the matter"),
    (10, "kendra", "work and public action — the matter resolves through doing, "
     "in the open; reputation and duty carry it"),
    (11, "upachaya", "gains and friends — the matter tends toward fulfilment, "
     "especially with the help of a network; growth compounds"),
    (12, "dusthana", "expense, distance, or rest — the matter may cost, conclude, "
     "or move far away; release what is complete and keep what serves"),
]

# thamboola remainder (leaf count mod 8) → gentle curated theme. Simplified
# count-reading DRAFT for astrologer review — not a claim of classical fidelity.
_THAMBOOLA_REMAINDERS: list[tuple[int, str]] = [
    (0, "completion and fullness — a cycle is closing; harvest and consolidate "
     "before beginning the next thing"),
    (1, "a fresh start — the matter is at its seed stage and welcomes a clear, "
     "simple first step"),
    (2, "partnership and balance — the answer involves another person; seek "
     "agreement before speed"),
    (3, "growth and expression — favourable for learning, children, and creative "
     "ventures; speak the intention aloud"),
    (4, "foundations — attend to home and stability first; the rest follows"),
    (5, "change and movement — the matter shifts; adaptability serves better "
     "than holding rigid plans"),
    (6, "service and care — health, duty, and small consistent kindnesses are "
     "the door through which this matter opens"),
    (7, "reflection and patience — the ripest answer is not yet; quiet "
     "preparation now saves effort later"),
]


def _prashnam_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = [
        {
            "id": "prashnam-basics",
            "topic": "prashnam",
            "text": (
                "Prashnam (പ്രശ്നം) is the Kerala horary tradition: instead of the "
                "birth chart, the astrologer reads the chart of the very moment a "
                "question is asked — the udaya lagna (ഉദയ ലഗ്നം, the rasi rising "
                "right now), the Moon, and the tithi. In thamboola prashnam "
                "(താംബൂല പ്രശ്നം) the querent offers betel leaves and the count is "
                "read; in swarna prashnam (സ്വർണ പ്രശ്നം) the querent touches one "
                "of twelve unmarked rasi squares, and that square becomes the "
                "arudha (ആരൂഢം). The moment itself is treated as meaningful — a "
                "mirror held up to the question, guidance to reflect with, never a "
                "fixed decree."
            ),
            "reviewed": False,
        },
        {
            "id": "prashnam-honesty",
            "topic": "prashnam",
            "text": (
                "An honest note on prashnam done through an app: a full "
                "ashtamangala prashnam (അഷ്ടമംഗല പ്രശ്നം) is an elaborate in-person "
                "ritual conducted by an experienced Daivajna with cowries, lamps, "
                "and hours of judgement — no digital reading is equivalent to it, "
                "and none should claim to be. What an app can offer sincerely is a "
                "traditional-style reading of the question moment: the udaya "
                "lagna, the Moon, and the count or arudha, read by the classical "
                "frames. Take it as reflective guidance; for a full prashnam, "
                "tradition points to a qualified astrologer in person."
            ),
            "reviewed": False,
        },
        {
            "id": "prashnam-sankhya-basics",
            "topic": "prashnam",
            "text": (
                "Sankhya prashnam (സംഖ്യാ പ്രശ്നം) — prashnam sankhya number "
                "reading: the querent names a number from the sacred 1 to 108 "
                "(the count of a japa mala and of the navamsa padas). The zodiac "
                "divides 108 evenly, so the number falls on one rasi (nine "
                "numbers each) and one nakshatra (four numbers each) — the "
                "KP-horary way of letting the questioner's own pick anchor the "
                "chart. The number's rasi is read against the udaya lagna like "
                "an arudha, and its nakshatra lends the question its "
                "temperament. The number carries the moment's signature — "
                "guidance to reflect with, never a verdict."
            ),
            "reviewed": False,
        },
        {
            "id": "prashnam-thamboola-odd",
            "topic": "prashnam",
            "text": (
                "In thamboola prashnam, an odd count of leaves (prashnam thamboola "
                "odd leaves) is traditionally read as gati (ഗതി) — movement. The "
                "question is alive and in motion: circumstances are changing, and "
                "action taken now participates in that change. Odd counts favour "
                "questions about beginnings, journeys, and decisions — the "
                "counsel is to move, mindfully."
            ),
            "reviewed": False,
        },
        {
            "id": "prashnam-thamboola-even",
            "topic": "prashnam",
            "text": (
                "In thamboola prashnam, an even count of leaves (prashnam "
                "thamboola even leaves) is traditionally read as sthiti (സ്ഥിതി) — "
                "steadiness. The matter rests on what already exists: "
                "consolidation, patience, and tending what is planted serve "
                "better than fresh upheaval. Even counts favour questions of "
                "stability, family, and preservation — the counsel is to hold "
                "steady and strengthen the base."
            ),
            "reviewed": False,
        },
    ]
    for ml, alias, flavour in _ARUDHA_PROFILES:
        chunks.append({
            "id": f"prashnam-arudha-{ml}",
            "topic": "prashnam",
            "text": (
                f"In swarna prashnam, when the arudha (ആരൂഢം) falls in {ml} "
                f"({alias}) — prashnam arudha {ml} — the question carries "
                f"{flavour}. The arudha shows the temperament of the matter as "
                "the querent holds it; read together with the udaya lagna, it "
                "orients the answer without deciding it — the choice stays with "
                "the person."
            ),
            "reviewed": False,
        })
    for house, klass, meaning in _PRASHNA_HOUSE_MEANINGS:
        chunks.append({
            "id": f"prashnam-lagna-house-{house}",
            "topic": "prashnam",
            "text": (
                f"Prashnam lagna house {house} ({klass}): when the arudha or the "
                f"Moon stands in the {house}th house from the udaya lagna, the "
                f"reading turns on {meaning}. House placements in a prashna chart "
                "describe the terrain of the question — they advise the route, "
                "they do not close the road."
            ),
            "reviewed": False,
        })
    for rem, theme in _THAMBOOLA_REMAINDERS:
        chunks.append({
            "id": f"prashnam-thamboola-rem-{rem}",
            "topic": "prashnam",
            "text": (
                f"Thamboola count reading — prashnam thamboola remainder {rem} "
                f"(the leaf count in groups of eight): the offering points to "
                f"{theme}. This simplified count-reading is guidance to reflect "
                "with, offered in the spirit of the tradition."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# Vazhipadu (temple offerings) — WHAT each offering is, WHOM it addresses, and
# WHAT concern tradition pairs it with. Texts carry Malayalam script + Latin
# transliteration so BM25 matches both scripts (users often type Manglish).
# Framing per GUARDRAILS §1: offerings are acts of devotion chosen freely —
# never demanded, never feared into, never tied to a price.
# ---------------------------------------------------------------------------

# (slug, Malayalam, transliteration, whom/where, traditionally-for, description)
_VAZHIPADU: list[tuple[str, str, str, str, str, str]] = [
    ("pushpanjali", "പുഷ്പാഞ്ജലി", "pushpanjali", "any deity",
     "general blessing and devotion",
     "flowers offered at the deity's feet while mantras are chanted — the "
     "simplest and most universal Kerala offering"),
    ("archana", "അർച്ചന", "archana", "any deity",
     "personal blessing in one's own name",
     "an offering performed in the devotee's name and janma nakshatram, "
     "invoking the deity's attention personally"),
    ("ganapathi-homam", "ഗണപതി ഹോമം", "ganapathi homam", "Ganapathi",
     "removing obstacles before any new beginning",
     "a fire ritual to Ganapathi performed at dawn — the classical start "
     "before ventures, weddings, housewarmings, and exams"),
    ("bhagavathi-seva", "ഭഗവതി സേവ", "bhagavathi seva", "Devi (Bhagavathi)",
     "family welfare, protection, and peace at home",
     "an evening lamp-lit seva to the Goddess, traditionally sought for "
     "household harmony and protection"),
    ("mrityunjaya-homam", "മൃത്യുഞ്ജയ ഹോമം", "mrityunjaya homam", "Shiva",
     "health, recovery from illness, and longevity",
     "a fire ritual with the Mrityunjaya mantra, performed during illness or "
     "health anxieties — devotion alongside treatment, never instead of it"),
    ("navagraha-pooja", "നവഗ്രഹ പൂജ", "navagraha pooja", "the nine grahas",
     "graha preethi — softening difficult planetary periods",
     "worship of all nine grahas together, common during dasha transitions "
     "and dosha periods"),
    ("thulabharam", "തുലാഭാരം", "thulabharam", "Krishna (famous at Guruvayur)",
     "gratitude and fulfilment of a vow",
     "the devotee is weighed against an offering (banana, sugar, jaggery) "
     "given to the temple — a beloved Kerala act of thanksgiving"),
    ("niramala", "നിറമാല", "niramala", "any deity",
     "prosperity and full-hearted devotion",
     "adorning the deity fully with garlands and lamps for a day"),
    ("chuttuvilakku", "ചുറ്റുവിളക്ക്", "chuttuvilakku", "Devi and Shiva temples",
     "dispelling gloom; light in a dark season",
     "lighting every lamp around the temple — the shrine glowing whole"),
    ("neyyabhishekam", "നെയ്യഭിഷേകം", "neyyabhishekam", "Ayyappan and Shiva",
     "health and steadfast devotion",
     "abhishekam of ghee over the deity, central to Sabarimala tradition"),
    ("paal-payasam", "പാൽപായസം", "paal payasam nivedyam", "Krishna and Vishnu",
     "well-being and sweetness in life",
     "a milk-sweet nivedyam offered and received back as prasadam"),
    ("appam-ada", "അപ്പം/അട നിവേദ്യം", "appam ada nivedyam",
     "Krishna (famous at Ambalappuzha)",
     "children's welfare and Krishna preethi",
     "the classic appam and ada offering associated with little Krishna"),
    ("vedivazhipadu", "വെടിവഴിപാട്", "vedivazhipadu",
     "Devi and Muthappan temples of north Kerala",
     "announcing gratitude or a fulfilled prayer",
     "a firecracker offering — joy made audible"),
    ("kalabhabhishekam", "കളഭാഭിഷേകം", "kalabhabhishekam", "Shiva and Ayyappan",
     "peace of mind and cooling of distress",
     "abhishekam of fragrant sandal paste over the deity"),
    ("dhara", "ധാര", "dhara", "Shiva",
     "calming anger, anxiety, and heat in the mind or body",
     "an unbroken stream of water or milk poured over the Shivalinga"),
    ("udayasthamana-pooja", "ഉദയാസ്തമന പൂജ", "udayasthamana pooja", "any major temple",
     "a life-sized vow or deep gratitude",
     "continuous poojas from sunrise to sunset — the grandest single-day "
     "offering a family can make"),
    ("noorum-palum", "നൂറും പാലും", "noorum palum", "the Nagas (serpent deities)",
     "sarpa dosha, skin ailments (traditional), and progeny",
     "rice flour, turmeric and milk offered to serpent deities, often with "
     "ayilya pooja on the Ayilyam star day (Mannarasala is famous for it)"),
    ("saraswati-pooja", "സരസ്വതി പൂജ", "saraswati pooja / vidyarambham", "Saraswati",
     "learning, exams, arts — and a child's first letters",
     "worship of the goddess of vidya; vidyarambham begins a child's learning"),
    ("naranga-vilakku", "നാരങ്ങാവിളക്ക്", "naranga vilakku", "Devi",
     "chovva dosha and mangalya prayers",
     "lamps lit in halved lemon peels, a Devi-temple offering often chosen "
     "while praying about marriage"),
    ("annadanam", "അന്നദാനം", "annadanam", "any temple",
     "universal merit; gratitude expressed as service",
     "feeding devotees — held by tradition to be the highest offering"),
    ("ellu-thiri", "എള്ള് തിരി", "ellu thiri / ellu payasam", "Sastha and Shani",
     "ezhara shani (Sade Sati) and Saturn preethi",
     "sesame-oil wicks or sesame payasam offered on Saturdays"),
    ("swayamvara-pushpanjali", "സ്വയംവര പുഷ്പാഞ്ജലി", "swayamvara pushpanjali",
     "Devi and Krishna",
     "timely marriage (mangalya bhagya)",
     "pushpanjali with the Swayamvara mantra, sought when marriage is delayed"),
    ("santhanagopala-pushpanjali", "സന്താനഗോപാലം", "santhanagopala pushpanjali",
     "Krishna",
     "blessing of children (santana bhagya)",
     "pushpanjali with the Santhanagopala mantra for couples hoping for a child"),
    ("bhagyasuktha-pushpanjali", "ഭാഗ്യസൂക്തം", "bhagyasuktha pushpanjali",
     "Devi and Vishnu",
     "fortune and relief from a run of setbacks",
     "pushpanjali with the Bhagya Sooktham verses"),
    ("aikyamathya-pushpanjali", "ഐക്യമത്യ സൂക്തം", "aikyamathya sooktham pushpanjali",
     "Shiva (famous at Vaikom)",
     "harmony between couples and within families",
     "pushpanjali with the unity sooktham, sought when a household is quarrelling"),
    ("kalamezhuthu", "കളമെഴുത്തും പാട്ടും", "kalamezhuthu pattu",
     "Bhadrakali and Ayyappan",
     "protection and fulfilment of family vows",
     "ritual floor-drawing of the deity in coloured powders with song — a "
     "north-and-central Kerala tradition"),
    ("guruthi", "ഗുരുതി", "guruthi pooja", "Bhadrakali",
     "protection from persistent adversity (as tradition frames it)",
     "an evening ritual of red guruthi liquid at Kali temples; Tara presents "
     "it as devotion, never as fear of any entity"),
    ("muttarukkal", "മുട്ടറുക്കൽ", "muttarukkal", "Ganapathi and Devi",
     "breaking through a stuck obstacle (mutt = block)",
     "smashing coconuts before the deity as prayers name the obstacle"),
    ("vidya-ganapathi", "വിദ്യാഗണപതി ഹോമം", "vidya ganapathi homam", "Ganapathi",
     "focus and success in studies and exams",
     "the study-focused form of ganapathi homam, done before exam seasons"),
    ("ayur-sooktham", "ആയുർസൂക്തം", "ayur sooktha pushpanjali", "Shiva and Dhanwantari",
     "health and vitality",
     "pushpanjali with the Ayur Sooktham, often alongside medical treatment"),
]


def _vazhipadu_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = []
    for slug, ml, translit, whom, for_what, desc in _VAZHIPADU:
        chunks.append({
            "id": f"vazhipadu-{slug}",
            "topic": "vazhipadu",
            "text": (
                f"{ml} ({translit}) is a Kerala temple offering to {whom}, "
                f"traditionally chosen for {for_what}: {desc}. Like every "
                "vazhipadu, it is an act of devotion a person may freely "
                "choose — tradition never demands it, ties it to fear, or "
                "prices the blessing."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# Deity profiles ("god details") — who each deity is in Kerala devotion and
# what people traditionally approach them for. Pairs with remedy_map.DEITIES
# (the deterministic suggestion tables); these chunks give the LLM narrative
# depth. Bilingual + transliteration for BM25.
# ---------------------------------------------------------------------------

# (slug, Malayalam, transliteration/aliases, profile)
_DEITY_PROFILES: list[tuple[str, str, str, str]] = [
    ("ganapathi", "ഗണപതി", "Ganapathi / Vigneshwaran",
     "the remover of obstacles, worshipped FIRST before any new beginning — "
     "ventures, journeys, weddings, education. Coconut-breaking and modakam "
     "offerings are his hallmarks"),
    ("shiva", "ശിവൻ", "Shiva / Mahadevan",
     "the great ascetic and dissolver, approached for health, longevity, "
     "inner steadiness, and release from what must end. Mondays and "
     "Pradosham evenings are his days"),
    ("vishnu", "വിഷ്ണു", "Vishnu / Padmanabhan",
     "the preserver, approached for overall wellbeing, prosperity, and Guru "
     "preethi; Anantha Padmanabha of Thiruvananthapuram reclines on the "
     "serpent Anantha"),
    ("krishna", "കൃഷ്ണൻ / ഗുരുവായൂരപ്പൻ", "Krishna / Guruvayoorappan",
     "beloved as the child of Guruvayur — approached for children, family "
     "joy, and devotion that feels like friendship. Thulabharam and paal "
     "payasam are his famous offerings"),
    ("devi", "ദേവി", "Devi / Bhagavathi / Durga",
     "the Mother in her many Kerala forms — Attukal, Chottanikkara, "
     "Kodungallur — approached for protection, family welfare, mangalya "
     "prayers, and strength in adversity"),
    ("bhadrakali", "ഭദ്രകാളി", "Bhadrakali / Kali",
     "the fierce protective form of the Mother, guardian against injustice "
     "and persistent adversity; guruthi and kalamezhuthu belong to her "
     "worship — fierce in form, motherly toward devotees"),
    ("saraswati", "സരസ്വതി", "Saraswati",
     "the goddess of vidya — learning, music, and the arts. Vidyarambham at "
     "her shrines (Panachikkadu is Kerala's own Mookambika) begins every "
     "child's education"),
    ("lakshmi", "ലക്ഷ്മി", "Lakshmi / Mahalakshmi",
     "the goddess of prosperity and grace, invoked for wealth that "
     "circulates kindly — with the reminder that effort is her companion"),
    ("subrahmanya", "സുബ്രഹ്മണ്യൻ", "Subrahmanyan / Murukan / Karthikeya",
     "the commander of the devas, strongly tied to Chevvai (Mars) — "
     "approached for courage, victory over rivalry, and chovva dosha "
     "shanti; Haripad and Payyannur are famous seats"),
    ("ayyappan", "അയ്യപ്പൻ / ശബരിമല ശാസ്താവ്", "Ayyappan / Sastha / Dharmasastha",
     "the lord of Sabarimala, born of Hari and Hara — approached for "
     "discipline, protection on hard paths, and Shani preethi; the "
     "41-day vratham and irumudikettu mark his pilgrimage"),
    ("hanuman", "ഹനുമാൻ", "Hanuman / Anjaneya",
     "the embodiment of strength, service, and fearlessness — approached "
     "for courage, career obstacles, and protection; vadamala and betel "
     "garlands are his offerings, Tuesdays and Saturdays his days"),
    ("naga", "നാഗരാജാവ്", "Nagaraja and Nagayakshi (serpent deities)",
     "the serpent guardians of Kerala's sacred groves (kavu) — approached "
     "for sarpa dosha, Rahu-Ketu periods, skin ailments (traditional), and "
     "progeny; Mannarasala and Vetticode are their great seats"),
    ("surya", "സൂര്യൻ", "Surya / Aditya",
     "the Sun, source of vitality and clarity — approached for health, "
     "confidence, and Surya preethi; Adithyapuram is Kerala's famous Sun "
     "temple"),
    ("dhanwantari", "ധന്വന്തരി", "Dhanwantari",
     "the divine physician, Vishnu's healing form — approached during "
     "illness and recovery, always alongside real treatment; Nelluvai and "
     "Thottuva are his well-known Kerala temples"),
    ("muthappan", "മുത്തപ്പൻ", "Muthappan",
     "the folk deity of Parassinikkadavu, worshipped through the living "
     "theyyam tradition — approachable without ritual barriers, beloved of "
     "working people; offerings are simple: toddy, fish, and devotion"),
]


def _deity_chunks() -> list[SeedChunk]:
    chunks: list[SeedChunk] = []
    for slug, ml, aliases, profile in _DEITY_PROFILES:
        chunks.append({
            "id": f"deity-{slug}",
            "topic": "deity",
            "text": (
                f"{ml} ({aliases}) — in Kerala devotion, {profile}. Approaching "
                "any deity is a matter of love and steadiness of mind; the "
                "blessing is in the devotion itself, never in fear or payment."
            ),
            "reviewed": False,
        })
    return chunks


# ---------------------------------------------------------------------------
# Final corpus.
# ---------------------------------------------------------------------------

SEED_CHUNKS: list[SeedChunk] = (
    _ORIGINAL_CHUNKS
    + _planet_house_chunks()
    + _nakshatra_chunks()
    + _dasha_chunks()
    + _lagna_chunks()
    + _DOSHA_AND_FAQ_CHUNKS
    + _prashnam_chunks()
    + _vazhipadu_chunks()
    + _deity_chunks()
)
