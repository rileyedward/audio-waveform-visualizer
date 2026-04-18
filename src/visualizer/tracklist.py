from __future__ import annotations

from pathlib import Path

from .fingerprint.match import TrackSegment


def _fmt_timestamp(sec: float) -> str:
    s = max(0, int(round(sec)))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def write_youtube_txt(segments: list[TrackSegment], path: Path | str) -> None:
    lines = [
        f"[{_fmt_timestamp(seg.start_sec)}] {seg.artist} — {seg.title}"
        for seg in segments
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_chapter_metadata(
    segments: list[TrackSegment], total_duration_sec: float, path: Path | str
) -> None:
    if not segments:
        Path(path).write_text(";FFMETADATA1\n", encoding="utf-8")
        return

    out = [";FFMETADATA1"]
    for i, seg in enumerate(segments):
        start_ms = int(round(seg.start_sec * 1000))
        next_start = (
            segments[i + 1].start_sec if i + 1 < len(segments) else total_duration_sec
        )
        end_ms = int(round(next_start * 1000))
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        title = f"{seg.artist} — {seg.title}".replace("\n", " ").replace("=", "-")
        out.append("[CHAPTER]")
        out.append("TIMEBASE=1/1000")
        out.append(f"START={start_ms}")
        out.append(f"END={end_ms}")
        out.append(f"title={title}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
