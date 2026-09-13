"""
fonts.py  --  a typeface, and text wrapped to a width.

Captions (render.py) and the thumbnail (cover.py) both set type. Neither
should have to import the other to do it.
"""

from __future__ import annotations

from PIL import ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def load_font(size: int, override: str | None = None) -> ImageFont.FreeTypeFont:
    paths = ([override] if override else []) + FONT_CANDIDATES
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


def wrap_to_width(d: ImageDraw.ImageDraw, text: str, font, max_px: float
                  ) -> list[str]:
    """Greedy word wrap. Any newline you typed yourself is kept."""
    lines: list[str] = []
    for para in text.splitlines():
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for word in words[1:]:
            trial = f"{cur} {word}"
            if d.textlength(trial, font=font) <= max_px:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [text]


def line_height(font) -> int:
    try:
        asc, desc = font.getmetrics()
        return asc + desc
    except Exception:
        return int(getattr(font, "size", 24) * 1.2)
