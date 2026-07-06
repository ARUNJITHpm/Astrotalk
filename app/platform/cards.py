"""Shared card image renderer — (template, texts, branding) → PNG bytes.

One renderer serves every growth surface: daily content cards (Part 1),
personal share cards (Part 2), temple QR posters (Part 3). Built on Pillow.

Malayalam rendering has two requirements:
  1. A font with Malayalam glyphs. Resolution order: repo ``assets/fonts/``
     → the Docker image's Noto fonts → Windows' Nirmala UI → Pillow default
     (Latin-only, last resort so tests never crash).
  2. Complex-text shaping (conjuncts, reph). Pillow shapes correctly when
     built with libraqm — the manylinux/Windows wheels bundle it; we log a
     warning if it's missing rather than fail.

Templates are fixed sizes: "feed" 1080×1350 (IG/FB feed) and "story"
1080×1920 (WhatsApp Status / IG Stories). Output is PNG bytes for
``platform.storage`` — this module does no I/O of its own.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from app.platform.logging_config import get_logger

logger = get_logger(__name__)

TEMPLATES: dict[str, tuple[int, int]] = {
    "feed": (1080, 1350),
    "story": (1080, 1920),
}

# Malayalam-capable fonts, tried in order. The repo path wins so dev/prod
# render identically once a font ships in assets/; the Docker image installs
# fonts-noto-core (Linux paths); Nirmala UI covers Windows dev machines.
_FONT_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "assets" / "fonts" / "NotoSansMalayalam-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansMalayalamUI-Regular.ttf"),
    Path("C:/Windows/Fonts/Nirmala.ttf"),
]


@dataclass(frozen=True)
class Branding:
    """Colors + footer identity; Part 4 white-label orgs get their own."""

    name: str = "Tara"
    tagline: str = "AI ജ്യോതിഷ സഹായി"
    bg_top: str = "#0b0f2a"
    bg_bottom: str = "#1a1040"
    text_color: str = "#f5f1e8"
    accent_color: str = "#e8b64c"


TARA_BRANDING = Branding()


def _font_path() -> Path | None:
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path()
    if path is not None:
        return ImageFont.truetype(str(path), size)
    logger.warning("cards: no Malayalam font found; falling back to Pillow default")
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1: size arg unsupported
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Word-wrap by rendered pixel width (Malayalam word-spaces wrap fine)."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
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


def _gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    """Vertical gradient background — 1px strip resized, cheap and smooth."""
    width, height = size
    top_rgb = Image.new("RGB", (1, 1), top).getpixel((0, 0))
    bottom_rgb = Image.new("RGB", (1, 1), bottom).getpixel((0, 0))
    strip = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        strip.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(top_rgb, bottom_rgb)),
        )
    return strip.resize((width, height))


def render_card(
    *,
    title: str,
    body: str,
    footer: str | None = None,
    template: str = "feed",
    branding: Branding = TARA_BRANDING,
) -> bytes:
    """Render one branded card and return PNG bytes.

    ``title`` — short accent-colored header (e.g. date + nakshatra).
    ``body``  — the insight itself; wrapped, may contain newlines.
    ``footer``— override the brand line; default "{name} · {tagline}".
    """
    if template not in TEMPLATES:
        raise ValueError(f"unknown card template {template!r}; use one of {sorted(TEMPLATES)}")
    if not features.check("raqm"):
        logger.warning("cards: Pillow lacks libraqm — Malayalam conjuncts may render incorrectly")

    width, height = TEMPLATES[template]
    margin = 96
    image = _gradient((width, height), branding.bg_top, branding.bg_bottom)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(56)
    body_font = _load_font(72)
    footer_font = _load_font(40)
    max_text_width = width - 2 * margin

    # Title, top-anchored.
    y = margin + (64 if template == "story" else 0)
    for line in _wrap(draw, title, title_font, max_text_width):
        draw.text((margin, y), line, font=title_font, fill=branding.accent_color)
        y += int(56 * 1.45)

    # Accent rule under the title.
    y += 24
    draw.rectangle((margin, y, margin + 160, y + 6), fill=branding.accent_color)
    y += 72

    # Body — shrink until it fits above the footer block.
    footer_top = height - margin - 120
    body_size = 72
    while body_size > 32:
        body_font = _load_font(body_size)
        lines = _wrap(draw, body, body_font, max_text_width)
        line_height = int(body_size * 1.5)
        if y + len(lines) * line_height <= footer_top:
            break
        body_size -= 6
    else:
        lines = _wrap(draw, body, body_font, max_text_width)
        line_height = int(body_size * 1.5)
    for line in lines:
        draw.text((margin, y), line, font=body_font, fill=branding.text_color)
        y += line_height

    # Footer brand line, bottom-anchored.
    footer_text = footer if footer is not None else f"{branding.name} · {branding.tagline}"
    draw.rectangle((margin, footer_top, width - margin, footer_top + 2), fill=branding.accent_color)
    draw.text((margin, footer_top + 32), footer_text, font=footer_font, fill=branding.text_color)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
