from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

RGB = tuple[int, int, int]

DEFAULT_PALETTES_PATH = Path(__file__).resolve().parent / "palettes.json"


def hex_to_rgb(h: str) -> RGB:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def load_palettes(path: Path | str) -> dict[str, dict[str, list[RGB]]]:
    data = json.loads(Path(path).read_text())
    out: dict[str, dict[str, list[RGB]]] = {}
    for name, pal in data.items():
        out[name] = {
            "bg": [hex_to_rgb(c) for c in pal["bg"]],
            "viz": [hex_to_rgb(c) for c in pal["viz"]],
        }
    return out


def interp_rgb(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, float(t)))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def vertical_gradient(size: tuple[int, int], top: RGB, bottom: RGB) -> Image.Image:
    w, h = size
    ts = np.linspace(0.0, 1.0, h, dtype=np.float32).reshape(h, 1)
    top_a = np.asarray(top, dtype=np.float32)
    bot_a = np.asarray(bottom, dtype=np.float32)
    col = top_a * (1.0 - ts) + bot_a * ts  # (h, 3)
    grad = np.broadcast_to(col[:, None, :], (h, w, 3)).astype(np.uint8).copy()
    return Image.fromarray(grad, mode="RGB")
