from __future__ import annotations

import sqlite3
from pathlib import Path

from tqdm import tqdm

from .extract import FingerprintConfig, extract_fingerprints
from .metadata import read_metadata

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    path     TEXT UNIQUE NOT NULL,
    artist   TEXT NOT NULL,
    title    TEXT NOT NULL,
    album    TEXT,
    duration REAL
);
CREATE TABLE IF NOT EXISTS hashes (
    hash      INTEGER NOT NULL,
    track_id  INTEGER NOT NULL,
    offset    INTEGER NOT NULL,
    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_hashes_hash ON hashes(hash);
CREATE INDEX IF NOT EXISTS idx_hashes_track ON hashes(track_id);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}


def open_db(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _scan_folder(folder: Path) -> list[Path]:
    out: list[Path] = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            out.append(p)
    return sorted(out)


def _track_already_indexed(conn: sqlite3.Connection, path: str) -> bool:
    row = conn.execute("SELECT 1 FROM tracks WHERE path = ?", (path,)).fetchone()
    return row is not None


def build_index(
    source_folder: Path | str,
    db_path: Path | str,
    cfg: FingerprintConfig | None = None,
    rebuild: bool = False,
) -> dict:
    cfg = cfg or FingerprintConfig()
    src = Path(source_folder).expanduser().resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"source folder not found: {src}")

    db_path = Path(db_path).expanduser()
    if rebuild and db_path.exists():
        db_path.unlink()

    conn = open_db(db_path)
    files = _scan_folder(src)
    stats = {"scanned": len(files), "indexed": 0, "skipped": 0, "hashes": 0}

    for fp in tqdm(files, unit="track"):
        path_str = str(fp)
        if _track_already_indexed(conn, path_str) and not rebuild:
            stats["skipped"] += 1
            continue
        try:
            meta = read_metadata(fp)
            fps = extract_fingerprints(path_str, cfg)
        except Exception as e:
            print(f"  skip {fp.name}: {e}")
            stats["skipped"] += 1
            continue
        if not fps:
            stats["skipped"] += 1
            continue

        cur = conn.execute(
            "INSERT INTO tracks(path, artist, title, album) VALUES (?, ?, ?, ?)",
            (path_str, meta.artist, meta.title, meta.album),
        )
        track_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO hashes(hash, track_id, offset) VALUES (?, ?, ?)",
            [(h, track_id, off) for h, off in fps],
        )
        conn.commit()
        stats["indexed"] += 1
        stats["hashes"] += len(fps)

    conn.close()
    return stats
