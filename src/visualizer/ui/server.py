from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..fingerprint.index import AUDIO_EXTS
from ..palettes import DEFAULT_PALETTES_PATH, load_palettes
from ..pipeline import IndexOptions, RenderOptions
from ..styles import FEATURE_KINDS, STYLES
from .jobs import SENTINEL, registry

HOME = Path.home()
DEFAULT_DB_PATH = HOME / ".visualizer" / "fingerprints.db"
LIBRARY_DIR = HOME / "Music" / "visualizer-library"
DOWNLOADS_DIR = HOME / "Downloads"
UPLOAD_DIR = HOME / ".visualizer" / "uploads"

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="audio-waveform-visualizer")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index_html():
    f = STATIC_DIR / "index.html"
    if not f.exists():
        return JSONResponse({"error": "index.html not found"}, status_code=500)
    return FileResponse(str(f))


@app.get("/api/styles")
def get_styles():
    return [
        {"name": s, "feature_kind": FEATURE_KINDS[s], "preview": f"/static/previews/style_{s}.png"}
        for s in sorted(STYLES.keys())
    ]


@app.get("/api/palettes")
def get_palettes():
    palettes = load_palettes(DEFAULT_PALETTES_PATH)
    out = []
    for name, p in palettes.items():
        out.append({
            "name": name,
            "bg": ["#%02x%02x%02x" % c for c in p["bg"]],
            "viz": ["#%02x%02x%02x" % c for c in p["viz"]],
            "preview": f"/static/previews/palette_{name}.png",
        })
    return out


def _db_stats(db_path: Path) -> dict:
    if not db_path.exists():
        return {
            "tracks": 0,
            "hashes": 0,
            "db_size_bytes": 0,
            "db_path": str(db_path),
            "exists": False,
        }
    conn = sqlite3.connect(str(db_path))
    try:
        tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        hashes = conn.execute("SELECT COUNT(*) FROM hashes").fetchone()[0]
    finally:
        conn.close()
    return {
        "tracks": tracks,
        "hashes": hashes,
        "db_size_bytes": db_path.stat().st_size,
        "db_path": str(db_path),
        "exists": True,
    }


@app.get("/api/library/stats")
def library_stats():
    return _db_stats(DEFAULT_DB_PATH)


@app.get("/api/library/tracks")
def library_tracks(q: Optional[str] = None, limit: int = 5000):
    if not DEFAULT_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    try:
        sql = "SELECT id, artist, title, COALESCE(album,''), path FROM tracks"
        params: list[Any] = []
        if q:
            sql += " WHERE artist LIKE ? OR title LIKE ? OR path LIKE ?"
            like = f"%{q}%"
            params = [like, like, like]
        sql += " ORDER BY artist, title LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "artist": r[1], "title": r[2], "album": r[3], "path": r[4]}
        for r in rows
    ]


@app.post("/api/library/upload")
async def library_upload(files: list[UploadFile] = File(...)):
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in AUDIO_EXTS:
            continue
        dest = LIBRARY_DIR / Path(f.filename).name
        if dest.exists():
            stem = dest.stem
            i = 1
            while dest.exists():
                dest = LIBRARY_DIR / f"{stem}_{i}{ext}"
                i += 1
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(str(dest))
    if not saved:
        raise HTTPException(400, "no supported audio files in upload")
    opts = IndexOptions(
        source_folder=str(LIBRARY_DIR),
        db=str(DEFAULT_DB_PATH),
        rebuild=False,
    )
    job = registry().submit_index(opts)
    return {"job_id": job.id, "saved": saved}


class FolderRequest(BaseModel):
    folder: str


@app.post("/api/library/index-folder")
def library_index_folder(req: FolderRequest):
    folder = Path(req.folder).expanduser()
    if not folder.exists():
        raise HTTPException(400, f"folder not found: {folder}")
    job = registry().submit_index(IndexOptions(
        source_folder=str(folder),
        db=str(DEFAULT_DB_PATH),
        rebuild=False,
    ))
    return {"job_id": job.id}


