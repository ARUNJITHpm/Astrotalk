"""Pydantic schemas (DTOs) for the community module's public boundary."""

from datetime import date, datetime

from pydantic import BaseModel


class FeedItem(BaseModel):
    """One card in the user feed. ``post_id`` is present only for real content
    posts (which can be reacted to); live items like today's panchangam omit it."""

    kind: str  # panchangam_today | post | poll
    post_id: int | None = None
    title: str = ""
    body: str = ""
    media_url: str | None = None
    platform: str | None = None
    day: date | None = None
    external_url: str | None = None
    # emoji -> count, and (when logged in) which emojis the caller has left.
    reactions: dict[str, int] = {}
    my_reactions: list[str] = []


class FeedOut(BaseModel):
    """The assembled feed plus the caller's streak (0 when not logged in)."""

    items: list[FeedItem]
    streak: int = 0
    available_reactions: list[str]


class ReactionPayload(BaseModel):
    emoji: str


class ReactionOut(BaseModel):
    post_id: int
    reactions: dict[str, int]
    my_reactions: list[str]


class StreakOut(BaseModel):
    streak: int
    checked_in_today: bool


class PollOptionResult(BaseModel):
    text: str
    votes: int


class PollOut(BaseModel):
    id: int
    question: str
    options: list[str]
    results: list[PollOptionResult]
    total_votes: int
    active: bool
    my_vote: int | None = None
    created_at: datetime


class PollVotePayload(BaseModel):
    option_index: int


class PollCreate(BaseModel):
    question: str
    options: list[str]
