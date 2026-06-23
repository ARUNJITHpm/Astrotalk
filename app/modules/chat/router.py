"""HTTP routes for the chat module — the in-app AI astrologer."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.modules.chat.schemas import ChatRequest
from app.modules.chat.service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

_service = ChatService()


@router.post("/message")
async def send_message(payload: ChatRequest) -> StreamingResponse:
    """Stream the assistant reply token-by-token (Claude-desktop style).

    Flow (docs §6): tone_safety crisis screen FIRST, then persona + LLM.
    """
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    async def token_stream():
        async for chunk in _service.stream_reply(messages):
            yield chunk

    return StreamingResponse(token_stream(), media_type="text/plain; charset=utf-8")
