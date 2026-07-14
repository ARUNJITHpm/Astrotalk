"""Generate Tara_Developer_Guide.pdf  -  an as-built explainer of how the codebase
actually works today (not the original aspirational plan). Run once:

    vinimon/Scripts/python generate_dev_guide_pdf.py

Outputs Tara_Developer_Guide.pdf in the project root.

NOTE: core PDF fonts are latin-1 only, so Malayalam script cannot appear here;
Malayalam terms are shown transliterated.
"""

import math

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
GRAY = (120, 112, 104)


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
        self.cell(0, 7, "An as-built walkthrough: every module, every data store, every LLM call,", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 7, "the RAG document pipeline, Malayalam handling, and flowcharts of the core paths.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(210)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(163, 153, 140)
        self.cell(0, 8, "Real (live in current .env):", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "Swiss Ephemeris  |  Sarvam-105B  |  MongoDB  |  Hybrid RAG (BM25)  |  Porutham", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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
        self.cell(10, 8, num, border=0, fill=True, align="C")
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(self.l_margin + 12, y)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 5, detail)
        self.ln(2)

    def kv_row(self, key: str, value: str, key_w: int = 50):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ACCENT)
        self.cell(key_w, 7, key)
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

    # ---- flowchart primitives (absolute positioning) --------------------

    _NODE_STYLES = {
        # kind: (fill, border, text)
        "dark":   (DARK, DARK, WHITE),
        "step":   (WHITE, (180, 170, 160), DARK),
        "engine": (LIGHT, (200, 190, 178), DARK),
        "llm":    (ACCENT, ACCENT, WHITE),
        "warn":   ((248, 236, 214), AMBER, (110, 80, 20)),
        "danger": ((246, 226, 223), RED, (130, 45, 40)),
        "bg":     ((236, 233, 228), (170, 162, 154), GRAY),
        "green":  ((228, 238, 230), GREEN, (40, 85, 55)),
    }

    def flow_node(self, x, y, w, lines, kind="step", lh=3.6):
        fill, border, text = self._NODE_STYLES[kind]
        h = len(lines) * lh + 3.0
        self.set_fill_color(*fill)
        self.set_draw_color(*border)
        self.set_line_width(0.35)
        self.rect(x, y, w, h, "FD")
        self.set_text_color(*text)
        for i, line in enumerate(lines):
            size = 7.6
            self.set_font("Helvetica", "B" if i == 0 else "", size)
            # shrink to fit the box width so no line ever overflows its node
            while size > 5.4 and self.get_string_width(line) > w - 3:
                size -= 0.2
                self.set_font_size(size)
            self.set_xy(x + 1.5, y + 1.5 + i * lh)
            self.cell(w - 3, lh, line, align="C")
        return h

    def flow_arrow(self, x1, y1, x2, y2, label=None):
        self.set_draw_color(*GRAY)
        self.set_line_width(0.35)
        self.line(x1, y1, x2, y2)
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (math.radians(152), math.radians(-152)):
            self.line(x2, y2, x2 + 2.1 * math.cos(ang + da), y2 + 2.1 * math.sin(ang + da))
        if label:
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*GRAY)
            self.set_xy(min(x1, x2) + abs(x2 - x1) / 2 + 1.2, min(y1, y2) + abs(y2 - y1) / 2 - 3.2)
            self.cell(20, 3, label)


def chat_flowchart(pdf: PDF) -> None:
    """Full-page flowchart: one POST /chat/message from arrival to background save."""
    pdf.add_page()
    pdf.set_auto_page_break(False)
    pdf.section_title("5. Flowchart  -  one chat message, end to end")
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 4.5,
                   "Everything below happens inside ChatService.handle_message() (app/modules/chat/service.py), "
                   "in this exact order. Orange = LLM call. Cream = deterministic engine (no LLM). Red = hard stop.")

    spine_x, spine_w = 20, 118
    cx = spine_x + spine_w / 2
    side_x, side_w = 143, 49
    gap = 3.4
    y = pdf.get_y() + 3

    nodes = [
        (["POST /chat/message", "bearer token -> phone identity; per-user rate limit (429 over budget)"], "dark", None),
        (["1. CRISIS SCREEN  (tone_safety.screen)", "keyword match: English + Malayalam script + Manglish"], "warn",
         (["HIT: canned Tele-MANAS", "14416 reply. STOP.", "No LLM, nothing saved."], "danger")),
        (["2. Load natal chart", "identity.get_chart_by_phone -> Postgres/SQLite charts.natal_json"], "step", None),
        (["2b. Today's transits + Sade Sati check", "astrology_engine.get_transits -> Swiss Ephemeris, computed now"], "engine", None),
        (["2p / 2c. Prashnam or Porutham  (only when this turn carries one)", "horary chart of the moment / ten-porutham grading; deterministic"], "engine", None),
        (["3. Build retrieval query", "question + computed facts: retrogrades, sade sati, nakshatram, lagna, dasha lord, doshas"], "step", None),
        (["3a. knowledge.retrieve(query, k=4)", "BM25 over 2,451 chunks (+Chroma dense when enabled) -> top-4 notes"], "step", None),
        (["3a2. Pick ONE varga by topic keywords", "career->D10, marriage->D9, children->D7, parents->D12, siblings->D3"], "step", None),
        (["3b. Durable memory  (MongoDB user_memory)", "facts remembered across sessions, capped; current district"], "step", None),
        (["3c. Temple suggestion  (temples.suggest, k=1)", "only if remedy asked OR classic concern+dosha pair; max ONE temple"], "engine", None),
        (["4. build_system_prompt  (tone_safety)", "persona rules + Malayalam glossary + chart + transits + notes + memory"], "step", None),
        (["5. LLM CALL #1  -  llm_client.complete()", "sarvam-105b, reasoning_effort=low, max_tokens=4096 (empty reply -> 1 retry, doubled budget)"], "llm", None),
        (["5b. REPLY SCREEN  (tone_safety.screen_reply)", "regex: fear language / payment-linked remedy / manufactured urgency"], "warn",
         (["VIOLATION: LLM CALL #2", "with corrective note;", "still bad -> canned", "safe reply (no 3rd call)"], "warn")),
        (["6. Respond to the user", "{reply, grounded_in[...], provider, tokens, price INR/USD}"], "green", None),
        (["BACKGROUND (after the reply, never on a crisis turn):", "save turn -> Mongo chat_history;  LLM CALL #3 distills durable facts -> user_memory"], "bg", None),
    ]

    for i, (lines, kind, side) in enumerate(nodes):
        h = pdf.flow_node(spine_x, y, spine_w, lines, kind)
        if side is not None:
            s_lines, s_kind = side
            s_h = len(s_lines) * 3.6 + 3.0
            s_y = y + h / 2 - s_h / 2
            pdf.flow_node(side_x, s_y, side_w, s_lines, s_kind)
            pdf.flow_arrow(spine_x + spine_w, y + h / 2, side_x, y + h / 2)
        if i < len(nodes) - 1:
            pdf.flow_arrow(cx, y + h, cx, y + h + gap)
        y += h + gap
    pdf.set_auto_page_break(True, margin=20)


