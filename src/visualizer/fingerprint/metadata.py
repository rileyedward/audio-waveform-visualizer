from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mutagen import File as MutagenFile


@dataclass(frozen=True)
class TrackMetadata:
    artist: str
    title: str
    album: str = ""


def _parse_filename(path: Path) -> TrackMetadata:
    stem = path.stem
    if " - " in stem:
        artist, _, title = stem.partition(" - ")
        return TrackMetadata(artist=artist.strip(), title=title.strip())
    return TrackMetadata(artist="Unknown Artist", title=stem.strip())


def _first_tag(tags, keys: list[str]) -> str:
    for k in keys:
        val = tags.get(k)
        if val is None:
            continue
        if isinstance(val, list):
            if not val:
                continue
            val = val[0]
        s = str(val).strip()
        if s:
            return s
    return ""


def read_metadata(path: Path | str) -> TrackMetadata:
    p = Path(path)
    try:
        f = MutagenFile(str(p), easy=True)
    except Exception:
        f = None

    if f is None or not getattr(f, "tags", None):
        return _parse_filename(p)

    tags = f.tags
    artist = _first_tag(tags, ["artist", "albumartist", "performer", "TPE1", "TPE2"])
    title = _first_tag(tags, ["title", "TIT2"])
    album = _first_tag(tags, ["album", "TALB"])

    if not artist and not title:
        return _parse_filename(p)
    fallback = _parse_filename(p)
    return TrackMetadata(
        artist=artist or fallback.artist,
        title=title or fallback.title,
        album=album,
    )
