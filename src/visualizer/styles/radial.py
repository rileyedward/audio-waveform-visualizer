from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import interp_rgb


def draw(overlay: Image.Image, features: np.ndarray, palette: dict, t: float) -> None:
    w, h = overlay.size
    cx, cy = w // 2, h // 2
    n = len(features)
    r_in = int(min(w, h) * 0.20)
    r_max = int(min(w, h) * 0.22)
    viz0, viz1 = palette["viz"][0], palette["viz"][1]
    d = ImageDraw.Draw(overlay, "RGBA")
    for i in range(n):
        mag = float(features[i])
        theta = 2.0 * math.pi * i / n - math.pi / 2.0
        r_out = r_in + int(mag * r_max)
        x1 = cx + math.cos(theta) * r_in
        y1 = cy + math.sin(theta) * r_in
        x2 = cx + math.cos(theta) * r_out
        y2 = cy + math.sin(theta) * r_out
        color = interp_rgb(viz0, viz1, mag)
        d.line([(x1, y1), (x2, y2)], fill=color + (240,), width=4)
