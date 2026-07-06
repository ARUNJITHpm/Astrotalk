"""Premium PDF report renderer (internal — GROWTH_PLAN.md Part 5b).

The premium ജാതക report: cover + planet table + dasha timeline + a calm
yearly outlook, rendered as image pages and saved as a multi-page PDF via
Pillow. Deliberately NOT reportlab: reportlab does no complex-text shaping,
so Malayalam conjuncts would render broken — Pillow shares the exact same
font + raqm shaping path the share cards already use.

Copy rules here are the product's core promise (AGENTS.md guardrail #1):
doshas are stated as facts WITH agency framing, the outlook never predicts
doom, and nothing ties a remedy to money.
"""

import io
from datetime import UTC, datetime

from PIL import Image, ImageDraw

from app.platform.cards import load_font
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# A4 at 150 dpi.
PAGE = (1240, 1754)
MARGIN = 110

_BG = "#fdfaf3"
_INK = "#22243a"
_ACCENT = "#8a5a00"
_MUTED = "#6b6f8a"

# Malayalam display names for the navagraha keys the engine uses.
_GRAHA_ML = {
    "surya": "സൂര്യൻ", "chandra": "ചന്ദ്രൻ", "chevvai": "ചൊവ്വ",
    "budhan": "ബുധൻ", "guru": "വ്യാഴം", "shukran": "ശുക്രൻ",
    "shani": "ശനി", "rahu": "രാഹു", "ketu": "കേതു",
}

# Gentle themes per mahadasha lord for the yearly outlook — guidance with
# agency, never fate. Deterministic copy; no LLM in the money path.
_DASHA_THEMES = {
    "surya": "ആത്മവിശ്വാസവും ഉത്തരവാദിത്വവും വളരുന്ന കാലം. നേതൃത്വം ഏറ്റെടുക്കാൻ നല്ല സമയം.",
    "chandra": "മനസ്സിന്റെയും ബന്ധങ്ങളുടെയും കാലം. കുടുംബത്തോടൊപ്പം സമയം ചെലവിടുന്നത് ശക്തി നൽകും.",
    "chevvai": "ഊർജ്ജവും ധൈര്യവും കൂടുന്ന കാലം. വ്യായാമവും ക്ഷമയും ഒരുപോലെ പ്രധാനം.",
    "budhan": "പഠനം, ആശയവിനിമയം, പുതിയ കഴിവുകൾ — ഇവയ്ക്ക് അനുകൂലമായ കാലം.",
    "guru": "വളർച്ചയുടെയും ജ്ഞാനത്തിന്റെയും കാലം. നല്ല ഉപദേശകരെ കേൾക്കൂ.",
    "shukran": "കല, സൗന്ദര്യം, ബന്ധങ്ങൾ എന്നിവ തിളങ്ങുന്ന കാലം. ആസ്വാദനത്തിൽ മിതത്വം നന്ന്.",
    "shani": "ക്ഷമയോടെ അധ്വാനിച്ചാൽ ഉറച്ച ഫലം തരുന്ന കാലം. ചിട്ടയായ ജീവിതം വലിയ കൂട്ട്.",
    "rahu": "പുതിയ വഴികളും അവസരങ്ങളും തുറക്കുന്ന കാലം. തീരുമാനങ്ങൾ പതിയെ എടുക്കൂ.",
    "ketu": "ഉള്ളിലേക്ക് നോക്കാനുള്ള കാലം. ധ്യാനവും ലാളിത്യവും മനസ്സിന് തെളിച്ചം നൽകും.",
}

_DISCLAIMER = (
    "നക്ഷത്രങ്ങൾ വഴി കാട്ടുന്നു; അവ ഒന്നും അടിച്ചേൽപ്പിക്കുന്നില്ല. "
    "തിരഞ്ഞെടുപ്പ് എപ്പോഴും നിങ്ങളുടേതാണ്. — Tara"
)


def _new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    page = Image.new("RGB", PAGE, _BG)
    return page, ImageDraw.Draw(page)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _text_block(draw, xy, text, font, fill=_INK, max_width=PAGE[0] - 2 * MARGIN,
                line_gap=1.5) -> int:
    """Draw wrapped text; returns the y just under the block."""
    x, y = xy
    size = getattr(font, "size", 24)
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += int(size * line_gap)
    return y


def _footer(draw, page_no: int) -> None:
    small = load_font(20)
    y = PAGE[1] - 96
    for line in _wrap(draw, _DISCLAIMER, small, PAGE[0] - 2 * MARGIN - 60):
        draw.text((MARGIN, y), line, font=small, fill=_MUTED)
        y += 30
    draw.text((PAGE[0] - MARGIN - 30, PAGE[1] - 96), str(page_no), font=small, fill=_MUTED)


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m")
    except (ValueError, TypeError):
        return str(iso)[:7]


