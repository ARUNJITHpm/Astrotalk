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

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.modules.admin.router import router as admin_router
from app.modules.astrology_engine.router import router as astrology_engine_router
from app.modules.chat.router import router as chat_router
from app.modules.commerce.router import router as commerce_router
from app.modules.community.router import router as community_router
from app.modules.content.router import router as content_router
from app.modules.identity.router import router as identity_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.notifications.router import router as notifications_router
from app.modules.temples.router import router as temples_router
from app.modules.tone_safety.router import router as tone_safety_router
from app.modules.whatsapp.router import router as whatsapp_router
from app.platform.db import init_db
from app.platform.logging_config import configure_logging
from app.platform.mongo import close_mongo

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Every table-owning module's models are imported above via its router, so
    # Base.metadata is complete by the time we create missing tables here.
    await init_db()
    yield
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
    temples_router,
    whatsapp_router,
    community_router,
    commerce_router,
    notifications_router,
    admin_router,
):
    app.include_router(router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Dev convenience: never let the browser serve a stale copy of the web UI. The
# app runs with uvicorn --reload locally, so edits to app.js / auth.js / styles
# / the HTML pages must show up on refresh without a hard-reload.
@app.middleware("http")
async def _no_store_web_assets(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path in ("/", "/auth", "/wa"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ---- Web UI (Claude-desktop-style chatbot) ----
_WEB_DIR = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html")


# Login / register page. The chat (`/`) redirects here when no account is known;
# on success this page stores the mobile number and sends the user back to `/`.
@app.get("/auth", include_in_schema=False)
async def auth_page() -> FileResponse:
    return FileResponse(_WEB_DIR / "auth.html")


# WhatsApp-style skin over the SAME chat brain (POST /chat/message). This is a
# demo surface only — the real whatsapp module stays compliance-locked and does
# NOT expose open-ended AI chat (GUARDRAILS.md §3).
@app.get("/wa", include_in_schema=False)
async def whatsapp_ui() -> FileResponse:
    return FileResponse(_WEB_DIR / "whatsapp.html")


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
    print(f"Tara running →  website http://localhost:{port}/   ·   WhatsApp http://localhost:{port}/wa")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
