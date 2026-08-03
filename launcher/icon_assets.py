"""Generates the tray icon image in-memory (no .ico asset file needed)."""
from __future__ import annotations

from PIL import Image, ImageDraw

BACKGROUND = (28, 32, 38, 255)
GLYPH = (255, 255, 255, 235)

STATE_COLORS = {
    "running": (46, 204, 113, 255),
    "starting": (241, 196, 15, 255),
    "stopped": (149, 165, 166, 255),
    "error": (231, 76, 60, 255),
}


def build_icon(state: str = "stopped", size: int = 64) -> Image.Image:
    """Draws a simple menu-board glyph with a status-colored dot badge in the corner."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size * 0.06
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin], radius=size // 5, fill=BACKGROUND
    )

    # Plate outline + a couple of "menu lines" as the glyph.
    plate_margin = size * 0.20
    draw.ellipse(
        [plate_margin, plate_margin, size - plate_margin, size - plate_margin],
        outline=GLYPH,
        width=max(2, size // 16),
    )
    line_width = max(2, size // 20)
    draw.line([size * 0.34, size * 0.44, size * 0.66, size * 0.44], fill=GLYPH, width=line_width)
    draw.line([size * 0.34, size * 0.58, size * 0.60, size * 0.58], fill=GLYPH, width=line_width)

    dot_color = STATE_COLORS.get(state, STATE_COLORS["stopped"])
    dot_r = size * 0.15
    cx = size - dot_r - size * 0.04
    cy = size - dot_r - size * 0.04
    draw.ellipse(
        [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
        fill=dot_color,
        outline=(0, 0, 0, 255),
        width=1,
    )

    return img
