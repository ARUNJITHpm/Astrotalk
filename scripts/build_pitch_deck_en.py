"""Build Tara_Pitch_Deck_English.pdf -- a startup pitch + marketing deck for
Tara, the Malayalam-first AI astrology companion. Non-technical, for investors,
partners and the founder's own brand/marketing setup. Re-run after edits:

    .venv312/Scripts/python scripts/build_pitch_deck_en.py

Outputs Tara_Pitch_Deck_English.pdf in the project root.

Core PDF fonts are latin-1 only, so a few Malayalam brand words appear
transliterated here; the Malayalam edition (build_pitch_deck_ml.py) carries the
real script.
"""

from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Tara_Pitch_Deck_English.pdf"

# Brand palette (shared with the app + dev guide)
INDIGO = (11, 15, 42)       # deep night sky
GOLD = (232, 182, 76)       # star gold
ACCENT = (196, 90, 59)      # terracotta
INK = (43, 39, 34)
CREAM = (245, 241, 232)
MUTED = (138, 129, 120)
WHITE = (255, 255, 255)
GREEN = (74, 124, 89)
SOFT = (250, 245, 236)
CARD = (248, 244, 236)


class Pitch(FPDF):
    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"Tara  |  Malayalam-first AI Astrology Companion  |  {self.page_no()}",
                  align="C")

    # ---- building blocks -------------------------------------------------

    def slide(self, kicker: str, title: str):
        self.add_page()
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ACCENT)
        self.cell(0, 6, kicker.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*INDIGO)
        self.multi_cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GOLD)
        self.set_line_width(1.1)
        self.line(self.l_margin, self.get_y() + 2, self.l_margin + 26, self.get_y() + 2)
        self.ln(7)

    def lead(self, text: str):
        self.set_font("Helvetica", "", 12.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 6.8, text)
        self.ln(3)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet(self, text: str, bold_lead: str = ""):
        x = self.get_x()
        self.set_x(x + 2)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*ACCENT)
        self.cell(5, 6, chr(183))
        if bold_lead:
            self.set_text_color(*INDIGO)
            self.set_font("Helvetica", "B", 10.5)
            w = self.get_string_width(bold_lead + "  ")
            self.cell(w, 6, bold_lead + "  ")
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 6, text)
        self.set_x(x)
        self.ln(0.6)

    def card(self, title: str, lines: list[str], fill=CARD, tcol=INDIGO):
        pad = 4
        # measure height first
        self.set_font("Helvetica", "", 9.5)
        h = 10 + pad
        for ln_ in lines:
            h += self.get_string_height(ln_, 5.4)
        # never split a card across a page
        if self.get_y() + h > self.page_break_trigger:
            self.add_page()
        self.set_draw_color(*GOLD)
        self.set_fill_color(*fill)
        top = self.get_y()
        self.rect(self.l_margin, top, 190 - self.l_margin, h, "DF")
        self.set_xy(self.l_margin + pad, top + pad)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*tcol)
        self.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for ln_ in lines:
            self.set_x(self.l_margin + pad)
            self.set_font("Helvetica", "", 9.5)
            self.set_text_color(*INK)
            self.multi_cell(190 - self.l_margin - 2 * pad, 5.4, ln_)
        self.set_y(top + h)
        self.ln(4)

    def get_string_height(self, text, line_h):
        # rough: how many wrapped lines this string needs at current width
        max_w = 190 - self.l_margin - 8
        words = text.split()
        if not words:
            return line_h
        lines, cur = 1, ""
        for w in words:
            trial = (cur + " " + w).strip()
            if self.get_string_width(trial) > max_w:
                lines += 1
                cur = w
            else:
                cur = trial
        return lines * line_h

    def stat(self, x, w, big: str, label: str):
        self.set_xy(x, self.get_y())
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*ACCENT)
        self.cell(w, 9, big, align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_xy(x, self.get_y())
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*MUTED)
        self.multi_cell(w, 4.4, label, align="C")

    def callout(self, text: str):
        self.set_fill_color(*INDIGO)
        self.set_text_color(*CREAM)
        self.set_font("Helvetica", "I", 10.5)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6.4, text, fill=True)
        self.ln(3)