@app.post("/api/library/rebuild")
def library_rebuild(req: FolderRequest):
    folder = Path(req.folder).expanduser()
    if not folder.exists():
        raise HTTPException(400, f"folder not found: {folder}")
    job = registry().submit_index(IndexOptions(
        source_folder=str(folder),
        db=str(DEFAULT_DB_PATH),
        rebuild=True,
    ))
    return {"job_id": job.id}


def _safe_filename(name: str) -> str:
    name = name.strip().replace("/", "_").replace("\\", "_")
    return name or "mix.mp4"


@app.post("/api/render")
async def render(
    mix: UploadFile = File(...),
    style: str = Form(...),
    palette: str = Form(...),
    output_filename: str = Form(...),
    artist: str = Form(""),
    mix_name: str = Form(""),
    title: str = Form(""),
    auto_tracklist: bool = Form(False),
    write_tracklist: bool = Form(False),
    chapters: bool = Form(False),
    duration: Optional[float] = Form(None),
    preset: str = Form("medium"),
):
    if style not in STYLES:
        raise HTTPException(400, f"unknown style: {style}")
    palettes_avail = load_palettes(DEFAULT_PALETTES_PATH)
    if palette not in palettes_avail:
        raise HTTPException(400, f"unknown palette: {palette}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    src_ext = Path(mix.filename or "mix.wav").suffix.lower() or ".wav"
    fd, tmp_path = tempfile.mkstemp(prefix="mix_", suffix=src_ext, dir=str(UPLOAD_DIR))
    os.close(fd)
    with open(tmp_path, "wb") as out:
        shutil.copyfileobj(mix.file, out)

    out_name = _safe_filename(output_filename)
    if not out_name.lower().endswith(".mp4"):
        out_name += ".mp4"
    out_path = DOWNLOADS_DIR / out_name

    tracklist_out = None
    if write_tracklist and auto_tracklist:
        tracklist_out = str(DOWNLOADS_DIR / (Path(out_name).stem + " - tracklist.txt"))

    opts = RenderOptions(
        input=tmp_path,
        output=str(out_path),
        style=style,
        palette=palette,
        artist=artist,
        mix_name=mix_name,
        title=title,
        duration=duration,
        preset=preset,
        fingerprint_db=str(DEFAULT_DB_PATH) if auto_tracklist else None,
        auto_tracklist=auto_tracklist,
        tracklist_out=tracklist_out,
        chapters=chapters and auto_tracklist,
    )
    job = registry().submit_render(opts)
    return {"job_id": job.id, "output_path": str(out_path)}


@app.get("/api/jobs")
def list_jobs():
    return registry().list()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = registry().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.snapshot()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = registry().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    q = job.subscribe()

    async def gen():
        loop = asyncio.get_event_loop()
        try:
            while True:
                item = await loop.run_in_executor(None, q.get)
                if item is SENTINEL:
                    break
                yield {"data": json.dumps(item)}
                if isinstance(item, dict) and item.get("status") in ("done", "error"):
                    break
        finally:
            job.unsubscribe(q)

    return EventSourceResponse(gen())


class RevealRequest(BaseModel):
    path: str


@app.post("/api/reveal")
def reveal(req: RevealRequest):
    p = Path(req.path).expanduser().resolve()
    allowed_roots = [DOWNLOADS_DIR.resolve(), LIBRARY_DIR.resolve(), DEFAULT_DB_PATH.parent.resolve()]
    if not any(str(p).startswith(str(root)) for root in allowed_roots):
        raise HTTPException(403, f"path not under allowed roots: {p}")
    if not p.exists():
        raise HTTPException(404, f"path not found: {p}")
    try:
        subprocess.run(["open", "-R", str(p)], check=True)
    except FileNotFoundError:
        raise HTTPException(500, "`open` not available (macOS only)")
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"open failed: {e}")
    return {"ok": True, "path": str(p)}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "downloads_dir": str(DOWNLOADS_DIR),
        "library_dir": str(LIBRARY_DIR),
        "db_path": str(DEFAULT_DB_PATH),
        "now": datetime.now(timezone.utc).isoformat(),
    }
