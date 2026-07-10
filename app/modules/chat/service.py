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

from app.modules.astrologers.service import AstrologersService
from app.modules.astrology_engine.service import AstrologyEngineService
from app.modules.chat import analytics, recurrence, user_memory
from app.modules.chat.llm_client import LLMClient
from app.modules.chat.schemas import ChatResponse, PoruthamPartner, PrashnamPick
from app.modules.chat.suggestions import build_suggestions
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
    (
        "D10",
        (
            "career",
            "job",
            "work",
            "business",
            "promotion",
            "profession",
            "ജോലി",
            "തൊഴിൽ",
            "ബിസിനസ",
            "കരിയർ",
            "ഉദ്യോഗ",
            "പ്രമോഷൻ",
            # Manglish (romanized) — users often type Malayalam in Latin script
            "joli",
            "jolik",
            "thozhil",
            "udyogam",
            "velakku",
        ),
    ),
    (
        "D9",
        (
            "marriage",
            "relationship",
            "love",
            "spouse",
            "partner",
            "wedding",
            "divorce",
            "പൊരുത്തം",
            "വിവാഹ",
            "കല്യാണ",
            "പ്രണയ",
            "ഭർത്താ",
            "ഭാര്യ",
            "ദാമ്പത്യ",
            "വിവാഹമോചന",
            "kalyanam",
            "vivaham",
            "porutham",
            "pranayam",
            "bharthavu",
            "bharya",
            "dambatyam",
        ),
    ),
    (
        "D7",
        (
            "child",
            "children",
            "baby",
            "pregnan",
            "കുട്ടി",
            "കുഞ്ഞ",
            "സന്താന",
            "ഗർഭ",
            "kutti",
            "kunju",
            "santhanam",
            "garbham",
        ),
    ),
    (
        "D12",
        (
            "parent",
            "mother",
            "father",
            "അമ്മ",
            "അച്ഛ",
            "മാതാപിതാ",
            "achan",
            "achhan",
            "mathapithak",
        ),
    ),
    (
        "D3",
        (
            "sibling",
            "brother",
            "sister",
            "സഹോദര",
            "sahodaran",
            "sahodari",
            "chettan",
            "aniyan",
            "chechi",
            "aniyathi",
        ),
    ),
]