def rag_flowcharts(pdf: PDF) -> None:
    """One page, two flowcharts: how a document gets INTO the corpus, and how a
    query gets chunks OUT of it."""
    pdf.add_page()
    pdf.set_auto_page_break(False)
    pdf.section_title("9. Flowchart  -  a document's journey into RAG, and a query's journey out")

    # --- A: ingestion ---
    pdf.sub_title("A.  Offline: how a document becomes retrievable chunks")
    spine_x, spine_w = 30, 128
    cx = spine_x + spine_w / 2
    gap = 3.2
    y = pdf.get_y() + 1

    ingest_nodes = [
        (["Source document (public-domain PDF / text / markdown)", "e.g. Brihat Jataka 1885 translation, Brihat Samhita"], "dark"),
        (["python -m app.modules.knowledge.ingest <file> --topic ... --source ...", "text extracted via pypdf (PDF) or read directly (txt/md)"], "step"),
        (["chunk_text(): split at sentence boundaries, ~600 chars, 1-sentence overlap", "Malayalam/Devanagari-aware regex; fragments < 80 chars dropped"], "step"),
        (["every chunk tagged: id, topic, source, reviewed: False", "unreviewed = second-class until an astrologer signs off (NEEDS_ASTROLOGER.md)"], "warn"),
        (["written to app/modules/knowledge/ingested/<slug>.json", "brihat-jataka.json (1,231 chunks)  +  brihat-samhita.json (972 chunks)"], "green"),
        (["at app startup: load_corpus() = 248 curated seed chunks + 2,203 ingested", "BM25 index built in RAM; Chroma embeddings only if dense is enabled"], "engine"),
    ]
    for i, (lines, kind) in enumerate(ingest_nodes):
        h = pdf.flow_node(spine_x, y, spine_w, lines, kind)
        if i < len(ingest_nodes) - 1:
            pdf.flow_arrow(cx, y + h, cx, y + h + gap)
        y += h + gap

    # --- B: retrieval ---
    pdf.set_y(y + 5)
    pdf.sub_title("B.  Per message: how the top-4 chunks are chosen (HybridRetriever.search)")
    y = pdf.get_y() + 1

    q_h = pdf.flow_node(spine_x, y, spine_w, [
        "query = user question + computed chart facts",
        "(nakshatram, lagna, dasha lord, doshas, retrogrades, sade sati)"], "dark")
    # parallel split
    par_y = y + q_h + 6
    left_x, left_w = 20, 76
    right_x, right_w = 100, 76
    lh_ = pdf.flow_node(left_x, par_y, left_w, [
        "SPARSE: BM25Okapi  (always on)",
        "Unicode tokenizer incl. Malayalam block", "U+0D00-0D7F; English stopwords dropped;", "scores normalized to [0,1]"], "engine")
    rh_ = pdf.flow_node(right_x, par_y, right_w, [
        "DENSE: Chroma + OpenAI embeddings",
        "(currently DORMANT: MOCK_CHROMA=true)", "persistent store knowledge_vectordb/,", "relevance scores in [0,1]"], "bg")
    pdf.flow_arrow(cx, y + q_h, left_x + left_w / 2, par_y)
    pdf.flow_arrow(cx, y + q_h, right_x + right_w / 2, par_y)

    merge_y = par_y + max(lh_, rh_) + 6
    m_h = pdf.flow_node(spine_x, merge_y, spine_w, [
        "merge: score = 0.5 x dense + 0.5 x sparse   (sparse alone when dense is off)"], "step")
    pdf.flow_arrow(left_x + left_w / 2, par_y + lh_, cx - 14, merge_y)
    pdf.flow_arrow(right_x + right_w / 2, par_y + rh_, cx + 14, merge_y)

    y = merge_y + m_h + 3.2
    tail = [
        (["IMPORT PENALTY: unreviewed ingested chunks get score x 0.7", "a curated, hand-written chunk always beats an import saying the same thing"], "warn"),
        (["IMPORT CAP: unreviewed imports fill at most HALF the k slots", "2,203 classical-text chunks can never crowd out the 248 curated ones"], "warn"),
        (["top-4 chunks -> 'Relevant interpretation notes' in the system prompt", "each hit is audited in the response: grounded_in: [knowledge:<chunk-id>, ...]"], "green"),
    ]
    pdf.flow_arrow(cx, merge_y + m_h, cx, y)
    for i, (lines, kind) in enumerate(tail):
        h = pdf.flow_node(spine_x, y, spine_w, lines, kind)
        if i < len(tail) - 1:
            pdf.flow_arrow(cx, y + h, cx, y + h + 3.2)
        y += h + 3.2
    pdf.set_auto_page_break(True, margin=20)


