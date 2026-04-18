from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .fingerprint import build_index


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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.source_folder).expanduser()
    if not src.exists():
        print(f"error: source folder not found: {src}", file=sys.stderr)
        return 2

    print(f"indexing {src} → {args.db}")
    t0 = time.time()
    stats = build_index(src, args.db, rebuild=args.rebuild)
    dt = time.time() - t0
    print(
        f"done in {dt:.1f}s — scanned: {stats['scanned']}, "
        f"indexed: {stats['indexed']}, skipped: {stats['skipped']}, "
        f"hashes: {stats['hashes']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
