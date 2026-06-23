"""HTTP routes for the whatsapp module — BSP webhooks + consent ledger."""

from fastapi import APIRouter

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def webhook() -> dict[str, str]:
    # Opt-in only; first live send needs human approval (AGENTS.md / GUARDRAILS.md).
    # TODO(whatsapp): handle delivery/consent callbacks.
    return {"status": "ok"}
