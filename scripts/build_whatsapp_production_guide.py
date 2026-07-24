"""Build docs/WhatsApp_Cloud_API_Production_Guide.pdf -- a step-by-step guide to take
Nitara's WhatsApp Cloud API from the free TEST number to a PRODUCTION number that
real users can message.

Why this exists: the first setup was done on an old/fake Facebook account + an app
Meta has now restricted ("you can't use this app for..."). You cannot pass Business
Verification on a throwaway identity, so production needs a clean, real setup. This
guide lists every screen, every field to fill, realistic wait times, and the
test->production differences.

Re-run after edits:
    python scripts/build_whatsapp_production_guide.py

Outputs docs/WhatsApp_Cloud_API_Production_Guide.pdf. Core PDF fonts
are latin-1 only, so this is plain ASCII (no emoji / non-latin script).
"""

from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "WhatsApp_Cloud_API_Production_Guide.pdf"

INDIGO = (11, 15, 42)
GOLD = (232, 182, 76)
ACCENT = (196, 90, 59)
INK = (43, 39, 34)
CREAM = (245, 241, 232)
MUTED = (138, 129, 120)
WHITE = (255, 255, 255)
GREEN = (74, 124, 89)
CARD = (248, 244, 236)
BLUEGREY = (232, 236, 244)


class Guide(FPDF):
    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"Nitara  |  WhatsApp Cloud API - Production Setup Guide  |  {self.page_no()}",
                  align="C")

    def h1(self, kicker: str, title: str):
        self.add_page()
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ACCENT)
        self.cell(0, 6, kicker.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*INDIGO)
        self.multi_cell(0, 9, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GOLD)
        self.set_line_width(1.1)
        self.line(self.l_margin, self.get_y() + 2, self.l_margin + 26, self.get_y() + 2)
        self.ln(6)

    def h2(self, text: str):
        if self.get_y() > 250:
            self.add_page()
        self.ln(1)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*ACCENT)
        self.multi_cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.8, text)
        self.ln(1.5)

    def bullet(self, text: str, lead: str = ""):
        x = self.get_x()
        self.set_x(x + 2)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*ACCENT)
        self.cell(5, 5.6, chr(183))
        if lead:
            self.set_text_color(*INDIGO)
            self.set_font("Helvetica", "B", 10.5)
            w = self.get_string_width(lead + "  ")
            self.cell(w, 5.6, lead + "  ")
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.6, text)
        self.set_x(x)
        self.ln(0.4)

    def step(self, n: int, title: str, wait: str):
        if self.get_y() > 255:
            self.add_page()
        self.ln(1)
        self.set_fill_color(*INDIGO)
        self.set_text_color(*GOLD)
        self.set_font("Helvetica", "B", 12)
        self.cell(9, 8, str(n), align="C", fill=True)
        self.set_x(self.l_margin + 11)
        self.set_text_color(*INDIGO)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 11)
        self.set_font("Helvetica", "I", 8.5)
        self.set_text_color(*GREEN)
        self.cell(0, 4.5, "Typical time: " + wait, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)

    def field(self, name: str, guidance: str):
        x = self.get_x()
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*INDIGO)
        self.set_x(x + 3)
        self.multi_cell(52, 5.2, name)
        y_after_name = self.get_y()
        self.set_xy(x + 3 + 52, y_after_name - 5.2 if name else self.get_y())
        # simpler: print guidance on its own indented line block
        self.set_x(x + 3)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.0, "   " + guidance)
        self.set_x(x)
        self.ln(0.8)

    def kv(self, label: str, value: str):
        x = self.get_x()
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*INDIGO)
        self.set_x(x + 3)
        self.cell(48, 5.4, label)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.4, value)
        self.set_x(x)

    def callout(self, text: str, fill=INDIGO, tcol=CREAM):
        self.ln(1)
        self.set_fill_color(*fill)
        self.set_text_color(*tcol)
        self.set_font("Helvetica", "I", 10)
        self.set_x(self.l_margin)
        self.multi_cell(0, 5.8, text, fill=True)
        self.ln(2)

    def card(self, title: str, lines: list[str], fill=CARD, tcol=INDIGO):
        pad = 4
        self.set_font("Helvetica", "", 9.3)
        h = 9 + pad
        for ln_ in lines:
            h += self._sh(ln_, 5.0)
        if self.get_y() + h > self.page_break_trigger:
            self.add_page()
        self.set_draw_color(*GOLD)
        self.set_fill_color(*fill)
        top = self.get_y()
        self.rect(self.l_margin, top, 190 - self.l_margin, h, "DF")
        self.set_xy(self.l_margin + pad, top + pad)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*tcol)
        self.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for ln_ in lines:
            self.set_x(self.l_margin + pad)
            self.set_font("Helvetica", "", 9.3)
            self.set_text_color(*INK)
            self.multi_cell(190 - self.l_margin - 2 * pad, 5.0, ln_)
        self.set_y(top + h)
        self.ln(3)

    def _sh(self, text, line_h):
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


