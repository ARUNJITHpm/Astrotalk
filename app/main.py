"""Tara modular monolith — single FastAPI app composed from bounded modules."""

from pathlib import Path

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
from app.modules.tone_safety.router import router as tone_safety_router
from app.modules.whatsapp.router import router as whatsapp_router

app = FastAPI(title="Tara", description="Malayalam-first AI astrology companion.")

for router in (
    identity_router,
    astrology_engine_router,
    knowledge_router,
    tone_safety_router,
    chat_router,
    content_router,
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


# ---- Web UI (Claude-desktop-style chatbot) ----
_WEB_DIR = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html")
