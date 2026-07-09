"""Conversational onboarding state machine for WhatsApp users.

On the website, users fill a form (name, DOB, birth time, place, password) before
chatting. On WhatsApp there's no form UI, so we collect the same details step by
step in a Malayalam conversation. The state is tracked in ``wa_sessions`` (see
models.py) and partial data is accumulated in ``onboarding_data`` JSON until
registration completes.

Once onboarding finishes, the user is created via ``IdentityService.create_user()``
exactly like the web registration — same chart computation, same identity row, same
phone key. A user who already registered on the website is recognised by phone and
skips straight to chatting.

GUARDRAILS.md §4: birth data is sensitive — never logged, never in URLs. The
partial onboarding_data is cleared from wa_sessions after registration succeeds.
"""

import re
from datetime import date, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp.models import WASession
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# ---- Malayalam prompts for each onboarding step ----

WELCOME_MSG = (
    "🙏 നമസ്കാരം! ഞാൻ *താര* — നിങ്ങളുടെ AI ജ്യോതിഷ സഹായി 🌟\n\n"
    "ജോലി, വിവാഹം, ആരോഗ്യം, ഭാവി — എന്തും എന്നോട് ചോദിക്കാം. "
    "വെറുതെ ഒന്ന് സംസാരിക്കാനും ഞാൻ ഉണ്ട് 😊\n\n"
    "എന്താണ് അറിയാൻ ആഗ്രഹിക്കുന്നത്?"
)

# Shown the moment a personal, chart-based question arrives from someone we don't
# know yet — this is the ONLY place we start asking for birth details, and we do
# it warmly, explaining why.
COLLECT_INTRO_NAME = (
    "അതിന് നിങ്ങളുടെ വ്യക്തിഗത ജാതകം നോക്കണം — അതിനായി കുറച്ച് ജനന വിവരങ്ങൾ വേണം 🙏\n\n"
    "തുടങ്ങാം — എന്താണ് നിങ്ങളുടെ *പേര്*? 😊"
)

# Prefixed to the answer of the user's original question once their chart is ready.
CHART_READY_MSG = "✅ നന്ദി! നിങ്ങളുടെ ജാതകം തയ്യാറാക്കി 🌙"

ASK_DOB_MSG = (
    "നന്ദി, {name}! 🌟\n\n"
    "ഇനി നിങ്ങളുടെ *ജനന തീയതി* പറയൂ.\n"
    "ഉദാ: `15/03/1990` (DD/MM/YYYY)"
)

ASK_TIME_MSG = (
    "👍 *ജനന സമയം* അറിയാമെങ്കിൽ പറയൂ.\n"
    "ഉദാ: `14:30` (24-hour format)\n\n"
    "അറിയില്ലെങ്കിൽ *skip* എന്ന് ടൈപ്പ് ചെയ്യൂ."
)

ASK_PLACE_MSG = "🏡 *ജനിച്ച സ്ഥലം* ഏതാണ്?\nഉദാ: Thrissur, Kerala"

ASK_PASSWORD_MSG = (
    "🔐 വെബ്‌സൈറ്റിൽ ലോഗിൻ ചെയ്യാൻ ഒരു *password* സെറ്റ് ചെയ്യൂ.\n"
    "(കുറഞ്ഞത് 4 അക്ഷരങ്ങൾ)"
)

REGISTRATION_SUCCESS_MSG = (
    "✅ *രജിസ്‌ട്രേഷൻ പൂർത്തിയായി!*\n\n"
    "നിങ്ങളുടെ ജാതകം തയ്യാറാക്കിയിട്ടുണ്ട്. "
    "ഇനി എന്തും ചോദിക്കാം — ജോലി, വിവാഹം, ആരോഗ്യം... 🌙\n\n"
    "_വെബ്‌സൈറ്റിൽ ലോഗിൻ ചെയ്യാൻ ഈ നമ്പറും password-ഉം ഉപയോഗിക്കൂ._"
)

EXISTING_USER_MSG = (
    "🙏 തിരികെ വരവ് സ്വാഗതം, *{name}*!\n\n"
    "നിങ്ങളുടെ അക്കൗണ്ട് ഇതിനകം ഉണ്ട്. "
    "എന്തും ചോദിക്കാം — ഞാൻ തയ്യാറാണ് 🌟"
)

INVALID_DOB_MSG = (
    "❌ തീയതി മനസ്സിലായില്ല. DD/MM/YYYY ഫോർമാറ്റിൽ പറയൂ.\n"
    "ഉദാ: `25/12/1995`"
)

