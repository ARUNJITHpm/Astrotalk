"""User memory profile for the chat module (internal).

Distinct from chat history: history is the raw transcript; this is the distilled,
durable profile of the person — keyed by ``user_id``, shared across ALL sessions.
This is what lets Tara feel like she remembers someone.

Stored in the MongoDB ``user_memory`` collection, one document per user:
    { user_id, summary, facts: [{text, kind, created_at}], updated_at }

Everything degrades to a safe no-op when Mongo is disabled/unavailable
(get_db() -> None), so a down document store never breaks a chat reply.
"""

from datetime import UTC, datetime

from app.platform.logging_config import get_logger
from app.platform.mongo import get_db

logger = get_logger(__name__)

_COLLECTION = "user_memory"
_MAX_FACTS = 50  # bound growth; keep the most recent facts
_INJECT_FACTS = 8  # how many facts to surface into the prompt


async def get_profile(user_id: str) -> dict | None:
    """Return the user's memory document, or None if none/unavailable."""
    db = get_db()
    if db is None:
        return None
    try:
        return await db[_COLLECTION].find_one({"user_id": user_id}, {"_id": False})
    except Exception as exc:  # pragma: no cover - depends on Mongo availability
        logger.warning("chat.user_memory: read failed (%s); no profile.", exc)
        return None


async def upsert_facts(
    user_id: str, facts: list[dict], summary: str | None = None
) -> None:
    """Merge new distilled ``facts`` (and optionally a ``summary``) into the profile.

    Each fact is ``{"text": str, "kind": str}``; created_at is stamped here. Facts
    are capped at the most recent ``_MAX_FACTS``. No-op when Mongo is disabled or
    there is nothing to write.
    """
    db = get_db()
    if db is None:
        return
    now = datetime.now(UTC)

    # Dedup: skip facts whose text is already in the profile (or repeated within
    # this batch), so the same note/observation doesn't pile up turn after turn.
    existing = await get_profile(user_id)
    seen = {
        (f.get("text") or "").strip().lower()
        for f in ((existing or {}).get("facts") or [])
    }
    stamped = []
    for f in facts:
        text = (f.get("text") or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        stamped.append({"text": text, "kind": f.get("kind", "fact"), "created_at": now})
    if not stamped and summary is None:
        return

    set_fields: dict = {"updated_at": now}
    if summary is not None:
        set_fields["summary"] = summary
    update: dict = {"$set": set_fields}
    if stamped:
        update["$push"] = {"facts": {"$each": stamped, "$slice": -_MAX_FACTS}}

    try:
        await db[_COLLECTION].update_one({"user_id": user_id}, update, upsert=True)
    except Exception as exc:  # pragma: no cover - depends on Mongo availability
        logger.warning("chat.user_memory: write failed (%s); continuing.", exc)


def format_for_prompt(profile: dict | None) -> str | None:
    """Render a profile into a compact block for the system prompt, or None."""
    if not profile:
        return None
    lines: list[str] = []
    summary = profile.get("summary")
    if summary:
        lines.append(summary.strip())
    for fact in (profile.get("facts") or [])[-_INJECT_FACTS:]:
        text = (fact or {}).get("text")
        if text:
            lines.append(f"- {text}")
    rendered = "\n".join(lines).strip()
    return rendered or None
