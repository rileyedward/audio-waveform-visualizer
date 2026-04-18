from __future__ import annotations

import queue
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ..pipeline import (
    IndexOptions,
    IndexProgress,
    RenderOptions,
    RenderProgress,
    run_index,
    run_render,
)

JobKind = str  # "render" | "index"
JobStatus = str  # "queued" | "running" | "done" | "error"

_SENTINEL = object()
_LOG_TAIL = 200


@dataclass
class Job:
    id: str
    kind: JobKind
    status: JobStatus = "queued"
    phase: str = "queued"
    progress: float = 0.0
    eta_sec: float | None = None
    message: str = ""
    log: list[str] = field(default_factory=list)
    output_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    _subscribers: list[queue.Queue] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "phase": self.phase,
            "progress": self.progress,
            "eta_sec": self.eta_sec,
            "message": self.message,
            "log": list(self.log[-_LOG_TAIL:]),
            "output_path": self.output_path,
            "extra": dict(self.extra),
            "error": self.error,
        }

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            q.put(self.snapshot())
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast(self) -> None:
        snap = self.snapshot()
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(snap)
            except queue.Full:
                pass

    def _close(self) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(_SENTINEL)
            except queue.Full:
                pass


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._render_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="render")
        self._index_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="index")

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            return [j.snapshot() for j in self._jobs.values()]

    def _new_job(self, kind: JobKind) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def submit_render(self, opts: RenderOptions) -> Job:
        job = self._new_job("render")
        job.output_path = opts.output

        def _cb(p: RenderProgress) -> None:
            job.phase = p.phase
            if p.progress:
                job.progress = float(p.progress)
            job.eta_sec = p.eta_sec
            if p.message:
                job.message = p.message
                job.log.append(p.message)
                job.log = job.log[-_LOG_TAIL:]
            job._broadcast()

        def _run() -> None:
            job.status = "running"
            job._broadcast()
            try:
                result = run_render(opts, progress_cb=_cb)
                job.status = "done"
                job.progress = 1.0
                job.eta_sec = 0.0
                job.extra = {
                    "duration_sec": result.duration_sec,
                    "elapsed_sec": result.elapsed_sec,
                    "tracklist_path": result.tracklist_path,
                    "chapters_embedded": result.chapters_embedded,
                    "segments": [
                        {
                            "artist": s.artist,
                            "title": s.title,
                            "start_sec": s.start_sec,
                            "end_sec": s.end_sec,
                        }
                        for s in result.segments
                    ],
                }
            except Exception as e:
                job.status = "error"
                job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                job.message = str(e)
            finally:
                job._broadcast()
                job._close()

        self._render_pool.submit(_run)
        return job

    def submit_index(self, opts: IndexOptions) -> Job:
        job = self._new_job("index")

        def _cb(p: IndexProgress) -> None:
            job.phase = p.phase
            if p.progress:
                job.progress = float(p.progress)
            job.eta_sec = p.eta_sec
            if p.message:
                job.message = p.message
                job.log.append(p.message)
                job.log = job.log[-_LOG_TAIL:]
            job.extra = {
                "current": p.current,
                "total": p.total,
                "current_file": p.current_file,
                "hashes_added": p.hashes_added,
            }
            job._broadcast()

        def _run() -> None:
            job.status = "running"
            job._broadcast()
            try:
                result = run_index(opts, progress_cb=_cb)
                job.status = "done"
                job.progress = 1.0
                job.eta_sec = 0.0
                job.extra = {
                    **job.extra,
                    "scanned": result.scanned,
                    "indexed": result.indexed,
                    "skipped": result.skipped,
                    "hashes": result.hashes,
                    "elapsed_sec": result.elapsed_sec,
                }
            except Exception as e:
                job.status = "error"
                job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                job.message = str(e)
            finally:
                job._broadcast()
                job._close()

        self._index_pool.submit(_run)
        return job


_registry: JobRegistry | None = None


def registry() -> JobRegistry:
    global _registry
    if _registry is None:
        _registry = JobRegistry()
    return _registry


SENTINEL = _SENTINEL
