from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from .pipeline import IndexOptions, IndexProgress, run_index


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fingerprint-index",
        description="Build a local fingerprint database from a folder of source tracks.",
    )
    p.add_argument(
        "--source-folder", "-s", required=True,
        help="Folder containing your DJ crate (scanned recursively for MP3/WAV/FLAC/M4A)",
    )
    p.add_argument(
        "--db", "-d", required=True,
        help="Output SQLite database path (will be created if missing)",
    )
    p.add_argument(
        "--rebuild", action="store_true",
        help="Delete the existing DB and rebuild from scratch",
    )
    return p


def _make_cli_callback():
    state = {"bar": None}

    def cb(p: IndexProgress) -> None:
        if p.phase == "indexing":
            if state["bar"] is None and p.total > 0:
                state["bar"] = tqdm(total=p.total, unit="track")
            if state["bar"] is not None:
                delta = p.current - state["bar"].n
                if delta > 0:
                    state["bar"].update(delta)
        elif p.message:
            print(p.message)
        if p.phase == "done" and state["bar"] is not None:
            state["bar"].close()
            state["bar"] = None

    return cb


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.source_folder).expanduser()
    if not src.exists():
        print(f"error: source folder not found: {src}", file=sys.stderr)
        return 2

    print(f"indexing {src} → {args.db}")
    opts = IndexOptions(source_folder=str(src), db=args.db, rebuild=args.rebuild)
    try:
        run_index(opts, progress_cb=_make_cli_callback())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
