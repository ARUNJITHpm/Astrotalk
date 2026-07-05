"""Deity ↔ concern/graha/dosha mapping rules (internal to the temples module).

These are deterministic lookup tables following common Kerala remedial
convention (which deity is traditionally worshipped for which graha, dosha, or
life concern). They are FACTS in the compute/retrieve/generate split: Python
picks the deity and temple; the LLM only narrates.

⚠️ DRAFT — conventions vary between traditions and families; an astrologer
review pass should confirm these mappings before launch (same workflow as the
knowledge corpus).

Tone (GUARDRAILS.md §1): a temple visit is an optional act of devotion the
person may choose — never a demand, never tied to fear or payment. The
``mantra`` and ``days`` fields are devotional guidance, not conditions.
"""

from typing import TypedDict


class DeityInfo(TypedDict):
    name: str
    name_ml: str
    mantra: str
    days: str


# Deity keys used across seed_data and this map.
DEITIES: dict[str, DeityInfo] = {
    "ganapathi": {
        "name": "Ganapathi",
        "name_ml": "ഗണപതി",
        "mantra": "ഓം ഗം ഗണപതയേ നമഃ (Om Gam Ganapataye Namah)",
        "days": "daily; especially Vinayaka Chaturthi days",
    },
    "shiva": {
        "name": "Shiva",
        "name_ml": "ശിവൻ",
        "mantra": "ഓം നമഃ ശിവായ (Om Namah Shivaya)",
        "days": "Mondays; Pradosham days",
    },
    "vishnu": {
        "name": "Vishnu",
        "name_ml": "മഹാവിഷ്ണു",
        "mantra": "ഓം നമോ നാരായണായ (Om Namo Narayanaya)",
        "days": "Thursdays; Ekadasi days",
    },
    "krishna": {
        "name": "Sree Krishna",
        "name_ml": "ശ്രീകൃഷ്ണൻ",
        "mantra": "ഓം നമോ ഭഗവതേ വാസുദേവായ (Om Namo Bhagavate Vasudevaya)",
        "days": "Thursdays; Ashtami Rohini",
    },
    "devi": {
        "name": "Devi (Bhagavathy)",
        "name_ml": "ഭഗവതി",
        "mantra": "ഓം സർവ്വമംഗള മാംഗല്യേ ശിവേ സർവ്വാർത്ഥ സാധികേ... (Sarva Mangala Mangalye)",
        "days": "Tuesdays and Fridays",
    },
    "subrahmanya": {
        "name": "Subrahmanya (Murugan)",
        "name_ml": "സുബ്രഹ്മണ്യൻ",
        "mantra": "ഓം ശരവണഭവായ നമഃ (Om Saravanabhavaya Namah)",
        "days": "Tuesdays; Shashti days",
    },
    "sastha": {
        "name": "Dharma Sastha (Ayyappan)",
        "name_ml": "ധർമ്മശാസ്താവ് / അയ്യപ്പൻ",
        "mantra": "സ്വാമിയേ ശരണമയ്യപ്പ (Swamiye Saranam Ayyappa)",
        "days": "Saturdays; Mandala season",
    },
    "hanuman": {
        "name": "Hanuman",
        "name_ml": "ഹനുമാൻ",
        "mantra": "കാര്യസിദ്ധി ഹനുമദ് മന്ത്രം / ഹനുമാൻ ചാലിസ (Karya Siddhi Hanuman mantra / Hanuman Chalisa)",
        "days": "Tuesdays and Saturdays",
    },
    "naga": {
        "name": "Nagaraja (serpent deities)",
        "name_ml": "നാഗരാജാവ്",
        "mantra": "ഓം നാഗരാജായ നമഃ (Om Nagarajaya Namah)",
        "days": "Ayilyam nakshatra days",
    },
    "saraswati": {
        "name": "Saraswati",
        "name_ml": "സരസ്വതി",
        "mantra": "സരസ്വതി നമസ്തുഭ്യം വരദേ കാമരൂപിണി (Saraswati Namastubhyam)",
        "days": "Navaratri; Vidyarambham day",
    },
    "surya": {
        "name": "Surya (Sun)",
        "name_ml": "സൂര്യദേവൻ",
        "mantra": "ആദിത്യഹൃദയം / ഓം സൂര്യായ നമഃ (Aditya Hridayam / Om Suryaya Namah)",
        "days": "Sundays",
    },
    "dhanwantari": {
        "name": "Dhanwantari",
        "name_ml": "ധന്വന്തരി",
        "mantra": "ഓം ധന്വന്തരയേ നമഃ (Om Dhanvantaraye Namah)",
        "days": "any day; Dhanwantari Jayanti",
    },
}

