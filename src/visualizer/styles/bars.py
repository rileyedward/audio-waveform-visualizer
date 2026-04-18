from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import interp_rgb


def draw(overlay: Image.Image, features: np.ndarray, palette: dict, t: float) -> None:
    w, h = overlay.size
    n = len(features)
    max_h = int(h * 0.45)
    baseline = int(h * 0.85)
    bar_w = w / n
    gap = bar_w * 0.15
    viz0, viz1 = palette["viz"][0], palette["viz"][1]
    d = ImageDraw.Draw(overlay, "RGBA")
    for i in range(n):
        mag = float(features[i])
        bh = int(mag * max_h)
        x0 = int(i * bar_w + gap)
        x1 = int((i + 1) * bar_w - gap)
        y0 = baseline - bh
        y1 = baseline
        color = interp_rgb(viz0, viz1, mag)
        d.rectangle([x0, y0, x1, y1], fill=color + (230,))
