from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from tqdm import tqdm

from .audio import (
    compute_band_matrix,
    compute_rms,
    load_audio,
    waveform_sample,
)
from .encode import FFmpegEncoder
from .palettes import DEFAULT_PALETTES_PATH, load_palettes
from .render import FrameRenderer
from .styles import FEATURE_KINDS, STYLES


def parse_resolution(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"resolution must be WIDTHxHEIGHT, got {s!r}") from e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="visualize",
        description="Render a Monstercat-style visualizer MP4 from an audio file.",
    )
    p.add_argument("--input", "-i", required=True, help="Input audio file (WAV or MP3)")
    p.add_argument("--output", "-o", required=True, help="Output MP4 path")
    p.add_argument(
        "--style", "-s", required=True, choices=sorted(STYLES.keys()),
        help="Visualizer style",
    )
    p.add_argument("--palette", "-p", required=True, help="Palette name (see palettes.json)")
    p.add_argument("--artist", default="", help="Artist text overlay (e.g. 'Riley Edward')")
    p.add_argument("--title", default="", help="Mix title text overlay")
    p.add_argument("--logo", default=None, help="Optional logo image path (circular masked)")
    p.add_argument("--fps", type=int, default=30, help="Frames per second (default 30)")
    p.add_argument(
        "--resolution", type=parse_resolution, default=(1920, 1080),
        help="WIDTHxHEIGHT (default 1920x1080)",
    )
    p.add_argument("--n-bands", type=int, default=72, help="Bands for radial/bars styles")
    p.add_argument(
        "--palettes-file", default=str(DEFAULT_PALETTES_PATH),
        help="Path to palettes.json (default: bundled)",
    )
    p.add_argument("--crf", type=int, default=18, help="x264 CRF quality (lower=better)")
    p.add_argument("--preset", default="medium", help="x264 preset")
    p.add_argument("--duration", type=float, default=None,
                   help="Optional cap on rendered duration (seconds) for smoke tests")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input not found: {in_path}", file=sys.stderr)
        return 2

    palettes = load_palettes(args.palettes_file)
    if args.palette not in palettes:
        print(
            f"error: palette {args.palette!r} not found. Options: {sorted(palettes)}",
            file=sys.stderr,
        )
        return 2
    palette = palettes[args.palette]
    style_fn = STYLES[args.style]
    feature_kind = FEATURE_KINDS[args.style]

    print(f"loading audio: {in_path}")
    t0 = time.time()
    y, sr, duration = load_audio(str(in_path))
    if args.duration is not None:
        duration = min(duration, args.duration)
        y = y[: int(duration * sr)]
    print(f"  duration: {duration:.2f}s, sr: {sr}, loaded in {time.time()-t0:.1f}s")

    fps = args.fps
    total_frames = int(duration * fps)
    if total_frames < 1:
        print("error: audio too short for any frames", file=sys.stderr)
        return 2

    print(f"computing features (kind={feature_kind})...")
    t0 = time.time()
    bands = rms = None
    if feature_kind == "bands":
        bands = compute_band_matrix(y, sr, fps, n_bands=args.n_bands)
    elif feature_kind == "energy":
        rms = compute_rms(y, sr, fps)
    print(f"  features ready in {time.time()-t0:.1f}s")

    renderer = FrameRenderer(
        size=args.resolution,
        palette=palette,
        style_fn=style_fn,
        artist=args.artist,
        title=args.title,
        logo_path=args.logo,
    )

    encoder = FFmpegEncoder(
        audio_path=str(in_path),
        output_path=args.output,
        size=args.resolution,
        fps=fps,
        crf=args.crf,
        preset=args.preset,
    )

    print(f"rendering {total_frames} frames → {args.output}")
    t0 = time.time()
    with encoder:
        for i in tqdm(range(total_frames), unit="frame"):
            t = i / fps
            if feature_kind == "bands":
                col = min(i, bands.shape[1] - 1)
                feat = bands[:, col]
            elif feature_kind == "energy":
                col = min(i, len(rms) - 1)
                feat = rms[col]
            else:  # wave
                feat = waveform_sample(y, sr, fps, i)
            frame = renderer.render(i, total_frames, feat, t)
            encoder.write(frame)
    dt = time.time() - t0
    print(f"done in {dt:.1f}s ({total_frames/dt:.1f} fps render; real-time ratio {duration/dt:.2f}x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
