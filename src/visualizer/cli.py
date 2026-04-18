from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from .palettes import DEFAULT_PALETTES_PATH, load_palettes
from .pipeline import RenderOptions, RenderProgress, run_render
from .styles import STYLES


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
    p.add_argument("--artist", default="", help="Artist/DJ name overlay (e.g. 'Riley Edward')")
    p.add_argument(
        "--mix-name", default="",
        help="Mix name; rendered on the same line as --artist, separated by ' - '"
             " (e.g. 'Live Mix | Disco Fever')",
    )
    p.add_argument("--title", default="", help="Mix title text overlay (used only when --auto-tracklist is off)")
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
    p.add_argument(
        "--fingerprint-db", default=None,
        help="Path to fingerprint SQLite DB (built via fingerprint-index)",
    )
    p.add_argument(
        "--auto-tracklist", action="store_true",
        help="Use --fingerprint-db to detect tracks and overlay dynamic text",
    )
    p.add_argument(
        "--tracklist-out", default=None,
        help="Write YouTube-formatted tracklist to this path",
    )
    p.add_argument(
        "--chapters", action="store_true",
        help="Embed MP4 chapter markers at track boundaries",
    )
    return p


def _make_cli_callback():
    state = {"bar": None, "phase": None}

    def cb(p: RenderProgress) -> None:
        if p.phase != state["phase"]:
            if state["bar"] is not None:
                state["bar"].close()
                state["bar"] = None
            state["phase"] = p.phase
            if p.phase == "rendering" and p.total_frames > 0:
                state["bar"] = tqdm(total=p.total_frames, unit="frame")

        if p.phase == "rendering" and state["bar"] is not None:
            delta = p.frame - state["bar"].n
            if delta > 0:
                state["bar"].update(delta)
        elif p.message:
            print(p.message)

        if p.phase in ("done", "error") and state["bar"] is not None:
            state["bar"].close()
            state["bar"] = None

    return cb


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not Path(args.input).exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    palettes = load_palettes(args.palettes_file)
    if args.palette not in palettes:
        print(
            f"error: palette {args.palette!r} not found. Options: {sorted(palettes)}",
            file=sys.stderr,
        )
        return 2

    if args.auto_tracklist and not args.fingerprint_db:
        print("error: --auto-tracklist requires --fingerprint-db", file=sys.stderr)
        return 2
    if args.auto_tracklist and not Path(args.fingerprint_db).exists():
        print(f"error: fingerprint db not found: {args.fingerprint_db}", file=sys.stderr)
        return 2

    opts = RenderOptions(
        input=args.input,
        output=args.output,
        style=args.style,
        palette=args.palette,
        artist=args.artist,
        mix_name=args.mix_name,
        title=args.title,
        logo=args.logo,
        fps=args.fps,
        resolution=args.resolution,
        n_bands=args.n_bands,
        palettes_file=args.palettes_file,
        crf=args.crf,
        preset=args.preset,
        duration=args.duration,
        fingerprint_db=args.fingerprint_db,
        auto_tracklist=args.auto_tracklist,
        tracklist_out=args.tracklist_out,
        chapters=args.chapters,
    )

    try:
        result = run_render(opts, progress_cb=_make_cli_callback())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if result.tracklist_path:
        print(f"wrote tracklist: {result.tracklist_path}")
    if result.chapters_embedded:
        print(f"embedded {len(result.segments)} chapters in {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
