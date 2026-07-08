"""Build docs/Temple_Partnership_Malayalam.pdf -- a non-technical explainer,
in Malayalam, of the temple partnership feature (GROWTH_PLAN.md Part 3): how
it works, why it's a good idea, and the links/routes used to reach it.

Uses the bundled NotoSansMalayalam font with uharfbuzz text shaping so
conjuncts render correctly (unlike the ASCII-only growth-plan PDF). Re-run
after wording changes:

    vinimon/Scripts/python scripts/build_temple_partnership_pdf_ml.py
"""

import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "NotoSansMalayalam-Regular.ttf"
OUT = ROOT / "docs" / "Temple_Partnership_Malayalam.pdf"

ACCENT = (196, 90, 59)
INK = (44, 38, 34)
MUTED = (138, 129, 120)
SOFT_BG = (250, 244, 236)

TITLE = "ക്ഷേത്ര പങ്കാളിത്തം"
SUBTITLE = "താരയുടെ പുതിയ ഫീച്ചർ — ലളിതമായി മനസ്സിലാക്കാം"

INTRO = (
    "ക്ഷേത്രങ്ങളെ താരയുടെ പങ്കാളികളാക്കുന്ന ഒരു പുതിയ സംവിധാനം ഇപ്പോൾ തയ്യാറായി. "
    "ഇത് എന്താണ്, എങ്ങനെ പ്രവർത്തിക്കുന്നു, എന്തുകൊണ്ട് ഇതൊരു നല്ല പദ്ധതിയാണ്, "
    "എവിടെ ചെന്നാൽ ഇത് കാണാം എന്നെല്ലാം ഈ പേജുകളിൽ സാങ്കേതിക പദങ്ങളില്ലാതെ വിശദീകരിക്കുന്നു."
)

