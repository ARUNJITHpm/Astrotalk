"""Public service for the chat module — the AI astrologer orchestrator.

Implements the request flow in PROJECT_DOCS.md §6, in this exact order:
  1. tone_safety.screen() FIRST — if crisis, return the safety response and STOP
     (no chart, no transits, no RAG, no LLM, no memory). GUARDRAILS.md §2.
  2. identity.get_chart() + astrology_engine.get_transits()
  3. knowledge.retrieve() grounded in the computed chart facts + the question
     (3c: temples.suggest() when remedies are asked for or traditional)
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
from app.modules.chat.schemas import ChatResponse, PrashnamPick
from app.modules.identity.service import IdentityService
from app.modules.knowledge.service import KnowledgeService
from app.modules.temples.service import TemplesService
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

# Explicit remedy/temple intent — the user is ASKING for devotional guidance.
# (Careful with short Malayalam stems: "തൊഴ" would also match "തൊഴിൽ"/job.)
_REMEDY_INTENT = (
    "temple", "remedy", "remedies", "pariharam", "pooja", "puja", "vazhipadu",
    "prayer", "pray", "worship", "mantra", "offering", "darshan",
    "ക്ഷേത്ര", "അമ്പല", "വഴിപാട", "പരിഹാര", "പ്രാർത്ഥ", "പൂജ", "മന്ത്ര",
    "ദർശന", "തൊഴണ", "തൊഴാൻ",
)

# Concern+dosha pairs where a temple suggestion is traditional even without the
# user explicitly asking (e.g. chovva dosha in a marriage question). Kept narrow
# so suggestions don't spam every chat; anything else needs explicit intent.
_AUTO_SUGGEST_PAIRS = {
    ("marriage", "chovva_dosha"),
    ("children", "kala_sarpa_dosha"),
}


class ChatService:
    def __init__(
        self,
        tone_safety: ToneSafetyService | None = None,
        identity: IdentityService | None = None,
        astrology: AstrologyEngineService | None = None,
        knowledge: KnowledgeService | None = None,
        llm: LLMClient | None = None,
        temples: TemplesService | None = None,
    ) -> None:
        self._tone_safety = tone_safety or ToneSafetyService()
        self._identity = identity or IdentityService()
        self._astrology = astrology or AstrologyEngineService()
        self._knowledge = knowledge or KnowledgeService()
        self._llm = llm or LLMClient()
        self._temples = temples or TemplesService()

    async def handle_message(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        session: AsyncSession | None = None,
        debug: bool = False,
        prashnam: PrashnamPick | None = None,
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

        # --- Step 2p: prashnam (horary) reading, when this turn carries a pick ---
        # Deterministic end to end: the engine computes the question-moment
        # chart and the thamboola/swarna rules; the LLM only narrates them.
        prashnam_note: str | None = None
        prashnam_cues: list[str] = []
        if prashnam is not None:
            s = time.perf_counter()
            lat, lng = await self._load_user_location(session, user_id)
            loc = {"lat": lat, "lng": lng} if lat is not None and lng is not None else {}
            reading = await self._astrology.get_prashnam_reading(
                prashnam.mode,
                leaf_count=prashnam.leaf_count,
                arudha_rasi_index=prashnam.arudha_rasi_index,
                number=prashnam.number,
                **loc,
            )
            prashnam_cues = reading["cues"]
            prashnam_note = self._prashnam_note(reading)
            grounded_in.append(f"prashnam:{prashnam.mode}")
            _mark(
                "prashnam_reading", s, tool="astrology_engine.get_prashnam_reading",
                mode=prashnam.mode, cues=prashnam_cues,
            )

        # --- Step 3: RAG grounded in the question + computed facts ---
        # The chart facts (mahadasha lord, janma nakshatram, doshas, sade sati)
        # are computed by astrology_engine; feeding them into the query pulls the
        # interpretation chunks that match THIS person's chart, not just the
        # question's wording. A prashnam turn retrieves on the reading's cues
        # instead — the prashna chart of the moment, not the natal chart, is
        # what the answer hangs on.
        s = time.perf_counter()
        if prashnam_cues:
            query = " ".join([latest, *prashnam_cues]).strip()
        else:
            query = self._retrieval_query(latest, transits, chart)
        retrieved = self._knowledge.retrieve(query, k=4)
        grounded_in.extend(f"knowledge:{chunk.id}" for chunk in retrieved)
        _mark("rag_retrieve", s, tool="knowledge.retrieve", k=4, hits=len(retrieved), query=query)

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
        memory, stored_district = await self._load_memory(user_id)
        if memory:
            grounded_in.append("memory")
        _mark("load_memory", s, used=bool(memory), tool="chat.user_memory.get_profile")

        # --- Step 3c: temple guidance (optional devotional suggestion) ---
        # Deterministic: temples.suggest picks deity+temple from the computed
        # doshas/dasha and the message's concern; the LLM only narrates it.
        # The profile's stored district ("where I live now") localizes the
        # suggestion when the message itself names no place.
        s = time.perf_counter()
        temple_note, temple_ids = await self._temple_guidance(
            latest, chart, transits, session, user_id, stored_district
        )
        grounded_in.extend(f"temple:{tid}" for tid in temple_ids)
        _mark(
            "temple_guidance", s, tool="temples.suggest",
            suggested=temple_ids or None,
        )

        # --- Step 4: persona system prompt with context ---
        s = time.perf_counter()
        notes = [c.text for c in retrieved]
        if prashnam_note:
            notes.append(prashnam_note)
        if temple_note:
            notes.append(temple_note)
        system_prompt = self._tone_safety.build_system_prompt(
            chart=chart_for_prompt,
            transits=transits,
            retrieved=notes,
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

    async def _load_memory(self, user_id: str) -> tuple[str | None, str | None]:
        """Load the user's durable memory profile: (prompt block, current district).

        The district is where the user lives NOW (captured by memory extraction),
        distinct from the birth place in identity. Degrades to (None, None) if
        Mongo is disabled/unavailable — chat still answers, just without the
        personalization.
        """
        try:
            profile = await user_memory.get_profile(user_id)
        except Exception as exc:  # pragma: no cover - depends on Mongo availability
            logger.warning("chat: memory lookup unavailable (%s); continuing.", exc)
            return None, None
        district = (profile or {}).get("district")
        return user_memory.format_for_prompt(profile), district

    async def _temple_guidance(
        self,
        question: str,
        chart: dict | None,
        transits: dict,
        session: AsyncSession | None,
        user_id: str,
        stored_district: str | None = None,
    ) -> tuple[str | None, list[str]]:
        """Suggest temples when the user asks for remedies — or when a classic
        concern+dosha pairing makes it traditional (e.g. marriage + chovva).

        Returns (prompt note, temple ids). The note carries its own framing so
        the LLM presents the visit as an optional act of devotion — never a
        demand, never fear, never payment (GUARDRAILS.md §1).
        """
        lower = question.lower()
        concern = self._temples.detect_concern(question)

        doshas: list[str] = []
        if isinstance(chart, dict):
            chart_doshas = chart.get("doshas") or {}
            doshas = [
                name for name, d in chart_doshas.items()
                if isinstance(d, dict) and d.get("present")
            ]
        if transits.get("sade_sati", {}).get("active"):
            doshas.append("sade_sati")

        asked = any(kw in lower for kw in _REMEDY_INTENT)
        traditional = any(
            (concern, dosha) in _AUTO_SUGGEST_PAIRS for dosha in doshas
        )
        if not asked and not traditional:
            return None, []

        grahas: list[str] = []
        if isinstance(chart, dict):
            maha = ((chart.get("dasha") or {}).get("current") or {}).get("mahadasha") or {}
            if maha.get("lord"):
                grahas.append(maha["lord"])

        # The message's own place mention wins; else where the user said they
        # live (memory profile); the identity lat/lng (birth place) is last.
        district = self._temples.detect_district(question) or stored_district
        lat, lng = await self._load_user_location(session, user_id)

        # k=1 on purpose: gpt-4o-mini narrates everything it is given, so the
        # "at most one temple" guardrail is enforced here, not by instruction.
        suggestions = self._temples.suggest(
            concern=concern, doshas=doshas, grahas=grahas,
            district=district, lat=lat, lng=lng, k=1,
        )
        if not suggestions:
            return None, []

        t = suggestions[0]
        near = f", about {t.distance_km:g} km away" if t.distance_km is not None else ""
        note = (
            "Temple guidance (share only if it fits the conversation "
            "naturally, as an optional act of devotion the person may choose "
            "— never as a requirement, never out of fear, and never linked "
            "to payment. Copy the temple name, town and district EXACTLY as "
            "written below; do not substitute a different place):\n"
            f"- {t.name} ({t.name_ml}), {t.town}, {t.district}{near}: "
            f"{t.reason}. Known for {t.famous_for}. "
            f"Vazhipadu: {', '.join(t.vazhipadu)}. Days: {t.days}. "
            f"Mantra: {t.mantra}."
        )
        return note, [t.id]

    @staticmethod
    def _prashnam_note(reading: dict) -> str:
        """Deterministic prompt note for a prashnam reading.

        Carries the computed facts AND the honesty guardrail: Tara presents
        this as a traditional-STYLE reading of the question moment, never as
        equivalent to an in-person ashtamangala prashnam with a Daivajna.
        """
        chart = reading["prashna_chart"]
        moon = chart["moon"]
        facts = [
            f"- Udaya lagnam (rising now): {chart['udaya_lagnam']}; "
            f"Moon: {moon['rasi']} ({moon['nakshatram']}), house {moon['house']} "
            f"from the lagna; tithi {chart['tithi']} ({chart['paksha']})."
        ]
        if reading["mode"] == "thamboola":
            facts.append(
                f"- Thamboola (താംബൂല പ്രശ്നം): {reading['leaf_count']} leaves — "
                f"{reading['parity']} "
                f"({'gati/movement' if reading['parity'] == 'odd' else 'sthiti/steadiness'}), "
                f"remainder {reading['remainder']} of 8; Moon's house relation: "
                f"{reading['moon_house_relation']}."
            )
        elif reading["mode"] == "sankhya":
            facts.append(
                f"- Sankhya (സംഖ്യാ പ്രശ്നം): number {reading['number']} of 108 — "
                f"falls in {reading['number_rasi']} rasi and "
                f"{reading['number_nakshatram']} nakshatra (pada "
                f"{reading['number_pada']}), house "
                f"{reading['number_house_from_lagna']} from the udaya lagna "
                f"({reading['number_lagna_relation']})."
            )
        else:
            facts.append(
                f"- Swarna (സ്വർണ പ്രശ്നം): arudha (ആരൂഢം) {reading['arudha_rasi']}, "
                f"house {reading['arudha_house_from_lagna']} from the udaya lagna "
                f"({reading['arudha_lagna_relation']}); Moon is house "
                f"{reading['moon_house_from_arudha']} from the arudha."
            )
        return (
            "Prashnam reading of this question's moment (facts computed by the "
            "engine — narrate them, do not add placements):\n"
            + "\n".join(facts)
            + "\nHONESTY RULE: present this as a traditional-style reading of "
            "the question moment. NEVER claim or imply it equals an in-person "
            "ashtamangala prashnam (അഷ്ടമംഗല പ്രശ്നം) conducted by a Daivajna; "
            "if the matter is weighty, gently note that a full prashnam is done "
            "in person. Frame as reflective guidance the person is free to "
            "weigh — never as a decree, never with fear."
        )

    async def _load_user_location(
        self, session: AsyncSession | None, user_id: str
    ) -> tuple[float | None, float | None]:
        """The user's stored place (lat/lng), for 'temples near you' ranking.

        Uses identity's public service; degrades to (None, None) without a
        session/registration. Coordinates stay in memory only — never logged,
        never in URLs (GUARDRAILS.md §4).
        """
        if session is None or not any(ch.isdigit() for ch in user_id):
            return None, None
        try:
            user = await self._identity.get_user_by_phone(session, user_id)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.warning("chat: user lookup unavailable (%s); continuing.", exc)
            return None, None
        if user is None:
            return None, None
        return user.lat, user.lng

    @staticmethod
    def _select_varga(question: str) -> str | None:
        """Pick the divisional chart matching the question's topic, if any."""
        lower = question.lower()
        for varga, keywords in _VARGA_TOPICS:
            if any(kw in lower for kw in keywords):
                return varga
        return None

    @staticmethod
    def _retrieval_query(question: str, transits: dict, chart: dict | None = None) -> str:
        """Build the RAG query from the question plus computed chart/transit facts.

        Facts are computed (astrology_engine), knowledge is retrieved (this
        query), language is generated (LLM). Every cue added here is a fact the
        engine derived — the query never invents astrology.
        """
        cues: list[str] = []

        # Transit cues: retrograde planets. Rahu/Ketu are excluded — the nodes
        # are perpetually retrograde, so they carry no signal and would drag
        # retrograde chunks into every single query.
        for name, body in transits.get("transits", {}).items():
            if body.get("retrograde") and name not in ("rahu", "ketu"):
                cues.append(f"{name} retrograde")

        # Transit cue: active Sade Sati (Saturn 12th/1st/2nd from janma rasi).
        if transits.get("sade_sati", {}).get("active"):
            cues.append("sade sati shani saturn")

        # Chart cues: the person's own computed facts.
        if isinstance(chart, dict):
            if chart.get("nakshatram"):
                cues.append(str(chart["nakshatram"]))
            if chart.get("lagnam"):
                cues.append(f"{chart['lagnam']} lagna")
            current = (chart.get("dasha") or {}).get("current") or {}
            maha = current.get("mahadasha") or {}
            if maha.get("lord"):
                cues.append(f"{maha['lord']} mahadasha dasha")
            doshas = chart.get("doshas") or {}
            if doshas.get("chovva_dosha", {}).get("present"):
                cues.append("chovva dosha mangal")
            if doshas.get("kala_sarpa_dosha", {}).get("present"):
                cues.append("kala sarpa dosha")

        return " ".join([question, *cues]).strip()
