from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from .audio import (
    compute_band_matrix,
    compute_rms,
    load_audio,
    waveform_sample,
)
from .encode import FFmpegEncoder, mux_chapters
from .fingerprint import build_index, match_mix
from .palettes import DEFAULT_PALETTES_PATH, load_palettes
from .render import FrameRenderer
from .styles import FEATURE_KINDS, STYLES
from .tracklist import write_chapter_metadata, write_youtube_txt

RenderPhase = Literal[
    "queued", "matching", "loading", "features", "rendering", "muxing", "done", "error"
]
IndexPhase = Literal["queued", "scanning", "indexing", "done", "error"]


@dataclass
class RenderOptions:
    input: str
    output: str
    style: str
    palette: str
    artist: str = ""
    mix_name: str = ""
    title: str = ""
    logo: str | None = None
    fps: int = 30
    resolution: tuple[int, int] = (1920, 1080)
    n_bands: int = 72
    palettes_file: str = str(DEFAULT_PALETTES_PATH)
    crf: int = 18
    preset: str = "medium"
    duration: float | None = None
    fingerprint_db: str | None = None
    auto_tracklist: bool = False
    tracklist_out: str | None = None
    chapters: bool = False


@dataclass
class IndexOptions:
    source_folder: str
    db: str
    rebuild: bool = False


@dataclass
class RenderProgress:
    phase: RenderPhase
    message: str = ""
    frame: int = 0
    total_frames: int = 0
    fps_so_far: float = 0.0
    eta_sec: float | None = None
    progress: float = 0.0  # 0..1 within current phase


@dataclass
class IndexProgress:
    phase: IndexPhase
    message: str = ""
    current: int = 0
    total: int = 0
    current_file: str = ""
    eta_sec: float | None = None
    progress: float = 0.0
    hashes_added: int = 0


@dataclass
class RenderResult:
    output_path: str
    duration_sec: float
    total_frames: int
    elapsed_sec: float
    tracklist_path: str | None = None
    chapters_embedded: bool = False
    segments: list = field(default_factory=list)


@dataclass
class IndexResult:
    scanned: int
    indexed: int
    skipped: int
    hashes: int
    elapsed_sec: float


def _noop_render(p: RenderProgress) -> None:
    pass


def _noop_index(p: IndexProgress) -> None:
    pass


