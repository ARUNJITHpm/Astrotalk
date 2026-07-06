"""Tests for the Part-0 platform enablers (GROWTH_PLAN.md).

Covers:
  - platform.cron_auth — the X-Cron-Token gate for scheduled endpoints
    (dev-open, prod-503 when unset, constant-time match when set).
  - platform.storage — the local-disk impl, key sanitisation (path
    traversal must be impossible: /media serves straight from this
    namespace), and settings-driven selection.
  - GET /media/{key} — serving stored objects with the right content type.
  - platform.cards — PNG output at the exact template sizes, Malayalam text.
"""

import io

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from PIL import Image

from app.main import app as main_app
from app.platform import storage as storage_module
from app.platform.cards import TEMPLATES, render_card
from app.platform.config import get_settings
from app.platform.cron_auth import CronGuard
from app.platform.storage import LocalStorage, StorageKeyError, get_storage, reset_storage

# ---- cron auth ----


@pytest.fixture
def cron_app() -> FastAPI:
    api = FastAPI()

    @api.post("/jobs/run", dependencies=[CronGuard])
    async def run_job() -> dict[str, bool]:
        return {"ran": True}

    return api


async def _post(api: FastAPI, headers: dict | None = None) -> httpx.Response:
    transport = ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/jobs/run", headers=headers or {})


@pytest.mark.asyncio
async def test_cron_open_in_dev_when_unset(cron_app, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_token", "")
    monkeypatch.setattr(get_settings(), "app_env", "development")
    assert (await _post(cron_app)).status_code == 200


@pytest.mark.asyncio
async def test_cron_refuses_in_prod_when_unset(cron_app, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_token", "")
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert (await _post(cron_app)).status_code == 503


@pytest.mark.asyncio
async def test_cron_token_must_match(cron_app, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_token", "s3cret")
    assert (await _post(cron_app)).status_code == 401
    assert (await _post(cron_app, {"X-Cron-Token": "wrong"})).status_code == 401
    assert (await _post(cron_app, {"X-Cron-Token": "s3cret"})).status_code == 200


# ---- storage ----


def test_local_storage_roundtrip(tmp_path):
    store = LocalStorage(tmp_path)
    key = store.put("cards/2026-07-07/ashwathi.png", b"png-bytes", "image/png")
    assert key == "cards/2026-07-07/ashwathi.png"
    assert store.exists(key)
    assert store.get(key) == b"png-bytes"
    assert store.url(key) == f"/media/{key}"
    assert store.delete(key) is True
    assert store.get(key) is None
    assert store.delete(key) is False


@pytest.mark.parametrize("bad", ["", "../outside.txt", "a/../../b.png"])
def test_storage_rejects_unsafe_keys(tmp_path, bad):
    store = LocalStorage(tmp_path)
    with pytest.raises(StorageKeyError):
        store.put(bad, b"x")


def test_storage_contains_absolute_keys_under_root(tmp_path):
    # A leading slash is stripped, not honoured: the object lands INSIDE root.
    store = LocalStorage(tmp_path)
    key = store.put("/etc/passwd", b"x")
    assert key == "etc/passwd"
    assert (tmp_path / "etc" / "passwd").is_file()


def test_get_storage_is_local_when_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_storage", True)
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    reset_storage()
    try:
        store = get_storage()
        assert isinstance(store, LocalStorage)
        assert store.root == tmp_path
        assert get_storage() is store  # singleton until reset
    finally:
        reset_storage()


# ---- GET /media/{key} ----


@pytest.fixture
def media_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_storage", True)
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    reset_storage()
    yield get_storage()
    reset_storage()


@pytest.mark.asyncio
async def test_media_route_serves_stored_object(media_storage):
    media_storage.put("cards/test.png", b"\x89PNG fake", "image/png")
    transport = ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get("/media/cards/test.png")
        assert ok.status_code == 200
        assert ok.content == b"\x89PNG fake"
        assert ok.headers["content-type"] == "image/png"
        assert (await client.get("/media/cards/nope.png")).status_code == 404
        assert (await client.get("/media/..%2Fsecret.txt")).status_code == 404


# ---- cards ----


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_render_card_produces_png_at_template_size(template):
    png = render_card(
        title="2026 ജൂലൈ 7 · അശ്വതി",
        body="ഇന്ന് ശാന്തമായ മനസ്സോടെ തുടങ്ങാം. ചെറിയ നന്മകൾ വലിയ മാറ്റങ്ങളുണ്ടാക്കും.",
        template=template,
    )
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    assert image.size == TEMPLATES[template]


def test_render_card_rejects_unknown_template():
    with pytest.raises(ValueError):
        render_card(title="x", body="y", template="billboard")
