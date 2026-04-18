from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import interp_rgb


def draw(overlay: Image.Image, features: np.ndarray, palette: dict, t: float) -> None:
    w, h = overlay.size
    samples = np.asarray(features, dtype=np.float32)
    n = len(samples)
    if n < 2:
        return
    cy = h // 2
    amp = int(h * 0.22)
    step = w / (n - 1)
    viz0, viz1 = palette["viz"][0], palette["viz"][1]
    peak = float(np.abs(samples).max())
    color = interp_rgb(viz0, viz1, min(1.0, peak * 1.5))
    top = [(int(i * step), cy - int(samples[i] * amp)) for i in range(n)]
    bot = [(int(i * step), cy + int(samples[i] * amp)) for i in range(n)]
    d = ImageDraw.Draw(overlay, "RGBA")
    d.line(top, fill=color + (220,), width=3)
    d.line(bot, fill=color + (220,), width=3)
