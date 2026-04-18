from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegEncoder:
    def __init__(
        self,
        audio_path: str,
        output_path: str,
        size: tuple[int, int],
        fps: int,
        crf: int = 18,
        preset: str = "medium",
    ):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH. Install via `brew install ffmpeg`.")

        self.audio_path = str(Path(audio_path).resolve())
        self.output_path = str(Path(output_path).resolve())
        w, h = size
        self.size = size
        self.fps = fps
        self.crf = crf
        self.preset = preset

        self.cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}",
            "-r", str(fps),
            "-i", "-",
            "-i", self.audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "320k",
            "-shortest",
            self.output_path,
        ]
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "FFmpegEncoder":
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self

    def write(self, frame_bytes: bytes) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        try:
            self.proc.stdin.write(frame_bytes)
        except BrokenPipeError as e:
            err = self.proc.stderr.read().decode("utf-8", errors="replace") if self.proc.stderr else ""
            raise RuntimeError(f"ffmpeg pipe closed: {err}") from e

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.proc is not None
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
        rc = self.proc.wait()
        err = self.proc.stderr.read().decode("utf-8", errors="replace") if self.proc.stderr else ""
        if rc != 0 and exc_type is None:
            raise RuntimeError(f"ffmpeg exited {rc}: {err}")