# NOTE on mixed script lines: fpdf2's uharfbuzz text shaping mis-renders a
# line where Latin text is immediately followed by Malayalam text (overlapping
# glyphs) -- the reverse order (Malayalam then Latin) shapes fine. So every
# line below keeps Latin fragments (URLs, route paths) on their own line with
# nothing Malayalam trailing after them on that same line.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "1. എന്താണ് ഇത്?",
        [
            (
                "",
                "\"ക്ഷേത്ര പങ്കാളിത്തം\" എന്നാൽ, ഒരു ക്ഷേത്രത്തെ താരയുടെ ഔദ്യോഗിക "
                "പങ്കാളിയാക്കുന്ന സംവിധാനമാണ്. ക്ഷേത്ര വളപ്പിൽ ഒരു ക്യുആർ കോഡ് വച്ചാൽ "
                "മതി — അത് സ്കാൻ ചെയ്യുന്ന ആർക്കും ആ ക്ഷേത്രത്തിന്റെ സ്വന്തം ഡിജിറ്റൽ "
                "പേജ് ലഭിക്കും.\n\n"
                "ഇത് വെറും ഒരു പരസ്യബോർഡ് അല്ല. ഇന്നത്തെ പഞ്ചാംഗം, വരാനിരിക്കുന്ന "
                "ഉത്സവങ്ങൾ, പ്രധാന വഴിപാടുകൾ എന്നിവയെല്ലാം ആ പേജിൽ കാണാം — "
                "ക്ഷേത്രം സന്ദർശിക്കുന്നവർക്ക് ശരിക്കും ഉപകാരമുള്ള ഒരു പേജ്."
            ),
        ],
    ),
    (
        "2. ഇത് എങ്ങനെ പ്രവർത്തിക്കുന്നു?",
        [
            (
                "1. ക്ഷേത്രം താരയിൽ രജിസ്റ്റർ ചെയ്യുന്നു",
                "ക്ഷേത്രത്തിന്റെ പേരും ബന്ധപ്പെടാനുള്ള വിവരങ്ങളും നൽകി, ആ ക്ഷേത്രത്തിന് "
                "മാത്രമായി ഒരു പ്രത്യേക ലിങ്ക് ഉണ്ടാക്കുന്നു. ഉദാഹരണം:\n"
                "  tara.app/t/guruvayur"
            ),
            (
                "2. ക്യുആർ കോഡ് പ്രിന്റ് ചെയ്ത് വളപ്പിൽ വയ്ക്കുന്നു",
                "ആ ലിങ്കിലേക്ക് നേരിട്ട് പോകുന്ന ഒരു ക്യുആർ കോഡ് ഉണ്ടാക്കി, പോസ്റ്ററായി "
                "പ്രിന്റ് ചെയ്ത് ക്ഷേത്ര കവാടത്തിലോ നോട്ടീസ് ബോർഡിലോ വയ്ക്കാം."
            ),
            (
                "3. സന്ദർശകൻ ഫോണിൽ സ്കാൻ ചെയ്യുന്നു",
                "ഒരു നിമിഷം കൊണ്ട് ആ ക്ഷേത്രത്തിന്റെ പേജ് ഫോണിൽ തുറക്കും — ഇന്നത്തെ "
                "നക്ഷത്രം, തിഥി, നല്ല നേരം, വരാനിരിക്കുന്ന ഉത്സവങ്ങൾ, പ്രധാന വഴിപാടുകൾ."
            ),
            (
                "4. ഉത്സവ അറിയിപ്പിന് സബ്സ്ക്രൈബ് ചെയ്യാം",
                "മൊബൈൽ നമ്പർ നൽകിയാൽ, ഉത്സവത്തിന് 3 ദിവസം മുൻപ് വാട്സ്ആപ്പ് വഴി "
                "ഓർമ്മപ്പെടുത്തൽ ലഭിക്കും. ഇത് പൂർണ്ണമായും സന്ദർശകന്റെ സ്വന്തം "
                "തീരുമാനമാണ് — എപ്പോൾ വേണമെങ്കിലും 'സ്റ്റോപ്പ്' എന്നയച്ച് നിർത്താം."
            ),
            (
                "5. താര ചാറ്റിലേക്ക് ക്ഷണം",
                "പേജിൽ \"നിങ്ങളുടെ നക്ഷത്രം അറിയാൻ താരയോട് ചോദിക്കൂ\" എന്നൊരു "
                "ബട്ടൺ ഉണ്ട്. ഇത് ക്ലിക്ക് ചെയ്താൽ സന്ദർശകൻ താര ചാറ്റിലേക്ക് പോകും — "
                "ഇങ്ങനെയാണ് ക്ഷേത്രത്തിലൂടെ പുതിയ ഉപയോക്താക്കൾ താരയിൽ എത്തുന്നത്."
            ),
            (
                "6. ക്ഷേത്രത്തിന്റെ സ്വന്തം വെബ്സൈറ്റിലും പഞ്ചാംഗം",
                "ക്ഷേത്രത്തിന് സ്വന്തമായി വെബ്സൈറ്റ് ഉണ്ടെങ്കിൽ, അതിൽ ഒരു ചെറിയ "
                "പഞ്ചാംഗം ബോക്സ് ഒട്ടിക്കാം — ഒരു ലിങ്ക് കോപ്പി ചെയ്ത് വച്ചാൽ മതി. "
                "അതിലും താരയുടെ പേര് ചെറുതായി കാണിക്കും."
            ),
        ],
    ),
    (
        "3. എന്തുകൊണ്ട് ഇതൊരു നല്ല പദ്ധതിയാണ്?",
        [
            (
                "",
                "- വിശ്വാസ്യത കൂടുതൽ: ക്ഷേത്രം ആളുകൾ മനസ്സുകൊണ്ട് വിശ്വസിക്കുന്ന ഇടമാണ്. "
                "അവിടെനിന്ന് താരയെ പരിചയപ്പെടുന്നത് ഒരു സാധാരണ പരസ്യത്തേക്കാൾ "
                "എത്രയോ വിശ്വാസ്യതയുള്ളതാണ്.\n"
                "- സ്പാം ഇല്ല, സമ്മതം മാത്രം: സ്വയം സബ്സ്ക്രൈബ് ചെയ്തവർക്ക് മാത്രമേ "
                "സന്ദേശം അയക്കൂ. ദിവസം പരമാവധി 3 സന്ദേശം എന്ന പരിധിയുണ്ട് — "
                "ഗ്രൂപ്പുകളിൽ കാണുന്ന സ്പാമിൽ നിന്ന് ഇത് വ്യത്യസ്തമാണ്.\n"
                "- ക്ഷേത്രത്തിനും സൗജന്യ ഗുണം: സ്വന്തമായി വെബ്സൈറ്റ് ഉണ്ടാക്കാൻ "
                "പണച്ചെലവില്ലാതെ, ഡിജിറ്റൽ പേജും ക്യുആർ പോസ്റ്ററും വിജറ്റും "
                "സൗജന്യമായി ലഭിക്കുന്നു.\n"
                "- രണ്ടു കൂട്ടർക്കും ഗുണം: ക്ഷേത്രത്തിന് കൂടുതൽ ആളുകളിലേക്ക് എത്താം, "
                "ഭക്തർക്ക് കൃത്യമായ വിവരം ലഭിക്കും, താരയ്ക്ക് പുതിയ "
                "വിശ്വാസയോഗ്യരായ ഉപയോക്താക്കൾ ലഭിക്കും.\n"
                "- അളക്കാൻ കഴിയും: എത്ര പേർ ക്യുആർ സ്കാൻ ചെയ്തു, എത്ര പേർ പേജ് "
                "സന്ദർശിച്ചു, എത്ര പേർ സബ്സ്ക്രൈബ് ചെയ്തു എന്നെല്ലാം കണക്കുകൾ "
                "ലഭ്യമാണ് — പദ്ധതി വിജയമാണോ എന്നറിയാൻ ഇത് സഹായിക്കും.\n"
                "- ദീർഘകാല ബന്ധം: ഒരു തവണ ക്ഷേത്രം സന്ദർശിച്ച ആൾ, ഉത്സവ "
                "അറിയിപ്പിലൂടെ വീണ്ടും ക്ഷേത്രത്തെയും താരയെയും ഓർക്കും."
            ),
        ],
    ),
    (
        "4. ആക്സസ് ചെയ്യാനുള്ള വഴികൾ (Routes)",
        [
            (
                "പൊതുജനങ്ങൾക്ക് — ആർക്കും, ലോഗിൻ വേണ്ട",
                "- ക്ഷേത്രത്തിന്റെ പേജ് ലിങ്ക് ഇങ്ങനെയാണ്:\n"
                "  tara.app/t/temple-name\n"
                "  ഉദാഹരണം:\n"
                "  tara.app/t/guruvayur\n"
                "- ക്യുആർ വഴി വന്നാൽ അതേ പേജ് തന്നെ തുറക്കും, പക്ഷേ ആ സന്ദർശനങ്ങൾ "
                "പ്രത്യേകം എണ്ണാൻ ലിങ്കിന്റെ അവസാനം ഒരു ചെറിയ കോഡ് ചേരും — സന്ദർശകന് "
                "ഒരു വ്യത്യാസവും തോന്നില്ല. ഉദാ:\n"
                "  ?src=qr\n"
                "- വെബ്സൈറ്റ് വിജറ്റ് ലിങ്ക്:\n"
                "  tara.app/widget/panchangam?temple=temple-name\n"
                "  ക്ഷേത്രത്തിന്റെ സ്വന്തം വെബ്സൈറ്റിൽ ഒട്ടിക്കാവുന്ന ചെറിയ "
                "പഞ്ചാംഗം ബോക്സ്."
            ),
            (
                "അഡ്മിന് മാത്രം — രഹസ്യ പാസ്‌വേഡ് വേണം",
                "- പുതിയ ക്ഷേത്രം ചേർക്കൽ, ഉത്സവ തീയതികൾ ചേർക്കൽ, ക്യുആർ പോസ്റ്റർ "
                "ഡൗൺലോഡ് ചെയ്യൽ — ഇവയെല്ലാം താരയുടെ അഡ്മിൻ പാനൽ വഴി ചെയ്യാം:\n"
                "  /admin\n"
                "- ഇത് സാങ്കേതികമായി കൈകാര്യം ചെയ്യേണ്ട ഭാഗമാണ്; ക്ഷേത്ര "
                "ഭരണകർത്താക്കൾക്ക് നേരിട്ട് പ്രവേശനം ഇപ്പോൾ ഇല്ല — അത് അടുത്ത "
                "ഘട്ടത്തിൽ വരും."
            ),
        ],
    ),
    (
        "5. ഇനി എന്ത് വേണം — പൂർണ്ണമായി Live ആകാൻ",
        [
            (
                "",
                "ഈ ഫീച്ചർ പൂർണ്ണമായും തയ്യാറാണ്, എല്ലാം പരീക്ഷിച്ചുറപ്പിച്ചതാണ്. "
                "ക്ഷേത്ര പേജ്, ക്യുആർ കോഡ്, വെബ്സൈറ്റ് വിജറ്റ് — ഇവ മൂന്നും ഇപ്പോൾ "
                "തന്നെ യഥാർത്ഥത്തിൽ ഉപയോഗിക്കാം.\n\n"
                "എന്നാൽ വാട്സ്ആപ്പ് വഴി യഥാർത്ഥ ഉത്സവ അറിയിപ്പ് അയക്കാൻ ഒരു അംഗീകൃത "
                "വാട്സ്ആപ്പ് ബിസിനസ് സേവനം വേണം. അത് ലഭിക്കുന്നതു വരെ, ആ സന്ദേശങ്ങൾ "
                "ഒരു ടെസ്റ്റ് മോഡിൽ മാത്രമേ പ്രവർത്തിക്കൂ."
            ),
        ],
    ),
]


