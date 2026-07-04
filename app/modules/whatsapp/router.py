"""HTTP routes for the whatsapp module — BSP webhooks + consent ledger.

Opt-in is required before any send (GUARDRAILS.md §3). The first live send needs
human approval (AGENTS.md). No open-ended AI chat is exposed here by design.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp import consent
from app.modules.whatsapp.schemas import ConsentRequest, ConsentResponse
from app.platform.db import get_session

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/webhook")
async def webhook() -> dict[str, str]:
    # Opt-in only; first live send needs human approval (AGENTS.md / GUARDRAILS.md).
    # TODO(whatsapp): handle delivery/consent callbacks.
    return {"status": "ok"}


@router.post("/opt-in", response_model=ConsentResponse)
async def opt_in(payload: ConsentRequest, session: SessionDep) -> ConsentResponse:
    record = await consent.opt_in(session, payload.phone)
    await session.commit()
    return ConsentResponse(phone=record.phone, opted_in=record.opted_in)


@router.post("/opt-out", response_model=ConsentResponse)
async def opt_out(payload: ConsentRequest, session: SessionDep) -> ConsentResponse:
    record = await consent.opt_out(session, payload.phone)
    await session.commit()
    return ConsentResponse(phone=record.phone, opted_in=record.opted_in)
