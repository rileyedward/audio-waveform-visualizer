from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .extract import FingerprintConfig, extract_fingerprints
from .metadata import TrackMetadata


@dataclass(frozen=True)
class TrackSegment:
    track_id: int
    artist: str
    title: str
    start_sec: float
    end_sec: float
    confidence: float

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class TransitionZone:
    from_track_id: int
    to_track_id: int
    start_sec: float
    end_sec: float

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class MatchConfig:
    window_sec: float = 10.0
    hop_sec: float = 2.0
    min_window_votes: int = 8
    second_place_ratio: float = 0.5
    min_segment_sec: float = 12.0
    transition_sec: float = 8.0


def _load_track_meta(conn: sqlite3.Connection) -> dict[int, TrackMetadata]:
    out: dict[int, TrackMetadata] = {}
    for tid, artist, title, album in conn.execute(
        "SELECT id, artist, title, COALESCE(album,'') FROM tracks"
    ):
        out[tid] = TrackMetadata(artist=artist, title=title, album=album)
    return out


def _query_hashes(
    conn: sqlite3.Connection, hashes: list[int]
) -> dict[int, list[tuple[int, int]]]:
    """Return hash -> list of (track_id, db_offset)."""
    out: dict[int, list[tuple[int, int]]] = defaultdict(list)
    chunk = 900
    for i in range(0, len(hashes), chunk):
        batch = hashes[i : i + chunk]
        placeholders = ",".join("?" * len(batch))
        rows = conn.execute(
            f"SELECT hash, track_id, offset FROM hashes WHERE hash IN ({placeholders})",
            batch,
        ).fetchall()
        for h, tid, off in rows:
            out[h].append((tid, off))
    return out


def _window_vote(
    window_fps: list[tuple[int, int]],
    hash_lookup: dict[int, list[tuple[int, int]]],
) -> Counter:
    """(track_id, delta_bin) vote counter for a window of (hash, mix_offset)."""
    votes: Counter = Counter()
    for h, mix_off in window_fps:
        matches = hash_lookup.get(h)
        if not matches:
            continue
        for tid, db_off in matches:
            delta = db_off - mix_off
            votes[(tid, delta)] += 1
    return votes


def _top_tracks(votes: Counter) -> list[tuple[int, int]]:
    """Collapse (track_id, delta) votes to per-track best delta. Sorted desc."""
    per_track: dict[int, int] = {}
    for (tid, _delta), count in votes.items():
        if count > per_track.get(tid, 0):
            per_track[tid] = count
    return sorted(per_track.items(), key=lambda x: x[1], reverse=True)


def _merge_segments(
    windows: list[tuple[float, int | None, int]],
    cfg: MatchConfig,
    meta: dict[int, TrackMetadata],
    total_sec: float,
) -> list[TrackSegment]:
    segs: list[TrackSegment] = []
    cur_tid: int | None = None
    cur_start: float = 0.0
    cur_votes: list[int] = []

    def flush(end: float) -> None:
        if cur_tid is None or not cur_votes:
            return
        conf = float(np.mean(cur_votes))
        m = meta[cur_tid]
        segs.append(
            TrackSegment(
                track_id=cur_tid,
                artist=m.artist,
                title=m.title,
                start_sec=cur_start,
                end_sec=end,
                confidence=conf,
            )
        )

    for idx, (t, tid, votes) in enumerate(windows):
        if tid != cur_tid:
            flush(t)
            cur_tid = tid
            cur_start = t
            cur_votes = [votes] if tid is not None else []
        else:
            if tid is not None:
                cur_votes.append(votes)
    flush(total_sec)

    filtered = [s for s in segs if s.track_id is not None and s.duration >= cfg.min_segment_sec]
    return filtered


def _detect_transitions(
    segments: list[TrackSegment], cfg: MatchConfig
) -> list[TransitionZone]:
    zones: list[TransitionZone] = []
    for a, b in zip(segments, segments[1:]):
        boundary = b.start_sec
        start = max(a.start_sec, boundary - cfg.transition_sec)
        end = boundary
        if end > start:
            zones.append(
                TransitionZone(
                    from_track_id=a.track_id,
                    to_track_id=b.track_id,
                    start_sec=start,
                    end_sec=end,
                )
            )
    return zones


def match_mix(
    mix_path: str,
    db_path: Path | str,
    cfg: MatchConfig | None = None,
    fp_cfg: FingerprintConfig | None = None,
) -> tuple[list[TrackSegment], list[TransitionZone]]:
    cfg = cfg or MatchConfig()
    fp_cfg = fp_cfg or FingerprintConfig()

    fps = extract_fingerprints(mix_path, fp_cfg)
    if not fps:
        return [], []

    spf = fp_cfg.seconds_per_frame
    total_sec = max(off for _, off in fps) * spf + fp_cfg.n_fft / fp_cfg.sample_rate

    conn = sqlite3.connect(str(db_path))
    try:
        meta = _load_track_meta(conn)
        unique_hashes = list({h for h, _ in fps})
        hash_lookup = _query_hashes(conn, unique_hashes)
    finally:
        conn.close()

    fps_sorted = sorted(fps, key=lambda x: x[1])
    offsets = np.array([off for _, off in fps_sorted])
    win_frames = int(cfg.window_sec / spf)
    hop_frames = int(cfg.hop_sec / spf)

    windows: list[tuple[float, int | None, int]] = []
    last_frame = int(total_sec / spf)
    for start_frame in range(0, max(1, last_frame - win_frames + 1), max(1, hop_frames)):
        end_frame = start_frame + win_frames
        lo = int(np.searchsorted(offsets, start_frame))
        hi = int(np.searchsorted(offsets, end_frame))
        if hi - lo == 0:
            windows.append((start_frame * spf, None, 0))
            continue
        chunk = fps_sorted[lo:hi]
        votes = _window_vote(chunk, hash_lookup)
        top = _top_tracks(votes)
        if not top or top[0][1] < cfg.min_window_votes:
            windows.append((start_frame * spf, None, 0))
        else:
            windows.append((start_frame * spf, top[0][0], top[0][1]))

    segments = _merge_segments(windows, cfg, meta, total_sec)
    transitions = _detect_transitions(segments, cfg)
    return segments, transitions