class TemplePdf(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("NotoMal", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, TITLE, align="L")
        self.cell(0, 6, f"{date.today().isoformat()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("NotoMal", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"{self.page_no()}", align="C")

    def chapter(self, title: str, blocks: list[tuple[str, str]]):
        self.add_page()
        self.set_font("NotoMal", "", 17)
        self.set_text_color(*ACCENT)
        self.multi_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y() + 1, self.l_margin + 60, self.get_y() + 1)
        self.ln(6)
        for heading, body in blocks:
            if heading:
                self.set_font("NotoMal", "", 12.5)
                self.set_text_color(*ACCENT)
                self.multi_cell(0, 7, heading, new_x="LMARGIN", new_y="NEXT")
                self.ln(0.5)
            self.set_font("NotoMal", "", 11)
            self.set_text_color(*INK)
            for raw in body.split("\n"):
                line = raw.rstrip()
                if line.startswith("- "):
                    x = self.get_x()
                    self.set_x(x + 4)
                    self.set_text_color(*ACCENT)
                    self.cell(4, 6.6, chr(8226))
                    self.set_text_color(*INK)
                    self.multi_cell(0, 6.6, line[2:], new_x="LMARGIN", new_y="NEXT")
                    self.set_x(x)
                elif line == "":
                    self.ln(2.5)
                else:
                    self.multi_cell(0, 6.6, line, new_x="LMARGIN", new_y="NEXT")
            self.ln(4)


def build() -> Path:
    pdf = TemplePdf(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_margins(20, 16, 20)
    pdf.add_font("NotoMal", "", str(FONT))
    pdf.set_text_shaping(True)

    # Cover
    pdf.add_page()
    pdf.set_fill_color(*SOFT_BG)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.ln(50)
    pdf.set_font("NotoMal", "", 30)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 14, TITLE, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoMal", "", 15)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, SUBTITLE, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("NotoMal", "", 11)
    pdf.set_text_color(*MUTED)
    pdf.set_x(pdf.l_margin + 12)
    pdf.multi_cell(190 - 24, 6.5, INTRO, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)
    pdf.set_font("NotoMal", "", 10.5)
    pdf.set_text_color(*INK)
    for title, _ in SECTIONS:
        pdf.set_x(pdf.l_margin + 20)
        pdf.multi_cell(0, 7.5, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("NotoMal", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 5, f"തയ്യാറാക്കിയത്: {date.today().isoformat()}",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )

    for title, blocks in SECTIONS:
        pdf.chapter(title, blocks)

    OUT.parent.mkdir(exist_ok=True)
    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    size_kb = path.stat().st_size // 1024
    sys.stdout.write(f"wrote {path} ({size_kb} KB)\n")
