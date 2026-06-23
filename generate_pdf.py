"""Generate Tara project overview PDF -run once, outputs tara_project_overview.pdf."""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ACCENT = (196, 90, 59)   # terracotta
DARK   = (44, 38, 34)    # sidebar dark
LIGHT  = (244, 241, 234) # cream bg
MUTED  = (138, 129, 120)
WHITE  = (255, 255, 255)
BLACK  = (43, 39, 34)


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Tara  |  Malayalam-first AI Astrology Companion  |  Page {self.page_no()}", align="C")

    def cover_page(self):
        self.add_page()
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 297, "F")
        self.set_fill_color(*ACCENT)
        self.rect(0, 120, 210, 6, "F")

        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 42)
        self.set_y(60)
        self.cell(0, 20, "TARA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 16)
        self.set_text_color(233, 226, 214)
        self.cell(0, 10, "Malayalam-first AI Astrology Companion", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(30)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(163, 153, 140)
        self.cell(0, 8, "Technical Architecture & System Overview", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(200)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "Stack: FastAPI (Python)  |  OpenAI gpt-4o-mini  |  ChromaDB  |  AWS", align="C")

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

    def mono_block(self, lines: list[str]):
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
        y = self.get_y()
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(80, 60, 40)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, text, border="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)


def build() -> None:
    pdf = PDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)

    # ── Cover ──────────────────────────────────────────────────────────────────
    pdf.cover_page()

    # ── Page 2: What is Tara + High-level Architecture ────────────────────────
    pdf.add_page()
    pdf.section_title("1. What is Tara?")
    pdf.body(
        "Tara is a Malayalam-first AI astrology companion. Users ask questions about their "
        "horoscope, daily transits, compatibility, and career in their native language. Tara "
        "responds with warm, grounded guidance - never fear-mongering - backed by classical "
        "Vedic astrology knowledge retrieved via RAG. The product promise is guidance and "
        "comfort, never fear."
    )
    pdf.body(
        "The backend is a FastAPI modular monolith: a single deployable service divided into "
        "12 strongly-bounded modules (+ shared platform) that communicate only through explicit "
        "public service interfaces, never by crossing module boundaries at the database layer."
    )

    pdf.section_title("2. High-level Architecture")
    pdf.mono_block([
        "                     +----------------------------------------------+",
        "  Browser / App  --> |             Tara  FastAPI  Monolith           |",
        "                     |                                               |",
        "                     |  identity   astrology_engine   knowledge      | --> PostgreSQL (RDS)",
        "                     |  chat       tone_safety         content       | --> ChromaDB  (vectors)",
        "                     |  whatsapp   community           commerce      | --> Redis / ElastiCache",
        "                     |  notifications   admin                        |",
        "                     |                                               |",
        "                     |  -- shared platform: events, config, db --    |",
        "                     +----------+-------------------+----------------+",
        "                                |                   |",
        "                         OpenAI API           Ephemeris API",
        "                        (gpt-4o-mini)    WhatsApp BSP / Razorpay",
        "",
        "  Hosting: AWS ECS/Fargate  |  RDS (Postgres)  |  ElastiCache (Redis)  |  S3+CloudFront",
    ])

    # ── Page 3: Data Flow ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3. Request Data Flow - Chat Turn")
    pdf.body("Every user message passes through these steps in strict order:")
    pdf.ln(3)

    pdf.step_box("1", "User sends a message",
                 "Browser POSTs { user_id, messages[] } to  POST /chat/message  over HTTPS.")
    pdf.step_box("2", "Tone Safety Screen  (GUARDRAIL - runs FIRST, always)",
                 "tone_safety.screen(latest_message) checks for distress keywords in English & Malayalam.\n"
                 "If triggered -> stream Tele-MANAS helpline (14416) back immediately and STOP.\n"
                 "No astrology logic runs. No LLM call is made. This path cannot be bypassed.")
    pdf.step_box("3", "Load birth chart  (identity module)",
                 "identity.get_birth_chart(user_id) fetches the user's natal chart from Postgres.\n"
                 "Computed on first run from dob/birth_time/birth_place via the ephemeris API.")
    pdf.step_box("4", "Astrology context  (astrology_engine module)",
                 "astrology_engine.get_transits(now, chart) fetches live planetary positions\n"
                 "from the ephemeris API. Results cached in Redis (TTL = 24 h for daily transits).")
    pdf.step_box("5", "RAG Retrieval  (knowledge module)",
                 "The user question + active transits are embedded (OpenAI text-embedding-3-small).\n"
                 "knowledge.retrieve() queries ChromaDB for the top-k matching astrology chunks\n"
                 "(planet x sign x house interpretations, transit rulebook, porutham tables).")
    pdf.step_box("6", "System prompt assembly  (tone_safety module)",
                 "tone_safety.build_system_prompt() composes the final system prompt:\n"
                 "Tara persona + retrieved chunks + natal chart summary + active guardrails.")
    pdf.step_box("7", "OpenAI streaming call  (chat module)",
                 "chat._stream_from_openai() calls OpenAI chat.completions.create(\n"
                 "  model='gpt-4o-mini', stream=True, messages=[system, ...history, user]\n"
                 ") and yields each token chunk as it arrives.")
    pdf.step_box("8", "Streaming response to browser",
                 "FastAPI StreamingResponse (text/plain; charset=utf-8) pipes the token stream\n"
                 "directly to the browser. The frontend reads via fetch + ReadableStream and\n"
                 "appends each chunk to the chat bubble in real time.")
    pdf.step_box("9", "Async memory extraction  (Celery task)",
                 "After the reply is sent, chat.extract_memory(conversation) runs as a background\n"
                 "Celery task - extracting durable facts/preferences and writing them to the\n"
                 "memories table. This never blocks the user's reply.")

    # ── Page 4: Module Map ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Module Map")
    pdf.body(
        "Each module owns its router, service, schemas, and (where needed) ORM models. "
        "Modules may only call each other's public service.py - never internal files or tables. "
        "Cross-module side effects go through domain events (e.g. chat.crisis_detected)."
    )
    pdf.ln(2)

    modules = [
        ("identity",          "Auth (JWT/OAuth), user profile, birth data capture, geocoding/timezone"),
        ("astrology_engine",  "Natal chart, transits, dasha, porutham; wraps ephemeris API; caches in Redis"),
        ("knowledge",         "ChromaDB-backed RAG store: planet x sign x house chunks, transit rulebook"),
        ("tone_safety",       "Crisis screen (distress -> 14416 + STOP); builds Tara persona system prompt"),
        ("chat",              "Orchestrator: tone_safety -> identity -> transits -> RAG -> gpt-4o-mini stream;\n"
                              "async memory extraction via Celery"),
        ("content",           "Generates daily/weekly readings, panchangam, nakshatraphalam (gpt-4o-mini draft)"),
        ("whatsapp",          "Daily Channel message via BSP; opt-in/opt-out ledger; AI disclosure; human approval"),
        ("community",         "Audio rooms (temple/area/nakshatra), membership, moderation, gifting"),
        ("commerce",          "Subscriptions, paid reports, consult billing, temple pooja booking, Razorpay"),
        ("notifications",     "Push / email / WhatsApp notification dispatch"),
        ("admin",             "Astrologer onboarding, moderation queue, analytics dashboards"),
        ("platform (shared)", "Event bus, config (pydantic-settings), logging, DB access, error types"),
    ]
    for name, desc in modules:
        pdf.kv_row(name, desc)
        pdf.divider()

    # ── Page 5: External API Integrations ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. External API Integrations")
    pdf.ln(2)

    apis = [
        ("OpenAI API",
         "gpt-4o-mini  +  text-embedding-3-small",
         "Chat generation and daily content drafting via gpt-4o-mini (streamed, openai SDK).\n"
         "text-embedding-3-small used for RAG chunk ingestion and query embedding.\n"
         "Note: Malayalam quality must be regression-tested - gpt-4o-mini is noticeably\n"
         "weaker in Malayalam than English. Keep a reviewed prompt/answer set."),
        ("Ephemeris API",
         "Hosted astrology REST API  (Swiss Ephemeris at scale)",
         "Returns planetary positions, nakshatram, tithi, dasha periods, panchanga for a\n"
         "given date/location. Results cached in Redis (TTL = 24 h for daily transits)."),
        ("WhatsApp BSP",
         "Gupshup / Wati / Twilio",
         "Compliant broadcast channel. Opt-in only. Max 3 business-initiated messages/user/24h.\n"
         "First live send requires human approval. Inbound messages route to chat via webhook.\n"
         "No open-ended AI chat on WhatsApp - that lives in the app only."),
        ("Razorpay",
         "Payments & subscriptions",
         "India-standard UPI/card gateway. Human approval required before any payment flow\n"
         "goes live. Refund/cancel logic must exist before subscriptions ship."),
        ("Geocoding API",
         "OpenCage / Google Maps + IANA timezone",
         "Converts city name to lat/lon + timezone for accurate birth-chart calculation.\n"
         "Called once at birth-data capture; result stored in the user's identity record."),
    ]
    for name, model, detail in apis:
        pdf.sub_title(f"{name}  ({model})")
        pdf.body(detail, indent=4)
        pdf.ln(1)

    # ── Page 6: RAG Pipeline ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. RAG Pipeline - Knowledge Retrieval")

    pdf.body(
        "Tara's astrology knowledge is stored as vector embeddings in ChromaDB. When a user "
        "asks a question, the most relevant interpretation chunks are retrieved and injected "
        "into the system prompt before the LLM call. This grounds the reply in real "
        "astrological content rather than the model's general knowledge."
    )
    pdf.ln(3)

    pdf.sub_title("6.1  What is stored in ChromaDB?")
    for item in [
        "Planet x sign x house interpretation texts  (e.g. Saturn in 7th house in Scorpio)",
        "Transit rulebook - how current planetary movements affect each rasi",
        "Porutham (compatibility) tables and scoring rules",
        "Dasha period meanings and life-theme keywords",
        "Frequently asked astrology Q&A (seed corpus)",
    ]:
        pdf.bullet(item)
    pdf.ln(3)

    pdf.sub_title("6.2  Ingestion flow  (offline / Celery background job)")
    pdf.mono_block([
        "  Source texts (Markdown / JSON)",
        "       |",
        "       v",
        "  Chunk splitter  (max 512 tokens, 50-token overlap)",
        "       |",
        "       v",
        "  OpenAI text-embedding-3-small  --> 1536-dim vector",
        "       |",
        "       v",
        "  ChromaDB collection  'tara_knowledge'",
        "       |-- id        : uuid",
        "       |-- embedding : [float x 1536]",
        "       |-- document  : original chunk text",
        "       '-- metadata  : { topic, planet, sign, house, source }",
    ])

    pdf.sub_title("6.3  Retrieval flow  (per chat turn, step 5 of the request flow)")
    pdf.mono_block([
        "  user question + active transits",
        "       |",
        "       v",
        "  Embed with text-embedding-3-small",
        "       |",
        "       v",
        "  ChromaDB.query(embedding, n_results=5)",
        "       |",
        "       v",
        "  Top-k chunks  (cosine similarity)",
        "       |",
        "       v",
        "  Injected into system prompt as 'Knowledge context'",
        "       |",
        "       v",
        "  gpt-4o-mini generates a grounded, cited Malayalam reply",
    ])

    # ── Page 7: AWS Hosting ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. AWS Hosting Architecture")
    pdf.ln(2)

    pdf.mono_block([
        "  Route 53 (DNS)",
        "       |",
        "  CloudFront (CDN) <-- S3 bucket (Next.js web / React Native OTA assets)",
        "       |",
        "  Application Load Balancer",
        "       |",
        "  ECS Fargate  (Tara FastAPI container)     ECS Fargate (Celery workers)",
        "     |               |              |",
        "  RDS (Postgres)  ElastiCache    ChromaDB (ECS sidecar dev / EC2 prod)",
        "     (Multi-AZ)    (Redis 7)",
        "",
        "  Secrets Manager  --> OPENAI_API_KEY, DB creds, BSP keys  (injected at startup)",
        "  ECR              --> Docker image registry",
        "  CloudWatch       --> Logs, metrics, alarms  (alert on crisis-screen hits too)",
    ])
    pdf.ln(2)

    components = [
        ("ECS / Fargate",     "Runs the FastAPI container. Auto-scales on CPU/memory. No server management."),
        ("RDS PostgreSQL",    "Multi-AZ managed Postgres. Users, conversations, commerce, wa_consent, audit."),
        ("ElastiCache Redis", "Ephemeris cache (24 h TTL) + Celery broker and result backend."),
        ("ChromaDB",          "Vector store for RAG. ECS sidecar for dev; self-managed EC2 for prod scale."),
        ("S3 + CloudFront",   "Static assets, React Native OTA updates, Next.js export / marketing site."),
        ("Secrets Manager",   "Rotatable secrets injected as env vars into ECS task at startup."),
        ("CloudWatch",        "Centralized logs and alarms. Include an alarm on crisis-screen fire rate."),
        ("Celery Workers",    "Separate ECS task definition. Runs: daily content job, memory extraction,\n"
                              "knowledge re-embedding, WhatsApp scheduled sends."),
    ]
    for name, desc in components:
        pdf.kv_row(name, desc)
        pdf.divider()

    # ── Page 8: Build Sequence ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Build Sequence (Antigravity / Agent phases)")

    pdf.body(
        "Use the Agent Manager with one manager agent coordinating module-scoped worker agents. "
        "Isolate domains so agents don't conflict. Require human checkpoints on anything irreversible."
    )
    pdf.ln(3)

    phases = [
        ("Phase 0 - Scaffold",
         "Repo, FastAPI modular skeleton (app/modules/*, app/platform/*), Postgres + ChromaDB + "
         "Redis wiring, CI, Dockerfile, AGENTS.md + GUARDRAILS.md. One manager agent."),
        ("Phase 1 - MVP loop (prove demand)",
         "identity: onboarding + birth data capture\n"
         "astrology_engine: natal chart + transits via hosted ephemeris API\n"
         "tone_safety + chat: working AI astrologer with crisis screen wired first\n"
         "content + whatsapp: daily Channel message on Celery/arq schedule"),
        ("Phase 2 - Monetise",
         "commerce: subscriptions, porutham/Jathakam reports, Razorpay integration.\n"
         "Human-astrologer consult handoff. Human approval required before ship."),
        ("Phase 3 - Moat",
         "community: audio rooms with moderation from day one (not after an incident).\n"
         "admin: dashboards, moderation queue, analytics.\n"
         "notifications: push/email pipeline."),
    ]
    for title, detail in phases:
        pdf.sub_title(title)
        pdf.body(detail, indent=4)
        pdf.ln(1)

    pdf.ln(2)
    pdf.sub_title("Agent assignment tips")
    for tip in [
        "One agent per module; declare its file boundary in AGENTS.md.",
        "Run agents in parallel only across orthogonal modules (e.g. knowledge + whatsapp).",
        "Never run two agents in the same module at the same time.",
        "Use scheduled tasks for daily content/WhatsApp job and nightly knowledge re-embedding.",
        "Require human approval for: DB migrations (Alembic), first live WhatsApp send,\n"
        "  commerce/payments, AWS infra changes, any edit to tone_safety or GUARDRAILS.md.",
    ]:
        pdf.bullet(tip)
        pdf.ln(1)

    # ── Page 9: Safety & Hard Guardrails ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. Safety & Hard Guardrails  (GUARDRAILS.md)")
    pdf.body(
        "These constraints are encoded in code and must never be weakened without explicit "
        "human review. If a feature request conflicts with a guardrail, the guardrail wins - "
        "the agent implements the feature in a guardrail-preserving way and flags the tension."
    )
    pdf.ln(3)

    guardrails = [
        ("1.  Crisis screen first",
         "tone_safety.screen() runs BEFORE any astrology or LLM logic on every turn.\n"
         "Distress keywords (English + Malayalam) -> empathetic response + Tele-MANAS 14416 + stop.\n"
         "No astrology, no upsell follows. Cannot be A/B tested away or skipped for latency reasons.\n"
         "Log that the crisis route fired (for review) - not for product analytics."),
        ("2.  No fear-mongering",
         "Never generate code or copy that invents a dosha, predicts misfortune as certain,\n"
         "uses urgency language ('act now'), or links a problem to a paid remedy in the same turn.\n"
         "Reports and results must always present the balanced picture with a no-friction decline."),
        ("3.  Secrets never hardcoded",
         "All API keys and credentials come from env vars / AWS Secrets Manager only.\n"
         "The .env file is gitignored. Never hardcode. Never commit credentials."),
        ("4.  Birth data is sensitive",
         "Birth data never logged in plaintext, never placed in URLs, never in error messages.\n"
         "Cross-module access only through identity's public service interface.\n"
         "Right-to-delete must cascade: charts, conversations, messages, memories, wa_consent."),
        ("5.  WhatsApp opt-in only",
         "Opt-in required before any send; ledger in wa_consent keyed by phone.\n"
         "Hard cap: 3 business-initiated messages/user/24 h (enforced with a counter, not manual).\n"
         "Every proactive send includes a visible opt-out and AI disclosure.\n"
         "No open-ended AI chat on WhatsApp. First live send requires human approval."),
        ("6.  Payments guardrail",
         "All payment flows via Razorpay documented APIs only - no custom card/UPI handling.\n"
         "Price shown must match price charged. Refund/cancel logic ships before subscriptions."),
        ("7.  Community moderation",
         "Every audio room needs a reporting action and at least one designated moderator\n"
         "before it goes live. A code of conduct must be shown on first room join."),
        ("8.  Human approval gates",
         "DB migrations (Alembic), first live WhatsApp send, commerce/payments,\n"
         "AWS infra changes (ECS, RDS, IAM, Secrets Manager), any edit to tone_safety\n"
         "prompts or GUARDRAILS.md - all require explicit human sign-off before execution."),
    ]
    for title, detail in guardrails:
        pdf.sub_title(title)
        pdf.body(detail, indent=4)
        pdf.ln(1)

    pdf.info_box(
        "Rule: When a guardrail and a feature request conflict, the guardrail wins. "
        "Implement the feature in a way that preserves the guardrail and flag the tension "
        "to a human rather than silently relaxing the rule."
    )

    # ── Output ──────────────────────────────────────────────────────────────────
    out = "tara_project_overview.pdf"
    pdf.output(out)
    print(f"PDF written -> {out}  ({len(guardrails)} guardrails, 9 sections)")


if __name__ == "__main__":
    build()
