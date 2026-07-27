"""Operator writes against the app feed (console plan Part 8).

`feed.py`'s own docstring said "admin CRUD layer on later" — this is that
layer. The three curated cards were a Python literal, so correcting a festival
notice meant a code change and a redeploy, which is the opposite of what a
notices feed is for.

Two rules the module enforces rather than trusts:

  - **Attribution is required.** ``who_en`` says whose words these are. A notice
    carries the temple's name because it came from the temple; anything in
    Nithara's own voice says "Nithara". A card with no attribution reads as an
    anonymous authority making claims, which GUARDRAILS §1 exists to prevent.
  - **Nobody sets engagement counts.** ``likes``/``comments`` are not columns
    and not writable; the API serves 0 until real reactions exist (§4).

Publish/unpublish, never delete: an unpublished card is a draft the operator is
still working on, and pulling a wrong notice off the app should not destroy the
text that has to be corrected.
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.feed import CATEGORIES
from app.modules.content.models import FeedItem

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")

FEED_FIELDS = frozenset({
    "cat", "image", "glyph", "live", "title_en", "title_ml", "body_en",
    "body_ml", "who_en", "who_ml", "temple_id", "published", "sort_order",
})


class FeedAdminError(ValueError):
    """A rejected write."""


class NotFound(FeedAdminError):
    """No feed card with that id."""


def _validate(changes: dict[str, Any], *, creating: bool) -> None:
    unknown = set(changes) - FEED_FIELDS
    if unknown:
        raise FeedAdminError(f"cannot set: {', '.join(sorted(unknown))}")
    if "cat" in changes and changes["cat"] not in CATEGORIES:
        raise FeedAdminError(f"cat must be one of: {', '.join(CATEGORIES)}")
    if "title_en" in changes and not (changes["title_en"] or "").strip():
        raise FeedAdminError("title_en cannot be empty")
    # Attribution: required to create, and never blankable afterwards.
    if creating or "who_en" in changes:
        if not (changes.get("who_en") or "").strip():
            raise FeedAdminError(
                "who_en is required — a card must say whose words it carries"
            )


async def get(session: AsyncSession, item_id: str) -> FeedItem | None:
    """The raw row, published or not — the console edits drafts too."""
    return await session.get(FeedItem, item_id)


async def listing(
    session: AsyncSession, *, include_unpublished: bool = True
) -> list[FeedItem]:
    query = select(FeedItem).order_by(FeedItem.sort_order, FeedItem.id)
    if not include_unpublished:
        query = query.where(FeedItem.published.is_(True))
    return list((await session.execute(query)).scalars().all())


async def create(session: AsyncSession, *, item_id: str, **fields: Any) -> FeedItem:
    if not _ID_RE.match(item_id or ""):
        raise FeedAdminError("id must be lowercase letters/digits/hyphens")
    if await session.get(FeedItem, item_id) is not None:
        raise FeedAdminError(f"feed card {item_id!r} already exists")
    _validate(fields, creating=True)
    row = FeedItem(id=item_id, **fields)
    session.add(row)
    await session.flush()
    return row


async def update(
    session: AsyncSession, *, item_id: str, changes: dict[str, Any]
) -> FeedItem:
    row = await session.get(FeedItem, item_id)
    if row is None:
        raise NotFound(f"unknown feed card {item_id!r}")
    _validate(changes, creating=False)
    for key, value in changes.items():
        setattr(row, key, value)
    await session.flush()
    return row
