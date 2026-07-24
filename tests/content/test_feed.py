"""Tests for NITHARA-BUILD-PLAN Part 4: the curated app feed.

Stateless (no DB): the feed is a curated bilingual seed served read-only.
"""

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.modules.content.feed import CATEGORIES, FEED_ITEMS, list_feed
from app.modules.temples.service import TemplesService


def test_feed_seed_is_complete_and_bilingual():
    assert FEED_ITEMS
    for a in FEED_ITEMS:
        assert a["cat"] in CATEGORIES
        assert a["title_en"] and a["title_ml"]
        assert a["body_en"] and a["body_ml"]
        assert a["who_en"] and a["who_ml"]


def test_feed_temple_links_resolve_to_real_temples():
    svc = TemplesService()
    for a in FEED_ITEMS:
        if a["temple_id"] is not None:
            assert svc.get_temple(a["temple_id"]) is not None, a["id"]


def test_list_feed_filters():
    festivals = list_feed(cat="Festival")
    assert festivals and all(a["cat"] == "Festival" for a in festivals)
    by_temple = list_feed(temple_id="tsr-guruvayur")
    assert by_temple and all(a["temple_id"] == "tsr-guruvayur" for a in by_temple)
    assert list_feed(cat="Nope") == []


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_feed_endpoint(client):
    async with client:
        allitems = await client.get("/feed")
        assert allitems.status_code == 200, allitems.text
        assert len(allitems.json()) == len(FEED_ITEMS)

        # Case-insensitive category filter.
        fest = await client.get("/feed", params={"cat": "festival"})
        assert fest.json() and all(a["cat"] == "Festival" for a in fest.json())