def build_premium_report(*, name: str, dob: str, birth_place: str, chart: dict) -> bytes:
    """(profile, natal chart JSON) → multi-page PDF bytes."""
    pages: list[Image.Image] = []

    # ---- Page 1: cover ----
    page, draw = _new_page()
    draw.rectangle((0, 0, PAGE[0], 14), fill=_ACCENT)
    y = 260
    y = _text_block(draw, (MARGIN, y), "Tara", load_font(64), fill=_ACCENT)
    y = _text_block(draw, (MARGIN, y + 8), "Premium ജാതക റിപ്പോർട്ട്", load_font(52))
    y += 60
    y = _text_block(draw, (MARGIN, y), name, load_font(44), fill=_INK)
    profile = f"ജനനം: {dob} · {birth_place}"
    y = _text_block(draw, (MARGIN, y + 6), profile, load_font(30), fill=_MUTED)
    y += 70
    for label, value in (
        ("ജന്മ രാശി", chart.get("rasi", "—")),
        ("ജന്മ നക്ഷത്രം", f"{chart.get('nakshatram', '—')} (പാദം {chart.get('nakshatra_pada', '—')})"),
        ("ലഗ്നം", chart.get("lagnam", "—")),
    ):
        y = _text_block(draw, (MARGIN, y), f"{label}: {value}", load_font(34))
        y += 10
    if not chart.get("birth_time_known", True):
        y = _text_block(
            draw, (MARGIN, y + 10),
            "കുറിപ്പ്: ജനന സമയം കൃത്യമല്ലാത്തതിനാൽ ലഗ്നം ഏകദേശമാണ്.",
            load_font(26), fill=_MUTED,
        )
    _text_block(
        draw, (MARGIN, PAGE[1] - 220),
        f"തയ്യാറാക്കിയത്: {datetime.now(UTC).date().isoformat()}",
        load_font(24), fill=_MUTED,
    )
    _footer(draw, 1)
    pages.append(page)

    # ---- Page 2: graha positions ----
    page, draw = _new_page()
    y = _text_block(draw, (MARGIN, MARGIN), "ഗ്രഹനില", load_font(44), fill=_ACCENT)
    y += 30
    header_font, row_font = load_font(28), load_font(30)
    cols = (MARGIN, MARGIN + 330, MARGIN + 610, MARGIN + 920)
    for x, label in zip(cols, ("ഗ്രഹം", "രാശി", "നക്ഷത്രം", "ഭാവം")):
        draw.text((x, y), label, font=header_font, fill=_MUTED)
    y += 52
    draw.line((MARGIN, y - 8, PAGE[0] - MARGIN, y - 8), fill=_MUTED, width=2)
    planets = chart.get("planets", {}) or {}
    for key in ("surya", "chandra", "chevvai", "budhan", "guru", "shukran", "shani", "rahu", "ketu"):
        p = planets.get(key)
        if not isinstance(p, dict):
            continue
        retro = " (വക്രം)" if p.get("retrograde") else ""
        cells = (
            _GRAHA_ML.get(key, key) + retro,
            str(p.get("rasi", "—")),
            f"{p.get('nakshatra', '—')} · {p.get('pada', '—')}",
            str(p.get("house", "—")),
        )
        for x, cell in zip(cols, cells):
            draw.text((x, y), cell, font=row_font, fill=_INK)
        y += 58
    doshas = chart.get("doshas") or []
    if doshas:
        y += 40
        y = _text_block(draw, (MARGIN, y), "ശ്രദ്ധിക്കേണ്ട യോഗങ്ങൾ", load_font(36), fill=_ACCENT)
        y += 10
        for d in doshas[:4]:
            label = d.get("name_ml") or d.get("name") or str(d)
            y = _text_block(draw, (MARGIN, y), f"• {label}", load_font(28))
        y = _text_block(
            draw, (MARGIN, y + 10),
            "ഇവ ഭയപ്പെടേണ്ട കാര്യങ്ങളല്ല — അറിഞ്ഞ് മുന്നോട്ട് പോകാനുള്ള അടയാളങ്ങളാണ്.",
            load_font(26), fill=_MUTED,
        )
    _footer(draw, 2)
    pages.append(page)

    # ---- Page 3: dasha timeline ----
    page, draw = _new_page()
    y = _text_block(draw, (MARGIN, MARGIN), "ദശാകാലങ്ങൾ (വിംശോത്തരി)", load_font(44), fill=_ACCENT)
    y += 30
    dasha = chart.get("dasha") or {}
    current = (dasha.get("current") or {}).get("lord", "")
    for md in (dasha.get("mahadashas") or [])[:12]:
        lord = str(md.get("lord", ""))
        line = (
            f"{_GRAHA_ML.get(lord, lord)} ദശ: "
            f"{_fmt_date(md.get('start', ''))} → {_fmt_date(md.get('end', ''))}"
        )
        is_current = lord == current
        if is_current:
            line += "   ← ഇപ്പോൾ"
        y = _text_block(
            draw, (MARGIN, y), line, load_font(32 if is_current else 28),
            fill=_ACCENT if is_current else _INK,
        )
        y += 14
    _footer(draw, 3)
    pages.append(page)

    # ---- Page 4: the year ahead ----
    page, draw = _new_page()
    y = _text_block(draw, (MARGIN, MARGIN), "വരും വർഷം", load_font(44), fill=_ACCENT)
    y += 30
    theme = _DASHA_THEMES.get(current, "ശാന്തമായ വളർച്ചയുടെ കാലം.")
    if current:
        y = _text_block(
            draw, (MARGIN, y),
            f"നിങ്ങൾ ഇപ്പോൾ {_GRAHA_ML.get(current, current)} ദശയിലാണ്.",
            load_font(32),
        )
        y += 16
    y = _text_block(draw, (MARGIN, y), theme, load_font(30))
    y += 40
    y = _text_block(
        draw, (MARGIN, y),
        "ഓർക്കുക: നല്ല ശീലങ്ങൾ, അടുത്ത ബന്ധങ്ങൾ, ശാന്തമായ മനസ്സ് — "
        "ഇവയാണ് ഏത് ദശയിലും ഏറ്റവും വലിയ ബലം. നിങ്ങളുടെ നക്ഷത്രത്തെക്കുറിച്ച് "
        "എന്തും Tara-യോട് ചോദിക്കാം.",
        load_font(30),
    )
    _footer(draw, 4)
    pages.append(page)

    # Pillow writes a multi-page PDF from image frames.
    buffer = io.BytesIO()
    pages[0].save(
        buffer, format="PDF", save_all=True, append_images=pages[1:],
        resolution=150,
    )
    return buffer.getvalue()
