"""Build docs/Tara_Growth_Plan_Malayalam.pdf -- a non-technical explainer, in
Malayalam, of every part of GROWTH_PLAN.md: what each feature is, how it
works, and every route (with the full public base URL) used to reach it.

Supersedes build_temple_partnership_pdf_ml.py (Part 3 only); this covers
Parts 0-5c. Uses the bundled NotoSansMalayalam font with uharfbuzz text
shaping. Re-run after wording/route changes:

    vinimon/Scripts/python scripts/build_growth_plan_pdf_ml.py
"""

import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "NotoSansMalayalam-Regular.ttf"
OUT = ROOT / "docs" / "Tara_Growth_Plan_Malayalam.pdf"

BASE = "https://arunjith-tara.hf.space"

ACCENT = (196, 90, 59)
INK = (44, 38, 34)
MUTED = (138, 129, 120)
SOFT_BG = (250, 244, 236)
ROUTE_BG = (245, 233, 219)
ROUTE_TEXT = (150, 70, 40)

TITLE = "താരയുടെ ഗ്രോത്ത് പ്ലാൻ"
SUBTITLE = "എല്ലാ പുതിയ ഫീച്ചറുകളും — ലളിതമായി മനസ്സിലാക്കാം"

INTRO = (
    "താരയെ കൂടുതൽ ആളുകളിലേക്ക് എത്തിക്കാനുള്ള ഒരു സമഗ്ര പദ്ധതി ഇപ്പോൾ പൂർണ്ണമായി "
    "കോഡ് ചെയ്തു കഴിഞ്ഞു. എട്ട് ഭാഗങ്ങളായി തിരിച്ച ഈ പദ്ധതി എന്താണ്, ഓരോ ഭാഗവും "
    "എങ്ങനെ പ്രവർത്തിക്കുന്നു, ഏതെല്ലാം ലിങ്കുകൾ വഴി അത് കാണാം എന്നെല്ലാം ഈ "
    "പേജുകളിൽ സാങ്കേതിക പദങ്ങളില്ലാതെ വിശദീകരിക്കുന്നു."
)

