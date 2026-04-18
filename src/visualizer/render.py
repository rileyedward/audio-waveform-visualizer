from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .fingerprint.match import TrackSegment, TransitionZone
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


def _format_track(seg: TrackSegment | None) -> str:
    if seg is None:
        return ""
    return f"{seg.artist} — {seg.title}"


class FrameRenderer:
    def __init__(
        self,
        size: tuple[int, int],
        palette: dict,
        style_fn,
        artist: str,
        title: str,
        mix_name: str = "",
        logo_path: str | None = None,
        segments: list[TrackSegment] | None = None,
        transitions: list[TransitionZone] | None = None,
    ):
        self.size = size
        self.palette = palette
        self.style_fn = style_fn
        self.artist = artist
        self.mix_name = mix_name
        self.header = " - ".join(s for s in (artist, mix_name) if s)
        self.title = title
        self.segments = sorted(segments or [], key=lambda s: s.start_sec)
        self.transitions = sorted(transitions or [], key=lambda z: z.start_sec)

        w, h = size
        self.background = build_background(size, palette["bg"][0], palette["bg"][1])
        logo_diam = int(min(w, h) * 0.30)
        self.logo = build_logo(logo_path, logo_diam)
        self.logo_pos = ((w - logo_diam) // 2, (h - logo_diam) // 2) if self.logo else None

        self.font_artist = _load_font(34)
        self.font_title = _load_font(22)
        self.font_next = _load_font(18)
        self.progress_color = palette["viz"][1]
        self.progress_bg = (255, 255, 255, 40)

    def _resolve(
        self, t: float
    ) -> tuple[TrackSegment | None, TrackSegment | None, TransitionZone | None]:
        current: TrackSegment | None = None
        nxt: TrackSegment | None = None
        for seg in self.segments:
            if seg.start_sec <= t < seg.end_sec:
                current = seg
            elif seg.start_sec > t and nxt is None:
                nxt = seg
                break
        trans: TransitionZone | None = None
        for z in self.transitions:
            if z.start_sec <= t < z.end_sec:
                trans = z
                break
        return current, nxt, trans

    def _draw_text_alpha(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        alpha: int,
    ) -> None:
        if not text or alpha <= 0:
            return
        a = max(0, min(255, int(alpha)))
        draw.text(xy, text, font=font, fill=(255, 255, 255, a))

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

        self._draw_text_alpha(
            draw, (margin_x, text_y), self.header, self.font_artist, 240
        )

        if self.segments:
            current, nxt, trans = self._resolve(t)
            if trans is not None:
                zone_len = max(1e-6, trans.end_sec - trans.start_sec)
                progress = max(0.0, min(1.0, (t - trans.start_sec) / zone_len))
                out_alpha = int(220 * (1.0 - progress))
                in_alpha = int(220 * progress)
                self._draw_text_alpha(
                    draw, (margin_x, text_y + 40),
                    _format_track(current), self.font_title, out_alpha,
                )
                incoming = _format_track(nxt)
                if incoming:
                    self._draw_text_alpha(
                        draw, (margin_x, text_y + 75),
                        f"NEXT: {incoming}", self.font_next, in_alpha,
                    )
            elif current is not None:
                self._draw_text_alpha(
                    draw, (margin_x, text_y + 40),
                    _format_track(current), self.font_title, 220,
                )
            else:
                self._draw_text_alpha(
                    draw, (margin_x, text_y + 40), self.title, self.font_title, 200
                )
        else:
            self._draw_text_alpha(
                draw, (margin_x, text_y + 40), self.title, self.font_title, 200
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