def cover(pdf: Pitch):
    pdf.add_page()
    pdf.set_fill_color(*INDIGO)
    pdf.rect(0, 0, 210, 297, "F")
    # gold star band
    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 138, 210, 3, "F")

    pdf.set_text_color(*GOLD)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_y(48)
    pdf.cell(0, 8, "*", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 58)
    pdf.set_y(60)
    pdf.cell(0, 22, "TARA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 10, "(Thaara)  -  the guiding star", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 9, "The Malayalam-first AI astrology companion", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(200, 196, 214)
    pdf.cell(0, 8, "Astrology that speaks your language - warm, grounded, always with you.",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(250)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 7, "Startup Pitch & Marketing Playbook", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 146, 168)
    pdf.cell(0, 6, f"Prepared {date.today().strftime('%B %Y')}", align="C")


def build():
    pdf = Pitch(format="A4")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(True, margin=18)

    cover(pdf)

    # 1. Elevator pitch ----------------------------------------------------
    pdf.slide("The one-liner", "Astrology in Malayalam, that actually cares")
    pdf.lead(
        "Tara is a Malayalam-first AI astrology companion. It answers life's questions the way a "
        "trusted family jyotishan would - in warm, simple Malayalam, grounded in a real Vedic "
        "chart, never in fear. Chat any time, get a daily panchangam, check marriage porutham, ask "
        "a prashnam, find the right temple remedy - all in the language people actually think and "
        "pray in."
    )
    pdf.card("In one sentence", [
        "Tara is 'Astrotalk for Malayalis' - but AI-first, Malayalam-native, and built on a real "
        "astronomy engine with hard safety rails, so it scales to millions at near-zero marginal "
        "cost while staying kind and trustworthy.",
    ])
    pdf.ln(1)
    y = pdf.get_y()
    third = (190 - pdf.l_margin) / 3
    pdf.stat(pdf.l_margin, third, "38M+", "Malayalam speakers worldwide (Kerala + Gulf + global diaspora)")
    pdf.stat(pdf.l_margin + third, third, "#1", "cultural habit: astrology touches marriage, career, naming, housewarming")
    pdf.stat(pdf.l_margin + 2 * third, third, "~Rs 0", "marginal cost per AI conversation vs. a human consultation")

    # 2. Problem -----------------------------------------------------------
    pdf.slide("The problem", "Trusted astrology doesn't scale - and the web version is scary")
    pdf.bullet("A good family astrologer is scarce, booked out, and expensive. Most people get one "
               "rushed consultation a year, if that.", "Access:")
    pdf.bullet("English-first astrology apps feel foreign. Nuance, emotion and the exact Kerala "
               "terms (nakshatram, porutham, dosham) get lost in translation.", "Language:")
    pdf.bullet("Much of online astrology runs on fear - curses, doom, 'pay for this pooja or "
               "else'. It preys on anxiety instead of easing it.", "Trust:")
    pdf.bullet("Generic chatbots hallucinate placements. If the chart is wrong, the guidance is "
               "worthless - and no one can tell.", "Accuracy:")
    pdf.ln(2)
    pdf.callout(
        "The gap: something as available as a chatbot, as personal as your own family astrologer, "
        "as safe as a good counsellor - and fluent in Malayalam."
    )

    # 3. Solution ----------------------------------------------------------
    pdf.slide("The solution", "Meet Tara")
    pdf.body(
        "Tara pairs a real Vedic astronomy engine with a Malayalam-native AI voice and a strict "
        "safety layer. The engine COMPUTES the facts (never guesses), the AI NARRATES them warmly "
        "in Malayalam, and a guardrail SCREENS every reply for fear, false urgency and "
        "pay-to-be-safe remedies before it ever reaches the user."
    )
    pdf.card("What makes it different (the moat)", [
        "Malayalam-native, not translated - tuned on an Indic-first model that scored 4.79/5 for "
        "Malayalam fluency in our own evals (vs 3.00 for a mainstream model).",
        "Real astronomy - a Swiss Ephemeris engine computes the chart, dashas, doshas, transits, "
        "porutham and prashnam. The AI never invents a placement.",
        "Safety by design - a crisis screen runs FIRST, and every answer is checked for "
        "fear/urgency/payment-linked remedies. Distress conversations are never stored.",
        "Culturally native - temple remedies, vazhipadu, muhurtham, the ten poruthams - the "
        "things a Malayali actually asks about.",
    ])

    # 4. Product features --------------------------------------------------
    pdf.slide("The product", "One companion, many daily reasons to open it")
    pdf.body("Tara is already far more than a chatbot. Everything below is built and running today:")
    pdf.card("Ask & understand", [
        "Chat in Malayalam, English or Manglish - grounded answers tied to your real chart.",
        "Porutham - ten-match marriage compatibility from both partners' stars.",
        "Prashnam - Kerala horary answers (betel-leaf, square, number).",
        "Temple remedies - the right deity and temple for your concern, never fear-driven.",
    ], fill=SOFT)
    pdf.card("Come back every day", [
        "The Feed - a daily home: today's panchangam, fresh posts, reactions, check-in streaks "
        "and polls, in a mobile app-like layout.",
        "Content Studio - reels, weekly astro-news, festival specials, nakshatra episodes and "
        "myth-busters, drafted daily and safety-screened before publishing.",
        "Share cards - beautiful, shareable star cards for WhatsApp status and Instagram.",
    ], fill=SOFT)
    pdf.card("Grow & earn", [
        "Referral loop - invite friends, unlock a free premium report.",
        "Temple partnerships - a QR poster in the temple opens that temple's own live page.",
        "Premium Jathakam report - a paid, generated PDF (launch product).",
        "For astrologers (B2B) - a branded Tara with booking, billing and a client CRM.",
    ], fill=SOFT)

    # 5. Market ------------------------------------------------------------
    pdf.slide("The opportunity", "A devoted audience, underserved online")
    pdf.bullet("38M+ Malayalam speakers - Kerala plus a large, high-earning Gulf and global "
               "diaspora who stay deeply connected to home rituals.", "Who:")
    pdf.bullet("Astrology is woven into marriage, careers, naming, housewarming, travel and "
               "health decisions - a recurring need, not a one-off.", "Why sticky:")
    pdf.bullet("Indian online astrology is already a multi-hundred-crore market led by "
               "English/Hindi players. Malayalam is wide open and defensible.", "Timing:")
    pdf.bullet("AI just made 'a personal astrologer for everyone' possible at near-zero marginal "
               "cost for the first time.", "Tailwind:")
    pdf.ln(1)
    pdf.callout(
        "Illustrative funnel: 1% of 38M = 380,000 reachable users. At a modest 3-5% paying for "
        "reports/consults at Rs 199-999, that is a multi-crore annual opportunity from Malayalam "
        "alone - before B2B and other languages."
    )
    pdf.body("(Figures above are planning assumptions to show the shape of the opportunity, not a forecast.)")

    # 6. Business model ----------------------------------------------------
    pdf.slide("How it makes money", "Four revenue streams, one platform")
    pdf.card("1. Premium reports  (live product, launch first)", [
        "A generated multi-page Jathakam report at Rs 199. Zero human labour, instant delivery, "
        "high margin. The referral reward is a free one - so growth and revenue share an engine.",
    ], fill=SOFT)
    pdf.card("2. Consultations marketplace  (built)", [
        "Book a real human astrologer through Tara; platform takes a commission. AI handles the "
        "everyday questions; humans handle the high-value ones.",
    ], fill=SOFT)
    pdf.card("3. B2B SaaS for astrologers  (built)", [
        "Astrologers get a branded Tara with booking, billing and a client CRM on a monthly "
        "Starter/Pro subscription - predictable recurring revenue.",
    ], fill=SOFT)
    pdf.card("4. Temple & brand partnerships  (built)", [
        "Temples get a free digital page + QR poster; a distribution channel that can carry "
        "sponsored festival features and premium listings later.",
    ], fill=SOFT)

    # 7. Go-to-market ------------------------------------------------------
    pdf.slide("Go to market", "Content first, community always, offline where it counts")
    pdf.body(
        "Tara's marketing engine is the same engine that runs the product - the Content Studio. "
        "Every day it drafts shareable content; every share is an ad; every happy user is a "
        "referrer. Growth compounds instead of being bought."
    )
    pdf.bullet("Daily short-form video: Instagram Reels, YouTube Shorts and a WhatsApp channel - "
               "nakshatra-of-the-day, festival specials, gentle myth-busting. This is the top of "
               "the funnel.", "Content:")
    pdf.bullet("A WhatsApp channel + daily panchangam message is the habit loop - people open it "
               "with their morning coffee.", "WhatsApp:")
    pdf.bullet("QR posters in partner temples turn real-world trust and footfall into installs - "
               "a channel no English app can copy.", "Temples:")
    pdf.bullet("Every reading is a one-tap branded share; every invite that converts unlocks a "
               "reward. Users become the growth team.", "Referral:")
    pdf.bullet("Onboard local astrologers and micro-influencers with the branded B2B product - "
               "they bring their own audience.", "Creators:")

    # 8. The content engine ------------------------------------------------
    pdf.slide("The marketing machine", "How one operator runs a daily media brand")
    pdf.body(
        "From a single owner console, one person runs what would normally need a content team:"
    )
    pdf.bullet("Generate - one click drafts a reel script, weekly astro-news, a festival special "
               "or a myth-buster from today's panchangam.", "1.")
    pdf.bullet("Review - every draft is auto-screened for fear/urgency/payment language, then the "
               "owner approves it. Nothing risky goes out.", "2.")
    pdf.bullet("Publish - approved posts appear on the Feed and are ready to cross-post to "
               "Instagram, YouTube and WhatsApp.", "3.")
    pdf.bullet("Measure - the console shows content, polls, referral funnel and revenue in one "
               "place.", "4.")
    pdf.ln(1)
    pdf.callout(
        "Result: a daily Malayalam astrology media brand - reels, news, festivals, polls - run by "
        "one person, feeding both engagement and the top of the sales funnel for free."
    )

    # 9. Traction ----------------------------------------------------------
    pdf.slide("Traction", "This is built, not a slide-ware idea")
    pdf.card("Working today (in code, tested)", [
        "Real Vedic engine: charts, vargas, dashas, doshas, transits, panchangam, porutham, prashnam.",
        "Malayalam AI chat with memory, crisis screening and per-reply cost accounting.",
        "Hybrid RAG over 2,451 astrology knowledge chunks for grounded answers.",
        "User Feed, Content Studio, share cards, polls, streaks and the referral loop.",
        "Temple partner microsites + QR posters; consultation booking; B2B CRM/billing.",
        "Premium report generation and the full commerce flow (running in safe mock mode).",
        "An owner console that ties every growth feature together.",
    ], fill=SOFT, tcol=GREEN)
    pdf.body(
        "What is intentionally still switched off: real WhatsApp sending, live payment capture and "
        "cloud media storage - each just needs an external account and a go-live decision. The "
        "code is done; these are business switches, not build work."
    )

    # 10. Brand & identity kit --------------------------------------------
    pdf.slide("Brand kit", "Ready-to-use identity for every signup form")
    pdf.body(
        "Copy-paste blocks for registering the business, social accounts and email - so every "
        "touchpoint says the same thing."
    )
    pdf.card("Name & tagline", [
        "Name:  Tara  (Malayalam: Thaara - 'star')",
        "Tagline:  Astrology that speaks your language.",
        "Alt tagline:  Your Malayalam astrology companion.",
        "Category:  AI astrology / spiritual wellness app.",
    ])
    pdf.card("Descriptions (paste into bios & app stores)", [
        "Short (bio, <=80 chars):  Malayalam-first AI astrology companion. Warm, grounded, always with you.",
        "Medium (~150 chars):  Tara is a Malayalam-first AI astrology companion - daily panchangam, "
        "porutham, prashnam and temple remedies in warm, simple Malayalam. Grounded, never fear-based.",
        "Long (about section):  Tara brings trusted Kerala jyotisham to everyone, in Malayalam. "
        "Chat any time, get your daily panchangam, check marriage porutham, ask a prashnam and find "
        "the right temple remedy - all grounded in a real Vedic chart and guided by strict, caring "
        "safety rules. Astrology that eases anxiety instead of feeding it.",
    ])
    pdf.card("Suggested business email addresses", [
        "hello@ - general & press first point of contact.",
        "support@ - user help and account questions.",
        "partners@ - temples, astrologers and brand partnerships.",
        "founders@ - investors and business enquiries.",
        "(Set these up on a business email suite once the domain is registered; use a professional "
        "domain, not a personal Gmail, on all public material.)",
    ])

    # 11. Roadmap & ask ----------------------------------------------------
    pdf.slide("Roadmap & the ask", "From built to broad")
    pdf.bullet("Go live on the three external switches (WhatsApp business, payments, storage) and "
               "launch the premium report.", "Now:")
    pdf.bullet("Turn on the daily content engine across Instagram, YouTube and the WhatsApp "
               "channel; sign the first 10 partner temples.", "0-3 months:")
    pdf.bullet("Onboard the first cohort of B2B astrologers; add TTS so reels get Malayalam voice; "
               "grow the referral loop.", "3-6 months:")
    pdf.bullet("Expand to Tamil and Kannada on the same engine - the hard part (a safe, grounded, "
               "Indic-native astrology platform) is already built.", "6-12 months:")
    pdf.ln(2)
    pdf.callout(
        "The ask: partners, pilot temples and early believers to help take a finished product to "
        "its audience. The technology risk is behind us - this is now a distribution story."
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 8, "Tara - the guiding star, now in everyone's pocket.", align="C")

    pdf.output(str(OUT))
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