# NOTE on mixed script lines: fpdf2's uharfbuzz text shaping mis-renders a
# line where Latin text is immediately followed by Malayalam text (overlapping
# glyphs) -- the reverse order (Malayalam then Latin) shapes fine. So every
# line below keeps Latin fragments (URLs, route paths) on their own line with
# nothing Malayalam trailing after them on that same line. Route lines start
# with two spaces and either "http" or "/" or "?" so the renderer can box them.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "0. ഈ പ്ലാനിൽ എന്തെല്ലാം ഉണ്ട്?",
        [
            (
                "",
                "താരയെ കൂടുതൽ ആളുകളിലേക്ക് എത്തിക്കാനുള്ള ഒരു സമഗ്ര പദ്ധതിയാണിത്. "
                "ഓരോ ഭാഗവും ഒരു പ്രത്യേക ലക്ഷ്യത്തിനു വേണ്ടിയാണ്: ദിവസേന പുതിയ "
                "കണ്ടന്റ് ഉണ്ടാക്കുക, ഉപയോക്താക്കൾ സുഹൃത്തുക്കൾക്ക് പങ്കുവയ്ക്കാൻ "
                "പ്രോത്സാഹിപ്പിക്കുക, ക്ഷേത്രങ്ങളെ പങ്കാളികളാക്കുക, ജ്യോതിഷർക്ക് "
                "സ്വന്തം ബ്രാൻഡഡ് ആപ്പ് നൽകുക, പണം സ്വീകരിക്കുക, പ്രീമിയം "
                "റിപ്പോർട്ടുകൾ വിൽക്കുക.\n\n"
                "ഈ എല്ലാ ഭാഗങ്ങളും ഇപ്പോൾ കോഡ് ചെയ്തു കഴിഞ്ഞു, പരീക്ഷിച്ചുറപ്പിച്ചതാണ് "
                "(197 ടെസ്റ്റുകൾ). ചില ഭാഗങ്ങൾക്ക് മാത്രം പുറത്തുള്ള അക്കൗണ്ടുകൾ "
                "(ഉദാ: പണമടയ്ക്കൽ സേവനം) കൂടി വേണം പൂർണ്ണമായി തത്സമയം "
                "പ്രവർത്തിക്കാൻ — അതെല്ലാം അതാത് ഭാഗത്തിനൊപ്പം ഈ പേജുകളിൽ "
                "പറയുന്നുണ്ട്, ഒപ്പം അവസാന അധ്യായത്തിലും ഒരുമിച്ച്."
            ),
        ],
    ),
    (
        "1. താരയുടെ പ്രധാന പേജുകൾ",
        [
            (
                "",
                "ഇവയാണ് ആർക്കും നേരിട്ട് ബ്രൗസറിൽ തുറക്കാവുന്ന താരയുടെ പ്രധാന "
                "പേജുകൾ:\n"
                "- പ്രധാന വെബ്സൈറ്റ്:\n"
                f"  {BASE}/\n"
                "- പുതിയ ചാറ്റ് പേജ് (ഏറ്റവും നല്ല അനുഭവം):\n"
                f"  {BASE}/ui\n"
                "- ചാറ്റിലേക്ക് ലോഗിൻ ചെയ്യാൻ:\n"
                f"  {BASE}/ui/login\n"
                "- വാട്സ്ആപ്പ് രൂപത്തിലുള്ള ഡെമോ പേജ്:\n"
                f"  {BASE}/whatsapp\n"
                "- അഡ്മിൻ പാനൽ (രഹസ്യ പാസ്‌വേഡ് വേണം):\n"
                f"  {BASE}/admin"
            ),
        ],
    ),
    (
        "2. ദിവസേനയുള്ള കണ്ടന്റ്",
        [
            (
                "എന്താണ് ഇത്?",
                "എല്ലാ ദിവസവും രാവിലെ, താര സ്വയമേവ ഒരു 'കണ്ടന്റ് പായ്ക്ക്' "
                "തയ്യാറാക്കുന്നു — ഒരു വാട്സ്ആപ്പ് ചാനൽ സന്ദേശം, ഫേസ്ബുക്ക് പോസ്റ്റ്, "
                "ഇൻസ്റ്റാഗ്രാം റീൽ സ്ക്രിപ്റ്റ്, യൂട്യൂബ് ഷോർട്സ് സ്ക്രിപ്റ്റ് "
                "എന്നിവയും അതിനൊപ്പം ഭംഗിയുള്ള കാർഡ് ചിത്രങ്ങളും. ഇതെല്ലാം ഒരു "
                "ജീവനക്കാരൻ അഡ്മിൻ പാനലിൽ പരിശോധിച്ച് അംഗീകരിച്ച ശേഷം മാത്രമേ "
                "പബ്ലിഷ് ചെയ്യൂ — തെറ്റായ ഉള്ളടക്കം പുറത്തുപോകാതിരിക്കാൻ."
            ),
            (
                "ആക്സസ്",
                "ഇത് പൂർണ്ണമായും അഡ്മിൻ പാനലിലൂടെ കൈകാര്യം ചെയ്യുന്ന ഒരു പിന്നണി "
                "സംവിധാനമാണ് — സാധാരണ ഉപയോക്താക്കൾക്ക് നേരിട്ട് ബന്ധമില്ല, പക്ഷേ "
                "അതിന്റെ ഫലം (ദിവസേനയുള്ള വാട്സ്ആപ്പ് സന്ദേശങ്ങളും സോഷ്യൽ മീഡിയ "
                "പോസ്റ്റുകളും) എല്ലാവർക്കും കാണാം.\n"
                "- അഡ്മിൻ പാനലിലെ 'Content' ടാബ്:\n"
                f"  {BASE}/admin"
            ),
        ],
    ),
    (
        "3. ഷെയർ ചെയ്യലും റഫറൽ ഇനാമും",
        [
            (
                "എന്താണ് ഇത്?",
                "താരയിലെ ഏതൊരു നല്ല നിമിഷവും (ഒരു വായന, ഒരു പൊരുത്തം ഫലം, ഒരു "
                "നക്ഷത്ര സന്ദേശം) ഒരു ഭംഗിയുള്ള ചിത്രമായി ഷെയർ ചെയ്യാം. "
                "സുഹൃത്തുക്കളെ ക്ഷണിക്കുന്നവർക്ക് പ്രതിഫലവുമുണ്ട് — 3 സുഹൃത്തുക്കൾ "
                "രജിസ്റ്റർ ചെയ്ത് അവരുടെ ജാതകം കണക്കാക്കിക്കഴിഞ്ഞാൽ, ക്ഷണിച്ച "
                "ആൾക്ക് ഒരു പ്രീമിയം റിപ്പോർട്ട് സൗജന്യമായി ലഭിക്കും."
            ),
            (
                "",
                "- ഒരു ചാറ്റ് മറുപടിക്ക് താഴെ 'ഷെയർ' ബട്ടൺ അമർത്തിയാൽ ഒരു ബ്രാൻഡഡ് "
                "കാർഡ് ചിത്രം ഉണ്ടാകും, അത് നേരിട്ട് വാട്സ്ആപ്പ് സ്റ്റാറ്റസിലേക്കോ "
                "ഇൻസ്റ്റാഗ്രാം സ്റ്റോറിയിലേക്കോ ഷെയർ ചെയ്യാം.\n"
                "- ഓരോ ഉപയോക്താവിനും സ്വന്തമായി ഒരു റഫറൽ ലിങ്ക് ഉണ്ട് — ആ ലിങ്ക് "
                "വഴി വരുന്നവർ രജിസ്റ്റർ ചെയ്യുമ്പോൾ ഇത് സ്വയമേവ "
                "കണക്കാക്കപ്പെടും.\n"
                "- ദിവസേന 27 നക്ഷത്രങ്ങൾക്കുമുള്ള പൊതു കാർഡുകളും ലഭ്യമാണ്, ആർക്കും "
                "ഡൗൺലോഡ് ചെയ്യാം."
            ),
            (
                "ലിങ്കുകൾ",
                "- റഫറൽ ലിങ്കിന്റെ രൂപം ഇങ്ങനെയാണ് (CODE എന്നത് ഓരോരുത്തർക്കും "
                "വ്യത്യസ്തമായിരിക്കും):\n"
                f"  {BASE}/ui/login?ref=CODE\n"
                "- ദിവസേനയുള്ള നക്ഷത്ര കാർഡ് (ഉദാ: ഒന്നാം നക്ഷത്രം):\n"
                f"  {BASE}/content/cards/daily/1\n"
                "- ഷെയർ ചെയ്ത കാർഡ് തുറക്കുന്ന പേജ്:\n"
                f"  {BASE}/s/CARD-ID"
            ),
        ],
    ),
    (
        "4. ക്ഷേത്ര പങ്കാളിത്തം",
        [
            (
                "എന്താണ് ഇത്?",
                "ഒരു ക്ഷേത്രത്തെ താരയുടെ ഔദ്യോഗിക പങ്കാളിയാക്കുന്ന സംവിധാനമാണിത്. "
                "ക്ഷേത്ര വളപ്പിൽ ഒരു ക്യുആർ കോഡ് വച്ചാൽ മതി — അത് സ്കാൻ ചെയ്യുന്ന "
                "ആർക്കും ആ ക്ഷേത്രത്തിന്റെ സ്വന്തം ഡിജിറ്റൽ പേജ് ലഭിക്കും: ഇന്നത്തെ "
                "പഞ്ചാംഗം, വരാനിരിക്കുന്ന ഉത്സവങ്ങൾ, പ്രധാന വഴിപാടുകൾ, ഒപ്പം "
                "വാട്സ്ആപ്പ് വഴി ഉത്സവ ഓർമ്മപ്പെടുത്തലിന് സബ്സ്ക്രൈബ് ചെയ്യാനുള്ള "
                "സൗകര്യവും."
            ),
            (
                "എന്തുകൊണ്ട് നല്ലത്?",
                "- ക്ഷേത്രം ആളുകൾ വിശ്വസിക്കുന്ന ഇടമായതിനാൽ, അതിലൂടെ താരയെ "
                "പരിചയപ്പെടുന്നത് ഒരു സാധാരണ പരസ്യത്തേക്കാൾ വിശ്വാസ്യതയുള്ളതാണ്.\n"
                "- സ്വയം സബ്സ്ക്രൈബ് ചെയ്തവർക്ക് മാത്രമേ സന്ദേശം അയക്കൂ, ദിവസം "
                "പരമാവധി 3 സന്ദേശം — ഗ്രൂപ്പ് സ്പാമിൽ നിന്ന് ഇത് വ്യത്യസ്തമാണ്.\n"
                "- ക്ഷേത്രത്തിന് സൗജന്യമായി ഒരു ഡിജിറ്റൽ പേജും ക്യുആർ പോസ്റ്ററും "
                "വെബ്സൈറ്റ് വിജറ്റും ലഭിക്കുന്നു."
            ),
            (
                "ലിങ്കുകൾ",
                "- ക്ഷേത്രത്തിന്റെ പേജ് (ഉദാഹരണം):\n"
                f"  {BASE}/t/guruvayur\n"
                "- ക്യുആർ വഴി വന്നാൽ ഇതേ പേജ് തന്നെ, സന്ദർശനങ്ങൾ പ്രത്യേകം "
                "എണ്ണാൻ ഒരു ചെറിയ കോഡ് ചേരും:\n"
                f"  {BASE}/t/guruvayur?src=qr\n"
                "- വെബ്സൈറ്റ് വിജറ്റ് (ക്ഷേത്രത്തിന്റെ സ്വന്തം സൈറ്റിൽ "
                "ഒട്ടിക്കാവുന്നത്):\n"
                f"  {BASE}/widget/panchangam?temple=guruvayur\n"
                "- പുതിയ ക്ഷേത്രം ചേർക്കലും ഉത്സവ തീയതി ചേർക്കലും ക്യുആർ പോസ്റ്റർ "
                "ഡൗൺലോഡും അഡ്മിൻ പാനൽ വഴി:\n"
                f"  {BASE}/admin"
            ),
        ],
    ),
    (
        "5. സ്വന്തം ബ്രാൻഡഡ് താര — ജ്യോതിഷ പ്ലാറ്റ്ഫോം",
        [
            (
                "എന്താണ് ഇത്?",
                "ഒരു ജ്യോതിഷർക്ക് സ്വന്തം പേരിലും ലോഗോയിലും നിറത്തിലും ഒരു "
                "'സ്വകാര്യ താര' ലഭിക്കും. അകത്തെ ചാറ്റ് ബുദ്ധി, സുരക്ഷാ നിയമങ്ങൾ, "
                "ക്രൈസിസ് സ്ക്രീനിംഗ് എല്ലാം സാധാരണ താരയുടേത് തന്നെ — ജ്യോതിഷർക്ക് "
                "പേരും ചെറിയ ശൈലിയും മാത്രമേ മാറ്റാൻ കഴിയൂ, സുരക്ഷാ നിയമങ്ങൾ "
                "ആർക്കും മറികടക്കാൻ കഴിയില്ല. ഇത് അടുത്ത രണ്ട് ഭാഗങ്ങളുടെ "
                "(ബുക്കിംഗ്, ഡാഷ്ബോർഡ്) അടിത്തറയാണ്."
            ),
            (
                "ലിങ്കുകൾ",
                "- ബ്രാൻഡഡ് ചാറ്റ് പേജ് (handle-name എന്നത് ഓരോ ജ്യോതിഷർക്കും "
                "വ്യത്യസ്തമായ പേരാണ്):\n"
                f"  {BASE}/a/handle-name/ui\n"
                "- ബ്രാൻഡഡ് ലോഗിൻ പേജ്:\n"
                f"  {BASE}/a/handle-name/login\n"
                "- പുതിയ ജ്യോതിഷരെ ചേർക്കുന്നത് അഡ്മിൻ പാനൽ വഴിയാണ്:\n"
                f"  {BASE}/admin"
            ),
        ],
    ),
    (
        "6. കൺസൾട്ടേഷൻ ബുക്കിംഗ്",
        [
            (
                "എന്താണ് ഇത്?",
                "ജ്യോതിഷർക്ക് ആഴ്ചയിലെ ഒഴിവുള്ള സമയങ്ങൾ സെറ്റ് ചെയ്യാം; "
                "ഉപഭോക്താക്കൾക്ക് അതിൽ നിന്ന് സൗകര്യമുള്ള സമയം തിരഞ്ഞെടുത്ത് "
                "ബുക്ക് ചെയ്യാം. പണമുള്ള സ്ലോട്ട് ആണെങ്കിൽ പണമടച്ച ശേഷം മാത്രമേ "
                "ബുക്കിംഗ് ഉറപ്പാകൂ; സൗജന്യ സ്ലോട്ട് ഉടനെ ഉറപ്പാകും. ഒരേ "
                "സമയത്തേക്ക് രണ്ടു പേർ ബുക്ക് ചെയ്യാൻ ഒരിക്കലും കഴിയില്ല."
            ),
            (
                "ലിങ്കുകൾ",
                "- ഒരു ദിവസത്തെ ഒഴിവുള്ള സമയങ്ങൾ കാണാൻ:\n"
                f"  {BASE}/orgs/handle-name/booking/availability\n"
                "- ബുക്ക് ചെയ്യാനും സ്വന്തം ബുക്കിംഗുകൾ കാണാനും, ജ്യോതിഷരുടെ "
                "ബ്രാൻഡഡ് ചാറ്റ് പേജിലൂടെ ലോഗിൻ ചെയ്ത് ചെയ്യാം."
            ),
        ],
    ),
    (
        "7. ജ്യോതിഷരുടെ ഡാഷ്ബോർഡ്",
        [
            (
                "എന്താണ് ഇത്?",
                "ജ്യോതിഷർക്ക് സ്വന്തം ഉപഭോക്താക്കളുടെ പട്ടിക, അവരുടെ ജാതകം "
                "(നേരത്തെ തന്നെ കണക്കാക്കിയത്), ബുക്കിംഗ് ചരിത്രം, സ്വകാര്യ "
                "കുറിപ്പുകൾ എന്നിവയെല്ലാം ഒറ്റ ഡാഷ്ബോർഡിൽ കാണാം. ചാറ്റ് "
                "സംഭാഷണങ്ങൾ ഉപഭോക്താവ് പ്രത്യേകം സമ്മതിച്ചാൽ മാത്രമേ ജ്യോതിഷർക്ക് "
                "കാണാൻ കഴിയൂ — ജ്യോതിഷർക്ക് സ്വയം ആ അനുമതി എടുക്കാൻ കഴിയില്ല, "
                "ഉപഭോക്താവ് സമ്മതം കൊടുക്കണം."
            ),
            (
                "ലിങ്ക്",
                "- ഡാഷ്ബോർഡ്:\n"
                f"  {BASE}/a/handle-name/dashboard"
            ),
        ],
    ),
    (
        "8. പണമടയ്ക്കലും പ്രീമിയം റിപ്പോർട്ടും",
        [
            (
                "എന്താണ് ഇത്?",
                "താരയിലെ പണം ഇടപാടുകൾ Razorpay വഴിയാണ് നടക്കുന്നത് — ഓർഡർ "
                "ഉണ്ടാക്കൽ, പണം സ്വീകരിക്കൽ, എന്ത് അൺലോക്ക് ചെയ്തു എന്ന് "
                "സൂക്ഷിക്കൽ എല്ലാം സുരക്ഷിതമായി കൈകാര്യം ചെയ്യുന്നു. വാങ്ങുകയോ "
                "റഫറൽ വഴി നേടുകയോ ചെയ്യാവുന്ന ഒരു ഉൽപ്പന്നമാണ് 4 പേജുള്ള "
                "പ്രീമിയം ജാതക റിപ്പോർട്ട് — ഗ്രഹങ്ങളുടെ വിവരം, ദശാ കാലയളവ്, "
                "വരാനിരിക്കുന്ന വർഷത്തെക്കുറിച്ചുള്ള ശാന്തമായ ഒരു കാഴ്ചപ്പാട്."
            ),
            (
                "ആക്സസ്",
                "ഇത് പൂർണ്ണമായി ചാറ്റിനുള്ളിൽ നിന്ന് ഉപയോഗിക്കുന്ന ഒരു "
                "സവിശേഷതയാണ് — പ്രത്യേകം ബ്രൗസർ ലിങ്ക് സന്ദർശിക്കേണ്ടതില്ല. "
                "Razorpay അക്കൗണ്ട് ലഭിക്കുന്നതു വരെ ടെസ്റ്റ് മോഡിൽ മാത്രമേ "
                "യഥാർത്ഥ പണമിടപാട് നടക്കൂ."
            ),
        ],
    ),
    (
        "9. ജ്യോതിഷർക്കുള്ള മാസ വരിസംഖ്യ",
        [
            (
                "എന്താണ് ഇത്?",
                "സ്വന്തം ബ്രാൻഡഡ് താര ഉപയോഗിക്കുന്ന ജ്യോതിഷർ ഒരു മാസ വരിസംഖ്യ "
                "(starter അല്ലെങ്കിൽ pro പ്ലാൻ) അടയ്ക്കണം. വരിസംഖ്യ മുടങ്ങിയാൽ "
                "പുതിയ ബുക്കിംഗുകളും പുതിയ ഉപഭോക്താക്കളെ ചേർക്കലും "
                "താൽക്കാലികമായി നിർത്തും — പക്ഷേ പഴയ ഡാറ്റയും നിലവിലുള്ള "
                "ബുക്കിംഗുകളും ഒരിക്കലും ഇല്ലാതാകില്ല. അടുത്ത പണമടയ്ക്കൽ "
                "വിജയിച്ചാൽ ഉടനെ എല്ലാം സാധാരണ നിലയിലാകും."
            ),
            (
                "ലിങ്ക്",
                "- ബില്ലിംഗ് വിവരം കാണാൻ (ജ്യോതിഷർക്ക് മാത്രം):\n"
                f"  {BASE}/orgs/handle-name/billing"
            ),
        ],
    ),
    (
        "10. എല്ലാ ലിങ്കുകളും ഒറ്റനോട്ടത്തിൽ",
        [
            (
                "പൊതു പേജുകൾ — ആർക്കും തുറക്കാം",
                "- പ്രധാന വെബ്സൈറ്റ്:\n"
                f"  {BASE}/\n"
                "- ചാറ്റ് പേജ്:\n"
                f"  {BASE}/ui\n"
                "- ക്ഷേത്ര പേജ്:\n"
                f"  {BASE}/t/temple-name\n"
                "- പഞ്ചാംഗം വിജറ്റ്:\n"
                f"  {BASE}/widget/panchangam?temple=temple-name\n"
                "- ബ്രാൻഡഡ് ജ്യോതിഷ പേജ്:\n"
                f"  {BASE}/a/handle-name/ui\n"
                "- ഷെയർ ചെയ്ത കാർഡ് പേജ്:\n"
                f"  {BASE}/s/card-id\n"
                "- ദിവസേനയുള്ള നക്ഷത്ര കാർഡ്:\n"
                f"  {BASE}/content/cards/daily/1"
            ),
            (
                "അഡ്മിനും ജ്യോതിഷർക്കും മാത്രം — രഹസ്യ പ്രവേശനം വേണം",
                "- അഡ്മിൻ പാനൽ:\n"
                f"  {BASE}/admin\n"
                "- ജ്യോതിഷരുടെ ഡാഷ്ബോർഡ്:\n"
                f"  {BASE}/a/handle-name/dashboard\n"
                "- ജ്യോതിഷരുടെ ബില്ലിംഗ് പേജ്:\n"
                f"  {BASE}/orgs/handle-name/billing"
            ),
        ],
    ),
    (
        "11. ഇനി എന്ത് വേണം — പൂർണ്ണമായി Live ആകാൻ",
        [
            (
                "ഇപ്പോൾ തന്നെ യഥാർത്ഥത്തിൽ പ്രവർത്തിക്കുന്നവ",
                "വെബ്സൈറ്റ്, ചാറ്റ്, ക്ഷേത്ര പേജുകൾ, ഷെയർ കാർഡുകൾ, റഫറൽ, ബ്രാൻഡഡ് "
                "ജ്യോതിഷ പ്ലാറ്റ്ഫോം, ബുക്കിംഗ്, ഡാഷ്ബോർഡ് — എല്ലാം 197 "
                "ടെസ്റ്റുകൾ പാസായതാണ്, ഇപ്പോൾ തന്നെ ഉപയോഗിക്കാം."
            ),
            (
                "പുറത്തുള്ള അക്കൗണ്ടുകൾ കിട്ടിയാൽ മാത്രം പൂർണ്ണമായി Live ആകുന്നവ",
                "- വാട്സ്ആപ്പ് വഴിയുള്ള യഥാർത്ഥ സന്ദേശ അയക്കൽ — ഒരു അംഗീകൃത "
                "വാട്സ്ആപ്പ് ബിസിനസ് സേവനം വേണം.\n"
                "- ഫേസ്ബുക്ക്, ഇൻസ്റ്റാഗ്രാം, യൂട്യൂബിലേക്കുള്ള നേരിട്ടുള്ള "
                "പോസ്റ്റിംഗ് — ആ പ്ലാറ്റ്ഫോമുകളുടെ ഡെവലപ്പർ അക്കൗണ്ട് വേണം.\n"
                "- യഥാർത്ഥ പണമിടപാട് — Razorpay അക്കൗണ്ട് വേണം.\n"
                "- ചിത്രങ്ങളും റിപ്പോർട്ടുകളും സ്ഥിരമായി സൂക്ഷിക്കൽ — ഒരു "
                "ക്ലൗഡ് സ്റ്റോറേജ് അക്കൗണ്ട് വേണം.\n\n"
                "ഇവ ലഭിക്കുന്നതു വരെ, ബാക്കി എല്ലാം ഒരു ടെസ്റ്റ് മോഡിൽ "
                "പ്രവർത്തിക്കും — ഒന്നും തകരാറാകില്ല, കോഡ് പൂർണ്ണമായി "
                "തയ്യാറാണ്."
            ),
        ],
    ),
]


