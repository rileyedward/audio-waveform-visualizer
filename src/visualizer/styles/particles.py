from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from ..palettes import interp_rgb


def draw(overlay: Image.Image, features: np.ndarray, palette: dict, t: float) -> None:
    energy = float(np.asarray(features).item()) if np.ndim(features) else float(features)
    w, h = overlay.size
    cx, cy = w // 2, h // 2
    viz0, viz1 = palette["viz"][0], palette["viz"][1]
    d = ImageDraw.Draw(overlay, "RGBA")

    base_r = int(min(w, h) * 0.22)
    bloom = int(energy * min(w, h) * 0.12)
    color = interp_rgb(viz0, viz1, energy)

    for k in range(6):
        kr = base_r + bloom - k * 14
        if kr <= 0:
            continue
        alpha = int(200 * (1.0 - k / 6.0) * (0.35 + 0.65 * energy))
        d.ellipse([cx - kr, cy - kr, cx + kr, cy + kr], outline=color + (alpha,), width=3)

    n_orbits = 24
    orbit_r = base_r + bloom + 30
    for i in range(n_orbits):
        phase = 2 * math.pi * i / n_orbits + t * 0.6
        jitter = 0.15 * math.sin(t * 2.3 + i)
        r = orbit_r * (1.0 + jitter * energy)
        x = cx + math.cos(phase) * r
        y = cy + math.sin(phase) * r
        dot = int(3 + 6 * energy)
        alpha = int(120 + 120 * energy)
        d.ellipse([x - dot, y - dot, x + dot, y + dot], fill=color + (alpha,))
