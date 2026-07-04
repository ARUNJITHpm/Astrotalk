"""Public service for the chat module — the AI astrologer orchestrator.

Implements the request flow in PROJECT_DOCS.md §6, in this exact order:
  1. tone_safety.screen() FIRST — if crisis, return the safety response and STOP
     (no chart, no transits, no RAG, no LLM, no memory). GUARDRAILS.md §2.
  2. identity.get_chart() + astrology_engine.get_transits()
  3. knowledge.retrieve() grounded in the transits + the user's question
  4. tone_safety.build_system_prompt() with chart/transit/RAG context
  5. llm_client.complete()
  6. return the reply; the router schedules memory extraction as a BackgroundTask

This module imports only the PUBLIC services of other modules (AGENTS.md) — never
their internal files or tables.
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.chat import user_memory
from app.modules.chat.llm_client import LLMClient
from app.modules.chat.schemas import ChatResponse
from app.modules.identity.service import IdentityService
from app.modules.knowledge.service import KnowledgeService
from app.modules.tone_safety.service import ToneSafetyService
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Topic → divisional chart (varga). Checked in order against the user's latest
# message; the first hit picks which varga is grafted into the prompt alongside
# the fixed D1 chart. Keywords cover Malayalam + English phrasings.
_VARGA_TOPICS: list[tuple[str, tuple[str, ...]]] = [
    ("D10", ("career", "job", "work", "business", "promotion", "profession",
             "ജോലി", "തൊഴിൽ", "ബിസിനസ", "കരിയർ", "ഉദ്യോഗ", "പ്രമോഷൻ")),
    ("D9", ("marriage", "relationship", "love", "spouse", "partner", "wedding",
            "divorce", "പൊരുത്തം", "വിവാഹ", "കല്യാണ", "പ്രണയ", "ഭർത്താ", "ഭാര്യ",
            "ദാമ്പത്യ", "വിവാഹമോചന")),
    ("D7", ("child", "children", "baby", "pregnan", "കുട്ടി", "കുഞ്ഞ", "സന്താന",
            "ഗർഭ")),
    ("D12", ("parent", "mother", "father", "അമ്മ", "അച്ഛ", "മാതാപിതാ")),
    ("D3", ("sibling", "brother", "sister", "സഹോദര")),
]


class ChatService:
    def __init__(
        self,
        tone_safety: ToneSafetyService | None = None,
        identity: IdentityService | None = None,
        astrology: AstrologyEngineService | None = None,
        knowledge: KnowledgeService | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self._tone_safety = tone_safety or ToneSafetyService()
        self._identity = identity or IdentityService()
        self._astrology = astrology or AstrologyEngineService()
        self._knowledge = knowledge or KnowledgeService()
        self._llm = llm or LLMClient()

    async def handle_message(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        session: AsyncSession | None = None,
        debug: bool = False,
    ) -> ChatResponse:
        """Run the §6 orchestrator. When ``debug`` is set, attach a per-turn trace
        (params, tools invoked, timings, LLM config) to the response so a
        developer can see exactly how the reply was assembled."""
        t0 = time.perf_counter()
        # steps: ordered [{step, ms, ...}] built as the pipeline runs.
        steps: list[dict] = []

        def _mark(step: str, start: float, **detail) -> None:
            if debug:
                steps.append(
                    {"step": step, "ms": round((time.perf_counter() - start) * 1000, 1), **detail}
                )

        latest = messages[-1]["content"] if messages else ""

        # --- Step 1: crisis screen FIRST. On a hit, stop completely. ---
        s = time.perf_counter()
        crisis = self._tone_safety.screen(latest)
        _mark("crisis_screen", s, fired=crisis, tool="tone_safety.screen")
        if crisis:
            # GUARDRAILS §2: log THAT a crisis route fired, never the content.
            logger.warning("chat: crisis route fired; returning safety response.")
            return ChatResponse(
                reply=self._tone_safety.crisis_reply(),
                is_safety_response=True,
                grounded_in=[],
                debug=self._build_trace(
                    user_id, messages, steps, t0,
                    crisis=True, chart=None, transits=None, query=None,
                    retrieved=[], memory=None, system_prompt=None, reply=None,
                ) if debug else None,
            )

        grounded_in: list[str] = []

        # --- Step 2: chart + transits ---
        s = time.perf_counter()
        chart = await self._load_chart(session, user_id)
        if chart is not None:
            grounded_in.append("chart")
        _mark("load_chart", s, loaded=chart is not None, tool="identity.get_chart_by_phone")
        s = time.perf_counter()
        transits = await self._astrology.get_transits(chart=chart)
        grounded_in.append("transits")
        _mark("get_transits", s, tool="astrology_engine.get_transits")

        # --- Step 3: RAG grounded in transits + question ---
        s = time.perf_counter()
        query = self._retrieval_query(latest, transits)
        retrieved = self._knowledge.retrieve(query, k=3)
        grounded_in.extend(f"knowledge:{chunk.id}" for chunk in retrieved)
        _mark("rag_retrieve", s, tool="knowledge.retrieve", k=3, hits=len(retrieved), query=query)

        # --- Step 3a2: pick the topical divisional chart (varga) ---
        # The D1 chart is fixed; vargas answer specific domains (D9 marriage,
        # D10 career, …). Keep only the topical one in the prompt so it stays
        # focused instead of dumping all five divisional charts.
        varga_key = self._select_varga(latest)
        chart_for_prompt = chart
        varga_used = False
        if isinstance(chart, dict) and "vargas" in chart:
            vargas = chart["vargas"]
            chart_for_prompt = {k: v for k, v in chart.items() if k != "vargas"}
            if varga_key and varga_key in vargas:
                chart_for_prompt["divisional_chart"] = {varga_key: vargas[varga_key]}
                grounded_in.append(f"varga:{varga_key}")
                varga_used = True
        if debug:
            steps.append({
                "step": "select_varga", "ms": 0.0, "tool": "chat.service._select_varga",
                "topic_varga": varga_key, "used": varga_used,
            })

        # --- Step 3b: durable user memory (cross-session profile) ---
        s = time.perf_counter()
        memory = await self._load_memory(user_id)
        if memory:
            grounded_in.append("memory")
        _mark("load_memory", s, used=bool(memory), tool="chat.user_memory.get_profile")

        # --- Step 4: persona system prompt with context ---
        s = time.perf_counter()
        system_prompt = self._tone_safety.build_system_prompt(
            chart=chart_for_prompt,
            transits=transits,
            retrieved=[c.text for c in retrieved],
            memory=memory,
        )
        _mark("build_prompt", s, tool="tone_safety.build_system_prompt", chars=len(system_prompt))

        # --- Step 5: LLM ---
        s = time.perf_counter()
        reply = await self._llm.complete(system_prompt, messages)
        _mark("llm_complete", s, tool="llm_client.complete", **self._llm.debug_meta())

        # --- Step 6: reply (router schedules memory extraction) ---
        return ChatResponse(
            reply=reply,
            is_safety_response=False,
            grounded_in=grounded_in,
            debug=self._build_trace(
                user_id, messages, steps, t0,
                crisis=False, chart=chart, transits=transits, query=query,
                retrieved=retrieved, memory=memory, system_prompt=system_prompt, reply=reply,
            ) if debug else None,
        )

    def _build_trace(
        self, user_id, messages, steps, t0, *,
        crisis, chart, transits, query, retrieved, memory, system_prompt, reply,
    ) -> dict:
        """Assemble the developer trace returned when debug is on."""
        return {
            "user_id": user_id,
            "crisis": crisis,
            "pipeline": steps,
            "input": {
                "latest": messages[-1]["content"] if messages else "",
                "turns": len(messages),
            },
            "chart": {"loaded": chart is not None, "data": chart},
            "transits": transits,
            "rag": {
                "query": query,
                "hits": [
                    {"id": c.id, "topic": getattr(c, "topic", None),
                     "text": c.text[:280], "chars": len(c.text)}
                    for c in retrieved
                ],
            },
            "memory": {"used": bool(memory), "text": memory},
            "system_prompt": system_prompt,
            "llm": {
                **self._llm.debug_meta(),
                "messages_sent": [
                    {"role": m["role"], "chars": len(m["content"])} for m in messages
                ],
            },
            "reply_chars": len(reply) if reply is not None else 0,
            "total_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    async def _load_chart(
        self, session: AsyncSession | None, user_id: str
    ) -> dict | None:
        """Fetch the user's natal chart via identity's public service.

        ``user_id`` is the mobile number (the natural identity key). Degrades to
        None if there's no session, the id carries no digits, or the DB is
        unavailable — chat must still answer (with less grounding) rather than
        error out.
        """
        if session is None or not any(ch.isdigit() for ch in user_id):
            return None
        try:
            chart = await self._identity.get_chart_by_phone(session, user_id)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.warning("chat: chart lookup unavailable (%s); continuing.", exc)
            return None
        return chart.natal_json if chart is not None else None

    async def _load_memory(self, user_id: str) -> str | None:
        """Load the user's durable memory profile, formatted for the prompt.

        Degrades to None if Mongo is disabled/unavailable — chat still answers,
        just without the personalization.
        """
        try:
            profile = await user_memory.get_profile(user_id)
        except Exception as exc:  # pragma: no cover - depends on Mongo availability
            logger.warning("chat: memory lookup unavailable (%s); continuing.", exc)
            return None
        return user_memory.format_for_prompt(profile)

    @staticmethod
    def _select_varga(question: str) -> str | None:
        """Pick the divisional chart matching the question's topic, if any."""
        lower = question.lower()
        for varga, keywords in _VARGA_TOPICS:
            if any(kw in lower for kw in keywords):
                return varga
        return None

    @staticmethod
    def _retrieval_query(question: str, transits: dict) -> str:
        """Build the RAG query from the question plus transit cues (retrograde, etc.)."""
        cues = [
            name
            for name, body in transits.get("transits", {}).items()
            if body.get("retrograde")
        ]
        retro = " ".join(f"{name} retrograde" for name in cues)
        return f"{question} {retro}".strip()
