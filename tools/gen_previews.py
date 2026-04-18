"""Generate style + palette preview thumbnails for the web UI.

Run from the project root with the project venv:
    .venv/bin/python tools/gen_previews.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from visualizer.palettes import DEFAULT_PALETTES_PATH, load_palettes
from visualizer.render import FrameRenderer
from visualizer.styles import FEATURE_KINDS, STYLES

OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "visualizer" / "ui" / "static" / "previews"
SIZE = (1280, 720)
THUMB_SIZE = (480, 270)
N_BANDS = 72


def make_features(kind: str, t: float) -> np.ndarray | float:
    if kind == "bands":
        # Smooth, vibrant band array — simulated frequency response with bass + mid bumps.
        x = np.linspace(0, 1, N_BANDS)
        bass = np.exp(-((x - 0.10) ** 2) / 0.012) * 0.95
        mid = np.exp(-((x - 0.45) ** 2) / 0.05) * 0.55
        treb = np.exp(-((x - 0.85) ** 2) / 0.04) * 0.40
        wobble = 0.08 * np.sin(2 * np.pi * (x * 7 + t * 0.5))
        return np.clip(bass + mid + treb + wobble, 0.0, 1.0).astype(np.float32)
    if kind == "energy":
        return np.float32(0.7)
    # waveform
    n = 1024
    x = np.linspace(0, 4 * np.pi, n)
    return (0.6 * np.sin(x) + 0.25 * np.sin(3 * x + 0.5)).astype(np.float32)


def render_one_frame(style_name: str, palette: dict) -> Image.Image:
    style_fn = STYLES[style_name]
    feature_kind = FEATURE_KINDS[style_name]

    renderer = FrameRenderer(
        size=SIZE,
        palette=palette,
        style_fn=style_fn,
        artist="",
        mix_name="",
        title="",
        logo_path=None,
        segments=[],
        transitions=[],
    )

    feat = make_features(feature_kind, t=1.0)
    raw = renderer.render(frame_idx=10, total_frames=300, features=feat, t=1.0)
    img = Image.frombytes("RGB", SIZE, raw)
    return img.resize(THUMB_SIZE, Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    palettes = load_palettes(DEFAULT_PALETTES_PATH)

    default_palette_name = "sunset" if "sunset" in palettes else next(iter(palettes))
    default_style_name = "radial" if "radial" in STYLES else next(iter(STYLES))

    print(f"writing previews to {OUT_DIR}")

    # one preview per style, using the default palette
    for s in STYLES:
        out = OUT_DIR / f"style_{s}.png"
        img = render_one_frame(s, palettes[default_palette_name])
        img.save(out, format="PNG", optimize=True)
        print(f"  style: {s} → {out.name}")

    # one preview per palette, using the default style
    for name, pal in palettes.items():
        out = OUT_DIR / f"palette_{name}.png"
        img = render_one_frame(default_style_name, pal)
        img.save(out, format="PNG", optimize=True)
        print(f"  palette: {name} → {out.name}")

    print("done.")


if __name__ == "__main__":
    main()