def run_render(
    opts: RenderOptions,
    progress_cb: Callable[[RenderProgress], None] | None = None,
) -> RenderResult:
    cb = progress_cb or _noop_render

    in_path = Path(opts.input)
    if not in_path.exists():
        cb(RenderProgress(phase="error", message=f"input not found: {in_path}"))
        raise FileNotFoundError(f"input not found: {in_path}")

    if opts.auto_tracklist and not opts.fingerprint_db:
        cb(RenderProgress(phase="error", message="--auto-tracklist requires --fingerprint-db"))
        raise ValueError("auto_tracklist requires fingerprint_db")
    if opts.auto_tracklist and not Path(opts.fingerprint_db).exists():
        cb(RenderProgress(phase="error", message=f"fingerprint db not found: {opts.fingerprint_db}"))
        raise FileNotFoundError(f"fingerprint db not found: {opts.fingerprint_db}")

    palettes = load_palettes(opts.palettes_file)
    if opts.palette not in palettes:
        cb(RenderProgress(phase="error", message=f"palette {opts.palette!r} not found"))
        raise ValueError(f"palette {opts.palette!r} not found. Options: {sorted(palettes)}")
    palette = palettes[opts.palette]
    if opts.style not in STYLES:
        cb(RenderProgress(phase="error", message=f"style {opts.style!r} not found"))
        raise ValueError(f"style {opts.style!r} not in {sorted(STYLES)}")
    style_fn = STYLES[opts.style]
    feature_kind = FEATURE_KINDS[opts.style]

    segments: list = []
    transitions: list = []
    if opts.auto_tracklist:
        cb(RenderProgress(phase="matching", message="matching tracks against fingerprint db"))
        t0 = time.time()
        segments, transitions = match_mix(str(in_path), opts.fingerprint_db)
        cb(RenderProgress(
            phase="matching",
            message=f"matched {len(segments)} tracks, {len(transitions)} transitions in {time.time()-t0:.1f}s",
            progress=1.0,
        ))

    cb(RenderProgress(phase="loading", message=f"loading audio: {in_path.name}"))
    t0 = time.time()
    y, sr, duration = load_audio(str(in_path))
    if opts.duration is not None:
        duration = min(duration, opts.duration)
        y = y[: int(duration * sr)]
    cb(RenderProgress(
        phase="loading",
        message=f"loaded {duration:.1f}s @ {sr}Hz in {time.time()-t0:.1f}s",
        progress=1.0,
    ))

    fps = opts.fps
    total_frames = int(duration * fps)
    if total_frames < 1:
        cb(RenderProgress(phase="error", message="audio too short for any frames"))
        raise ValueError("audio too short for any frames")

    cb(RenderProgress(phase="features", message=f"computing features (kind={feature_kind})"))
    t0 = time.time()
    bands = rms = None
    if feature_kind == "bands":
        bands = compute_band_matrix(y, sr, fps, n_bands=opts.n_bands)
    elif feature_kind == "energy":
        rms = compute_rms(y, sr, fps)
    cb(RenderProgress(
        phase="features",
        message=f"features ready in {time.time()-t0:.1f}s",
        progress=1.0,
    ))

    renderer = FrameRenderer(
        size=opts.resolution,
        palette=palette,
        style_fn=style_fn,
        artist=opts.artist,
        mix_name=opts.mix_name,
        title=opts.title,
        logo_path=opts.logo,
        segments=segments,
        transitions=transitions,
    )

    encoder = FFmpegEncoder(
        audio_path=str(in_path),
        output_path=opts.output,
        size=opts.resolution,
        fps=fps,
        crf=opts.crf,
        preset=opts.preset,
    )

    cb(RenderProgress(
        phase="rendering",
        message=f"rendering {total_frames} frames",
        total_frames=total_frames,
    ))
    t0 = time.time()
    last_emit = 0
    emit_every = max(1, fps)  # ~1s cadence
    with encoder:
        for i in range(total_frames):
            t = i / fps
            if feature_kind == "bands":
                col = min(i, bands.shape[1] - 1)
                feat = bands[:, col]
            elif feature_kind == "energy":
                col = min(i, len(rms) - 1)
                feat = rms[col]
            else:
                feat = waveform_sample(y, sr, fps, i)
            frame = renderer.render(i, total_frames, feat, t)
            encoder.write(frame)

            if i - last_emit >= emit_every or i == total_frames - 1:
                last_emit = i
                elapsed = max(1e-6, time.time() - t0)
                fps_so_far = (i + 1) / elapsed
                remaining = total_frames - (i + 1)
                eta = remaining / fps_so_far if fps_so_far > 0 else None
                cb(RenderProgress(
                    phase="rendering",
                    frame=i + 1,
                    total_frames=total_frames,
                    fps_so_far=fps_so_far,
                    eta_sec=eta,
                    progress=(i + 1) / total_frames,
                    message=f"frame {i+1}/{total_frames} @ {fps_so_far:.1f}fps",
                ))
    elapsed = time.time() - t0

    tracklist_path: str | None = None
    if opts.tracklist_out and segments:
        write_youtube_txt(segments, opts.tracklist_out)
        tracklist_path = opts.tracklist_out

    chapters_embedded = False
    if opts.chapters and segments:
        cb(RenderProgress(phase="muxing", message=f"embedding {len(segments)} chapters"))
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
            chapter_path = tmp.name
        try:
            write_chapter_metadata(segments, duration, chapter_path)
            mux_chapters(opts.output, chapter_path)
            chapters_embedded = True
        finally:
            Path(chapter_path).unlink(missing_ok=True)

    cb(RenderProgress(
        phase="done",
        message=f"done in {elapsed:.1f}s ({total_frames/elapsed:.1f}fps render)",
        frame=total_frames,
        total_frames=total_frames,
        progress=1.0,
    ))

    return RenderResult(
        output_path=opts.output,
        duration_sec=duration,
        total_frames=total_frames,
        elapsed_sec=elapsed,
        tracklist_path=tracklist_path,
        chapters_embedded=chapters_embedded,
        segments=segments,
    )


def run_index(
    opts: IndexOptions,
    progress_cb: Callable[[IndexProgress], None] | None = None,
) -> IndexResult:
    cb = progress_cb or _noop_index
    src = Path(opts.source_folder).expanduser()
    if not src.exists():
        cb(IndexProgress(phase="error", message=f"source folder not found: {src}"))
        raise FileNotFoundError(f"source folder not found: {src}")

    cb(IndexProgress(phase="scanning", message=f"scanning {src}"))
    t0 = time.time()

    def _adapt(idx: int, total: int, filename: str, hashes_added: int) -> None:
        elapsed = max(1e-6, time.time() - t0)
        per = elapsed / max(1, idx)
        eta = (total - idx) * per if idx > 0 else None
        cb(IndexProgress(
            phase="indexing",
            current=idx,
            total=total,
            current_file=filename,
            eta_sec=eta,
            progress=(idx / total) if total else 0.0,
            hashes_added=hashes_added,
            message=f"[{idx}/{total}] {filename}",
        ))

    stats = build_index(src, opts.db, rebuild=opts.rebuild, progress_cb=_adapt)
    elapsed = time.time() - t0
    cb(IndexProgress(
        phase="done",
        message=(
            f"done in {elapsed:.1f}s — scanned: {stats['scanned']}, "
            f"indexed: {stats['indexed']}, skipped: {stats['skipped']}, "
            f"hashes: {stats['hashes']:,}"
        ),
        current=stats["scanned"],
        total=stats["scanned"],
        progress=1.0,
        hashes_added=stats["hashes"],
    ))
    return IndexResult(
        scanned=stats["scanned"],
        indexed=stats["indexed"],
        skipped=stats["skipped"],
        hashes=stats["hashes"],
        elapsed_sec=elapsed,
    )
