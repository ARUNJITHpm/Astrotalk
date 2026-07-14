"""Public service for the community module (ENGAGEMENT_PLAN.md Part A).

The engagement layer: a user feed assembled from the content module's published
posts plus today's live panchangam, with reactions, a daily check-in streak, and
weekly polls.

This is the ONLY surface other modules may depend on (AGENTS.md). Community reads
other modules only through their public services (ContentService,
AstrologyEngineService) and never queries their tables directly.
"""

from datetime import date as date_type
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.community.models import (
    REACTIONS,
    Poll,
    PollVote,
    PostReaction,
    UserCheckin,
)
from app.modules.community.schemas import (
    FeedItem,
    FeedOut,
    PollOptionResult,
    PollOut,
    ReactionOut,
    StreakOut,
)
from app.platform import metrics
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


class InvalidReaction(ValueError):
    """The emoji is not one of the allowed REACTIONS."""


class PollNotFound(LookupError):
    pass


class InvalidOption(ValueError):
    """The chosen option index is out of range for the poll."""


class CommunityService:
    # ---- Feed ----

    async def get_feed(self, session: AsyncSession, user_id: int | None = None) -> FeedOut:
        """Assemble the feed: today's panchangam + recent published posts.

        A logged-in visit also records a check-in (feed visit = daily streak).
        """
        items: list[FeedItem] = []

        # 1) Today's live panchangam — always present, even on a fresh DB.
        try:
            from app.modules.astrology_engine.service import AstrologyEngineService

            panchangam = await AstrologyEngineService().get_panchangam(date_type.today())
            nakshatram = panchangam.get("nakshatram", "")
            nalla = panchangam.get("nalla_neram", "")
            tithi = panchangam.get("tithi", "")
            body = f"ഇന്നത്തെ നക്ഷത്രം {nakshatram}."
            if nalla:
                body += f" നല്ല നേരം {nalla}."
            if tithi:
                body += f" തിഥി {tithi}."
            items.append(
                FeedItem(
                    kind="panchangam_today",
                    title=f"ഇന്ന് · {date_type.today().isoformat()}",
                    body=body,
                    day=date_type.today(),
                )
            )
        except Exception:  # a panchangam hiccup must never blank the whole feed
            logger.warning("community.feed: panchangam unavailable", exc_info=True)

        # 2) Recent PUBLISHED content posts (content module's public service).
        try:
            from app.modules.content.service import ContentService

            posts = await ContentService().list_posts(session)
            published = [p for p in posts if p.status == "published"][:40]
            post_ids = [p.id for p in published]
            counts = await self._reaction_counts(session, post_ids)
            mine = await self._my_reactions(session, post_ids, user_id) if user_id else {}
            for p in published:
                items.append(
                    FeedItem(
                        kind="post",
                        post_id=p.id,
                        title=p.day.isoformat(),
                        body=p.body,
                        media_url=p.media_url,
                        platform=p.platform,
                        day=p.day,
                        external_url=p.external_id,
                        reactions=counts.get(p.id, {}),
                        my_reactions=mine.get(p.id, []),
                    )
                )
        except Exception:  # content unavailable → still show the panchangam item
            logger.warning("community.feed: content posts unavailable", exc_info=True)

        streak = 0
        if user_id is not None:
            await self._record_checkin(session, user_id)
            await session.commit()
            streak = await self._compute_streak(session, user_id)

        return FeedOut(items=items, streak=streak, available_reactions=list(REACTIONS))

    # ---- Reactions ----

    async def react(
        self, session: AsyncSession, user_id: int, post_id: int, emoji: str
    ) -> ReactionOut:
        """Toggle one emoji reaction: add if absent, remove if already present."""
        if emoji not in REACTIONS:
            raise InvalidReaction(f"reaction must be one of {REACTIONS}")
        existing = (
            await session.execute(
                select(PostReaction).where(
                    PostReaction.user_id == user_id,
                    PostReaction.post_id == post_id,
                    PostReaction.emoji == emoji,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await session.delete(existing)
        else:
            session.add(PostReaction(user_id=user_id, post_id=post_id, emoji=emoji))
            metrics.increment("community.reactions")
        await session.commit()

        counts = (await self._reaction_counts(session, [post_id])).get(post_id, {})
        mine = (await self._my_reactions(session, [post_id], user_id)).get(post_id, [])
        return ReactionOut(post_id=post_id, reactions=counts, my_reactions=mine)

    async def _reaction_counts(
        self, session: AsyncSession, post_ids: list[int]
    ) -> dict[int, dict[str, int]]:
        if not post_ids:
            return {}
        rows = (
            await session.execute(
                select(PostReaction.post_id, PostReaction.emoji).where(
                    PostReaction.post_id.in_(post_ids)
                )
            )
        ).all()
        out: dict[int, dict[str, int]] = {}
        for post_id, emoji in rows:
            out.setdefault(post_id, {})
            out[post_id][emoji] = out[post_id].get(emoji, 0) + 1
        return out

    async def _my_reactions(
        self, session: AsyncSession, post_ids: list[int], user_id: int | None
    ) -> dict[int, list[str]]:
        if not post_ids or user_id is None:
            return {}
        rows = (
            await session.execute(
                select(PostReaction.post_id, PostReaction.emoji).where(
                    PostReaction.post_id.in_(post_ids),
                    PostReaction.user_id == user_id,
                )
            )
        ).all()
        out: dict[int, list[str]] = {}
        for post_id, emoji in rows:
            out.setdefault(post_id, []).append(emoji)
        return out

    # ---- Streak ----

    async def _record_checkin(self, session: AsyncSession, user_id: int) -> None:
        today = date_type.today()
        exists = (
            await session.execute(
                select(UserCheckin.id).where(
                    UserCheckin.user_id == user_id, UserCheckin.day == today
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(UserCheckin(user_id=user_id, day=today))

    async def _checkin_days(self, session: AsyncSession, user_id: int) -> set[date_type]:
        rows = (
            await session.execute(select(UserCheckin.day).where(UserCheckin.user_id == user_id))
        ).scalars()
        return set(rows)

    async def _compute_streak(self, session: AsyncSession, user_id: int) -> int:
        """Consecutive days ending today (or yesterday if not yet seen today)."""
        days = await self._checkin_days(session, user_id)
        if not days:
            return 0
        today = date_type.today()
        cursor = today if today in days else today - timedelta(days=1)
        if cursor not in days:
            return 0
        streak = 0
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    async def get_streak(self, session: AsyncSession, user_id: int) -> StreakOut:
        streak = await self._compute_streak(session, user_id)
        checked_today = date_type.today() in await self._checkin_days(session, user_id)
        return StreakOut(streak=streak, checked_in_today=checked_today)

    # ---- Polls ----

    async def create_poll(
        self, session: AsyncSession, question: str, options: list[str]
    ) -> PollOut:
        poll = Poll(question=question.strip(), options=[o.strip() for o in options if o.strip()])
        session.add(poll)
        await session.commit()
        await session.refresh(poll)
        return await self._poll_out(session, poll)

    async def list_polls(
        self, session: AsyncSession, user_id: int | None = None, active_only: bool = True
    ) -> list[PollOut]:
        query = select(Poll).order_by(Poll.created_at.desc())
        if active_only:
            query = query.where(Poll.active.is_(True))
        polls = (await session.execute(query.limit(20))).scalars().all()
        return [await self._poll_out(session, p, user_id) for p in polls]

    async def vote(
        self, session: AsyncSession, poll_id: int, user_id: int, option_index: int
    ) -> PollOut:
        poll = await session.get(Poll, poll_id)
        if poll is None:
            raise PollNotFound(f"poll {poll_id} not found")
        if option_index < 0 or option_index >= len(poll.options):
            raise InvalidOption(f"option {option_index} out of range")
        existing = (
            await session.execute(
                select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == user_id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.option_index = option_index  # a vote may be changed
        else:
            session.add(PollVote(poll_id=poll_id, user_id=user_id, option_index=option_index))
            metrics.increment("community.poll_votes")
        await session.commit()
        return await self._poll_out(session, poll, user_id)

    async def _poll_out(
        self, session: AsyncSession, poll: Poll, user_id: int | None = None
    ) -> PollOut:
        rows = (
            await session.execute(
                select(PollVote.option_index, PollVote.user_id).where(PollVote.poll_id == poll.id)
            )
        ).all()
        tally = [0] * len(poll.options)
        my_vote: int | None = None
        for option_index, voter in rows:
            if 0 <= option_index < len(tally):
                tally[option_index] += 1
            if user_id is not None and voter == user_id:
                my_vote = option_index
        results = [
            PollOptionResult(text=text, votes=tally[i]) for i, text in enumerate(poll.options)
        ]
        return PollOut(
            id=poll.id,
            question=poll.question,
            options=list(poll.options),
            results=results,
            total_votes=sum(tally),
            active=poll.active,
            my_vote=my_vote,
            created_at=poll.created_at,
        )
