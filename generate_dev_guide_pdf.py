"""Generate Tara_Developer_Guide.pdf  -  an as-built explainer of how the codebase
actually works today (not the original aspirational plan). Run once:

    .venv/Scripts/python generate_dev_guide_pdf.py

Outputs Tara_Developer_Guide.pdf in the project root.
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ACCENT = (196, 90, 59)     # terracotta
DARK = (44, 38, 34)        # sidebar dark
LIGHT = (244, 241, 234)    # cream bg
MUTED = (138, 129, 120)
WHITE = (255, 255, 255)
BLACK = (43, 39, 34)
GREEN = (74, 124, 89)      # "REAL" status
AMBER = (181, 130, 30)     # "PARTIAL" status
RED = (168, 68, 60)        # "STUB / OFF" status


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Tara  |  Developer Guide  -  as-built  |  Page {self.page_no()}", align="C")

    def cover_page(self):
        self.add_page()
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 297, "F")
        self.set_fill_color(*ACCENT)
        self.rect(0, 120, 210, 6, "F")

        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 40)
        self.set_y(58)
        self.cell(0, 20, "TARA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 15)
        self.set_text_color(233, 226, 214)
        self.cell(0, 10, "Malayalam-first AI Astrology Companion", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(28)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "Developer Guide  -  What Actually Works", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(4)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(190, 180, 168)
        self.cell(0, 7, "An as-built walkthrough of the running system, module by module,", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 7, "with the astrology domain knowledge and where it lives in the code.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(210)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(163, 153, 140)
        self.cell(0, 8, "Real (live in current .env):", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "Swiss Ephemeris  |  Sarvam-105B  |  MongoDB  |  Hybrid RAG (BM25)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(260)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "Generated from the current codebase, not the original design spec.", align="C")

    def section_title(self, text: str):
        self.ln(6)
        self.set_fill_color(*ACCENT)
        self.rect(self.l_margin, self.get_y(), 4, 8, "F")
        self.set_x(self.l_margin + 7)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*DARK)
        self.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def sub_title(self, text: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ACCENT)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body(self, text: str, indent: int = 0):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 4):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 6, f"  -  {text}")

    def step_box(self, num: str, title: str, detail: str):
        y = self.get_y()
        self.set_fill_color(*ACCENT)
        self.set_draw_color(*ACCENT)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(self.l_margin, y)
        self.cell(8, 8, num, border=0, fill=True, align="C")
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(self.l_margin + 10, y)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 10)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 5, detail)
        self.ln(2)

    def kv_row(self, key: str, value: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ACCENT)
        self.cell(50, 7, key)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*BLACK)
        self.multi_cell(0, 7, value)

    def divider(self):
        self.ln(2)
        self.set_draw_color(*LIGHT)
        self.line(self.l_margin, self.get_y(), 210 - self.r_margin, self.get_y())
        self.ln(3)

    def mono_block(self, lines: list):
        self.set_fill_color(248, 246, 241)
        self.set_draw_color(*LIGHT)
        start_y = self.get_y()
        line_h = 5.5
        total_h = len(lines) * line_h + 6
        self.rect(self.l_margin, start_y, 190 - self.l_margin, total_h, "FD")
        self.set_y(start_y + 3)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(60, 50, 40)
        for line in lines:
            self.set_x(self.l_margin + 4)
            self.cell(0, line_h, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def info_box(self, text: str):
        self.set_fill_color(240, 235, 226)
        self.set_draw_color(*ACCENT)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(80, 60, 40)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, text, border="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def status_row(self, name: str, status: str, color, detail: str):
        y = self.get_y()
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*DARK)
        self.set_xy(self.l_margin, y)
        self.cell(42, 7, name)
        self.set_fill_color(*color)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        self.set_xy(self.l_margin + 42, y)
        self.cell(24, 6, status, align="C", fill=True)
        self.set_xy(self.l_margin + 70, y)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*BLACK)
        self.multi_cell(0, 6, detail)
        self.ln(1.5)


def build() -> None:
    pdf = PDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)

    # ── Cover ──────────────────────────────────────────────────────────────
    pdf.cover_page()

    # ── Page: Reality check ──────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Read this first  -  what's real vs. planned")
    pdf.body(
        "This repo has two layers of documentation. Tara-Project-Documentation.md, AGENTS.md and "
        "GUARDRAILS.md describe the ORIGINAL PLAN (React Native app, Next.js, AWS, Razorpay, OpenAI "
        "gpt-4o-mini, ChromaDB, Redis/Celery for everything). This document instead describes what "
        "is actually built and running in the code today. Where they disagree, trust this document "
        "and the code, not the old plan."
    )
    pdf.info_box(
        "Rule of thumb: every external integration in this project is wired behind a MOCK_* flag "
        "in app/platform/config.py. If the flag is True (default), that feature runs on fake/local "
        "data and the app still boots with zero API keys. The project's real .env currently flips "
        "some of these to real integrations - see the table on the next page."
    )

    pdf.section_title("2. Module status at a glance")
    pdf.body("REAL = fully implemented and working.  PARTIAL = infra built, one piece missing.  STUB = TODO placeholder only, no logic.")
    pdf.ln(2)
    modules_status = [
        ("identity", "REAL", GREEN, "Register/login, PBKDF2 passwords, bearer sessions, birth-data capture, real geocoding, chart persistence."),
        ("astrology_engine", "REAL", GREEN, "Real Swiss Ephemeris (pyswisseph) sidereal engine: natal chart, dasha, doshas, transits, panchangam, prashnam."),
        ("knowledge (RAG)", "REAL", GREEN, "Hybrid BM25 + Chroma retrieval over 2,450+ chunks. BM25 is live now; the Chroma/dense half is code-complete but dormant (MOCK_CHROMA still true)."),
        ("tone_safety", "REAL*", AMBER, "Persona prompt + reply-screen guardrails are real and enforced. The crisis classifier is an explicit keyword-only placeholder, not clinically reviewed."),
        ("chat", "REAL", GREEN, "Full orchestrator wiring every module together; real Sarvam/OpenAI calls; Mongo-backed history + memory."),
        ("temples", "REAL", GREEN, "53 curated temples + deterministic concern/dosha/graha -> deity/temple lookup tables."),
        ("content", "REAL (narrow)", AMBER, "Only the daily WhatsApp-style Malayalam message generator exists. No weekly content module."),
        ("whatsapp", "PARTIAL", AMBER, "Real consent ledger, opt-out, 3/day throttle, and the daily pipeline exist - but the actual BSP send call is NotImplementedError (currently just logs)."),
        ("commerce", "STUB", RED, "Router/service/models are empty TODO placeholders. No subscriptions, no Razorpay, nothing implemented."),
        ("community", "STUB", RED, "Empty TODO placeholders. No audio rooms, no moderation."),
        ("notifications", "STUB", RED, "Empty TODO placeholders. No push/email dispatch."),
        ("admin", "STUB", RED, "Empty TODO placeholders. No dashboards, no moderation queue."),
        ("event bus (platform)", "UNUSED", RED, "EventBus class exists but nothing in the codebase calls .on()/.emit(). Modules call each other's services directly instead."),
        ("Celery + worker.py", "PARTIAL", AMBER, "Real infra, but only ONE task is registered: the WhatsApp daily message job (05:30 IST). Chat's memory/history save use FastAPI BackgroundTasks, not Celery."),
    ]
    for name, status, color, detail in modules_status:
        pdf.status_row(name, status, color, detail)

    # ── Page: current .env reality ──────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3. What's actually switched on right now")
    pdf.body(
        "Every integration below is controlled by a MOCK_* setting in app/platform/config.py, "
        "overridable per-environment in .env. This is the state of the project's own .env file "
        "(not .env.example) at time of writing:"
    )
    pdf.ln(2)
    env_rows = [
        ("MOCK_EPHEMERIS = false", "Real astronomy. Charts come from pyswisseph (Swiss Ephemeris), not fantasy data."),
        ("MOCK_GEOCODING = false", "Real place -> lat/lng/timezone via Google Geocoding, else Open-Meteo, else Nominatim."),
        ("MOCK_OPENAI = false", "Real LLM calls happen (see chat_provider below - this flag gates both OpenAI and Sarvam)."),
        ("CHAT_PROVIDER = sarvam", "Chat replies are generated by Sarvam AI's sarvam-105b model, not OpenAI, by default."),
        ("MOCK_MONGO = false", "Chat history and durable user memory are really persisted to MongoDB."),
        ("MOCK_CHROMA = true (default, unchanged)", "The vector/dense half of knowledge retrieval is OFF. Only BM25 keyword search is active."),
        ("MOCK_WHATSAPP = true (default, unchanged)", "Daily messages are composed but only logged, never actually sent to a BSP."),
        ("MOCK_RAZORPAY = true (default, unchanged)", "Irrelevant in practice - commerce module has no logic to call it anyway."),
    ]
    for key, detail in env_rows:
        pdf.kv_row(key, detail)
        pdf.divider()

    pdf.section_title("4. Data stores  -  a polyglot split, on purpose")
    pdf.mono_block([
        "  Postgres (prod) / SQLite tara.db (local dev, zero-setup)",
        "     users        - phone (unique key), password_hash, dob, birth_time,",
        "                     birth_place, lat/lng/tz",
        "     sessions     - bearer token, expires_at",
        "     charts       - natal_json (whatever Swiss Ephemeris computed)",
        "     wa_consent, wa_message_log   (whatsapp module)",
        "",
        "  MongoDB  (database: tara)",
        "     chat_history   - per-turn user message + reply, per conversation_id",
        "     user_memory    - one doc per user_id: durable facts, district, summary",
        "",
        "  Flat files (no DB)",
        "     app/modules/knowledge/seed_data.py   - 248 hand-written curated chunks",
        "     app/modules/knowledge/ingested/*.json - ingested classical texts (2,203 chunks)",
        "     app/modules/temples/seed_data.py     - 53 curated temples",
        "",
        "  Chroma vector store  (knowledge_vectordb/, gitignored) - dormant, MOCK_CHROMA=true",
    ])
    pdf.body(
        "Why split Postgres and Mongo? Birth data and auth are structured, relational, and "
        "privacy-sensitive (GUARDRAILS.md #4) - a good fit for Postgres with strict row ownership "
        "checks. Chat turns and durable memory are unstructured, high-volume, and per-user-document "
        "shaped - a good fit for a document store. Neither module reaches into the other's tables; "
        "identity never sees chat_history, and chat never queries the users table directly - it "
        "calls identity.get_chart_by_phone()."
    )

    # ── Page: the chat request flow ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. The core loop  -  what happens on one chat message")
    pdf.body(
        "POST /chat/message is the one endpoint that ties every module together. "
        "ChatService.handle_message() runs these steps, in this exact order, every time:"
    )
    pdf.ln(2)

    pdf.step_box("1", "Crisis screen FIRST (tone_safety.screen)",
                 "Keyword-matches the message against distress phrases (EN / Malayalam / Manglish).\n"
                 "If it fires: return the hardcoded Tele-MANAS 14416 safety reply immediately.\n"
                 "Nothing else below runs - no chart load, no RAG, no LLM call, nothing saved.")
    pdf.step_box("2", "Load chart + live transits",
                 "identity.get_chart_by_phone(user_id) reads the stored natal chart (Postgres).\n"
                 "astrology_engine.get_transits(chart) computes today's planetary positions and\n"
                 "checks Sade Sati against the natal Moon.")
    pdf.step_box("3", "Prashnam (only if the user picked a number/leaf/square in the UI)",
                 "astrology_engine.get_prashnam_reading() computes a horary chart for the exact\n"
                 "moment the question was asked, using the user's stored lat/lng.")
    pdf.step_box("4", "Build a retrieval query from real facts, not raw text",
                 "Combines the user's question with computed facts: retrograde planets, active\n"
                 "Sade Sati, nakshatram, lagna, current mahadasha lord, active doshas.")
    pdf.step_box("5", "RAG retrieval (knowledge.retrieve, k=4)",
                 "Hybrid BM25 + Chroma search over the 2,450+ chunk corpus (see section 7).\n"
                 "Returns the top-4 most relevant interpretation snippets with provenance.")
    pdf.step_box("6", "Pick ONE relevant divisional chart (varga)",
                 "Keyword-matches the message to career/marriage/children/parents/siblings and\n"
                 "grafts only that one D-chart (D10/D9/D7/D12/D3) into context - keeps the prompt\n"
                 "focused instead of dumping all 5 varga charts every time.")
    pdf.step_box("7", "Load durable memory (MongoDB, cross-session)",
                 "user_memory.get_profile() - facts remembered about this person from earlier\n"
                 "conversations (job, family, concerns already discussed), capped at 8 injected facts.")
    pdf.step_box("8", "Temple / remedy suggestion (at most ONE, on purpose)",
                 "If the user asks for a remedy, or a traditional concern+dosha pairing applies\n"
                 "(e.g. marriage question + Chovva dosha), temples.suggest() proposes exactly one\n"
                 "temple - deliberately capped so the LLM narrates one clear suggestion, not a list.")
    pdf.step_box("9", "Build the system prompt (tone_safety.build_system_prompt)",
                 "String-templates: Tara persona + Malayalam terminology glossary + chart summary +\n"
                 "transits + retrieved knowledge + memory + temple note, all in one system message.")
    pdf.step_box("10", "Call the LLM (llm_client.complete)",
                 "Tries Sarvam sarvam-105b first (configured default), falls back to OpenAI, falls\n"
                 "back to a hardcoded mock reply if neither has a working API key.")
    pdf.step_box("11", "Screen the OUTPUT before sending it back (tone_safety.screen_reply)",
                 "Regex-checks for fear language, payment-linked remedies, manufactured urgency.\n"
                 "If violated: retry once with a corrective note; if still violated, serve a hardcoded\n"
                 "safe fallback reply instead of the model's output.")
    pdf.step_box("12", "Respond + save in the background",
                 "Returns {reply, is_safety_response, grounded_in: [...]}. grounded_in is a real\n"
                 "audit trail (e.g. chart, transits, knowledge:planet-in-house-saturn-10, varga:D9).\n"
                 "history.save_turn + memory.extract_memory run as background tasks - never on the\n"
                 "crisis path, so distress conversations are never persisted.")

    # ── Page: Astrology engine domain knowledge ─────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Domain knowledge #1  -  the astrology engine")
    pdf.body(
        "This is real Vedic sidereal astronomy, computed at request time, not looked up from a "
        "table and not invented by the LLM. It lives in app/modules/astrology_engine/."
    )
    pdf.sub_title("6.1  Chart math (swiss_ephemeris.py)")
    for item in [
        "Uses the pyswisseph library (Moshier analytical ephemeris) - no external API, no data files.",
        "Sidereal zodiac, not tropical - ayanamsa is configurable: Lahiri (default, Indian govt standard), KP/Krishnamurti, or Raman.",
        "Whole-sign houses: the lagna's own rasi is house 1; each following rasi is house 2, 3... 12 in order.",
        "Computes Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu (mean node) and Ketu (Rahu+180 deg); retrograde = negative ephemeris speed.",
        "5 divisional charts (vargas) derived from the D1 longitude: D9 navamsa (marriage), D10 dashamsa (career), D7 saptamsa (children), D3 drekkana (siblings), D12 dwadasamsa (parents).",
    ]:
        pdf.bullet(item)
    pdf.ln(2)

    pdf.sub_title("6.2  Vimshottari dasha (vimshottari.py)")
    pdf.body(
        "The classical 120-year, 9-planet-lord cycle (Ketu 7y, Venus 20y, Sun 6y, Moon 10y, "
        "Mars 7y, Rahu 18y, Jupiter 16y, Saturn 19y, Mercury 17y). Genuinely derived from the "
        "Moon's exact sidereal position at birth - which nakshatra it sits in picks the starting "
        "lord, and how far through that nakshatra it has traveled gives the exact fraction of that "
        "lord's period already elapsed. Produces a full mahadasha/antardasha timeline with real "
        "calendar dates, plus 'what period is running right now.'",
        indent=2,
    )

    pdf.sub_title("6.3  Doshas (doshas.py)  -  deterministic rule checks, never LLM-guessed")
    for item in [
        "Chovva / Mangal dosha: Mars sitting in houses 1, 2, 4, 7, 8, or 12 - checked from both the lagna and the Moon (the Kerala convention).",
        "Kala Sarpa dosha: all seven classical grahas confined to one arc between Rahu and Ketu.",
        "Sade Sati: a live transit check (not natal) - is transiting Saturn in the 12th, 1st, or 2nd house from the natal Moon right now, and which phase.",
    ]:
        pdf.bullet(item)
    pdf.ln(2)

    pdf.sub_title("6.4  Panchangam & transits")
    pdf.body(
        "Daily panchangam computes nakshatram + tithi at local noon. One honest gap: nalla_neram "
        "(the auspicious time window) is a hardcoded fixed string, not computed per day/location - "
        "a real implementation needs sunrise time, which isn't wired in yet. Transits add "
        "house_from_moon (the traditional Vedic transit frame, counted from the natal Moon) on top "
        "of raw current planetary positions.",
        indent=2,
    )

    # ── Page: Prashnam + Temples ─────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Domain knowledge #2  -  prashnam & temple remedies")
    pdf.sub_title("7.1  Prashnam (Kerala horary astrology)  -  prashnam.py")
    pdf.body(
        "Three interactive modes, each a deterministic rule engine over a chart cast for the exact "
        "moment the question is asked (not the person's birth chart):"
    )
    for item in [
        "Thamboola (betel-leaf count): odd/even parity + remainder mod 8, combined with the Moon's house from the ascendant.",
        "Swarna (touching one of 12 unlabeled squares): classified by that square's house relationship to the rising sign - kendra/trikona/dusthana/upachaya/sama.",
        "Sankhya (picking a number 1-108): maps deterministically to 1 of 12 rasis and 1 of 27 nakshatra-padas, KP-horary style.",
    ]:
        pdf.bullet(item)
    pdf.info_box(
        "Thamboola is explicitly documented in the code (and in NEEDS_ASTROLOGER.md) as a "
        "'simplified draft,' not a claim to replicate an in-person ashtamangala prashnam by a "
        "trained Daivajna. This honesty caveat is injected straight into the chat prompt so Tara "
        "never overstates what a text-based prashnam can really tell someone."
    )

    pdf.sub_title("7.2  Temples & remedies  -  temples/remedy_map.py + seed_data.py")
    pdf.body(
        "53 curated Kerala temples (coordinates Google-Places-verified) with deity, district, "
        "vazhipadu (offering) options. remedy_map.py is a set of plain Python lookup dicts - no ML:"
    )
    for item in [
        "CONCERN_DEITIES  -  9 life-concern keys (career, marriage, children, health, ...) -> ordered deity list.",
        "CONCERN_KEYWORDS  -  free-text (English/Malayalam/Manglish) -> concern key.",
        "GRAHA_DEITIES  -  each of the 9 planets -> its Kerala remedial deity (e.g. Saturn -> Sastha/Shiva/Hanuman).",
        "DOSHA_DEITIES  -  chovva_dosha -> Subrahmanya/Devi; kala_sarpa_dosha -> Naga; sade_sati -> Sastha/Hanuman/Shiva.",
    ]:
        pdf.bullet(item)
    pdf.body(
        "TemplesService.suggest() combines concern + doshas + the current mahadasha lord into one "
        "ordered, de-duplicated deity list, then picks the nearest matching temple by real "
        "haversine great-circle distance if the user's location is known. Deliberately returns at "
        "most one temple per chat turn - the comment in the code literally says the LLM 'narrates "
        "everything it is given,' so the cap prevents an overwhelming list.",
        indent=2,
    )

    # ── Page: Knowledge corpus / RAG ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Domain knowledge #3  -  the knowledge corpus & RAG pipeline")
    pdf.body(
        "This is where astrology text knowledge (as opposed to computed chart facts) is stored "
        "and retrieved. Two layers, both plain files - no database table."
    )
    pdf.ln(2)
    pdf.sub_title("8.1  Two-layer corpus (app/modules/knowledge/)")
    pdf.kv_row("Curated (seed_data.py)", "248 hand-composed chunks: 108 planet-in-house, 37 prashnam, 30 vazhipadu, 28 nakshatra profiles, 15 deity profiles, 12 lagna, 9 dasha-lord, 3 dosha, plus a few one-offs. Every chunk marked reviewed: False (see NEEDS_ASTROLOGER.md).")
    pdf.divider()
    pdf.kv_row("Ingested (ingested/*.json)", "Produced offline by ingest.py from real public-domain texts: Brihat Jataka of Varahamihira (1885 translation, 1,231 chunks) and Brihat Samhita (972 chunks) - 2,203 chunks, far outnumbering the curated set.")
    pdf.divider()

    pdf.sub_title("8.2  Ingestion pipeline (ingest.py, run offline as a CLI)")
    pdf.mono_block([
        "  python -m app.modules.knowledge.ingest <file> --topic ... --source ...",
        "     |",
        "  Extract text (PDF via pypdf, or plain text/markdown)",
        "     |",
        "  chunk_text(): split at sentence boundaries (~600 chars, 1-sentence overlap),",
        "                Malayalam/Devanagari-aware regex, drop fragments <80 chars",
        "     |",
        "  Write ingested/<slug>.json, every chunk tagged reviewed: False + source",
    ])

    pdf.sub_title("8.3  Retrieval  -  HybridRetriever (retrieval.py)")
    for item in [
        "Sparse (BM25, always on, no API key): rank_bm25.BM25Okapi with a Unicode-aware tokenizer that explicitly includes the Malayalam block (U+0D00-U+0D7F), because Python's default word-regex strips Malayalam vowel signs.",
        "Dense (Chroma, currently dormant - MOCK_CHROMA=true): OpenAI text-embedding-ada-002 vectors persisted to a local Chroma store; code-complete, just switched off in this environment.",
        "Merge: score = 0.5*dense + 0.5*sparse when both ran, else sparse alone.",
        "Import penalty (0.7x): any unreviewed ingested chunk gets its score multiplied by 0.7, so a curated, reviewed chunk always wins a tie against a classical-text import.",
        "Import cap: unreviewed imported chunks can never fill more than half of the returned top-k slots, so the 2,203 ingested chunks can't drown out the 248 curated ones.",
        "No cross-encoder reranking yet - noted in code as an easy later addition.",
    ]:
        pdf.bullet(item)

    # ── Page: Tone & safety ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. The persona & safety layer  -  tone_safety module")
    pdf.body(
        "Everything that shapes HOW Tara talks (and when it must refuse to talk astrology at all) "
        "lives here. It has no HTTP endpoints of its own - it's a library consumed by chat."
    )
    pdf.sub_title("9.1  Persona prompt (persona.py)")
    pdf.body(
        "A hardcoded system prompt built from five fixed rules: disclose it's an AI astrologer; "
        "acknowledge feelings before the chart; tie every claim to a real placement/transit, never "
        "invent a dosha; frame challenges with agency ('the stars incline, they do not compel'); "
        "know its limits and hand off to a human/helpline for real distress. It also carries a "
        "hardcoded English-to-Malayalam-script glossary for every planet/term (so the model writes "
        "the Malayalam word for Sun, not 'surya'), and mandates the reply end with exactly one caring "
        "follow-up question. build_system_prompt() is literally string concatenation - no separate "
        "prompt-management framework.",
        indent=2,
    )
    pdf.sub_title("9.2  Crisis classifier (crisis_classifier.py)  -  READ THIS")
    pdf.info_box(
        "The file itself is commented 'PLACEHOLDER HEURISTIC - NOT PRODUCTION-READY.' It is a "
        "pure keyword/substring match across English, Malayalam script, and romanized Manglish "
        "distress phrases - not a trained classifier. It deliberately does NOT flag bare words like "
        "'death' or 'die' since those come up innocuously in astrology (8th house, longevity). The "
        "ROUTING (screen first, hard stop on hit, never bypassed) is solid, real infrastructure - "
        "it's the DETECTION QUALITY that needs a clinically-reviewed upgrade before real users rely "
        "on it. Flagged in NEEDS_ASTROLOGER.md."
    )
    pdf.sub_title("9.3  Output guardrail (reply_screen.py)  -  checks the LLM's reply, after the fact")
    for item in [
        "Fear: regex for asserted doom/curses ('a great danger awaits', 'cursed', 'doomed') in Malayalam and English.",
        "Payment-linked remedy: a remedy word (pooja/vazhipadu/homam/yantra/mantra) within ~60 characters of a payment cue (Rs / fee / pay).",
        "Manufactured urgency: 'act now or...', 'last chance', 'if you don't do X immediately...'.",
    ]:
        pdf.bullet(item)
    pdf.body(
        "If any category fires, chat retries once with a corrective note appended; if it still "
        "fires, the user gets a hardcoded safe fallback reply instead of the model's actual output.",
        indent=2,
    )

    # ── Page: LLM providers + evals ──────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("10. LLM providers  -  why Sarvam, not just OpenAI")
    pdf.body(
        "llm_client.py talks to both providers through one OpenAI-compatible AsyncOpenAI client "
        "(Sarvam just uses a different base_url) and resolves which one to use per request:"
    )
    pdf.mono_block([
        "  requested provider (or configured default CHAT_PROVIDER=sarvam)",
        "       |  has an API key configured?",
        "       v  no -> try next",
        "  sarvam (sarvam-105b)  -->  openai (gpt-4o-mini)  -->  hardcoded mock reply",
        "",
        "  Sarvam-specific tuning: reasoning_effort='low' + max_tokens=2048 (vs 1024 for OpenAI).",
        "  Reason: Sarvam models 'think' before answering by default, and that reasoning eats into",
        "  the completion token budget - observed to truncate long Malayalam replies in evals",
        "  without this tuning.",
    ])

    pdf.section_title("11. Evals  -  this has actually been measured, not just claimed")
    pdf.body(
        "evals/golden_set.py defines 25 fixed test conversations (everyday questions, 2 crisis "
        "cases, temple/remedy asks, all 3 prashnam modes, adversarial guardrail probes). "
        "evals/run.py calls ChatService.handle_message() directly and grades each reply with "
        "deterministic checks (crisis routing correct, no leaked astrology terms in a crisis reply, "
        "reply not truncated, no foreign-script glyphs, at most 1 temple mentioned, ends with a "
        "question) plus an optional LLM judge that scores Malayalam fluency 1-5. Real saved results:"
    )
    pdf.ln(2)
    eval_rows = [
        ("sarvam-105b", "23 / 25 passed", "avg fluency 4.79 / 5"),
        ("openai (gpt-4o-mini)", "24 / 25 passed", "avg fluency 3.00 / 5"),
        ("sarvam-fast (sarvam-30b)", "6 / 25 passed", "avg fluency 3.48 / 5  -  known regression: truncates replies, drops the mandated closing question much more often"),
    ]
    for model, passed, fluency in eval_rows:
        pdf.kv_row(model, f"{passed}  -  {fluency}")
        pdf.divider()
    pdf.body(
        "This is why sarvam-105b (not sarvam-fast, not gpt-4o-mini) is the configured default: it "
        "is both the most fluent in Malayalam AND passes the most guardrail checks.",
        indent=0,
    )

    # ── Page: security + auth ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("12. Auth & identity  -  how a user is recognized")
    for item in [
        "A user's identity key is their normalized mobile number (IdentityService.normalize_phone) - not a UUID. Everything (chat_history, user_memory, charts, sessions) is keyed off this phone.",
        "Passwords: PBKDF2-HMAC-SHA256, 200,000 rounds, unique salt per user, constant-time comparison. Real, not a toy hash.",
        "Sessions: plain bearer tokens (secrets.token_urlsafe(32)) stored server-side in a sessions table with expires_at, default TTL 47 hours. Not JWT - a stateful token the server can revoke by deleting the row.",
        "Ownership is checked everywhere: every route compares the token's user.id against the requested user_id and 403s on mismatch - a user can never read another user's chart, chat history, or memory.",
        "Onboarding (POST /identity/users) does register + geocode + compute the first natal chart + auto-login in one round trip, so a new user is chat-ready immediately.",
        "On every login, if the stored chart still looks like a mock/pending placeholder (from before MOCK_EPHEMERIS was flipped off), it's silently recomputed for real - a self-healing migration, not a one-time script.",
    ]:
        pdf.bullet(item)

    pdf.section_title("13. Running it locally")
    pdf.mono_block([
        "  python -m venv .venv && .venv\\Scripts\\activate",
        "  pip install -e \".[dev]\"       (or: pip install -r requirements.txt)",
        "  cp .env.example .env            # fill in real keys only for what you want live",
        "  python main.py                  # or: uvicorn app.main:app --reload --port 3000",
        "",
        "  Website chat UI  ->  http://localhost:3000/",
        "  WhatsApp-style demo skin (same brain, different CSS) -> http://localhost:3000/wa",
        "  API docs (Swagger) -> http://localhost:3000/docs",
        "",
        "  With every MOCK_* flag left at its default True, the whole app boots and answers chat",
        "  messages with ZERO external API keys - useful for UI/dev work without burning credits.",
    ])

    # ── Page: gaps + where to look ────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("14. Known gaps  -  read before promising a feature")
    for item in [
        "Crisis classifier is keyword-only (section 9.2) - needs a clinically-reviewed upgrade before real users in real distress rely on it.",
        "WhatsApp sending is not implemented - _send_via_bsp() raises NotImplementedError; only the consent/throttle/pipeline scaffolding around it is real.",
        "commerce, community, notifications, admin are empty TODO stubs - no subscriptions, no payments, no audio rooms, no push notifications, no admin dashboard exist yet.",
        "The event bus (platform/events.py) is defined but never called anywhere - modules currently just import each other's services directly instead.",
        "Celery has exactly one real job (the WhatsApp daily message) - it is not yet the general task queue for the rest of the app.",
        "The dense/Chroma half of knowledge retrieval is code-complete but switched off (MOCK_CHROMA=true) - only BM25 keyword search is live right now.",
        "panchangam's nalla_neram (auspicious time window) is a hardcoded fixed string, not computed per day/location.",
        "None of the astrology content (248 curated chunks, 53 temples' devotional details, remedy_map's deity tables, the thamboola prashnam scheme) has been reviewed by a qualified astrologer yet - every chunk carries reviewed: False. See NEEDS_ASTROLOGER.md at the repo root for the living punch-list.",
    ]:
        pdf.bullet(item)

    pdf.section_title("15. Where things live  -  quick file map")
    pdf.mono_block([
        "  app/main.py                      FastAPI app, wires every module's router",
        "  app/platform/config.py           ALL settings + every MOCK_* flag (read this first)",
        "  app/platform/db.py               Postgres/SQLite engine (users/sessions/charts)",
        "  app/platform/mongo.py            MongoDB client (chat_history/user_memory)",
        "",
        "  app/modules/identity/            auth, birth data, geocoding, chart storage",
        "  app/modules/astrology_engine/    Swiss Ephemeris chart math, dasha, doshas, prashnam",
        "  app/modules/knowledge/           RAG corpus + hybrid BM25/Chroma retrieval",
        "  app/modules/tone_safety/         persona prompt, crisis screen, output guardrail",
        "  app/modules/chat/                the orchestrator - ties everything together",
        "  app/modules/temples/             53 temples + remedy/deity lookup tables",
        "  app/modules/content/             daily Malayalam message generator",
        "  app/modules/whatsapp/            consent ledger + daily pipeline (send = TODO)",
        "  app/modules/commerce, community,",
        "  notifications, admin/            empty stubs, not yet built",
        "",
        "  evals/                           25-case golden set + automated grading harness",
        "  NEEDS_ASTROLOGER.md              living punch-list of unreviewed domain content",
        "  AGENTS.md / GUARDRAILS.md        the ORIGINAL rules/plan - still the source of truth",
        "                                   for non-negotiables (no fear-mongering, crisis-first,",
        "                                   WhatsApp compliance, birth-data privacy, secrets)",
    ])
    pdf.info_box(
        "Bottom line: the ethical guardrails and module boundaries from the original plan are "
        "still binding rules. What changed since that plan was written is the concrete stack - "
        "Sarvam instead of only OpenAI, self-computed Swiss Ephemeris instead of a hosted API, "
        "Postgres+MongoDB instead of Postgres-only, and a real hybrid RAG pipeline over 2,450+ "
        "chunks instead of a placeholder ChromaDB collection."
    )

    pdf.output("Tara_Developer_Guide.pdf")
    print("Wrote Tara_Developer_Guide.pdf")


if __name__ == "__main__":
    build()