def build():
    pdf = Guide()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(18, 16, 18)

    # ---- Cover ----
    pdf.add_page()
    pdf.set_fill_color(*INDIGO)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 8, "NITARA  -  WHATSAPP CLOUD API", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(*CREAM)
    pdf.multi_cell(0, 13, "From Test Number\nto Production", align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*WHITE)
    pdf.multi_cell(0, 6.5,
                   "A step-by-step setup guide: every screen, every field to fill,\n"
                   "realistic wait times, and how to go live the proper way on a\n"
                   "real, verified business account.", align="C")
    pdf.ln(12)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.6)
    pdf.line(70, pdf.get_y(), 140, pdf.get_y())
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, f"Prepared {date.today():%d %B %Y}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ---- 1. Why start over ----
    pdf.h1("Read this first", "Why the current app is blocked")
    pdf.body(
        "The test setup works technically -- inbound messages reach the app and replies "
        "are generated. But the app + Facebook account it was built on cannot be taken to "
        "production. Meta's message ('you can't use this app for...') means the app / "
        "business is flagged.")
    pdf.h2("The root cause")
    pdf.bullet("was created on an old, throwaway / fake Facebook account.", "The app")
    pdf.bullet(
        "requires Business Verification, and verification needs a REAL identity and "
        "real business details that match official documents. A fake account can never "
        "pass it -- so the app stays capped forever.", "Production")
    pdf.bullet(
        "the old app was reused for testing and may already carry a policy strike.",
        "On top of that,")
    pdf.callout(
        "Bottom line: do NOT try to 'unlock' the old app. Start clean on a real "
        "Facebook account tied to your real name / business. Everything below assumes a "
        "fresh, legitimate setup. Your CODE and server config do not change -- you only "
        "swap in the new token, phone number ID, and WABA ID at the end.")

    pdf.h2("Good news: what you can keep")
    pdf.bullet("The app code, HF Space, and all fixes are done and stay exactly as-is.", "Nothing to rebuild.")
    pdf.bullet(
        "Only three values change at the very end: META_ACCESS_TOKEN, "
        "META_PHONE_NUMBER_ID, META_WABA_ID (+ re-point the webhook to the new app).",
        "Swap-in only.")

    # ---- 2. The proper pipeline ----
    pdf.h1("The pipeline", "The proper path, in order")
    pdf.body(
        "Do these in sequence. Most steps are instant; the real waiting is Business "
        "Verification and the Display Name review. Total realistic time to go live: "
        "1-5 business days, almost all of it waiting on verification.")

    pdf.step(1, "Use a REAL personal Facebook account", "have it ready")
    pdf.body("Log in as your real self (real name). This is the human owner behind the "
             "business. If your real account is new, use it normally for a few days first "
             "so it looks legitimate.")

    pdf.step(2, "Create a Meta Business Portfolio", "5-10 minutes")
    pdf.body("At business.facebook.com -> Settings -> Business Portfolio (formerly "
             "'Business Manager'). Enter real, consistent business details (see the field "
             "list in the next section). This is the container that owns the app, the "
             "WhatsApp account, and the number.")

    pdf.step(3, "Complete Business Verification", "10 min to 2 business days (up to ~2 weeks worst case)")
    pdf.body("Business Settings -> Security Center (or Business Info) -> Start Verification. "
             "Meta checks your business is real via documents and/or a phone/email/domain "
             "check. THIS is the gating step -- the token is useless for production until "
             "this passes. Submit accurate documents that match your business name and "
             "address exactly.")

    pdf.step(4, "Create a new App + add WhatsApp", "10 minutes")
    pdf.body("developers.facebook.com -> Create App -> type 'Business' -> attach it to the "
             "verified Business Portfolio. Add the WhatsApp product. Give the app a clean, "
             "non-trademark name (not 'test', not a name you don't own).")

    pdf.step(5, "Register a DEDICATED production phone number", "10-20 minutes")
    pdf.body("WhatsApp -> API Setup -> add phone number. Use a NEW number that is NOT "
             "active on the regular WhatsApp or WhatsApp Business app. Registering a number "
             "that already has WhatsApp DELETES that WhatsApp account. Verify via the SMS / "
             "voice code. Never use your personal 9400.../8089... numbers.")

    pdf.step(6, "Set + submit the Display Name", "minutes to 48 hours")
    pdf.body("This is the business name users see. Meta reviews it against the Display Name "
             "guidelines. With a verified business it is often approved fast. Must relate to "
             "your brand (e.g. 'Nitara' or 'Nitara Astrology').")

    pdf.step(7, "Generate a permanent System User token", "5 minutes")
    pdf.body("Business Settings -> Users -> System Users -> Add ('Admin'). Assign the app "
             "and the WhatsApp Business Account, then Generate Token with the three "
             "permissions: whatsapp_business_messaging, whatsapp_business_management, "
             "whatsapp_business_manage_events. Set expiry to 'Never'. Copy it once.")

    pdf.step(8, "Swap the 3 values into the server + go live", "10 minutes")
    pdf.body("Update META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_WABA_ID (+ META_APP_SECRET, "
             "META_WEBHOOK_VERIFY_TOKEN) on the host, re-point the webhook callback URL to the "
             "new app, subscribe the app to the new WABA, and subscribe the 'messages' field. "
             "Send a test message. Done.")

    # ---- 3. Exactly what to fill ----
    pdf.h1("Field by field", "Exactly what to fill in everywhere")
    pdf.body("Keep every value consistent across all screens -- Meta cross-checks the "
             "business name, address and website during verification. Inconsistent details "
             "are the #1 reason verification fails.")

    pdf.h2("A. Business Portfolio (business.facebook.com)")
    pdf.field("Business name", "Your legal / registered business name. If a sole proprietor, "
              "use your real full name or a registered trade name. Must match documents.")
    pdf.field("Legal business name", "Exactly as on your registration / tax / utility document.")
    pdf.field("Business email", "A domain or professional email you can receive mail at (used for a verification code).")
    pdf.field("Business phone", "A reachable phone (can differ from the WhatsApp number).")
    pdf.field("Business website", "A live website or a strong social/landing page that shows the business. "
              "Have one ready -- verification is smoother with a matching domain.")
    pdf.field("Business address", "Real, complete address that matches your documents.")
    pdf.field("Country / currency", "Your operating country (e.g. India / INR).")

    pdf.h2("B. Business Verification documents (any that match the name+address)")
    pdf.bullet("Business registration / incorporation certificate, OR", "")
    pdf.bullet("GST / tax registration, OR", "")
    pdf.bullet("A utility bill / bank statement in the business name, OR", "")
    pdf.bullet("For an individual/sole prop: government ID + a document tying you to the business.", "")
    pdf.callout("Tip: the name + address on the document must match the Business Portfolio "
                "EXACTLY (spelling, abbreviations, everything). Mismatches cause rejection.",
                fill=BLUEGREY, tcol=INDIGO)

    pdf.h2("C. App (developers.facebook.com)")
    pdf.field("App name", "A clean brand name you own, e.g. 'Nitara'. Do NOT include 'WhatsApp', "
              "'FB', 'Insta', 'test', or a brand you don't own -- app names are screened.")
    pdf.field("App contact email", "A monitored email.")
    pdf.field("Business Portfolio", "Select your VERIFIED portfolio from step 2-3.")
    pdf.field("Privacy Policy URL", "Required. A hosted privacy policy page (can be simple). "
              "e.g. https://your-site/privacy")
    pdf.field("Terms of Service URL", "Recommended. A hosted terms page.")
    pdf.field("Category", "Pick the closest, e.g. 'Messaging' / 'Utilities & productivity'.")
    pdf.field("App icon", "A simple square logo (helps trust; optional for API-only use).")

    pdf.h2("D. WhatsApp Business Profile (what users see in the chat)")
    pdf.field("Display name", "The name shown to users. e.g. 'Nitara' or 'Nitara Astrology'. "
              "Must follow Display Name guidelines and relate to the brand.")
    pdf.field("Category", "e.g. 'Professional Services' or 'Personal Blog'.")
    pdf.field("Description", "One or two lines on what the service does. e.g. 'Malayalam-first AI "
              "astrology companion - personalised readings, panchangam, and guidance on WhatsApp.'")
    pdf.field("About text", "Short status line, e.g. 'Ask me anything about your stars.'")
    pdf.field("Profile photo", "Your logo (square).")
    pdf.field("Business email / website / address", "Same consistent details as the portfolio.")

    pdf.h2("E. The dedicated production number")
    pdf.field("Phone number", "A NEW SIM / number NOT on any WhatsApp app. Can receive SMS or a call.")
    pdf.field("Two-step PIN", "Set a 6-digit registration PIN when prompted; store it safely -- "
              "you need it to re-register the number.")

    # ---- 4. Timelines ----
    pdf.h1("Timelines", "How long the token really takes")
    pdf.body("The token itself is generated in minutes. What you actually wait on is Business "
             "Verification and the Display Name review. Everything else is instant. Below are "
             "typical ranges -- Meta does not publish hard SLAs and times vary by region and "
             "document quality.")

    pdf.card("Instant / minutes (no waiting)", [
        "- Personal FB account ready: immediate",
        "- Create Business Portfolio: 5-10 min",
        "- Create app + add WhatsApp: 10 min",
        "- Register production number: 10-20 min",
        "- Generate permanent System User token: 5 min",
        "- Swap values into the server + webhook: 10 min",
    ])
    pdf.card("The real waits (the gating steps)", [
        "- Business Verification: usually a few hours to 2 business days. Can be up to "
        "~2 weeks if a document is unclear or an appeal is needed.",
        "- Display Name review: minutes to 48 hours (often fast once the business is verified).",
        "- Messaging-limit tier upgrades: automatic over days of good-quality sending.",
    ], fill=BLUEGREY)
    pdf.callout(
        "Plan for 1-5 business days end to end, dominated by Business Verification. Start "
        "verification FIRST (step 3) so it runs in the background while you do everything else. "
        "You can build the app, register the number, and even test on the free test number "
        "WHILE verification is pending.")

    # ---- 5. Test vs Production ----
    pdf.h1("Test vs Production", "What actually changes when you go live")
    pdf.card("TEST number (what you have now)", [
        "- Meta-owned US number (+1 555...). Not your brand.",
        "- Can message ONLY up to 5 pre-approved recipients.",
        "- ~250 business-initiated conversations / day.",
        "- No business verification, no display name needed. Instant.",
        "- Good for: proving the pipeline (done).",
    ])
    pdf.card("PRODUCTION number (the goal)", [
        "- Your own dedicated number + approved display name.",
        "- Can message ANY user who messages you or opts in.",
        "- Starts at 1,000 unique customers / 24h, auto-scales to 10K, 100K, unlimited.",
        "- Requires: verified business + approved display name + registered number.",
        "- Good for: real users.",
    ], fill=BLUEGREY)

    pdf.h2("Messaging limit tiers (production, auto-scaling)")
    pdf.bullet("unverified business is capped at 250 unique customers / 24h.", "Before verification:")
    pdf.bullet("1,000 -> 10,000 -> 100,000 -> unlimited. Meta raises the tier automatically as "
               "you send more with a good Quality Rating (green).", "After verification:")
    pdf.bullet("keep replies helpful and wanted; users blocking/reporting you drops the Quality "
               "Rating and can freeze the tier.", "Protect quality:")

    # ---- 6. Policy do's and don'ts ----
    pdf.h1("Stay compliant", "Rules that keep the number alive")
    pdf.bullet("Only message people who messaged you first or explicitly opted in.", "Opt-in:")
    pdf.bullet("Free-form replies are allowed only within 24h of the user's last message. Outside "
               "that window you must use a pre-approved message template.", "24-hour window:")
    pdf.bullet("Proactive/daily messages (outside 24h) need an approved Message Template. Submit "
               "these under WhatsApp Manager -> Message Templates.", "Templates:")
    pdf.bullet("Keep the AI-assistant disclosure in messages (already handled in code).", "Disclosure:")
    pdf.bullet("No spam, no bulk cold outreach, no prohibited content -- these get numbers banned "
               "fast and are hard to appeal.", "Never:")

    # ---- 7. Final checklist ----
    pdf.h1("Checklist", "Your go-live checklist")
    items = [
        "Real personal Facebook account ready (real identity).",
        "Business Portfolio created with real, consistent details.",
        "Business Verification SUBMITTED (do this first - it's the long pole).",
        "Verification documents match the business name + address exactly.",
        "New Business-type app created and attached to the verified portfolio.",
        "Privacy Policy URL + Terms URL hosted and added to the app.",
        "WhatsApp product added; Display Name submitted and approved.",
        "Dedicated production number (NOT on any WhatsApp app) registered + PIN saved.",
        "Permanent System User token generated (Never expires, 3 WA permissions).",
        "Server updated: META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_WABA_ID, "
        "META_APP_SECRET, META_WEBHOOK_VERIFY_TOKEN.",
        "Webhook callback URL re-pointed to the new app + verify token matches.",
        "App subscribed to the new WABA; 'messages' field subscribed.",
        "Test send + test inbound reply confirmed on the production number.",
        "Old/flagged app + fake account abandoned (not reused).",
    ]
    for it in items:
        pdf.bullet(it)

    pdf.callout(
        "Reminder for the current test setup: rotate the permanent token you already "
        "generated (it was shared in chat) and shut down the unused Render WAHA instance. "
        "Separately, sending from the HF free Space has shown unreliable connectivity to "
        "graph.facebook.com; consider a Cloudflare Worker proxy or a sturdier host before "
        "real users rely on it.",
        fill=ACCENT, tcol=WHITE)

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
