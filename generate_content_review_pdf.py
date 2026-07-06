"""Generate Tara_Content_Review.pdf - a part-by-part pack of EVERY piece of
astrological/devotional content in the app, for a qualified Kerala astrologer
(and, for Part 7, a clinician) to actually read and sign off on. Run once:

    vinimon/Scripts/python generate_content_review_pdf.py

Outputs Tara_Content_Review.pdf in the project root.

Unlike generate_dev_guide_pdf.py, this document renders Malayalam script
natively (Windows' bundled Nirmala UI font + HarfBuzz shaping via uharfbuzz),
because the primary reader is expected to read Malayalam.

Content is pulled LIVE from the actual data modules (not retyped), so this
document always matches what ships. See NEEDS_ASTROLOGER.md for the running
status note: every `reviewed` flag was bulk-set to True to unblock other work
-- none of this has actually been checked yet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.modules.astrology_engine import doshas as dosha_mod
from app.modules.astrology_engine import porutham as por
from app.modules.astrology_engine import prashnam as prashnam_mod
from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS, RASIS
from app.modules.knowledge.seed_data import SEED_CHUNKS, _LAGNA_PROFILES, _NAKSHATRA_PROFILES
from app.modules.temples.remedy_map import (
    CONCERN_DEITIES,
    DEITIES,
    DISTRICTS,
    DOSHA_DEITIES,
    GRAHA_DEITIES,
)
from app.modules.temples.seed_data import SEED_TEMPLES
from app.modules.tone_safety import crisis_classifier as cc

ACCENT = (196, 90, 59)
DARK = (44, 38, 34)
LIGHT = (244, 241, 234)
MUTED = (138, 129, 120)
WHITE = (255, 255, 255)
BLACK = (43, 39, 34)
AMBER = (181, 130, 30)
RED = (168, 68, 60)
NIRMALA = r"C:\Windows\Fonts\Nirmala.ttc"

# English/alias lookups keyed by the Malayalam string the engine emits, so
# tables can show both scripts.
NAK_ALIAS = {ml: alias for ml, alias, _ in _NAKSHATRA_PROFILES}
RASI_ALIAS = {ml: alias.split(" (")[0] if " (" in alias else alias for ml, alias, _ in _LAGNA_PROFILES}


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Tara  |  Content Review Pack  |  Page {self.page_no()}", align="C")

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
        self.cell(0, 10, "Content Review Pack", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(28)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "Every chunk, table, and rule - for sign-off", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(4)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(190, 180, 168)
        self.cell(0, 7, "Porutham tables, dosha/prashnam rules, the knowledge corpus, temples,", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 7, "remedy maps, and the crisis keyword screen - organised part by part.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(230)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(163, 153, 140)
        self.cell(0, 8, "Status:", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "reviewed=True is a bulk placeholder - nothing here is astrologer-signed-off yet", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(260)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "Generated live from the current codebase. See NEEDS_ASTROLOGER.md for the workflow.", align="C")

    def part_title(self, num: str, text: str):
        self.add_page()
        self.set_fill_color(*ACCENT)
        self.rect(self.l_margin, self.get_y(), 4, 10, "F")
        self.set_x(self.l_margin + 7)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*DARK)
        self.cell(0, 10, f"Part {num}.  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def sub_title(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ACCENT)
        self.set_x(self.l_margin)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Nirmala", "", 10)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Nirmala", "", 10)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin + 4)
        self.multi_cell(0, 5.5, f"-  {text}")

    def info_box(self, text: str):
        self.set_fill_color(240, 235, 226)
        self.set_draw_color(*ACCENT)
        self.set_font("Nirmala", "", 9.5)
        self.set_text_color(80, 60, 40)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, text, border="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def warn_box(self, text: str):
        self.set_fill_color(248, 236, 214)
        self.set_draw_color(*AMBER)
        self.set_font("Nirmala", "", 9.5)
        self.set_text_color(110, 80, 20)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, text, border="L", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def entry(self, label: str, text: str):
        self.set_font("Nirmala", "B", 8)
        self.set_text_color(*ACCENT)
        self.set_x(self.l_margin)
        self.cell(0, 5, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Nirmala", "", 9.5)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin + 3)
        self.multi_cell(0, 5, text)
        self.ln(1)
        self.set_draw_color(*LIGHT)
        self.line(self.l_margin, self.get_y(), 210 - self.r_margin, self.get_y())
        self.ln(2)

    def data_table(self, headers, rows, widths, align="LEFT"):
        self.set_font("Nirmala", "", 9)
        self.set_text_color(*BLACK)
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(160, 150, 140)
        with self.table(
            col_widths=widths,
            text_align=align,
            headings_style=FontFace(emphasis="B", color=WHITE, fill_color=ACCENT),
            line_height=5,
            padding=1.5,
        ) as table:
            hrow = table.row()
            for h in headers:
                hrow.cell(h)
            for r in rows:
                row = table.row()
                for v in r:
                    row.cell(str(v))
        self.ln(2)

    def signoff(self, part_name: str):
        self.ln(4)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.4)
        y = self.get_y()
        self.rect(self.l_margin, y, 210 - self.l_margin - self.r_margin, 34)
        self.set_xy(self.l_margin + 3, y + 3)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*ACCENT)
        self.cell(0, 5, f"Review sign-off - {part_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 3)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        self.cell(90, 6, "Reviewed by: ______________________", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 6, "Date: ______________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 3)
        self.cell(0, 6, "Verdict:   [ ] Confirmed as-is    [ ] Corrected (see notes)    [ ] Rejected", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + 3)
        self.cell(0, 6, "Notes: ________________________________________________________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + 36)


def chunks_by_topic():
    order = [
        "planet-in-house", "nakshatra", "dasha", "lagna", "dosha", "remedies",
        "muhurtham", "panchangam", "retrograde", "porutham", "prashnam",
        "vazhipadu", "deity",
    ]
    by_topic: dict[str, list[dict]] = {}
    for c in SEED_CHUNKS:
        by_topic.setdefault(c["topic"], []).append(c)
    ordered = [(t, by_topic[t]) for t in order if t in by_topic]
    leftover = [(t, v) for t, v in by_topic.items() if t not in order]
    return ordered + leftover


def build() -> None:
    pdf = PDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_font("Nirmala", "", NIRMALA)
    pdf.add_font("Nirmala", "B", NIRMALA)
    pdf.set_text_shaping(True)

    pdf.cover_page()

    # == Part 0: how to use this document ===================================
    pdf.part_title("0", "How to use this document")
    pdf.body(
        "Every content 'reviewed' flag in the codebase (knowledge/seed_data.py, "
        "temples/seed_data.py) was bulk-set to True on 2026-07-06 to unblock other "
        "work - that flag is NOT a real sign-off. This document lists everything "
        "that flag covers, part by part, so a qualified Kerala astrologer (and, "
        "for Part 7, someone with clinical judgement) can actually go through it."
    )
    pdf.warn_box(
        "For each item: CONFIRM it as accurate, CORRECT the text/table cell (write "
        "the fix in the notes), or REJECT it outright. Anything corrected-in-place "
        "or rejected should have its `reviewed` flag flipped back to False in code "
        "until the fix is re-checked (see NEEDS_ASTROLOGER.md for the file/line "
        "each part comes from)."
    )
    for i, (num, title, src) in enumerate([
        ("1", "Porutham compatibility tables", "app/modules/astrology_engine/porutham.py"),
        ("2", "Dosha detection rules", "app/modules/astrology_engine/doshas.py"),
        ("3", "Prashnam (horary) rules", "app/modules/astrology_engine/prashnam.py"),
        ("4", "Knowledge corpus (RAG content)", "app/modules/knowledge/seed_data.py"),
        ("5", "Temple directory", "app/modules/temples/seed_data.py"),
        ("6", "Remedy & deity mapping tables", "app/modules/temples/remedy_map.py"),
        ("7", "Crisis/safety keyword screen (clinical review, not astrology)", "app/modules/tone_safety/crisis_classifier.py"),
        ("8", "Unverified folk terms", "NEEDS_ASTROLOGER.md"),
    ]):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACCENT)
        pdf.set_x(pdf.l_margin)
        pdf.cell(14, 6, f"Part {num}")
        pdf.set_font("Nirmala", "", 10)
        pdf.set_text_color(*BLACK)
        pdf.cell(90, 6, title)
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, src, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # == Part 1: Porutham tables =============================================
    pdf.part_title("1", "Porutham compatibility tables")
    pdf.body(
        "The classical Kerala pathu porutham (ten-fold marriage compatibility) "
        "reference tables. These are hardcoded FACTS, not narration - a wrong "
        "cell silently produces a wrong compatibility score, and nothing in the "
        "code flags an error here. Verify every table below against a Kerala "
        "jyotisha manual."
    )

    pdf.sub_title("1.1  Gana (temperament) and Yoni (instinct, animal symbol) by nakshatra")
    rows = []
    for i, ml in enumerate(NAKSHATRAS):
        gana = por._GANA[i]
        rows.append([ml, NAK_ALIAS.get(ml, ""), por._GANA_ML[gana], por._YONI[i]])
    pdf.data_table(["Nakshatra", "Alias", "Gana", "Yoni"], rows, (28, 42, 40, 30))
    pdf.body(
        "Yoni enemy pairs (worst-graded combination): "
        + "; ".join(" / ".join(sorted(p)) for p in por._YONI_ENEMIES)
    )

    pdf.sub_title("1.2  Rajju (the weightiest porutham - guards longevity of the marriage)")
    rows = [[ml, NAK_ALIAS.get(ml, ""), por._RAJJU_ML[por._RAJJU[i]]] for i, ml in enumerate(NAKSHATRAS)]
    pdf.data_table(["Nakshatra", "Alias", "Rajju group"], rows, (30, 50, 60))

    pdf.sub_title("1.3  Vedha (mutual affliction) nakshatra pairs")
    vedha_pairs = [tuple(sorted(p)) for p in por._VEDHA_PAIRS]
    rows = [[NAKSHATRAS[a], NAKSHATRAS[b]] for a, b in sorted(vedha_pairs)]
    pdf.data_table(["Star A", "Star B"], rows, (70, 70))

    pdf.sub_title("1.4  Rasi lord and naisargika (natural) planetary friendship")
    rows = []
    for i, ml in enumerate(RASIS):
        lord = por._RASI_LORD[i]
        friends = ", ".join(por._GRAHA_ML[g] for g in sorted(por._FRIENDS.get(lord, set())))
        enemies = ", ".join(por._GRAHA_ML[g] for g in sorted(por._ENEMIES.get(lord, set())))
        rows.append([ml, RASI_ALIAS.get(ml, ""), por._GRAHA_ML[lord], friends or "-", enemies or "-"])
    pdf.data_table(["Rasi", "Alias", "Lord", "Lord's friends", "Lord's enemies"], rows, (24, 34, 24, 44, 44))

    pdf.sub_title("1.5  Vasya (mutual attraction) - rasi holds sway over:")
    rows = [[ml, RASI_ALIAS.get(ml, ""), ", ".join(RASIS[j] for j in sorted(por._VASYA[i]))] for i, ml in enumerate(RASIS)]
    pdf.data_table(["Rasi", "Alias", "Holds sway over"], rows, (28, 42, 100))

    pdf.sub_title("1.6  Grading logic per porutham (verify the thresholds, not just the tables)")
    for item in [
        "Dina: count bride's star to groom's, mod 9. Even remainder (incl. 0) = uthamam; odd = adhamam.",
        "Gana: same gana = uthamam; deva+rakshasa = adhamam; any other mix = madhyamam.",
        "Mahendra: count bride to groom lands on 4/7/10/13/16/19/22/25 = uthamam, else adhamam.",
        "Stree-Deergha: count bride to groom >9 = uthamam; 7-9 = madhyamam; <7 = adhamam.",
        "Yoni: same animal = uthamam; enemy pair = adhamam; else madhyamam.",
        "Rasi (bhakoot): 6/8 placement (either direction) = adhamam; 2/12 = madhyamam; else uthamam.",
        "Rasyadhipathi: same lord or mutual friends = uthamam; mutual enemies (no friend) = adhamam; mixed = madhyamam.",
        "Vasya: mutual sway = uthamam; one-way = madhyamam; neither = adhamam.",
        "Rajju: same rajju group = adhamam (rajju dosha); different = uthamam.",
        "Vedha: star pair in the vedha table = adhamam; else uthamam.",
    ]:
        pdf.bullet(item)
    pdf.signoff("Part 1 - Porutham tables")

    # == Part 2: Dosha detection =============================================
    pdf.part_title("2", "Dosha detection rules")
    pdf.body(
        "Deterministic FACT checks over the natal/transit chart - pure if-statements, "
        "never LLM-guessed. Verify the house/graha sets below match Kerala convention."
    )
    pdf.sub_title("2.1  Chovva (Mangal/Kuja) dosha")
    pdf.body(
        f"Mars in houses {sorted(dosha_mod._CHOVVA_HOUSES)} (counted from BOTH the "
        "lagna and the Moon - present if either hits)."
    )
    pdf.sub_title("2.2  Kala Sarpa dosha")
    pdf.body(
        "Present when all seven classical grahas ("
        + ", ".join(dosha_mod._CLASSICAL_GRAHAS)
        + ") sit on one side of the Rahu-Ketu axis."
    )
    pdf.sub_title("2.3  Sade Sati (ezhara shani) phases")
    rows = [[house, phase] for house, phase in dosha_mod._SADE_SATI_PHASES.items()]
    pdf.data_table(["Saturn's house from natal Moon", "Phase"], rows, (80, 80))
    pdf.signoff("Part 2 - Dosha detection")

    # == Part 3: Prashnam rules ==============================================
    pdf.part_title("3", "Prashnam (horary) rules")
    pdf.body(
        "Three interactive Kerala forms, each a rule engine over the chart of the "
        "moment the question is asked. Facts are computed here; meanings are in "
        "the knowledge corpus (Part 4)."
    )
    pdf.sub_title("3.1  House classes from the udaya lagna (Prasna Marga convention)")
    rows = [[name, ", ".join(str(h) for h in sorted(houses))] for name, houses in prashnam_mod._HOUSE_CLASSES]
    pdf.data_table(["Class", "Houses"], rows, (40, 120))
    for item in [
        "Thamboola (betel leaf count): parity (odd=gati/movement, even=sthiti/steadiness) + remainder mod 8, combined with the Moon's house from the udaya lagna.",
        "Swarna (touch 1 of 12 unlabeled squares): that square is the arudha; classified by its house-class from the lagna, plus the Moon's house from the arudha.",
        "Sankhya (name a number 1-108): maps to 1 of 12 rasis (9 numbers each) and 1 of 27 nakshatra-padas (4 numbers each), KP-horary style.",
        "Thamboola count scheme is explicitly a simplified curated draft - NOT a claim to replicate an in-person ashtamangala prashnam.",
    ]:
        pdf.bullet(item)
    pdf.signoff("Part 3 - Prashnam rules")

    # == Part 4: Knowledge corpus ============================================
    pdf.part_title("4", "Knowledge corpus - every retrievable chunk")
    pdf.body(
        f"{len(SEED_CHUNKS)} curated chunks, grouped by topic. This is the narrative "
        "content an LLM is allowed to draw on when explaining a placement, offering, "
        "or deity - never invented, always retrieved from here."
    )
    for idx, (topic, items) in enumerate(chunks_by_topic(), start=1):
        pdf.sub_title(f"4.{idx}  Topic: {topic}  ({len(items)} chunks)")
        for c in sorted(items, key=lambda c: c["id"]):
            pdf.entry(c["id"], c["text"])
        pdf.signoff(f"Part 4.{topic} - {topic} chunks")

    # == Part 5: Temple directory ============================================
    pdf.part_title("5", "Temple directory")
    pdf.body(
        f"{len(SEED_TEMPLES)} curated Kerala temples. Coordinates are Google-Places-"
        "verified (2026-07-05); the devotional content (deity association, famous_for, "
        "vazhipadu list) is not."
    )
    seen_district = None
    for t in SEED_TEMPLES:
        if t["district"] != seen_district:
            seen_district = t["district"]
            pdf.sub_title(f"District: {seen_district}")
        text = (
            f"{t['name']} ({t['name_ml']})  -  {t['town']}, {t['district']}  -  "
            f"deity: {t['deity']}\n"
            f"Famous for: {t['famous_for']}\n"
            f"Vazhipadu: {', '.join(t['vazhipadu'])}"
        )
        pdf.entry(t["id"], text)
    pdf.signoff("Part 5 - Temple directory")

    # == Part 6: Remedy & deity mapping ======================================
    pdf.part_title("6", "Remedy & deity mapping tables")
    pdf.body(
        "Deterministic lookup tables: Python picks the deity/temple, the LLM only "
        "narrates. Conventions vary between traditions and families - confirm these "
        "match mainstream Kerala remedial practice."
    )
    pdf.sub_title("6.1  Deities - mantra and worship days")
    rows = [[k, d["name"], d["name_ml"], d["mantra"], d["days"]] for k, d in DEITIES.items()]
    pdf.data_table(["Key", "Name", "Malayalam", "Mantra", "Days"], rows, (20, 26, 26, 62, 36))

    pdf.sub_title("6.2  Life concern -> deities (priority order)")
    rows = [[k, ", ".join(v[0]), v[1]] for k, v in CONCERN_DEITIES.items()]
    pdf.data_table(["Concern", "Deities (priority order)", "Reason phrase"], rows, (28, 50, 92))

    pdf.sub_title("6.3  Graha (planet) -> deities")
    rows = [[k, ", ".join(v[0]), v[1]] for k, v in GRAHA_DEITIES.items()]
    pdf.data_table(["Graha", "Deities", "Reason phrase"], rows, (24, 40, 106))

    pdf.sub_title("6.4  Dosha -> deities")
    rows = [[k, ", ".join(v[0]), v[1]] for k, v in DOSHA_DEITIES.items()]
    pdf.data_table(["Dosha", "Deities", "Reason phrase"], rows, (36, 40, 94))

    pdf.info_box(
        f"Not reproduced here (keyword/lookup tables, not devotional content): "
        f"CONCERN_KEYWORDS (English/Malayalam/Manglish trigger words per concern) "
        f"and DISTRICTS ({len(DISTRICTS)} Kerala districts + variant spellings)."
    )
    pdf.signoff("Part 6 - Remedy & deity mapping")

    # == Part 7: Crisis classifier ===========================================
    pdf.part_title("7", "Crisis/safety keyword screen")
    pdf.warn_box(
        "This needs a CLINICIAN's review, not an astrologer's. The file is "
        "explicitly commented PLACEHOLDER HEURISTIC - NOT PRODUCTION-READY. It is "
        "a pure keyword/substring match, not a trained classifier, and it WILL "
        "miss real distress phrased in ways not listed below."
    )
    pdf.sub_title("7.1  English markers")
    pdf.body(", ".join(cc._MARKERS_EN))
    pdf.sub_title("7.2  Malayalam-script markers")
    pdf.body(", ".join(cc._MARKERS_ML))
    pdf.sub_title("7.3  Manglish (romanized Malayalam) markers")
    pdf.body(", ".join(cc._MARKERS_MANGLISH))
    pdf.info_box(
        "Design note from the source: markers target explicit self-harm intent "
        "only. Bare words like 'death'/'die'/'മരണം' are deliberately NOT flagged, "
        "since legitimate astrology questions discuss the 8th house, longevity, "
        "ancestors, etc. A real classifier is needed to catch implicit distress."
    )
    pdf.signoff("Part 7 - Crisis keyword screen (clinical review)")

    # == Part 8: Unverified folk terms =======================================
    pdf.part_title("8", "Unverified folk terms")
    pdf.body(
        "Terms surfaced during development that could not be verified and are "
        "therefore parked - not wired into any lexicon, corpus, or suggestion."
    )
    pdf.entry(
        "ദേഹമുട്ട് (dehamuttu)",
        "Possibly a folk vazhipadu/vow related to മുട്ട് "
        "(obstacle) affecting the body, or a regional name for a known offering. "
        "Could not verify a canonical meaning, which deity/temples it belongs to, "
        "or which life concern it addresses.",
    )
    pdf.signoff("Part 8 - Unverified folk terms")

    pdf.output("Tara_Content_Review.pdf")
    print("Wrote Tara_Content_Review.pdf")


if __name__ == "__main__":
    build()