# Life concern → deities in suggestion priority order, with the phrase used in
# the ``reason`` (English; the LLM narrates in Malayalam).
CONCERN_DEITIES: dict[str, tuple[list[str], str]] = {
    "career": (["hanuman", "ganapathi", "subrahmanya"],
               "career success and removal of obstacles at work"),
    "marriage": (["devi", "krishna", "subrahmanya"],
                 "timely and harmonious marriage (mangalya bhagya)"),
    "children": (["krishna", "naga", "devi"],
                 "blessing of children (santana bhagya)"),
    "education": (["saraswati", "ganapathi"],
                  "learning, exams, and vidya"),
    "health": (["dhanwantari", "devi", "shiva"],
               "healing and recovery of health"),
    "obstacles": (["ganapathi", "hanuman", "devi"],
                  "removal of persistent obstacles (vighna nivarana)"),
    "wealth": (["devi", "ganapathi", "vishnu"],
               "prosperity and relief from debts"),
    "ancestors": (["vishnu"],
                  "peace of ancestors (pitru karma / bali tharpanam)"),
    "peace": (["shiva", "devi", "sastha"],
              "peace of mind and steadiness"),
}

# Concern keyword map, English + Malayalam. First hit wins (ordered).
CONCERN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("career", ("job", "career", "work", "business", "promotion", "interview",
                "ജോലി", "തൊഴിൽ", "ബിസിനസ", "കരിയർ", "ഉദ്യോഗ", "പ്രമോഷൻ",
                "ഇന്റർവ്യൂ")),
    ("marriage", ("marriage", "wedding", "spouse", "mangalya",
                  "വിവാഹ", "കല്യാണ", "മംഗല്യ", "പൊരുത്തം", "ദാമ്പത്യ")),
    ("children", ("child", "children", "baby", "pregnan", "santana",
                  "കുട്ടി", "കുഞ്ഞ", "സന്താന", "ഗർഭ")),
    ("education", ("exam", "study", "studies", "education", "vidya",
                   "പഠന", "പഠി", "പരീക്ഷ", "വിദ്യ")),
    ("health", ("health", "illness", "disease", "recovery",
                "ആരോഗ്യ", "രോഗ", "അസുഖ", "ചികിത്സ")),
    ("wealth", ("money", "debt", "loan", "wealth", "financ",
                "പണം", "കടം", "ധനം", "സാമ്പത്തിക", "ലോൺ")),
    ("ancestors", ("ancestor", "pitru", "bali", "tharpanam",
                   "പിതൃ", "ബലി", "തർപ്പണ")),
    ("obstacles", ("obstacle", "court", "case", "enemy", "delay", "blocked",
                   "തടസ്സ", "കോടതി", "കേസ", "ശത്രു")),
    ("peace", ("peace", "anxiety", "stress", "sleep",
               "സമാധാന", "മനസ്സമാധാന", "ഉറക്ക", "ടെൻഷൻ")),
]

# Graha (dasha lord / afflicted planet) → deities, Kerala remedial convention.
GRAHA_DEITIES: dict[str, tuple[list[str], str]] = {
    "surya": (["surya", "shiva"], "the Sun (Surya preethi)"),
    "chandra": (["devi", "shiva"], "the Moon (Chandra preethi)"),
    "chevvai": (["subrahmanya", "devi"], "Mars (Kuja preethi)"),
    "budhan": (["vishnu", "krishna"], "Mercury (Budha preethi)"),
    "guru": (["vishnu"], "Jupiter (Guru preethi)"),
    "shukran": (["devi"], "Venus (Shukra preethi)"),
    "shani": (["sastha", "shiva", "hanuman"], "Saturn (Shani preethi)"),
    "rahu": (["naga", "devi"], "Rahu"),
    "ketu": (["naga", "ganapathi"], "Ketu"),
}

# Dosha (as detected by astrology_engine) → deities.
DOSHA_DEITIES: dict[str, tuple[list[str], str]] = {
    "chovva_dosha": (["subrahmanya", "devi"], "chovva (Mangal) dosha"),
    "kala_sarpa_dosha": (["naga"], "Kala Sarpa dosha"),
    "sade_sati": (["sastha", "hanuman", "shiva"], "Sade Sati (ezhara shani)"),
}

# Kerala districts (canonical English key + Malayalam + common variants) for
# detecting a place mentioned in the user's message.
DISTRICTS: dict[str, tuple[str, ...]] = {
    "Thiruvananthapuram": ("thiruvananthapuram", "trivandrum", "തിരുവനന്തപുരം"),
    "Kollam": ("kollam", "quilon", "കൊല്ലം"),
    "Pathanamthitta": ("pathanamthitta", "പത്തനംതിട്ട"),
    "Alappuzha": ("alappuzha", "alleppey", "ആലപ്പുഴ"),
    "Kottayam": ("kottayam", "കോട്ടയം"),
    "Idukki": ("idukki", "ഇടുക്കി"),
    "Ernakulam": ("ernakulam", "kochi", "cochin", "എറണാകുളം", "കൊച്ചി"),
    "Thrissur": ("thrissur", "trichur", "തൃശ്ശൂർ", "തൃശൂർ"),
    "Palakkad": ("palakkad", "palghat", "പാലക്കാട്"),
    "Malappuram": ("malappuram", "മലപ്പുറം"),
    "Kozhikode": ("kozhikode", "calicut", "കോഴിക്കോട്"),
    "Wayanad": ("wayanad", "വയനാട്"),
    "Kannur": ("kannur", "cannanore", "കണ്ണൂർ"),
    "Kasaragod": ("kasaragod", "കാസർഗോഡ്", "കാസറഗോഡ്"),
}
