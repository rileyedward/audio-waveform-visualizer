from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .palettes import RGB, vertical_gradient

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def build_background(size: tuple[int, int], bg_top: RGB, bg_bottom: RGB) -> Image.Image:
    return vertical_gradient(size, bg_top, bg_bottom).convert("RGBA")


def build_logo(logo_path: str | None, diameter: int) -> Image.Image | None:
    if not logo_path:
        return None
    img = Image.open(logo_path).convert("RGBA")
    img = img.resize((diameter, diameter), Image.LANCZOS)
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter, diameter), fill=255)
    img.putalpha(mask)
    return img


class FrameRenderer:
    def __init__(
        self,
        size: tuple[int, int],
        palette: dict,
        style_fn,
        artist: str,
        title: str,
        logo_path: str | None = None,
    ):
        self.size = size
        self.palette = palette
        self.style_fn = style_fn
        self.artist = artist
        self.title = title

        w, h = size
        self.background = build_background(size, palette["bg"][0], palette["bg"][1])
        logo_diam = int(min(w, h) * 0.30)
        self.logo = build_logo(logo_path, logo_diam)
        self.logo_pos = ((w - logo_diam) // 2, (h - logo_diam) // 2) if self.logo else None

        self.font_artist = _load_font(34)
        self.font_title = _load_font(22)
        self.progress_color = palette["viz"][1]
        self.progress_bg = (255, 255, 255, 40)

    def render(self, frame_idx: int, total_frames: int, features: np.ndarray, t: float) -> bytes:
        w, h = self.size
        frame = self.background.copy()
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))

        self.style_fn(overlay, features, self.palette, t)

        if self.logo is not None:
            overlay.alpha_composite(self.logo, self.logo_pos)

        draw = ImageDraw.Draw(overlay, "RGBA")

        margin_x = int(w * 0.04)
        text_y = int(h * 0.90)
        draw.text(
            (margin_x, text_y),
            self.artist,
            font=self.font_artist,
            fill=(255, 255, 255, 240),
        )
        draw.text(
            (margin_x, text_y + 40),
            self.title,
            font=self.font_title,
            fill=(255, 255, 255, 200),
        )

        bar_h = 4
        bar_y = h - bar_h - 2
        bar_x0 = int(w * 0.04)
        bar_x1 = int(w * 0.96)
        draw.rectangle([bar_x0, bar_y, bar_x1, bar_y + bar_h], fill=self.progress_bg)
        progress = max(0.0, min(1.0, frame_idx / max(1, total_frames - 1)))
        fill_x1 = bar_x0 + int((bar_x1 - bar_x0) * progress)
        draw.rectangle(
            [bar_x0, bar_y, fill_x1, bar_y + bar_h],
            fill=self.progress_color + (255,),
        )

        composite = Image.alpha_composite(frame, overlay).convert("RGB")
        return composite.tobytes()
