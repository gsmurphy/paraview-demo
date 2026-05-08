#!/usr/bin/env python3
"""make_titlecard.py — Render the inter-segment title card.

Writes a sequence of PNGs to frames/titlecard/ at the same dimensions
as the segment frames. The card lives between segments 1 and 2 with
fade-in / hold / fade-out.

Layout (1920×1080, dark background, thin sans-serif type):
    "Electrostatic Potential"   (large)
    "Lysozyme · APBS-PDB2PQR"   (small, lighter weight, below)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR   = REPO_ROOT / "frames" / "titlecard"

WIDTH, HEIGHT = 1920, 1080
FPS = 30
DURATION_S = 2.0      # total card duration (fade-in + hold + fade-out)
FADE_S = 0.6
BG = (5, 5, 8)
FG_TITLE = (235, 240, 248)
FG_SUB   = (170, 175, 190)

TITLE = "Electrostatic Potential"
SUB   = "Lysozyme · APBS-PDB2PQR"

# macOS system fonts. Fallback chain — first hit wins.
FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Helvetica.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/SFNS.ttf",
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def alpha_at(seconds: float) -> float:
    """0 → 1 → 0 envelope: fade-in, hold, fade-out."""
    if seconds < FADE_S:
        return smoothstep(seconds / FADE_S)
    if seconds > DURATION_S - FADE_S:
        return smoothstep((DURATION_S - seconds) / FADE_S)
    return 1.0


def render_frame(alpha: float) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    title_font = load_font(96)
    sub_font   = load_font(40)

    # Center the title block on a slight upward bias.
    t_bbox = draw.textbbox((0, 0), TITLE, font=title_font)
    s_bbox = draw.textbbox((0, 0), SUB, font=sub_font)
    t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
    s_w, s_h = s_bbox[2] - s_bbox[0], s_bbox[3] - s_bbox[1]
    gap = 36
    block_h = t_h + gap + s_h
    y0 = (HEIGHT - block_h) // 2 - 20

    def lerp(c: tuple[int, int, int]) -> tuple[int, int, int]:
        return tuple(int(BG[i] + (c[i] - BG[i]) * alpha) for i in range(3))

    draw.text(((WIDTH - t_w) // 2, y0), TITLE, font=title_font, fill=lerp(FG_TITLE))
    draw.text(((WIDTH - s_w) // 2, y0 + t_h + gap), SUB, font=sub_font, fill=lerp(FG_SUB))

    # Hairline rule under the subtitle for a cinematic touch.
    rule_y = y0 + t_h + gap + s_h + 24
    rule_w = max(t_w, s_w) // 2
    rx0 = (WIDTH - rule_w) // 2
    rule_color = lerp((90, 95, 110))
    draw.rectangle([rx0, rule_y, rx0 + rule_w, rule_y + 1], fill=rule_color)

    return img


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.png"):
        old.unlink()

    n_frames = int(DURATION_S * FPS)
    for i in range(n_frames):
        t = i / FPS
        a = alpha_at(t)
        img = render_frame(a)
        img.save(OUT_DIR / f"frame_{i:04d}.png", optimize=True)
    print(f"[make_titlecard] wrote {n_frames} frames to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