# Explicit remedy/temple intent — the user is ASKING for devotional guidance.
# (Careful with short Malayalam stems: "തൊഴ" would also match "തൊഴിൽ"/job.)
_REMEDY_INTENT = (
    "temple",
    "remedy",
    "remedies",
    "pariharam",
    "pooja",
    "puja",
    "vazhipadu",
    "prayer",
    "pray",
    "worship",
    "mantra",
    "offering",
    "darshan",
    "ക്ഷേത്ര",
    "അമ്പല",
    "വഴിപാട",
    "പരിഹാര",
    "പ്രാർത്ഥ",
    "പൂജ",
    "മന്ത്ര",
    "ദർശന",
    "തൊഴണ",
    "തൊഴാൻ",
    # Manglish (romanized) forms
    "kshethram",
    "kshetram",
    "ambalam",
    "vazhipad",
    "prarthana",
    "mantram",
    "darshanam",
    "homam",
    "archana",
    "pushpanjali",
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
        astrologers: AstrologersService | None = None,
    ) -> None:
        self._tone_safety = tone_safety or ToneSafetyService()
        self._identity = identity or IdentityService()
        self._astrology = astrology or AstrologyEngineService()
        self._knowledge = knowledge or KnowledgeService()
        self._llm = llm or LLMClient()
        self._temples = temples or TemplesService()
        self._astrologers = astrologers or AstrologersService()

    async def admin_stats(self, session: AsyncSession) -> dict:
        """Chat-volume metrics for the admin dashboard (read-only).

        Exposes the chat module's own history aggregation as its public surface
        so the admin module never touches ``chat_history`` directly. Degrades to
        ``{"available": False}`` only if the aggregation errors.
        """
        return await analytics.chat_metrics(session)

    async def handle_message(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        session: AsyncSession | None = None,
        debug: bool = False,
        prashnam: PrashnamPick | None = None,
        porutham: PoruthamPartner | None = None,
        provider: str | None = None,
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
                    {
                        "step": step,
                        "ms": round((time.perf_counter() - start) * 1000, 1),
                        **detail,
                    }
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
                debug=(
                    self._build_trace(
                        user_id,
                        messages,
                        steps,
                        t0,
                        crisis=True,
                        chart=None,
                        transits=None,
                        query=None,
                        retrieved=[],
                        memory=None,
                        system_prompt=None,
                        reply=None,
                    )
                    if debug
                    else None
                ),
            )

        grounded_in: list[str] = []

        # --- Step 2: chart + transits ---
        s = time.perf_counter()
        chart = await self._load_chart(session, user_id)
        if chart is not None:
            grounded_in.append("chart")
        _mark(
            "load_chart",
            s,
            loaded=chart is not None,
            tool="identity.get_chart_by_phone",
        )
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
            loc = (
                {"lat": lat, "lng": lng} if lat is not None and lng is not None else {}
            )
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
                "prashnam_reading",
                s,
                tool="astrology_engine.get_prashnam_reading",
                mode=prashnam.mode,
                cues=prashnam_cues,
            )

        # --- Step 2c: porutham (compatibility) when a partner is attached ---
        # Structured input → deterministic engine → the LLM only narrates. The
        # user's OWN chart is one side; the partner's chart is computed here from
        # the partner form (geocode + natal chart), then the ten Kerala
        # poruthams are graded in Python. This is what makes "പൊരുത്തം നോക്കാമോ?"
        # actually work instead of the LLM improvising over raw text.
        porutham_note: str | None = None
        if porutham is not None:
            s = time.perf_counter()
            porutham_note, porutham_result = await self._porutham_guidance(
                porutham, chart, session, user_id
            )
            if porutham_result is not None:
                grounded_in.append("porutham")
            _mark(
                "porutham",
                s,
                tool="astrology_engine.compute_porutham",
                computed=porutham_result is not None,
                score=(porutham_result or {}).get("score"),
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
        _mark(
            "rag_retrieve",
            s,
            tool="knowledge.retrieve",
            k=4,
            hits=len(retrieved),
            query=query,
        )

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
            steps.append(
                {
                    "step": "select_varga",
                    "ms": 0.0,
                    "tool": "chat.service._select_varga",
                    "topic_varga": varga_key,
                    "used": varga_used,
                }
            )

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
            "temple_guidance",
            s,
            tool="temples.suggest",
            suggested=temple_ids or None,
        )

        # --- Step 3d: human-astrologer escalation. If the same concern keeps
        # recurring (or the user asks outright), offer an experienced human
        # astrologer near them + pair a temple visit — optional support, never
        # pressure (GUARDRAILS.md §1). ``astrologer:<id>`` lets the UI render a
        # booking CTA.
        s = time.perf_counter()
        concern = self._temples.detect_concern(latest)
        astro_note, astrologer, recurring = await self._astrologer_guidance(
            latest, concern, session, user_id, stored_district
        )
        if astrologer is not None:
            grounded_in.append(f"astrologer:{astrologer['id']}")
            if recurring:
                grounded_in.append(f"recurring:{recurring}")
            # Pair a temple visit when the recurrence fired and none was already
            # suggested this turn (the brief: astrologer + temple together).
            if recurring and not temple_note:
                lat, lng = await self._load_user_location(session, user_id)
                district = self._temples.detect_district(latest) or stored_district
                paired = self._temples.suggest(
                    concern=recurring, district=district, lat=lat, lng=lng, k=1
                )
                if paired:
                    temple_note = self._format_temple_note(paired[0])
                    grounded_in.append(f"temple:{paired[0].id}")
        _mark(
            "astrologer_guidance",
            s,
            tool="astrologers.suggest_for",
            suggested=(astrologer or {}).get("id"),
            recurring=recurring,
        )

        # --- Step 4: persona system prompt with context ---
        s = time.perf_counter()
        notes = [c.text for c in retrieved]
        if prashnam_note:
            notes.append(prashnam_note)
        if porutham_note:
            notes.append(porutham_note)
        if temple_note:
            notes.append(temple_note)
        if astro_note:
            notes.append(astro_note)
        system_prompt = self._tone_safety.build_system_prompt(
            chart=chart_for_prompt,
            transits=transits,
            retrieved=notes,
            memory=memory,
        )
        # --- Step 4b: white-label persona overlay (Part 4a). Appended AFTER
        # the safety persona and pre-wrapped by orgs with an immutable-
        # guardrails preamble — flavor only, rules always win.
        org_overlay = await self._org_overlay(session, user_id)
        if org_overlay:
            system_prompt = f"{system_prompt}\n\n{org_overlay}"
            grounded_in.append("org")
        _mark(
            "build_prompt",
            s,
            tool="tone_safety.build_system_prompt",
            chars=len(system_prompt),
        )

        # --- Step 5: LLM ---
        s = time.perf_counter()
        reply = await self._llm.complete(system_prompt, messages, provider=provider)
        _mark("llm_complete", s, tool="llm_client.complete", **self._llm.debug_meta())

        # --- Step 5b: output guardrail screen (GUARDRAILS.md §1, enforced) ---
        # The persona asks for no fear / no paid remedies / no urgency; this
        # verifies the model complied. One corrective retry, then a safe
        # fallback — a violation must never reach the user.
        s = time.perf_counter()
        violations = self._tone_safety.screen_reply(reply)
        if violations:
            logger.warning(
                "chat: reply guardrail violation %s; retrying once.", violations
            )
            reply = await self._llm.complete(
                system_prompt + "\n\n" + self._tone_safety.corrective_note(),
                messages,
                provider=provider,
            )
            still = self._tone_safety.screen_reply(reply)
            if still:
                logger.warning(
                    "chat: retry still violates %s; serving safe fallback.", still
                )
                reply = self._tone_safety.safe_reply()
        _mark(
            "reply_screen",
            s,
            tool="tone_safety.screen_reply",
            violations=violations or None,
        )

        # --- Step 6: reply (router schedules memory extraction) ---
        provider_name = getattr(self._llm, "last_provider", "mock")
        model_name = getattr(self._llm, "last_model", None)
        usage = getattr(self._llm, "last_usage", None) or {}
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

        from app.platform.metrics import estimate_price

        price_inr, price_usd = estimate_price(
            provider_name, model_name, prompt_tokens, completion_tokens
        )

        # Curious, chart-personalized follow-up chips (deterministic, no LLM).
        suggestions = build_suggestions(
            latest=latest,
            chart=chart,
            transits=transits,
            grounded_in=grounded_in,
            concern=concern,
            astrologer=astrologer,
        )

        return ChatResponse(
            reply=reply,
            is_safety_response=False,
            grounded_in=grounded_in,
            suggestions=suggestions,
            llm_provider=provider_name,
            llm_model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            price_inr=price_inr,
            price_usd=price_usd,
            debug=(
                self._build_trace(
                    user_id,
                    messages,
                    steps,
                    t0,
                    crisis=False,
                    chart=chart,
                    transits=transits,
                    query=query,
                    retrieved=retrieved,
                    memory=memory,
                    system_prompt=system_prompt,
                    reply=reply,
                )
                if debug
                else None
            ),
        )

    def _build_trace(
        self,
        user_id,
        messages,
        steps,
        t0,
        *,
        crisis,
        chart,
        transits,
        query,
        retrieved,
        memory,
        system_prompt,
        reply,
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
                    {
                        "id": c.id,
                        "topic": getattr(c, "topic", None),
                        "text": c.text[:280],
                        "chars": len(c.text),
                    }
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

    async def _org_overlay(
        self, session: AsyncSession | None, user_id: str
    ) -> str | None:
        """The white-label persona overlay for this user's org, if any.

        Resolved user (phone) → users.org_id → orgs.persona_overlay_for, all
        through public services. Degrades to None on any failure — a broken
        tenant lookup must never take chat down.
        """
        if session is None or not any(ch.isdigit() for ch in user_id):
            return None
        try:
            user = await self._identity.get_user_by_phone(session, user_id)
            if user is None or user.org_id is None:
                return None
            from app.modules.orgs.service import OrgsService

            return await OrgsService().persona_overlay_for(session, user.org_id)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.warning("chat: org overlay unavailable (%s); continuing.", exc)
            return None

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
                name
                for name, d in chart_doshas.items()
                if isinstance(d, dict) and d.get("effective", d.get("present"))
            ]
        if transits.get("sade_sati", {}).get("active"):
            doshas.append("sade_sati")

        asked = any(kw in lower for kw in _REMEDY_INTENT)
        traditional = any((concern, dosha) in _AUTO_SUGGEST_PAIRS for dosha in doshas)
        if not asked and not traditional:
            return None, []

        grahas: list[str] = []
        if isinstance(chart, dict):
            maha = ((chart.get("dasha") or {}).get("current") or {}).get(
                "mahadasha"
            ) or {}
            if maha.get("lord"):
                grahas.append(maha["lord"])

        # The message's own place mention wins; else where the user said they
        # live (memory profile); the identity lat/lng (birth place) is last.
        district = self._temples.detect_district(question) or stored_district
        lat, lng = await self._load_user_location(session, user_id)

        # k=1 on purpose: gpt-4o-mini narrates everything it is given, so the
        # "at most one temple" guardrail is enforced here, not by instruction.
        suggestions = self._temples.suggest(
            concern=concern,
            doshas=doshas,
            grahas=grahas,
            district=district,
            lat=lat,
            lng=lng,
            k=1,
        )
        if not suggestions:
            return None, []

        return self._format_temple_note(suggestions[0]), [suggestions[0].id]

    @staticmethod
    def _format_temple_note(t) -> str:
        """Prompt note for one temple suggestion, carrying its own §1 framing."""
        near = f", about {t.distance_km:g} km away" if t.distance_km is not None else ""
        return (
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

    async def _astrologer_guidance(
        self,
        question: str,
        concern: str | None,
        session: AsyncSession | None,
        user_id: str,
        stored_district: str | None,
    ) -> tuple[str | None, dict | None, str | None]:
        """Offer a human astrologer when a concern keeps recurring (or on a
        direct ask). Returns (prompt note, astrologer dict, recurring concern).

        The note frames the consult as OPTIONAL human support the person may
        choose — never a demand, never out of fear, never a sales pitch, and
        never implying Tara is failing them (GUARDRAILS.md §1).
        """
        recurring, direct_ask = await recurrence.detect_recurring_concern(
            session, user_id, question, self._temples.detect_concern
        )
        if not recurring and not direct_ask:
            return None, None, None

        district = self._temples.detect_district(question) or stored_district
        lat, lng = await self._load_user_location(session, user_id)
        astro = self._astrologers.suggest_for(
            concern=recurring or concern, district=district, lat=lat, lng=lng
        )
        if astro is None:
            return None, None, recurring

        where = astro["town"]
        if astro["district"] and astro["district"] != astro["town"]:
            where = f"{astro['town']}, {astro['district']}"
        context = (
            "this person has raised the same concern several times across recent "
            "conversations"
            if recurring
            else "this person asked to speak with a human astrologer"
        )
        note = (
            "Human-support guidance (share only if it fits naturally, as an "
            "OPTIONAL idea the person may choose — never a requirement, never out "
            "of fear, never with urgency or a sales pitch, and never implying you "
            "are unable to help them). Consultations are free. Context: "
            f"{context}. You may warmly mention that talking things through with an "
            "experienced human astrologer can add comfort and depth, and that they "
            "can pick a convenient time on the astrologers page. Copy the name and "
            "place EXACTLY as written:\n"
            f"- {astro['name']}, {astro['experience_years']} years of experience, "
            f"{where}."
        )
        return note, astro, recurring

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

    async def _porutham_guidance(
        self,
        partner: PoruthamPartner,
        chart: dict | None,
        session: AsyncSession | None,
        user_id: str,
    ) -> tuple[str | None, dict | None]:
        """Compute the ten Kerala poruthams between the user and the partner.

        The logged-in user's OWN chart is one side; the partner's chart is
        computed here from the partner form (geocode → natal chart).
        ``partner.gender`` is the partner's — the user is taken as the opposite
        sex, since the directional poruthams count from the bride's star to the
        groom's. Returns (prompt note, result dict). Degrades to a helpful note
        (result ``None``) when the user's own chart isn't computed yet or the
        pair can't be scored — never a fabricated result.
        """
        # The user needs a real natal chart to match against. A missing or
        # placeholder chart is exactly the "it didn't fetch my profile" case:
        # tell them to complete their birth details rather than guessing.
        if not self._chart_usable(chart):
            return (
                "Porutham request, but the logged-in user's own birth chart "
                "isn't computed yet (it's missing or a placeholder). Gently tell "
                "them you need their birth details on file first — ask them to "
                "add or recompute their birth date, time and place in their "
                "profile, then try the porutham again. Do NOT invent a "
                "compatibility result.",
                None,
            )

        # Partner's chart from the form. Geocoding failures degrade to a
        # placeholder location inside identity — acceptable here, since the
        # janma nakshatram/rasi the porutham needs are Moon-driven, not
        # location-driven.
        try:
            lat, lng, tz = await self._identity.geocode_place(partner.birth_place)
            partner_chart = await self._astrology.compute_natal_chart(
                partner.dob, partner.birth_time, lat, lng, tz
            )
        except Exception as exc:  # pragma: no cover - depends on engine/network
            logger.warning(
                "chat: partner chart unavailable (%s); skipping porutham.", exc
            )
            return (
                "Porutham request, but the partner's chart could not be computed "
                "right now. Apologise briefly and ask them to re-check the "
                "partner's birth date, time and place. Do NOT invent a result.",
                None,
            )

        user_name = await self._user_name(session, user_id)
        partner_name = partner.name or "പങ്കാളി"
        if partner.gender == "female":
            female_chart, female_name = partner_chart, partner_name
            male_chart, male_name = chart, user_name or "നിങ്ങൾ"
        else:
            female_chart, female_name = chart, user_name or "നിങ്ങൾ"
            male_chart, male_name = partner_chart, partner_name

        try:
            result = await self._astrology.compute_porutham(
                female_chart,
                male_chart,
                female_name=female_name,
                male_name=male_name,
            )
        except ValueError as exc:
            logger.warning("chat: porutham not computable (%s); degrading.", exc)
            return (
                "Porutham request could not be scored (incomplete birth data). "
                "Ask the person to confirm both sets of birth details. Do NOT "
                "invent a result.",
                None,
            )
        return self._porutham_note(result), result

    @staticmethod
    def _chart_usable(chart: dict | None) -> bool:
        """True when the chart carries a real Moon placement (not mock/pending)."""
        return (
            isinstance(chart, dict)
            and bool(chart.get("nakshatram"))
            and not chart.get("mock")
            and chart.get("status") != "pending"
        )

    def _porutham_note(self, result: dict) -> str:
        """Deterministic prompt note for a porutham result, with the honesty rule.

        Carries every computed porutham verbatim so the LLM narrates exactly
        what the engine graded — never a marriage verdict, never fear. Each
        partner's star personality (the "how they love" trait from the knowledge
        base) is attached too, so the reading is grounded in BOTH people's stars
        the way a real compatibility talk opens — personality first, then the
        ten poruthams — rather than the model improvising temperament."""
        female, male = result["female"], result["male"]
        lines = [
            f"Pathu porutham (ദശപൊരുത്തം) computed by the almanac method — "
            f"score {result['score']}/{result['max_score']:g}:",
            f"- {female['name']}: {female['nakshatram']} നക്ഷത്രം, "
            f"{female['rasi']} രാശി (bride's side).",
            f"- {male['name']}: {male['nakshatram']} നക്ഷത്രം, "
            f"{male['rasi']} രാശി (groom's side).",
        ]
        # Star personalities, grounded from the knowledge base (never invented).
        for who, person in (("bride", female), ("groom", male)):
            trait = self._knowledge.nakshatra_relationship(person["nakshatram"])
            if trait:
                lines.append(
                    f"- {person['nakshatram']} personality in love ({who}, "
                    f"{person['name']}): {trait}"
                )
        for p in result["poruthams"].values():
            lines.append(f"- {p['label']} [{p['grade']}]: {p['reason']}")
        if result["rajju_dosha"]:
            lines.append(
                "- NOTE: രജ്ജുദോഷം is present (the couple share a rajju group), "
                "traditionally the weightiest concern."
            )
        return (
            "\n".join(lines)
            + "\nIf THIS message asks for the porutham itself, present the full "
            "reading and OPEN it by naming both people's janma nakshatram and "
            "rasi from the lines above (for example: 'നിങ്ങളുടെ നക്ഷത്രം പൂരം, "
            "പങ്കാളിയുടേത് രോഹിണി…') — seeing their own stars named is how the "
            "couple trusts this came from THEIR charts, so never skip it."
            "\nStructure the full reading like a warm astrologer's talk: (1) a "
            "short personality sketch of EACH person from their 'personality in "
            "love' line above, (2) the relationship's STRENGTHS drawn from the "
            "uthamam poruthams, (3) the points to WATCH drawn from the adhamam / "
            "madhyamam ones (name the porutham, e.g. യോനി or രജ്ജു, and what it "
            "means for daily life — communication, ego, patience), and (4) an "
            "honest close on what the score does and does not mean. Weave the "
            "two personalities together (how these two temperaments meet) — do "
            "not just list traits."
            "\nIf this message is a FOLLOW-UP about the couple (their stars, a "
            "specific porutham, what to do next), answer it directly from these "
            "same computed facts — they are already on file, so NEVER ask for "
            "the partner's birth details again."
            "\nHONESTY RULE: narrate exactly these computed poruthams — do not "
            "add or drop any, and do not invent placements or personality traits "
            "beyond the lines above. Present this as the "
            "traditional ten-porutham count families consult — useful guidance "
            "the couple are free to weigh, NEVER a verdict on whether they may "
            "marry, and never with fear or fatalism. A high score is "
            "encouraging; a low one is a single input among many (dosha "
            "remedies, elders' counsel, and above all the couple's own wishes). "
            "Real relationships rest on mutual respect, trust, and communication "
            "more than on a score. For anything binding, gently note a full "
            "match is done by an astrologer with both complete horoscopes. "
            "Warm, plain Malayalam."
        )

    async def _user_name(
        self, session: AsyncSession | None, user_id: str
    ) -> str | None:
        """The logged-in user's display name, for narrating their side of a
        porutham. Degrades to None without a session/registration."""
        if session is None or not any(ch.isdigit() for ch in user_id):
            return None
        try:
            user = await self._identity.get_user_by_phone(session, user_id)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.warning("chat: user lookup unavailable (%s); continuing.", exc)
            return None
        return user.name if user is not None else None

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
    def _retrieval_query(
        question: str, transits: dict, chart: dict | None = None
    ) -> str:
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
            chovva = doshas.get("chovva_dosha", {})
            if chovva.get("effective", chovva.get("present")):
                cues.append("chovva dosha mangal")
            if doshas.get("kala_sarpa_dosha", {}).get("present"):
                cues.append("kala sarpa dosha")

        return " ".join([question, *cues]).strip()

    async def get_chat_users(self, session: AsyncSession) -> list[dict]:
        """Fetch all unique users who have chat history, with turn counts and last active times.

        Admin Dashboard use case. Returns empty on error.
        """
        from sqlalchemy import func, select

        from app.modules.chat.models import ChatTurn

        try:
            rows = (
                await session.execute(
                    select(
                        ChatTurn.user_id,
                        func.count().label("turns"),
                        func.max(ChatTurn.created_at).label("last_active"),
                    )
                    .group_by(ChatTurn.user_id)
                    .order_by(func.max(ChatTurn.created_at).desc())
                )
            ).all()
            return [
                {"phone": uid, "turns": turns, "last_active": last_active}
                for uid, turns, last_active in rows
            ]
        except Exception as exc:
            logger.warning("chat.service: get_chat_users failed (%s)", exc)
            return []

    async def get_user_chat_history(
        self, session: AsyncSession, phone: str, limit: int = 100
    ) -> list[dict]:
        """Fetch raw chat history for a specific user.

        Admin Dashboard / CRM use case. Returns empty on error.
        """
        from app.modules.chat import history

        return await history.get_history(session, phone, limit=limit)
