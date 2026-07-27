"""SQLAlchemy models for the content module (internal — do not import elsewhere).

`content_posts` is the daily content pack (GROWTH_PLAN.md Part 1): one row per
platform per day, drafted by the pipeline, human-approved in /admin, then
published. `share_cards` (Part 2) are rendered branded images that leave Tara —
personal insights and the public daily nakshatra cards — each reachable through
the ``/s/{slug}`` landing page. Migrations are managed with Alembic (AGENTS.md);
this file only declares the ORM mapping.
"""

from datetime import UTC, date, datetime

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

# Publishing surfaces, in rollout order (GROWTH_PLAN.md Part 1).
PLATFORMS = ("wa_channel", "fb_post", "ig_reel", "yt_short")

# What the piece is about; "festival" arrives with Part 3's structured data.
KINDS = ("panchangam", "nakshatra", "festival", "tip")

STATUSES = ("draft", "approved", "published", "failed")

# Content Studio (ENGAGEMENT_PLAN.md Part B): on-demand creative pieces the
# owner generates, reviews, then posts BY HAND to YouTube/Instagram (auto-publish
# to those platforms stays mocked). Distinct from the scheduled daily pack.
STUDIO_KINDS = (
    "reel_script",  # 45-60s spoken Malayalam: Hook / Body / CTA + caption
    "weekly_astro_news",  # "ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങൾ" — the weekly show
    "festival_special",  # around an upcoming festival (owner supplies the name)
    "nakshatra_episode",  # one of 27 evergreen "know your nakshatram" scripts
    "myth_buster",  # gentle no-fear correction of a common astrology scare
)
STUDIO_STATUSES = ("draft", "approved", "published")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class FeedItem(Base):
    """One notices/articles card in the app feed.

    Was ``FEED_ITEMS``, a three-item literal in feed.py whose own docstring
    said "admin CRUD layer on later" — this is that. Column names match the
    seed dict key-for-key so the registry round-trips a row into the shape
    ``list_feed`` has always returned.

    ``likes``/``comments`` are deliberately NOT columns. They were hardcoded 0
    because inventing engagement counts is forbidden (GUARDRAILS §4); the API
    keeps serving 0 until real reactions exist, and a column here would be an
    invitation to type a number into it.
    """

    __tablename__ = "feed_items"

    id: Mapped[str] = mapped_column(primary_key=True)  # "pooram-ilanjithara"
    cat: Mapped[str] = mapped_column(index=True)  # one of feed.CATEGORIES
    image: Mapped[str] = mapped_column(default="i-fest")  # app art key
    glyph: Mapped[str] = mapped_column(default="i-parasol")
    live: Mapped[bool] = mapped_column(default=False)
    title_en: Mapped[str]
    title_ml: Mapped[str] = mapped_column(default="")
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_ml: Mapped[str] = mapped_column(Text, default="")
    # WHO is speaking. The honesty rule (GUARDRAILS §1): a notice is attributed
    # to the temple it came from, and anything in Nithara's own voice says so —
    # never a fabricated named authority.
    who_en: Mapped[str] = mapped_column(default="")
    who_ml: Mapped[str] = mapped_column(default="")
    temple_id: Mapped[str | None] = mapped_column(index=True, default=None)
    # Unpublished cards are drafts an operator is still writing; the app never
    # sees them. Distinct from deletion, which is not offered.
    published: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ContentPost(Base):
    __tablename__ = "content_posts"
    # One piece per platform per day — makes the daily cron idempotent.
    __table_args__ = (UniqueConstraint("day", "platform", name="uq_content_day_platform"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The content date (what day the piece is FOR, not when it was created).
    day: Mapped[date] = mapped_column(index=True)
    platform: Mapped[str]  # one of PLATFORMS
    kind: Mapped[str] = mapped_column(default="panchangam")  # one of KINDS
    body: Mapped[str] = mapped_column(Text)
    # Storage key of the rendered card (platform/storage.py); None until rendered.
    media_key: Mapped[str | None] = mapped_column(nullable=True, default=None)
    status: Mapped[str] = mapped_column(default="draft")  # one of STATUSES
    # Post/message ID returned by the platform API on publish.
    external_id: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)


class ShareCard(Base):
    """A rendered shareable card (GROWTH_PLAN.md Part 2).

    ``slug`` is an opaque token (personal cards must not be enumerable);
    daily nakshatra cards use a deterministic ``daily-{date}-{index}`` slug so
    repeat requests reuse the cached render. ``created_by_user_id`` is a plain
    int — the users table belongs to identity, so no cross-module FK — and is
    only used to attach the creator's referral code to the landing-page CTA.
    ``hits`` counts /s/{slug} landing views (share-click metric, survives
    restarts unlike the in-process counters).
    """

    __tablename__ = "share_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    kind: Mapped[str] = mapped_column(default="personal")  # personal|daily
    title: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    media_key: Mapped[str]
    # Referral code of the creator; the /s page's CTA carries it as ?ref=.
    ref_code: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_by_user_id: Mapped[int | None] = mapped_column(nullable=True, default=None)
    hits: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class StudioDraft(Base):
    """An on-demand creative piece from the Content Studio (ENGAGEMENT_PLAN Part B).

    Unlike ``ContentPost`` (one per platform per day, scheduled), studio drafts
    are ad-hoc — the owner generates a reel script / weekly-news script /
    myth-buster, reviews it, then posts it MANUALLY to YouTube/Instagram and
    pastes the resulting link back into ``external_url`` (status → published).
    No unique constraint: the owner may generate many pieces on any day.
    """

    __tablename__ = "studio_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]  # one of STUDIO_KINDS
    # Free-text steer the owner typed (a nakshatra, a festival, a myth) — audit.
    topic: Mapped[str | None] = mapped_column(nullable=True, default=None)
    title: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text)
    # Suggested caption + hashtags block for the manual post (reels/shorts).
    caption: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    media_key: Mapped[str | None] = mapped_column(nullable=True, default=None)
    status: Mapped[str] = mapped_column(default="draft")  # one of STUDIO_STATUSES
    # The public URL the owner pastes after posting by hand (proof + feed link).
    external_url: Mapped[str | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