INVALID_TIME_MSG = (
    "❌ സമയം മനസ്സിലായില്ല. HH:MM ഫോർമാറ്റിൽ പറയൂ (24h).\n"
    "ഉദാ: `06:30` അല്ലെങ്കിൽ *skip* എന്ന് ടൈപ്പ് ചെയ്യൂ."
)

INVALID_PASSWORD_MSG = "❌ Password കുറഞ്ഞത് 4 അക്ഷരങ്ങൾ വേണം. വീണ്ടും ശ്രമിക്കൂ."

OPT_OUT_MSG = (
    "✅ നിങ്ങൾ unsubscribe ചെയ്‌തു. ഇനി സന്ദേശങ്ങൾ അയക്കില്ല.\n"
    "തിരികെ വരാൻ *START* എന്ന് അയക്കൂ."
)

OPT_IN_MSG = "✅ സ്വാഗതം! നിങ്ങൾ വീണ്ടും subscribe ചെയ്‌തു. എന്തും ചോദിക്കാം 🌟"

# ---- Date/time parsing helpers ----

# Accepts DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
_DOB_PATTERN = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$")

# Accepts H:MM / H.MM / H MM, optional am/pm; compact "712"/"0712" handled below.
_TIME_PATTERN = re.compile(r"^(\d{1,2})[:.\s](\d{2})\s*(a\.?m\.?|p\.?m\.?)?$", re.I)


