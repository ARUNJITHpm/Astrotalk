"""Pydantic schemas (DTOs) for the content module's public boundary."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ContentPostOut(BaseModel):
    """One piece of the daily pack, as shown in the /admin Content tab."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    day: date
    platform: str
    kind: str
    body: str
    media_key: str | None
    # Browser-reachable URL for the rendered card (filled from storage.url()).
    media_url: str | None = None
    status: str
    external_id: str | None
    created_at: datetime
    published_at: datetime | None


class ApprovePayload(BaseModel):
    """Optional inline edit applied at approval time (admin reviewed the text)."""

    body: str | None = None


class RunDailySummary(BaseModel):
    day: str
    created: list[str]
    skipped: list[str]


class ShareCardCreate(BaseModel):
    """A personal share card request (Part 2): the insight the user wants out."""

    title: str = ""
    body: str
    template: str = "story"  # story (WhatsApp Status / IG Stories) or feed


class ShareCardOut(BaseModel):
    """A rendered share card: where the image is and where the share lands."""

    slug: str
    kind: str
    title: str
    media_url: str
    share_url: str
    hits: int = 0


# ---- Content Studio (ENGAGEMENT_PLAN.md Part B) ----


class StudioGeneratePayload(BaseModel):
    """Owner's request to draft one creative piece."""

    kind: str  # one of content.models.STUDIO_KINDS
    topic: str = ""  # optional steer: a nakshatra, a festival, a myth
    day: date | None = None  # defaults to today (grounds the panchangam facts)


class StudioDraftOut(BaseModel):
    """A studio draft as shown in the /admin Content Studio."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    topic: str | None
    title: str
    body: str
    caption: str | None
    media_url: str | None = None
    status: str
    external_url: str | None
    created_at: datetime
    published_at: datetime | None


class MarkPublishedPayload(BaseModel):
    """Manual-posting proof: the public URL of the post the owner made by hand."""

    external_url: str
