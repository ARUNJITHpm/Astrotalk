"""Tara modular monolith — single FastAPI app composed from bounded modules."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make the app importable and safe to launch from anywhere. Running the script
# directly (`python main.py` inside app/, or `python app/main.py`) has two traps:
#   1. `app.modules...` imports need the project ROOT (the folder containing
#      app/) on sys.path, else "No module named 'app'".
#   2. Python auto-adds the script's own dir (app/) to sys.path, where our local
#      `app/platform/` package SHADOWS the stdlib `platform` module and breaks
#      third-party imports (e.g. SQLAlchemy).
# So we drop the app/ dir from sys.path and prepend the project root. Launching
# via `uvicorn app.main:app` from the root is unaffected.
_HERE = Path(__file__).resolve().parent  # .../tara/app
_ROOT = _HERE.parent  # .../tara


def _is_app_dir(entry: str) -> bool:
    try:
        return Path(entry or ".").resolve() == _HERE
    except Exception:
        return False


sys.path[:] = [p for p in sys.path if not _is_app_dir(p)]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import mimetypes

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.modules.admin.router import router as admin_router
from app.modules.astrologers.router import router as astrologers_router
from app.modules.astrology_engine.router import router as astrology_engine_router
from app.modules.bookings.router import router as bookings_router
from app.modules.chat.router import router as chat_router
from app.modules.commerce.router import router as commerce_router
from app.modules.community.router import router as community_router
from app.modules.content.router import router as content_router
from app.modules.content.router import share_router as content_share_router
from app.modules.identity.router import router as identity_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.notifications.router import router as notifications_router
from app.modules.orgs.router import router as orgs_router
from app.modules.orgs.router import whitelabel_router as orgs_whitelabel_router
from app.modules.temples.router import router as temples_router
from app.modules.temples.router import site_router as temples_site_router
from app.modules.tone_safety.router import router as tone_safety_router
from app.modules.whatsapp.keepalive import start_keepalive
from app.modules.whatsapp.router import router as whatsapp_router
from app.platform.db import init_db
from app.platform.logging_config import configure_logging, get_logger
from app.platform.mongo import close_mongo

configure_logging()


async def _load_directories() -> None:
    """Cache the temple and astrologer directories, and the app feed.

    All three are read synchronously — the directories from inside the chat
    turn, the feed from a route with no session — so they are snapshots rather
    than per-call queries (see each module's ``registry.py``, and
    ``content/feed.py``). An empty table falls back to that module's curated
    seed, so a failure here must never stop the app booting: the fallback still
    serves working content.
    """
    from app.modules.astrologers import registry as astrologers_registry
    from app.modules.content import feed as content_feed
    from app.modules.temples import registry as temples_registry
    from app.platform.db import async_session_factory

    log = get_logger(__name__)
    for name, registry in (
        ("temple", temples_registry),
        ("astrologer", astrologers_registry),
        ("feed", content_feed),
    ):
        try:
            async with async_session_factory() as session:
                loaded = await registry.load(session)
            log.info("%s directory loaded: %d rows", name, loaded)
        except Exception:
            log.exception("%s directory load failed; falling back to the seed", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Every table-owning module's models are imported above via its router, so
    # Base.metadata is complete by the time we create missing tables here.
    await init_db()
    await _load_directories()
    # Keep a scale-to-zero WAHA host (Render free tier) awake by pinging it on
    # an interval. No-op unless waha_keepalive_enabled is set in production.
    keepalive_task = start_keepalive()
    yield
    if keepalive_task is not None:
        keepalive_task.cancel()
    await close_mongo()


app = FastAPI(
    title="Tara",
    description="Malayalam-first AI astrology companion.",
    lifespan=lifespan,
)

for router in (
    identity_router,
    astrology_engine_router,
    knowledge_router,
    tone_safety_router,
    chat_router,
    content_router,
    content_share_router,
    temples_router,
    temples_site_router,
    astrologers_router,
    whatsapp_router,
    community_router,
    commerce_router,
    bookings_router,
    notifications_router,
    orgs_router,
    orgs_whitelabel_router,
    admin_router,
):
    app.include_router(router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Generated media (share cards, report PDFs) — served out of platform storage.
# With local storage this reads the file from disk; with R2 + a public base
# URL, Storage.url() points browsers at the bucket and this route sits unused.
@app.get("/media/{key:path}", include_in_schema=False)
async def media(key: str) -> Response:
    from anyio import to_thread

    from app.platform.storage import StorageKeyError, get_storage

    try:
        data = await to_thread.run_sync(get_storage().get, key)
    except StorageKeyError:
        raise HTTPException(status_code=404, detail="Not found")
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"})


# The SPA shell and the operator pages must never be served stale (a new deploy
# has to reach an open tab), but Vite content-hashes everything under /assets/,
# so those filenames change whenever their bytes do and can be cached hard.
_NO_STORE_PATHS = frozenset((
    "/", "/poojas", "/astro", "/profile",
    "/sw.js", "/registerSW.js", "/manifest.webmanifest",
    "/admin", "/console", "/wa", "/whatsapp", "/prototype",
))


@app.middleware("http")
async def _web_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/static") or path in _NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store"
    return response


# ---- Web UI ----
# Two surfaces share this app:
#   /                          the Nithara PWA — a React SPA built from
#                              app-nithara/ into app-nithara/dist (see the
#                              frontend stage of the Dockerfile).
#   /admin, /console, /whatsapp   operator pages, still hand-written HTML.
# The old user-facing UI (chat at /, /auth, /feed, /ui/*) was removed when
# Nithara took the root; it lives on in the `legacy-tara-ui` branch.
_WEB_DIR = _HERE / "web"
_NITHARA_DIR = _ROOT / "app-nithara" / "dist"
_NITHARA_INDEX = _NITHARA_DIR / "index.html"

app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


def _spa_shell() -> FileResponse:
    if not _NITHARA_INDEX.is_file():
        raise HTTPException(
            status_code=503,
            detail="Nithara frontend not built — run `npm ci && npm run build` in app-nithara/.",
        )
    return FileResponse(_NITHARA_INDEX)


# react-router's client-side routes (app-nithara/src/App.tsx). Each serves the
# same shell and the router picks the screen. Listed explicitly rather than via
# a catch-all so an unknown path still 404s instead of silently rendering the
# app — a catch-all would turn every typo'd API call into an HTML 200.
for _spa_route in ("/", "/poojas", "/astro", "/profile"):
    app.get(_spa_route, include_in_schema=False)(_spa_shell)


# WhatsApp simulator: same brain as real WhatsApp (POST /whatsapp/simulate →
# onboarding FSM + chat), admin-token gated. Lets us test the exact flow a real
# WhatsApp user gets without touching the live WAHA session.
@app.get("/whatsapp", include_in_schema=False)
async def whatsapp_ui() -> FileResponse:
    return FileResponse(_WEB_DIR / "whatsapp.html")


# Back-compat: the skin used to live at /wa. Keep old links/bookmarks working.
@app.get("/wa", include_in_schema=False)
async def whatsapp_ui_legacy() -> RedirectResponse:
    return RedirectResponse(url="/whatsapp")


# Admin analytics dashboard (project overview: users, charts, chat, tokens).
# The page is static; every data call it makes hits the token-gated /admin API.
@app.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    return FileResponse(_WEB_DIR / "admin.html")


# Owner Admin Console: one place that surfaces every feature (content studio,
# daily pack, feed & polls, panchangam, temple tools, WhatsApp simulator) plus
# the growth-plan roadmap. Login = owner email + password (POST /admin/login);
# every data call it makes is gated by the X-Admin-Token it stores.
@app.get("/console", include_in_schema=False)
async def console_page() -> FileResponse:
    return FileResponse(_WEB_DIR / "console.html")


# The original design prototype, served as-is for eyeballing the intended UI
# against what the React port actually does. It is a single self-contained file
# (its own CSS, SVG sprite and mock data inline) and talks to nothing here — so
# it renders identically whether or not the API behind it is healthy, which is
# the point: it is the reference, not a second copy of the product.
@app.get("/prototype", include_in_schema=False)
async def prototype_page() -> FileResponse:
    prototype = _ROOT / "nithara-v11.html"
    if not prototype.is_file():
        raise HTTPException(status_code=404, detail="Prototype not found")
    return FileResponse(prototype)


# Nithara's build output (/assets/*, /sw.js, /manifest.webmanifest, icons).
# Mounted LAST and at the root: Starlette matches in registration order, so
# every API route and operator page declared above still wins, and only what
# none of them claimed reaches the static files. Guarded on the directory
# existing so the API (and the test suite) boots without a frontend build.
if _NITHARA_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_NITHARA_DIR), name="nithara")


# Dev entrypoint: `python main.py` (from anywhere) starts the server. Production
# should use `uvicorn app.main:app` directly. We chdir to the project root and
# put it on PYTHONPATH so uvicorn's reloader subprocess can import `app` too.
if __name__ == "__main__":
    import os

    import uvicorn

    from app.platform.config import get_settings

    os.chdir(_ROOT)
    os.environ["PYTHONPATH"] = str(_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")

    port = get_settings().port
    # ASCII-only banner: Windows consoles often default to cp1252, where
    # printing "→"/"·" raises UnicodeEncodeError and kills the server at boot.
    print(
        f"Nithara running -  app http://localhost:{port}/"
        f"   |   console http://localhost:{port}/console"
        f"   |   admin http://localhost:{port}/admin"
        f"   |   WhatsApp sim http://localhost:{port}/whatsapp"
    )
    # The app at / needs app-nithara/dist. For frontend work run Vite instead
    # (`npm run dev` in app-nithara/, VITE_API_BASE pointed at this server) —
    # dist is a build artefact and is not rebuilt by the reloader.
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