def parse_dob(text: str) -> date | None:
    """Parse a date of birth from user input. Returns None on failure."""
    text = text.strip()
    m = _DOB_PATTERN.match(text)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_time(text: str) -> time | None:
    """Parse a birth time from user input, leniently.

    Accepts ``7:12``, ``7.12``, ``7 12``, ``0712``/``712``, and an optional
    ``am``/``pm`` suffix. Returns None on failure.
    """
    text = text.strip().lower()
    ampm = None
    m = _TIME_PATTERN.match(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = (m.group(3) or "").replace(".", "") or None
    else:
        # Compact digits: "712" -> 7:12, "0712" -> 07:12, "1230" -> 12:30.
        digits = text.replace(" ", "")
        if digits.isdigit() and len(digits) in (3, 4):
            digits = digits.zfill(4)
            hour, minute = int(digits[:2]), int(digits[2:])
        else:
            return None
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    try:
        return time(hour, minute)
    except ValueError:
        return None


# ---- Session management ----


async def get_or_create_session(
    session: AsyncSession, phone: str
) -> WASession:
    """Get the WhatsApp session for a phone, creating one if it doesn't exist."""
    wa = await session.get(WASession, phone)
    if wa is None:
        # New contact starts in "casual": free conversation, no details asked
        # until a personal chart question makes them necessary.
        wa = WASession(phone=phone, state="casual", onboarding_data={})
        session.add(wa)
        await session.flush()
    return wa


async def get_session(session: AsyncSession, phone: str) -> WASession | None:
    """Get the WhatsApp session for a phone, or None if it doesn't exist."""
    return await session.get(WASession, phone)


async def reset_session(session: AsyncSession, phone: str) -> None:
    """Delete the WhatsApp session for a phone (e.g. after account deletion)."""
    wa = await session.get(WASession, phone)
    if wa is not None:
        await session.delete(wa)
        await session.flush()


# ---- State machine ----


# The states in which we're actively collecting birth details, in order.
COLLECT_STATES = ("collect_name", "collect_dob", "collect_time", "collect_place")

# Casual greetings / small talk — get a warm welcome, never a form.
_GREETING_KEYWORDS = {
    "hi", "hii", "hiii", "hey", "hai", "hallo", "hello", "helo", "hlo", "yo",
    "start", "namaskaram", "namaste", "vanakkam", "good morning", "good evening",
    "ഹായ്", "ഹലോ", "നമസ്കാരം", "നമസ്തേ", "സുപ്രഭാതം", "എന്തുണ്ട്", "സുഖമാണോ",
}

# Personal, chart-dependent intent — questions that only make sense with THIS
# person's horoscope. General knowledge ("what is rahu?") is deliberately absent,
# so it's answered without demanding birth details.
_PERSONAL_CHART_KEYWORDS = (
    # English / Manglish
    "my rashi", "my rasi", "my nakshatra", "my star", "my sign", "my chart",
    "my horoscope", "my kundli", "my jathakam", "my future", "my career",
    "my marriage", "my job", "my love life", "when will i", "will i get",
    "should i marry", "my dosha", "my dasha", "my life", "for me",
    "horoscope", "jathakam", "jadhakam", "kundli", "porutham", "compatibility",
    "dosham", "dosha", "dasha", "rashi", "raasi", "nakshatram", "zodiac", "natal",
    "kalyanam", "vivaham", "ente ", "eppo", "bhavi",
    # Malayalam
    "എന്റെ", "ജാതക", "രാശി", "നക്ഷത്ര", "ദോഷ", "ദശ", "പൊരുത്ത",
    "വിവാഹം", "കല്യാണം", "ഭാവി", "എപ്പോൾ", "നടക്കുമോ",
)


# Let a user bail out of detail collection instead of being stuck on one prompt.
_CANCEL_KEYWORDS = {
    "cancel", "later", "not now", "leave", "exit", "quit", "back", "nvm",
    "venda", "vendaa", "vendram", "mathi", "pinne", "pinnu",
    "വേണ്ട", "വേണ്ടാ", "പിന്നെ", "മതി",
}

CANCELLED_MSG = (
    "ശരി, സാരമില്ല 🙂 പിന്നീട് എപ്പോൾ വേണമെങ്കിലും ചോദിക്കാം. "
    "വേറെ എന്തെങ്കിലും അറിയണോ?"
)


def is_greeting(text: str) -> bool:
    """True for a bare greeting / opener (so we welcome instead of interrogating)."""
    return text.lower().strip().rstrip("!.?") in _GREETING_KEYWORDS


def is_cancel(text: str) -> bool:
    """True when the user wants to abandon the current details collection."""
    return text.lower().strip().rstrip("!.?") in _CANCEL_KEYWORDS


def needs_personal_chart(text: str) -> bool:
    """True when answering needs THIS user's birth chart (→ time to ask details)."""
    lower = text.lower()
    return any(kw in lower for kw in _PERSONAL_CHART_KEYWORDS)


async def process_collection_step(
    wa: WASession, text: str
) -> tuple[str, bool]:
    """Advance the birth-details collection by one step.

    Only entered once a personal chart question has been asked. Returns
    ``(reply_text, is_complete)``; on completion the caller registers the user
    and answers their original (pending) question.
    """
    state = wa.state
    data = wa.onboarding_data or {}
    text = text.strip()

    if state == "collect_name":
        name = text.strip()
        if not name or len(name) < 2:
            return "❌ പേര് ശരിയായി ടൈപ്പ് ചെയ്യൂ (കുറഞ്ഞത് 2 അക്ഷരം).", False
        data["name"] = name
        wa.state = "collect_dob"
        wa.onboarding_data = data
        return ASK_DOB_MSG.format(name=name), False

    if state == "collect_dob":
        dob = parse_dob(text)
        if dob is None or dob.year < 1900 or dob > date.today():
            return INVALID_DOB_MSG, False
        data["dob"] = dob.isoformat()
        wa.state = "collect_time"
        wa.onboarding_data = data
        return ASK_TIME_MSG, False

    if state == "collect_time":
        lower = text.lower().strip()
        if lower in ("skip", "no", "ഇല്ല", "അറിയില്ല", "ariyilla"):
            data["birth_time"] = None
        else:
            bt = parse_time(text)
            if bt is None:
                return INVALID_TIME_MSG, False
            data["birth_time"] = bt.isoformat()
        wa.state = "collect_place"
        wa.onboarding_data = data
        return ASK_PLACE_MSG, False

    if state == "collect_place":
        place = text.strip()
        if not place or len(place) < 2:
            return "❌ സ്ഥലത്തിന്റെ പേര് ശരിയായി ടൈപ്പ് ചെയ്യൂ.", False
        data["birth_place"] = place
        wa.state = "chatting"
        wa.onboarding_data = data
        return "", True  # complete → caller registers + answers pending question

    # Should not reach here — be safe.
    return WELCOME_MSG, False


def get_onboarding_fields(wa: WASession) -> dict:
    """Extract the onboarding fields from a completed session.

    Returns a dict ready to feed into ``IdentityService.create_user()``
    (via ``UserCreate``).
    """
    data = wa.onboarding_data or {}
    result = {
        "phone": wa.phone,
        "name": data.get("name", ""),
        "dob": data.get("dob", ""),
        "birth_place": data.get("birth_place", ""),
    }
    if data.get("birth_time"):
        result["birth_time"] = data["birth_time"]
    return result
