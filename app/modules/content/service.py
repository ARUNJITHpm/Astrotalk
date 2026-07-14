"""Public service for the content module.

Two responsibilities (this is the ONLY surface other modules may depend on):
  - the original §5 daily WhatsApp message (generate_daily_message), and
  - the daily content pack (GROWTH_PLAN.md Part 1): run_daily drafts one
    piece per platform, admins review/approve in /admin, publish sends via
    content/publishers.py.

Uses OpenAI gpt-4o-mini with the exact §5 system prompt; when the LLM is mocked
(MOCK_LLM env / mock_openai / no API key) it returns a calm, compliant fallback
template so the daily pipeline works with zero API key.
"""

import os
from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content import pipeline, publishers, studio, templates
from app.modules.content.models import ContentPost, StudioDraft
from app.modules.content.schemas import ContentPostOut, StudioDraftOut
from app.platform import metrics
from app.platform.config import get_settings
from app.platform.logging_config import get_logger
from app.platform.storage import get_storage

logger = get_logger(__name__)


class ContentPostNotFound(LookupError):
    pass


class InvalidTransition(ValueError):
    """The post is not in a status that allows the requested action."""


def _should_mock() -> bool:
    settings = get_settings()
    env = os.getenv("MOCK_LLM")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    return settings.mock_openai or not settings.openai_api_key


class ContentService:
    async def generate_daily_message(self, panchangam: dict) -> str:
        """Draft ONE short Malayalam WhatsApp Channel message from the panchangam."""
        if _should_mock():
            logger.info("content: mock daily message (no live OpenAI call).")
            return templates.fallback_message(panchangam)

        from openai import AsyncOpenAI

        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.chat_model,
            max_tokens=300,
            messages=[
                {"role": "system", "content": templates.system_prompt()},
                {"role": "user", "content": templates.build_input(panchangam)},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    # ---- Daily content pack (GROWTH_PLAN.md Part 1) ----

    async def run_daily(self, session: AsyncSession, day: date_type | None = None) -> dict:
        """Draft the day's pack (idempotent). Called by the cron endpoint."""
        return await pipeline.run_daily(session, day)

    async def list_posts(
        self, session: AsyncSession, day: date_type | None = None
    ) -> list[ContentPostOut]:
        query = select(ContentPost).order_by(ContentPost.day.desc(), ContentPost.platform)
        if day is not None:
            query = query.where(ContentPost.day == day)
        posts = (await session.execute(query.limit(200))).scalars().all()
        storage = get_storage()
        out = []
        for post in posts:
            dto = ContentPostOut.model_validate(post)
            if post.media_key:
                dto.media_url = storage.url(post.media_key)
            out.append(dto)
        return out

    async def _get(self, session: AsyncSession, post_id: int) -> ContentPost:
        post = await session.get(ContentPost, post_id)
        if post is None:
            raise ContentPostNotFound(f"content post {post_id} not found")
        return post

    async def approve(
        self, session: AsyncSession, post_id: int, body: str | None = None
    ) -> ContentPostOut:
        """Mark a draft approved, optionally applying the admin's inline edit."""
        post = await self._get(session, post_id)
        if post.status not in ("draft", "approved"):
            raise InvalidTransition(f"cannot approve a {post.status} post")
        if body is not None and body.strip():
            post.body = body.strip()
        post.status = "approved"
        await session.commit()
        metrics.increment("content.posts_approved")
        return ContentPostOut.model_validate(post)

    async def publish(self, session: AsyncSession, post_id: int) -> ContentPostOut:
        """Send an APPROVED post to its platform; record the outcome.

        Human approval is a hard prerequisite — publish never touches drafts
        (the review step is the safety net for public copy).
        """
        post = await self._get(session, post_id)
        if post.status != "approved":
            raise InvalidTransition(f"only approved posts publish (status={post.status})")
        try:
            post.external_id = await publishers.publish(post.platform, post.body)
            post.status = "published"
            post.published_at = datetime.now(UTC)
            metrics.increment("content.posts_published")
        except publishers.PublishError as exc:
            logger.error("content: publish failed for post %s: %s", post_id, exc)
            post.status = "failed"
            metrics.increment("content.posts_failed")
        await session.commit()
        return ContentPostOut.model_validate(post)

    async def mark_post_published(
        self, session: AsyncSession, post_id: int, external_url: str
    ) -> ContentPostOut:
        """Manual-posting path: mark an approved daily post published by hand.

        For platforms whose API isn't wired yet (FB/IG/YouTube), the owner posts
        by hand and pastes the link — no publisher call, but metrics and the feed
        archive stay truthful.
        """
        post = await self._get(session, post_id)
        if post.status not in ("approved", "draft"):
            raise InvalidTransition(f"cannot mark a {post.status} post published")
        post.external_id = external_url.strip()
        post.status = "published"
        post.published_at = datetime.now(UTC)
        await session.commit()
        metrics.increment("content.posts_published")
        return ContentPostOut.model_validate(post)

    # ---- Content Studio (ENGAGEMENT_PLAN.md Part B) ----

    def _studio_out(self, draft: StudioDraft) -> StudioDraftOut:
        dto = StudioDraftOut.model_validate(draft)
        if draft.media_key:
            dto.media_url = get_storage().url(draft.media_key)
        return dto

    async def generate_studio(
        self, session: AsyncSession, kind: str, topic: str = "", day=None
    ) -> StudioDraftOut:
        draft = await studio.generate(session, kind, topic, day)
        return self._studio_out(draft)

    async def list_studio(self, session: AsyncSession) -> list[StudioDraftOut]:
        return [self._studio_out(d) for d in await studio.list_drafts(session)]

    async def _get_studio(self, session: AsyncSession, draft_id: int) -> StudioDraft:
        draft = await session.get(StudioDraft, draft_id)
        if draft is None:
            raise ContentPostNotFound(f"studio draft {draft_id} not found")
        return draft

    async def approve_studio(
        self, session: AsyncSession, draft_id: int, body: str | None = None
    ) -> StudioDraftOut:
        """Approve a studio draft, optionally applying the owner's inline edit."""
        draft = await self._get_studio(session, draft_id)
        if body is not None and body.strip():
            draft.body = body.strip()
        draft.status = "approved"
        await session.commit()
        return self._studio_out(draft)

    async def mark_studio_published(
        self, session: AsyncSession, draft_id: int, external_url: str
    ) -> StudioDraftOut:
        """Owner posted this by hand — record the link and flip to published."""
        draft = await self._get_studio(session, draft_id)
        draft.external_url = external_url.strip()
        draft.status = "published"
        draft.published_at = datetime.now(UTC)
        await session.commit()
        metrics.increment("content.studio_published")
        return self._studio_out(draft)

    async def delete_studio(self, session: AsyncSession, draft_id: int) -> None:
        draft = await self._get_studio(session, draft_id)
        await session.delete(draft)
        await session.commit()


# Module-level convenience surface.
async def generate_daily_message(panchangam: dict) -> str:
    return await ContentService().generate_daily_message(panchangam)