def _is_route_line(line: str) -> bool:
    stripped = line.strip()
    return line.startswith("  ") and (
        stripped.startswith("http") or stripped.startswith("/") or stripped.startswith("?")
    )


class GrowthPdf(FPDF):
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
                if _is_route_line(line):
                    text = line.strip()
                    self.set_font("NotoMal", "", 10)
                    self.set_fill_color(*ROUTE_BG)
                    self.set_text_color(*ROUTE_TEXT)
                    x = self.get_x()
                    self.set_x(x + 4)
                    self.multi_cell(0, 6.2, text, fill=True, new_x="LMARGIN", new_y="NEXT")
                    self.set_x(x)
                    self.set_font("NotoMal", "", 11)
                    self.set_text_color(*INK)
                elif line.startswith("- "):
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
    pdf = GrowthPdf(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_margins(20, 16, 20)
    pdf.add_font("NotoMal", "", str(FONT))
    pdf.set_text_shaping(True)

    # Cover
    pdf.add_page()
    pdf.set_fill_color(*SOFT_BG)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.ln(38)
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
    pdf.ln(12)
    pdf.set_font("NotoMal", "", 10.5)
    pdf.set_text_color(*INK)
    for title, _ in SECTIONS:
        pdf.set_x(pdf.l_margin + 16)
        pdf.multi_cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
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
