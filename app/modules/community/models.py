"""SQLAlchemy models for the community module (internal — do not import elsewhere).

The engagement layer on top of the content feed (ENGAGEMENT_PLAN.md Part A):
reactions, daily check-in streaks, and weekly polls. These give users a reason
to open Tara that isn't "I have a question".

Cross-module references (``user_id`` → identity.users, ``post_id`` →
content.content_posts) are stored as PLAIN ints with NO ForeignKey: those tables
belong to other modules and community must never join to them directly
(AGENTS.md). It keeps its own rows and reads other modules only via their public
services.

Migrations are managed with Alembic and require human approval (AGENTS.md); in
dev these tables are auto-created by init_db's create_all.
"""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base

# The reactions a user may leave on a feed post. Deliberately small and warm —
# no downvote (GUARDRAILS.md tone: comfort, never fear or negativity).
REACTIONS = ("🙏", "❤️", "✨")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PostReaction(Base):
    """One emoji reaction by one user on one feed post (content_posts.id)."""

    __tablename__ = "post_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", "emoji", name="uq_reaction_user_post_emoji"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    post_id: Mapped[int] = mapped_column(index=True)
    emoji: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class UserCheckin(Base):
    """One row per (user, day) the user opened the feed — powers the streak."""

    __tablename__ = "user_checkins"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_checkin_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    day: Mapped[date] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Poll(Base):
    """A lightweight weekly poll shown in the feed. Options are a JSON list of
    Malayalam strings; a vote stores the chosen option's index."""

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str]
    options: Mapped[list[str]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class PollVote(Base):
    """One vote per user per poll (changeable — see service.vote)."""

    __tablename__ = "poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_vote_poll_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    option_index: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