def build() -> None:
    pdf = PDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)

    # == Cover ==============================================================
    pdf.cover_page()

    # == 1-2: reality check + module status =================================
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
        "some of these to real integrations - see section 3."
    )

    pdf.section_title("2. Module status at a glance")
    pdf.body("REAL = fully implemented and working.  PARTIAL = infra built, one piece missing.  STUB = TODO placeholder only, no logic.")
    pdf.ln(2)
    modules_status = [
        ("identity", "REAL", GREEN, "Register/login, PBKDF2 passwords, bearer sessions, birth-data capture, real geocoding, chart persistence - plus the referral loop (per-user code, activation tracking, reward grant)."),
        ("astrology_engine", "REAL", GREEN, "Real Swiss Ephemeris sidereal engine: natal chart, vargas, dasha, doshas, transits, panchangam, prashnam, and the ten-porutham marriage matching (porutham.py)."),
        ("knowledge (RAG)", "REAL", GREEN, "Hybrid BM25 + Chroma retrieval over 2,451 chunks (248 curated + 2,203 ingested). BM25 is live now; the Chroma/dense half is code-complete but dormant (MOCK_CHROMA=true)."),
        ("tone_safety", "REAL*", AMBER, "Persona prompt + reply-screen guardrails are real and enforced. The crisis classifier is an explicit keyword-only placeholder, not clinically reviewed."),
        ("chat", "REAL", GREEN, "The orchestrator wiring every module together; real Sarvam/OpenAI calls; Mongo-backed history + memory; per-user rate limit; token/price accounting per reply."),
        ("temples", "REAL", GREEN, "53 curated temples + concern/dosha/graha -> deity/temple lookup, PLUS the Part-3 partner layer: register a temple, festival calendar, WhatsApp-opt-in microsite, QR poster (PNG), embeddable widget."),
        ("content", "REAL", GREEN, "Daily Malayalam message generator + the Content Studio: LLM-drafted reel scripts, weekly astro-news, festival specials, nakshatra episodes and myth-busters, each tone-screened, with an approve -> publish workflow feeding the user feed."),
        ("community", "REAL", GREEN, "The user feed: today's panchangam + published posts, emoji reactions (toggle), daily check-in streaks, and live polls with vote tallies. Optional-auth (richer when logged in)."),
        ("commerce", "REAL (mock)", AMBER, "Orders, entitlements and a generated premium jathakam PDF report (Pillow) are live in MOCK mode: create_order -> mock-pay -> entitlement -> download. Real Razorpay capture is code-complete but gated OFF (MOCK_RAZORPAY=true) pending human approval."),
        ("notifications", "REAL (narrow)", AMBER, "run_festivals(): on a partner temple's festival day it queues a Malayalam WhatsApp nudge to that temple's opt-in subscribers (idempotent). Dispatch rides the whatsapp module, so real sends wait on the BSP call."),
        ("admin / console", "REAL", GREEN, "Read-only analytics at /admin PLUS the owner Console at /console (email login): daily content, studio, polls, cards, panchangam, temple partners, notifications, referral funnel and the commerce panel - every growth feature in one place."),
        ("astrologers", "REAL", GREEN, "Human-astrologer marketplace: profiles, availability, booking + cancel. A path to blend AI answers with real consultations."),
        ("orgs (B2B)", "REAL", GREEN, "Multi-tenant workspace for astrologer businesses: public handle page, booking, billing/subscribe, and a CRM (customers, per-customer charts, bookings, notes, transcript)."),
        ("whatsapp", "PARTIAL", AMBER, "Real consent ledger, opt-out, 3/day throttle, and the daily pipeline exist - but the actual BSP send call is NotImplementedError (currently just logs)."),
        ("event bus", "UNUSED", RED, "EventBus class exists but nothing calls .on()/.emit(). Modules call each other's public services directly instead."),
        ("Celery + worker.py", "PARTIAL", AMBER, "Real infra, but only ONE task registered: the WhatsApp daily message job (05:30 IST). Chat's history/memory saves use FastAPI BackgroundTasks, not Celery."),
    ]
    for name, status, color, detail in modules_status:
        pdf.status_row(name, status, color, detail)

    # == 3: env reality ======================================================
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
        ("MOCK_OPENAI = false", "Real LLM calls happen (this flag gates BOTH OpenAI and Sarvam; env var MOCK_LLM can force-override it)."),
        ("CHAT_PROVIDER = sarvam", "Chat replies come from Sarvam AI's sarvam-105b by default. The UI may request a provider per message; a provider without a key falls back: pick -> sarvam -> openai -> mock."),
        ("MOCK_MONGO = false", "Chat history and durable user memory are really persisted to MongoDB (database: tara)."),
        ("MOCK_CHROMA = true (default, unchanged)", "The vector/dense half of knowledge retrieval is OFF. Only BM25 keyword search is active."),
        ("MOCK_WHATSAPP = true (default, unchanged)", "Daily messages are composed but only logged, never actually sent to a BSP."),
        ("MOCK_RAZORPAY = true (default, unchanged)", "Commerce is now fully wired but deliberately runs mock: orders are captured locally and entitlements granted without a real charge. The real Razorpay create-order/webhook path exists in code but stays OFF until human sign-off (payments are a hard approval gate)."),
    ]
    for key, detail in env_rows:
        pdf.kv_row(key, detail)
        pdf.divider()
    pdf.info_box(
        "The admin dashboard (/admin) shows this same live/mocked wiring at runtime - "
        "AdminService reports which integrations are real vs mocked (booleans only, never keys)."
    )

    # == 4: data stores (detailed) ==========================================
    pdf.add_page()
    pdf.section_title("4. Data stores  -  every table, collection and file, and who touches it")
    pdf.sub_title("4.1  SQL  -  Postgres in prod, SQLite tara.db locally (zero-setup)")
    pdf.mono_block([
        "  users           phone (UNIQUE - the identity key), password_hash, name,",
        "                  dob, birth_time, birth_place, lat, lng, tz",
        "  sessions        bearer token, user ref, expires_at (TTL 47h)",
        "  charts          user ref, natal_json (everything Swiss Ephemeris computed:",
        "                  grahas, lagnam, nakshatram, vargas D3/D7/D9/D10/D12,",
        "                  dasha timeline, doshas)",
        "  wa_consent      WhatsApp opt-in/opt-out ledger",
        "  wa_message_log  what the daily pipeline sent (or would have sent)",
    ])
    pdf.sub_title("4.2  MongoDB  (database: tara)  -  document shapes as written by the code")
    pdf.mono_block([
        "  chat_history   one doc per TURN:",
        "                 { user_id (phone), conversation_id, messages (the user turn),",
        "                   reply, created_at }",
        "  user_memory    one doc per USER (upserted):",
        "                 { user_id, facts: [ {text, kind, at} ]  (capped, oldest",
        "                   dropped), summary, district, updated_at }",
    ])
    pdf.sub_title("4.3  Flat files  -  the RAG corpus and temple data live in the repo, not a DB")
    pdf.mono_block([
        "  app/modules/knowledge/seed_data.py       248 hand-written curated chunks",
        "  app/modules/knowledge/ingested/*.json    2,203 ingested classical-text chunks",
        "  app/modules/temples/seed_data.py         53 curated temples",
        "  knowledge_vectordb/  (gitignored)        Chroma vector store - dormant",
    ])
    pdf.sub_title("4.4  Who reads / writes what (one chat turn)")
    for item in [
        "identity (register/login/onboard): WRITES users, sessions, charts. The only module that touches these tables.",
        "chat step 2: READS charts - but only via identity.get_chart_by_phone(), never SQL directly.",
        "chat step 3b: READS Mongo user_memory; background task WRITES chat_history + user_memory.",
        "knowledge: READS the flat-file corpus once at startup into an in-RAM BM25 index; nothing at request time touches disk.",
        "temples: pure in-memory Python dicts (remedy_map.py) + the 53-temple list.",
        "admin: READ-ONLY, and only through IdentityService / ChatService public methods + the in-process metrics counters - it owns no tables.",
        "Crisis turns touch NOTHING: no read of chart/memory, no write of history (GUARDRAILS §2).",
    ]:
        pdf.bullet(item)
    pdf.body(
        "Why split Postgres and Mongo? Birth data and auth are structured, relational, and "
        "privacy-sensitive (GUARDRAILS.md #4) - a fit for SQL with strict row-ownership checks. Chat "
        "turns and durable memory are unstructured, high-volume, per-user-document shaped - a fit "
        "for a document store. No module reaches into another's tables; everything crosses module "
        "boundaries through public service methods."
    )

    # == 5: THE FLOWCHART page ==============================================
    chat_flowchart(pdf)

    # == 6: orchestrator narrative ==========================================
    pdf.add_page()
    pdf.section_title("6. The orchestrator  -  ChatService.handle_message, step by step")
    pdf.body(
        "'The orchestrator' is one method: ChatService.handle_message() in app/modules/chat/"
        "service.py. It is plain sequential Python - no agent framework, no LangChain chains, no "
        "planner. It calls the other modules' public services in a fixed order, collects "
        "deterministic facts, packs them into ONE system prompt, and makes ONE LLM call to narrate "
        "them. The division of labour is strict: facts are COMPUTED (astrology_engine), knowledge "
        "is RETRIEVED (knowledge), language is GENERATED (LLM). The LLM never invents placements."
    )
    pdf.step_box("1", "Crisis screen FIRST (tone_safety.screen)",
                 "Keyword-matches the message against distress phrases (EN / Malayalam / Manglish).\n"
                 "If it fires: return the hardcoded Tele-MANAS 14416 safety reply immediately.\n"
                 "Nothing else below runs - no chart load, no RAG, no LLM call, nothing saved.")
    pdf.step_box("2", "Load chart + live transits",
                 "identity.get_chart_by_phone(user_id) reads the stored natal chart (SQL).\n"
                 "astrology_engine.get_transits(chart) computes today's planetary positions and\n"
                 "checks Sade Sati against the natal Moon. Both degrade gracefully to None/partial\n"
                 "context if the DB is down - chat still answers, with less grounding.")
    pdf.step_box("2p", "Prashnam (only if the user picked a number/leaf/square in the UI)",
                 "astrology_engine.get_prashnam_reading() computes a horary chart for the exact\n"
                 "moment the question was asked, using the user's stored lat/lng. The reading's\n"
                 "cues replace the chart facts in the RAG query for this turn.")
    pdf.step_box("2c", "Porutham (only if a partner form is attached to this turn)",
                 "The partner's birth place is geocoded, their natal chart computed, and the ten\n"
                 "Kerala poruthams (dashaporutham) are graded IN PYTHON - bride's star to groom's.\n"
                 "The result note carries every porutham verbatim plus an honesty rule: guidance,\n"
                 "never a marriage verdict. Missing/placeholder charts degrade to a helpful note -\n"
                 "the LLM is told to ask for birth details, never to invent a score.")
    pdf.step_box("3", "Build a retrieval query from real facts, then retrieve (k=4)",
                 "Query = question + computed facts (retrogrades, Sade Sati, nakshatram, lagna,\n"
                 "mahadasha lord, doshas). knowledge.retrieve() runs the hybrid search of section 8\n"
                 "and returns the top-4 interpretation chunks with provenance ids.")
    pdf.step_box("3a2", "Pick ONE relevant divisional chart (varga)",
                 "Keyword-matches the message (EN + Malayalam + Manglish) to a life domain and\n"
                 "grafts only that D-chart (D10 career / D9 marriage / D7 children / D12 parents /\n"
                 "D3 siblings) into the prompt - never all five at once.")
    pdf.step_box("3b", "Load durable memory (MongoDB, cross-session)",
                 "user_memory.get_profile() - facts remembered from earlier conversations (job,\n"
                 "family, concerns), capped when injected; also the user's CURRENT district.")
    pdf.step_box("3c", "Temple / remedy suggestion (at most ONE, on purpose)",
                 "Fires only if the user asks for a remedy, or a traditional concern+dosha pairing\n"
                 "applies (marriage+chovva, children+kala sarpa). temples.suggest(k=1) - the cap is\n"
                 "enforced in code, not by prompt instruction, because the LLM narrates everything\n"
                 "it is given. District priority: message mention > memory profile > birth place.")
    pdf.step_box("4", "Build the system prompt (tone_safety.build_system_prompt)",
                 "String concatenation, in order: persona rules + Malayalam terminology glossary +\n"
                 "memory block + natal chart + transits + retrieved notes (RAG chunks, prashnam/\n"
                 "porutham/temple notes). One system message; the user's turns follow as-is.")
    pdf.step_box("5", "Call the LLM (llm_client.complete) - see section 7 for the call budget",
                 "Provider chain: requested-or-default -> sarvam -> openai -> canned mock reply.\n"
                 "Sarvam gets reasoning_effort=low + max_tokens=4096 (reasoning shares the budget;\n"
                 "2048 truncated porutham readings mid-sentence, seen live 2026-07-06). An empty\n"
                 "reply (model spent the whole budget thinking) triggers ONE retry at double budget.")
    pdf.step_box("5b", "Screen the OUTPUT before sending it back (tone_safety.screen_reply)",
                 "Regex-checks fear language, payment-linked remedies, manufactured urgency.\n"
                 "If violated: retry once with a corrective note; if still violated, serve a\n"
                 "hardcoded safe fallback instead of the model's output.")
    pdf.step_box("6", "Respond + save in the background",
                 "Returns {reply, is_safety_response, grounded_in, llm_provider/model, token counts,\n"
                 "price_inr/price_usd}. grounded_in is a real audit trail (chart, transits,\n"
                 "knowledge:<chunk-id>, varga:D9, temple:<id>, prashnam:<mode>, porutham).\n"
                 "history.save_turn + memory.extract_memory run as FastAPI BackgroundTasks -\n"
                 "never on the crisis path, so distress conversations are never persisted.")
    pdf.info_box(
        "Debug mode: POST /chat/message with debug:true (non-production only) attaches a full "
        "per-turn trace - every step's latency, the exact RAG query and hits, the final system "
        "prompt, and the LLM config - so you can see precisely how a reply was assembled."
    )

    # == 7: LLM call budget ==================================================
    pdf.add_page()
    pdf.section_title("7. How many LLM calls?  -  the complete call budget")
    pdf.body(
        "Every LLM call in the entire system, and when it happens. There is no hidden chain: "
        "no query-rewriting call, no router/classifier call, no embedding call at chat time "
        "(BM25 needs none), no re-ranker. Intent detection, varga choice, temple choice, crisis "
        "detection and porutham grading are all keyword/rule-based Python, costing zero tokens."
    )
    pdf.ln(2)
    rows = [
        ("Chat turn - reply", "1 call, always (sarvam-105b by default). This is the ONLY foreground call on a normal turn."),
        ("+ empty-reply retry", "+1, rare: sarvam occasionally burns the whole completion budget on internal reasoning and returns empty content; one retry with a doubled budget. Still empty -> canned Malayalam apology, no third call."),
        ("+ guardrail retry", "+1, rare: only when screen_reply flags fear/payment/urgency; the retry appends a corrective note. A second failure serves the canned safe reply - never a third call."),
        ("Memory distillation", "+1 per normal turn, in the BACKGROUND (after the reply is already sent, so it never adds latency). Distills durable facts to JSON via the same LLMClient. Offline mode stores a heuristic note instead (0 calls)."),
        ("Crisis turn", "0 calls. The screen fires before everything; the canned safety reply is served and nothing is persisted."),
        ("Mock mode", "0 calls anywhere. MOCK_LLM / mock_openai / missing keys -> canned Malayalam reply; the whole app works offline."),
        ("Daily content message", "1 OpenAI (gpt-4o-mini) call per DAY, total - not per user. The 05:30 IST Celery job drafts one Malayalam WhatsApp message from the panchangam; mocked -> template."),
        ("Evals (manual runs)", "1 call per golden-set case (25 cases) + 1 judge call per case when the Malayalam-fluency judge is enabled."),
    ]
    for key, detail in rows:
        pdf.kv_row(key, detail, key_w=48)
        pdf.divider()
    pdf.info_box(
        "Bottom line: a typical live chat turn = 2 LLM calls (1 foreground reply + 1 background "
        "memory distill). Absolute worst case = 6 (reply + empty retry + guardrail retry + its "
        "empty retry + distill + its empty retry). Token usage and estimated price (INR/USD) for "
        "the foreground call are recorded per reply and aggregated for the admin dashboard by "
        "app/platform/metrics.py."
    )

    # == 8: RAG corpus deep dive ============================================
    pdf.add_page()
    pdf.section_title("8. RAG  -  what the documents are, where they live, how they're stored")
    pdf.body(
        "'Documents' in Tara's RAG are NOT whole PDFs in a database. They are 2,451 small text "
        "CHUNKS (a few sentences each), kept as Python/JSON files in the repo, indexed in RAM at "
        "startup. There is no documents table anywhere - the corpus ships with the code."
    )
    pdf.sub_title("8.1  Layer 1: curated chunks - seed_data.py (248, hand-written)")
    pdf.mono_block([
        "  topic              count   what it teaches the model",
        "  planet-in-house      108   each graha in each of the 12 bhavas",
        "  prashnam              37   horary rules for thamboola/swarna/sankhya",
        "  vazhipadu             30   temple offerings and what each is for",
        "  nakshatra             28   one profile per birth star (27 + intro)",
        "  deity                 15   Kerala deities and their remedial domains",
        "  lagna                 12   one profile per ascendant sign",
        "  dasha                  9   one profile per mahadasha lord",
        "  dosha                  3   chovva, kala sarpa, sade sati",
        "  retrograde/porutham/",
        "  remedies/muhurtham/",
        "  panchangam             6   one-offs",
    ])
    pdf.sub_title("8.2  Layer 2: ingested chunks - ingested/*.json (2,203, from classical texts)")
    pdf.body(
        "Produced OFFLINE by the ingest.py CLI from real public-domain sources: Brihat Jataka of "
        "Varahamihira (1885 translation, 1,231 chunks) and Brihat Samhita (972 chunks). They far "
        "outnumber the curated set, which is exactly why retrieval penalizes and caps them "
        "(section 9 flowchart)."
    )
    pdf.sub_title("8.3  Anatomy of one chunk (the only 'document schema' in the system)")
    pdf.mono_block([
        '  {',
        '    "id":       "planet-in-house-shani-10",   <- cited in grounded_in',
        '    "topic":    "planet-in-house",',
        '    "text":     "Saturn in the 10th house of a sidereal chart ...",',
        '    "reviewed": false,   <- true only after astrologer sign-off',
        '    "source":   "brihat-jataka"  <- provenance; absent on curated seeds',
        '  }',
    ])
    pdf.body(
        "That id travels the whole way: retrieval returns it, chat appends knowledge:<id> to the "
        "reply's grounded_in list, and the debug trace shows the chunk text - so every claim in a "
        "reply can be traced back to the exact chunk (or computed fact) that grounded it."
    )
    pdf.info_box(
        "Adding knowledge = editing seed_data.py (curated) or running the ingest CLI (imports), "
        "then restarting. BM25 reindexes in RAM automatically at startup; the dormant Chroma index "
        "reseeds itself when the corpus size changes (or run knowledge.retrieval.reindex())."
    )

    # == 9: RAG flowcharts ===================================================
    rag_flowcharts(pdf)

    # == 10: astrology engine ================================================
    pdf.add_page()
    pdf.section_title("10. Domain knowledge #1  -  the astrology engine")
    pdf.body(
        "Real Vedic sidereal astronomy, computed at request time, not looked up from a table and "
        "not invented by the LLM. Lives in app/modules/astrology_engine/."
    )
    pdf.sub_title("10.1  Chart math (swiss_ephemeris.py)")
    for item in [
        "Uses the pyswisseph library (Moshier analytical ephemeris) - no external API, no data files.",
        "Sidereal zodiac, not tropical - ayanamsa configurable: Lahiri (default, Indian govt standard), KP, or Raman.",
        "Whole-sign houses: the lagna's rasi is house 1; each following rasi is house 2, 3 ... 12.",
        "Computes Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu (mean node), Ketu (Rahu+180); retrograde = negative ephemeris speed.",
        "5 divisional charts (vargas) from the D1 longitude: D9 navamsa (marriage), D10 dashamsa (career), D7 saptamsa (children), D3 drekkana (siblings), D12 dwadasamsa (parents).",
    ]:
        pdf.bullet(item)
    pdf.ln(2)
    pdf.sub_title("10.2  Vimshottari dasha (vimshottari.py)")
    pdf.body(
        "The classical 120-year, 9-lord cycle (Ketu 7y, Venus 20y, Sun 6y, Moon 10y, Mars 7y, "
        "Rahu 18y, Jupiter 16y, Saturn 19y, Mercury 17y), genuinely derived from the Moon's exact "
        "sidereal position at birth: its nakshatra picks the starting lord, and the fraction "
        "traveled through that nakshatra gives the elapsed fraction of that lord's period. "
        "Produces a full mahadasha/antardasha timeline with real dates, plus 'what runs now'.",
        indent=2,
    )
    pdf.sub_title("10.3  Doshas (doshas.py)  -  deterministic rule checks, never LLM-guessed")
    for item in [
        "Chovva / Mangal dosha: Mars in houses 1, 2, 4, 7, 8 or 12 - checked from BOTH lagna and Moon (Kerala convention).",
        "Kala Sarpa dosha: all seven classical grahas confined to one arc between Rahu and Ketu.",
        "Sade Sati: a live TRANSIT check - is transiting Saturn in the 12th/1st/2nd from the natal Moon right now, and which phase.",
    ]:
        pdf.bullet(item)
    pdf.ln(2)
    pdf.sub_title("10.4  Porutham (porutham.py)  -  the ten-match marriage compatibility, in Python")
    pdf.body(
        "The dashaporutham (ten Kerala poruthams) is graded deterministically from both partners' "
        "Moon nakshatram/rasi: the bride's star counts to the groom's, each porutham gets a "
        "grade and a reason, rajju dosha is flagged separately, and a total score /max is "
        "produced. In chat, the partner's chart is computed on the fly from the partner form "
        "(geocode -> natal chart); the LLM only narrates the computed result, opening with both "
        "janma nakshatrams so the couple can see the reading came from THEIR charts.",
        indent=2,
    )
    pdf.sub_title("10.5  Panchangam & transits")
    pdf.body(
        "Daily panchangam computes nakshatram + tithi at local noon. One honest gap: nalla_neram "
        "(the auspicious window) is a hardcoded string, not computed per day/location - a real "
        "implementation needs sunrise time, not wired in yet. Transits add house_from_moon (the "
        "traditional Vedic transit frame) on top of raw current positions.",
        indent=2,
    )

    # == 11: prashnam + temples ==============================================
    pdf.add_page()
    pdf.section_title("11. Domain knowledge #2  -  prashnam & temple remedies")
    pdf.sub_title("11.1  Prashnam (Kerala horary astrology)  -  prashnam.py")
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
        "Thamboola is explicitly documented in the code (and NEEDS_ASTROLOGER.md) as a "
        "'simplified draft', not a claim to replicate an in-person ashtamangala prashnam by a "
        "trained Daivajna. This honesty caveat is injected straight into the chat prompt so Tara "
        "never overstates what a text-based prashnam can tell someone."
    )
    pdf.sub_title("11.2  Temples & remedies  -  temples/remedy_map.py + seed_data.py")
    pdf.body(
        "53 curated Kerala temples (coordinates Google-Places-verified) with deity, district, "
        "vazhipadu options. remedy_map.py is a set of plain Python lookup dicts - no ML:"
    )
    for item in [
        "CONCERN_DEITIES - 9 life-concern keys (career, marriage, children, health, ...) -> ordered deity list.",
        "CONCERN_KEYWORDS - free-text (English/Malayalam/Manglish) -> concern key.",
        "GRAHA_DEITIES - each of the 9 planets -> its Kerala remedial deity (e.g. Saturn -> Sastha/Shiva/Hanuman).",
        "DOSHA_DEITIES - chovva_dosha -> Subrahmanya/Devi; kala_sarpa_dosha -> Naga; sade_sati -> Sastha/Hanuman/Shiva.",
    ]:
        pdf.bullet(item)
    pdf.body(
        "TemplesService.suggest() combines concern + doshas + the current mahadasha lord into one "
        "ordered, de-duplicated deity list, then picks the nearest matching temple by haversine "
        "distance if the user's location is known. At most ONE temple per turn - enforced with "
        "k=1 in code, because the LLM narrates everything it is given.",
        indent=2,
    )

    # == 12: tone & safety ===================================================
    pdf.add_page()
    pdf.section_title("12. The persona & safety layer  -  tone_safety module")
    pdf.body(
        "Everything that shapes HOW Tara talks (and when it must refuse to talk astrology at all) "
        "lives here. It has no HTTP endpoints - it's a library consumed by chat."
    )
    pdf.sub_title("12.1  Persona prompt (persona.py)")
    pdf.body(
        "A hardcoded system prompt with five fixed rules: disclose it's an AI astrologer; "
        "acknowledge feelings BEFORE the chart; tie every claim to a real placement (and NAME the "
        "person's actual nakshatram/rasi/dasha so they see it's their chart); frame challenges "
        "with agency ('the stars incline, they do not compel'); know its limits and hand off to a "
        "helpline for real distress. It also instructs the model to trust conversation history "
        "(never re-ask for a partner's details after a porutham) and to end every reply with "
        "exactly ONE caring follow-up question. build_system_prompt() is literally string "
        "concatenation - no prompt-management framework.",
        indent=2,
    )
    pdf.sub_title("12.2  Crisis classifier (crisis_classifier.py)  -  READ THIS")
    pdf.info_box(
        "The file is commented 'PLACEHOLDER HEURISTIC - NOT PRODUCTION-READY'. It is a pure "
        "keyword/substring match across English, Malayalam script, and romanized Manglish distress "
        "phrases - not a trained classifier. It deliberately does NOT flag bare words like 'death' "
        "(innocuous in astrology: 8th house, longevity). The ROUTING (screen first, hard stop, "
        "never bypassed) is solid infrastructure - the DETECTION QUALITY needs a clinically "
        "reviewed upgrade before real users rely on it. Flagged in NEEDS_ASTROLOGER.md."
    )
    pdf.sub_title("12.3  Output guardrail (reply_screen.py)  -  checks the LLM's reply, after the fact")
    for item in [
        "Fear: regex for asserted doom/curses ('a great danger awaits', 'cursed', 'doomed') in Malayalam and English.",
        "Payment-linked remedy: a remedy word (pooja/vazhipadu/homam/yantra/mantra) within ~60 chars of a payment cue (Rs / fee / pay).",
        "Manufactured urgency: 'act now or...', 'last chance', 'if you don't do X immediately...'.",
    ]:
        pdf.bullet(item)
    pdf.body(
        "If any category fires, chat retries once with a corrective note appended; if it still "
        "fires, the user gets a hardcoded safe fallback instead of the model's output.",
        indent=2,
    )

    # == 13: engagement & growth layer ======================================
    pdf.add_page()
    pdf.section_title("13. The engagement & growth layer  -  beyond the chatbot")
    pdf.body(
        "The chat brain (sections 5-12) is the core, but a companion people return to daily needs "
        "more than a question box. This layer - built module by module - turns Tara from a Q&A bot "
        "into a habit: a content feed to open every morning, temple partnerships that put Tara on "
        "posters, a referral loop that grows it, and a premium report that earns from it. Every "
        "surface reuses the same public services and the same tone_safety screen; nothing here "
        "bypasses a guardrail."
    )
    pdf.sub_title("13.1  Two web surfaces at the root (not /ui)")
    for item in [
        "/feed - the USER home: a mobile bottom-nav / desktop top-nav page showing today's panchangam, published content posts, emoji reactions, a check-in streak chip, live polls, an invite-a-friend card (referral) and a premium-report card. Optional-auth: it works logged-out and gets personal when a token is present.",
        "/console - the OWNER console: an email-login (arunjithpm1999@gmail.com) dashboard exposing every growth feature - daily content, Content Studio, polls, share cards, panchangam lookup, temple partners, notifications, the referral funnel and the commerce panel. Many nav items on purpose: it is the single back-office for one operator.",
        "Users only ever see feed + chat; the console is owner-only, behind the X-Admin-Token the email login returns.",
    ]:
        pdf.bullet(item)
    pdf.sub_title("13.2  Content Studio (content module)")
    pdf.body(
        "One admin action, POST /content/generate, drafts a piece in one of five formats - reel "
        "script, weekly astro-news, festival special, nakshatra episode, myth-buster - from the "
        "day's (or the week's) panchangam. Each draft is LLM-written, passed through the SAME "
        "reply-screen guardrail as chat (retry-then-fallback), then sits at status=draft until the "
        "owner approves and marks it published. Publishing a post is what makes it appear on /feed. "
        "TTS/audio is intentionally NOT wired yet - narration is added by hand for now.",
        indent=2,
    )
    pdf.sub_title("13.3  Community feed (community module)")
    for item in [
        "GET /community/feed assembles today's panchangam card + the published content posts; loading it records a check-in and updates the user's streak.",
        "POST /community/posts/{id}/react toggles one of three reactions; GET /streak returns the running day count; GET/POST /community/polls runs lightweight polls with live tallies.",
        "No cross-module foreign keys: posts are referenced by plain id, users by the identity phone/id - the module boundary rule holds.",
    ]:
        pdf.bullet(item)
    pdf.sub_title("13.4  Temple partnerships (temples module, Part 3)")
    pdf.body(
        "Any of the 53 directory temples can be registered as a distribution partner: it gets a "
        "public microsite, a printable QR poster (a real PNG served at /temples/partners/{slug}/"
        "qr.png), an embeddable widget, and a festival calendar. Devotees opt in to WhatsApp "
        "updates from the microsite (explicit consent, logged). On a festival day the notifications "
        "module queues a Malayalam nudge to that temple's subscribers - a growth channel that puts "
        "Tara in front of real temple-goers, offline.",
        indent=2,
    )
    pdf.sub_title("13.5  Referral loop (identity module)")
    pdf.body(
        "Every user has a referral code; GET /identity/referral returns it plus a live activation "
        "count. Registration consumes an incoming ref code, records the activation against the "
        "referrer, and once a threshold is crossed grants a reward (a commerce entitlement) "
        "automatically. The /feed invite card turns this into a one-tap share link (/auth?ref=CODE); "
        "the console shows the funnel.",
        indent=2,
    )
    pdf.sub_title("13.6  Commerce - premium report (commerce module, MOCK mode)")
    pdf.body(
        "The first paid product is a Premium Jathakam Report (Rs 199 / 19,900 paise). Flow: POST "
        "/commerce/orders {product: premium_report} -> in mock mode POST /orders/{id}/mock-pay "
        "captures it and grants an entitlement -> POST /commerce/reports/premium generates a real "
        "PDF (Pillow) and returns it; without the entitlement that endpoint 402s. The real "
        "Razorpay create-order + signature-verified webhook path is written but OFF: no money moves "
        "until a human flips MOCK_RAZORPAY and signs off. There is also a B2B path (orgs module): "
        "astrologer businesses subscribe to plans and run their own booking + CRM.",
        indent=2,
    )
    pdf.info_box(
        "The whole growth layer honours the same non-negotiables: tone_safety screens every piece "
        "of published copy, WhatsApp stays opt-in and throttled, birth data never leaves its tables, "
        "and payments are mock-only until explicitly approved. Growth never comes at the cost of a "
        "guardrail."
    )

    # == 14: Malayalam handling matrix ======================================
    pdf.add_page()
    pdf.section_title("14. How Malayalam is handled  -  feature by feature")
    pdf.body(
        "Malayalam is not one feature; it is threaded through every layer. Users write in three "
        "forms - Malayalam script, English, and Manglish (Malayalam in Latin letters, loose "
        "spelling) - and every matching layer below handles all three:"
    )
    pdf.ln(1)
    ml_rows = [
        ("Model choice", "sarvam-105b (an Indic-first model) is the default BECAUSE of Malayalam: evals scored it 4.79/5 fluency vs 3.00 for gpt-4o-mini. sarvam-fast (30B) regressed to 3.48 and truncates - rejected."),
        ("Sarvam tuning", "reasoning_effort=low + max_tokens=4096: Sarvam 'thinks' from the same token budget, and long-form Malayalam is token-hungry; 2048 truncated porutham readings mid-sentence. An all-reasoning empty reply triggers one doubled-budget retry."),
        ("Persona prompt", "'Reply primarily in Malayalam, warmly and concisely; simple English only if the user writes in English.' The terminology glossary maps the engine's stable ids (surya, guru, shani...) to the proper Malayalam SCRIPT terms, so replies say the authentic Kerala jyotisham word, not a transliteration or English."),
        ("Manglish input", "The prompt glossary teaches romanized forms (naal=janma nakshatram, jathakam, porutham, dosham, randalum...) and tells the model to read them as Malayalam - and to ask ONE short clarifying question in Malayalam when a Manglish message stays ambiguous, instead of guessing."),
        ("Keyword routing", "Every deterministic matcher carries all three forms: varga topics (career = job/joli/thozhil...), remedy intent (temple/kshethram/ambalam/vazhipad...), residence cues for memory (i live/njan/thamasik...), temple concern keywords."),
        ("Crisis screen", "Distress phrases matched in English + Malayalam script + Manglish. The safety reply itself is hand-written Malayalam naming Tele-MANAS 14416."),
        ("Output guardrail", "Fear/urgency/payment regexes cover Malayalam and English patterns, so a violation can't slip through by language choice."),
        ("RAG tokenizer", "BM25 uses a custom regex including the whole Malayalam Unicode block (U+0D00-0D7F). Python's \\w excludes combining marks (vowel signs, virama) and would shred Malayalam words into bare consonants - this is why Malayalam queries actually match."),
        ("Ingest chunker", "Sentence-boundary splitting is Malayalam/Devanagari-aware, so ingested texts chunk cleanly."),
        ("Canned fallbacks", "Every no-LLM path speaks Malayalam: the offline mock reply, the crisis reply, the empty-reply apology, and the guardrail safe fallback are all hand-written Malayalam."),
        ("Daily content", "The 05:30 IST WhatsApp message is drafted in Malayalam from the day's panchangam (LLM when live, Malayalam template when mocked)."),
        ("Evals", "Graders check replies for foreign-script glyph leakage (e.g. Devanagari sneaking in), truncation, and the mandated closing question; an optional LLM judge scores Malayalam fluency 1-5. This is measured, not assumed."),
    ]
    for key, detail in ml_rows:
        pdf.kv_row(key, detail, key_w=34)
        pdf.divider()

    # == 14: LLM providers + evals ==========================================
    pdf.add_page()
    pdf.section_title("15. LLM providers  -  why Sarvam, not just OpenAI")
    pdf.body(
        "llm_client.py talks to all providers through one OpenAI-compatible AsyncOpenAI client "
        "(Sarvam just uses a different base_url) and resolves which to use per request:"
    )
    pdf.mono_block([
        "  requested provider (UI may pick per message) or CHAT_PROVIDER=sarvam",
        "       |  has an API key configured?",
        "       v  no -> try next in chain",
        "  sarvam (sarvam-105b) --> openai (gpt-4o-mini) --> hardcoded mock reply",
        "  (sarvam-fast = same endpoint, 30B model - selectable, not default)",
        "",
        "  max_tokens: sarvam/sarvam-fast 4096, openai 1024.",
        "  sarvam extra: reasoning_effort='low' (default 'medium' thinking eats the",
        "  completion budget and truncates long Malayalam replies - seen in evals).",
        "  Empty reply (all budget spent thinking) -> 1 retry at double budget ->",
        "  else canned Malayalam apology. Usage + estimated INR/USD price recorded",
        "  per call (platform/metrics.py) and shown per-reply and in /admin.",
    ])
    pdf.section_title("16. Evals  -  this has actually been measured, not just claimed")
    pdf.body(
        "evals/golden_set.py defines 25 fixed conversations (everyday questions, 2 crisis cases, "
        "temple/remedy asks, all 3 prashnam modes, adversarial guardrail probes). evals/run.py "
        "calls ChatService.handle_message() directly and grades each reply with deterministic "
        "checks (crisis routing correct, no astrology terms in a crisis reply, not truncated, no "
        "foreign-script glyphs, at most 1 temple, ends with a question) plus an optional LLM judge "
        "for Malayalam fluency 1-5. Real saved results:"
    )
    pdf.ln(2)
    eval_rows = [
        ("sarvam-105b", "23 / 25 passed  -  avg fluency 4.79 / 5"),
        ("openai (gpt-4o-mini)", "24 / 25 passed  -  avg fluency 3.00 / 5"),
        ("sarvam-fast (30B)", "6 / 25 passed  -  avg fluency 3.48 / 5 - known regression: truncates, drops the closing question"),
    ]
    for model, result in eval_rows:
        pdf.kv_row(model, result)
        pdf.divider()
    pdf.body(
        "This is why sarvam-105b is the configured default: most fluent in Malayalam AND passes "
        "the most guardrail checks."
    )

    # == 16: auth + running ==================================================
    pdf.add_page()
    pdf.section_title("17. Auth & identity  -  how a user is recognized")
    for item in [
        "The identity key is the normalized mobile number (IdentityService.normalize_phone) - not a UUID. Everything (chat_history, user_memory, charts, sessions) is keyed off this phone.",
        "Passwords: PBKDF2-HMAC-SHA256, 200,000 rounds, unique salt per user, constant-time comparison.",
        "Sessions: bearer tokens (secrets.token_urlsafe(32)) stored server-side with expires_at, TTL 47 hours - stateful and revocable, not JWT.",
        "Identity is ALWAYS derived from the token; any user_id in a request payload is ignored, and every route 403s on ownership mismatch.",
        "Chat is rate-limited per user (sliding window per hour, configurable; in-process - move to Redis for multi-worker).",
        "Onboarding (POST /identity/users) does register + geocode + first natal chart + auto-login in one round trip.",
        "On login, a stored chart that still looks mock/pending is silently recomputed for real - a self-healing migration.",
        "The admin dashboard (/admin, app/web/admin.html) has its own auth guard (admin/auth.py), separate from user sessions.",
    ]:
        pdf.bullet(item)
    pdf.section_title("18. Running it locally")
    pdf.mono_block([
        "  python -m venv .venv && .venv\\Scripts\\activate",
        "  pip install -e \".[dev]\"       (or: pip install -r requirements.txt)",
        "  cp .env.example .env            # real keys only for what you want live",
        "  python main.py                  # or: uvicorn app.main:app --reload --port 3000",
        "",
        "  Website chat UI    ->  http://localhost:3000/",
        "  User feed          ->  http://localhost:3000/feed      (streak, posts, polls)",
        "  Owner console      ->  http://localhost:3000/console   (email login)",
        "  WhatsApp demo skin ->  http://localhost:3000/whatsapp   (same brain, other CSS)",
        "  Admin dashboard    ->  http://localhost:3000/admin",
        "  API docs (Swagger) ->  http://localhost:3000/docs",
        "",
        "  With every MOCK_* flag at its default True, the whole app boots and chats",
        "  with ZERO external API keys - the LLM, ephemeris, Mongo, geocoding all",
        "  degrade to local behaviour.",
    ])

    # == 18: gaps + file map =================================================
    pdf.add_page()
    pdf.section_title("19. Known gaps  -  read before promising a feature")
    for item in [
        "Crisis classifier is keyword-only (section 12.2) - needs a clinically-reviewed upgrade before real users in distress rely on it.",
        "WhatsApp sending is not implemented - _send_via_bsp() raises NotImplementedError; only the consent/throttle/pipeline scaffolding is real. Festival nudges (notifications) and daily content therefore compose but don't actually send yet.",
        "Commerce runs MOCK only: orders are captured and entitlements granted locally with no real charge. The Razorpay create-order/webhook code exists but MOCK_RAZORPAY stays true until a human signs off (payments are a hard approval gate).",
        "Content Studio has no TTS/audio: reel and episode scripts are text; narration/audio is added manually for now (integration is a later step).",
        "The event bus (platform/events.py) is defined but never called - modules import each other's public services directly.",
        "Celery has exactly one real job (the WhatsApp daily message); chat persistence uses FastAPI BackgroundTasks.",
        "The dense/Chroma half of retrieval is code-complete but OFF (MOCK_CHROMA=true) - BM25 only right now. No cross-encoder reranker either (noted in code as a later addition).",
        "panchangam's nalla_neram is a hardcoded string, not computed per day/location.",
        "The in-process rate limiter and metrics counters reset on restart and don't span workers - Redis is the noted upgrade path.",
        "None of the astrology content (248 curated chunks, 53 temples, remedy_map tables, thamboola scheme, porutham grading copy) has been reviewed by a qualified astrologer - every chunk carries reviewed: False. See NEEDS_ASTROLOGER.md.",
    ]:
        pdf.bullet(item)

    pdf.section_title("20. Where things live  -  quick file map")
    pdf.mono_block([
        "  app/main.py                      FastAPI app, wires every module's router",
        "  app/platform/config.py           ALL settings + every MOCK_* flag (read first)",
        "  app/platform/db.py               SQL engine (users/sessions/charts)",
        "  app/platform/mongo.py            MongoDB client (chat_history/user_memory)",
        "  app/platform/metrics.py          in-process LLM usage counters + price estimate",
        "",
        "  app/modules/identity/            auth, birth data, geocoding, chart storage",
        "  app/modules/astrology_engine/    chart math, dasha, doshas, prashnam, porutham",
        "  app/modules/knowledge/           RAG corpus + hybrid BM25/Chroma retrieval",
        "  app/modules/tone_safety/         persona, crisis screen, output guardrail",
        "  app/modules/chat/                the orchestrator + history/memory/analytics",
        "  app/modules/temples/             53 temples + remedy/deity lookup + partners",
        "  app/modules/admin/               analytics dashboard + owner console (own auth)",
        "  app/modules/content/             daily message + Content Studio (5 formats)",
        "  app/modules/community/           user feed, reactions, streaks, polls",
        "  app/modules/commerce/            orders, entitlements, premium PDF (mock mode)",
        "  app/modules/notifications/       partner-festival WhatsApp nudges (run_festivals)",
        "  app/modules/astrologers, orgs/   human-astrologer booking + B2B CRM/billing",
        "  app/modules/whatsapp/            consent ledger + daily pipeline (send = TODO)",
        "",
        "  app/web/                         index.html, feed.html, console.html, wa skin,",
        "                                   admin.html + JS/CSS  (all served from / root)",
        "  evals/                           25-case golden set + automated grading",
        "  NEEDS_ASTROLOGER.md              living punch-list of unreviewed content",
        "  AGENTS.md / GUARDRAILS.md        the ORIGINAL rules - still binding for the",
        "                                   non-negotiables (no fear, crisis-first,",
        "                                   WhatsApp compliance, birth-data privacy)",
    ])
    pdf.info_box(
        "Bottom line: the ethical guardrails and module boundaries from the original plan are "
        "still binding. What changed is the concrete stack - Sarvam instead of only OpenAI, "
        "self-computed Swiss Ephemeris, Postgres+MongoDB, a real hybrid RAG pipeline over 2,451 "
        "chunks, deterministic prashnam/porutham engines, and a working admin dashboard."
    )

    pdf.output("Tara_Developer_Guide.pdf")
    print("Wrote Tara_Developer_Guide.pdf")


if __name__ == "__main__":
    build()
