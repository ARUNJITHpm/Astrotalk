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
    "🙏 നമസ്കാരം! ഞാൻ *താര* — നിങ്ങളുടെ AI ജ്യോതിഷ സഹായി.\n\n"
    "നിങ്ങളുടെ ജാതകം തയ്യാറാക്കാൻ ചില വിവരങ്ങൾ വേണം.\n"
    "ആദ്യം നിങ്ങളുടെ *പേര്* പറയൂ 👇"
)

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

# Accepts HH:MM (24h) or H:MM
_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")


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
    """Parse a birth time from user input. Returns None on failure."""
    text = text.strip()
    m = _TIME_PATTERN.match(text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
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
        wa = WASession(phone=phone, state="greeting", onboarding_data={})
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


async def process_onboarding_step(
    wa: WASession, text: str
) -> tuple[str, bool]:
    """Advance the onboarding FSM by one step.

    Args:
        wa: The WhatsApp session (mutated in place).
        text: The user's message text.

    Returns:
        (reply_text, is_complete): The reply to send, and whether onboarding
        just completed (caller should create the user).
    """
    state = wa.state
    data = wa.onboarding_data or {}
    text = text.strip()

    if state == "greeting":
        # First contact — show welcome, move to ask_name.
        wa.state = "ask_name"
        wa.onboarding_data = data
        return WELCOME_MSG, False

    if state == "ask_name":
        # Validate: non-empty name.
        name = text.strip()
        if not name or len(name) < 2:
            return "❌ പേര് ശരിയായി ടൈപ്പ് ചെയ്യൂ (കുറഞ്ഞത് 2 അക്ഷരം).", False
        data["name"] = name
        wa.state = "ask_dob"
        wa.onboarding_data = data
        return ASK_DOB_MSG.format(name=name), False

    if state == "ask_dob":
        dob = parse_dob(text)
        if dob is None:
            return INVALID_DOB_MSG, False
        # Basic sanity: not in the future, not before 1900.
        if dob.year < 1900 or dob > date.today():
            return INVALID_DOB_MSG, False
        data["dob"] = dob.isoformat()
        wa.state = "ask_time"
        wa.onboarding_data = data
        return ASK_TIME_MSG, False

    if state == "ask_time":
        lower = text.lower().strip()
        if lower in ("skip", "no", "ഇല്ല", "അറിയില്ല", "ariyilla"):
            data["birth_time"] = None
        else:
            bt = parse_time(text)
            if bt is None:
                return INVALID_TIME_MSG, False
            data["birth_time"] = bt.isoformat()
        wa.state = "ask_place"
        wa.onboarding_data = data
        return ASK_PLACE_MSG, False

    if state == "ask_place":
        place = text.strip()
        if not place or len(place) < 2:
            return "❌ സ്ഥലത്തിന്റെ പേര് ശരിയായി ടൈപ്പ് ചെയ്യൂ.", False
        data["birth_place"] = place
        wa.state = "ask_password"
        wa.onboarding_data = data
        return ASK_PASSWORD_MSG, False

    if state == "ask_password":
        password = text.strip()
        if len(password) < 4:
            return INVALID_PASSWORD_MSG, False
        data["password"] = password
        wa.state = "chatting"
        wa.onboarding_data = data
        return REGISTRATION_SUCCESS_MSG, True  # Signal: registration needed

    # Should not reach here — but be safe.
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
        "password": data.get("password", ""),
    }
    if data.get("birth_time"):
        result["birth_time"] = data["birth_time"]
    return result
