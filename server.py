"""Local-only studio. Audio/projects never leave this machine except yt-dlp requests."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import engine

ROOT = Path(__file__).parent
DATA = Path(os.getenv("MANIA_DATA_DIR", str(ROOT / "data")))
DATA.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Mania Chart Studio", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
pool = ThreadPoolExecutor(max_workers=1)
jobs = {}
lock = threading.RLock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ("http://127.0.0.1:8765", "http://localhost:8765"):
        return Response("Origem não permitida", status_code=403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return Response("Acesso externo não permitido", status_code=403)
    if int(request.headers.get("content-length", "0")) > 20_000_000:
        return Response("Projeto muito grande", status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'"
    return response


class Generate(BaseModel):
    url: str = Field(max_length=500)
    style: str = "auto"


class Note(BaseModel):
    t: float
    end: float
    lane: int = Field(ge=0, le=3)
    origin: str = "manual"
    strength: float = 1


class Chart(BaseModel):
    name: str = Field(max_length=80)
    level: int = Field(ge=0, le=4)
    style: str = Field(max_length=30)
    notes: list[Note] = Field(max_length=100000)
    offset: float = Field(ge=-5000, le=5000)
    bpm: float = Field(ge=20, le=500)
    anchor: float
    reviewed: bool = False


class Save(BaseModel):
    charts: list[Chart] = Field(min_length=1, max_length=10)


def folder_for(ident):
    try:
        if uuid.UUID(ident).hex != ident:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, "Projeto não encontrado")
    folder = DATA / ident
    if not folder.is_dir():
        raise HTTPException(404, "Projeto não encontrado")
    return folder


def read_project(ident):
    folder = folder_for(ident)
    if not (folder / "project.json").exists():
        raise HTTPException(409, "Projeto ainda está sendo preparado")
    return json.loads((folder / "project.json").read_text(encoding="utf8"))


def write_project(folder, project):
    temp = folder / "project.tmp"
    temp.write_text(json.dumps(project, ensure_ascii=False), encoding="utf8")
    temp.replace(folder / "project.json")


def worker(ident, payload):
    folder = DATA / ident

    def status(message):
        with lock:
            jobs[ident] = {"id": ident, "state": "running", "message": message}
    try:
        meta = engine.download(payload.url, folder, status)
        analysis = engine.analyze(folder / "audio.wav", status)
        status("Criando cinco rascunhos 4K")
        charts = [engine.draft(analysis, payload.style, level) for level in range(5)]
        for chart in charts:
            chart["stats"] = engine.statistics(meta, chart)
        project = {"id": ident, "meta": meta, "analysis": analysis, "charts": charts}
        write_project(folder, project)
        with lock:
            jobs[ident] = {"id": ident, "state": "done", "message": "Rascunhos prontos para revisão"}
    except Exception as exc:
        with lock:
            jobs[ident] = {"id": ident, "state": "error", "message": str(exc)[-1600:]}


@app.get("/api/projects")
def projects():
    entries = []
    for file in sorted(DATA.glob("*/project.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            p = json.loads(file.read_text(encoding="utf8"))
            entries.append({"id": p["id"], "title": p["meta"]["title"], "artist": p["meta"]["artist"]})
        except (ValueError, KeyError):
            continue
    return entries


@app.post("/api/generate", status_code=202)
def generate(payload: Generate):
    try:
        engine.youtube_id(payload.url)
        if payload.style not in engine.STYLES:
            raise ValueError("Escolha um estilo válido.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    with lock:
        if any(j["state"] in ("queued", "running") for j in jobs.values()):
            raise HTTPException(409, "Aguarde a geração atual terminar.")
        ident = uuid.uuid4().hex
        (DATA / ident).mkdir()
        jobs[ident] = {"id": ident, "state": "queued", "message": "Na fila"}
        pool.submit(worker, ident, payload)
    return {"id": ident}


@app.get("/api/jobs/{ident}")
def job(ident: str):
    with lock:
        if ident not in jobs:
            raise HTTPException(404, "Geração não encontrada. Reabra o projeto na biblioteca.")
        return jobs[ident]


@app.get("/api/projects/{ident}")
def get_project(ident: str):
    with lock:
        return read_project(ident)


@app.get("/api/projects/{ident}/audio")
def get_audio(ident: str):
    path = folder_for(ident) / "audio.wav"
    if not path.exists():
        raise HTTPException(404, "Áudio ainda não está disponível")
    return FileResponse(path, media_type="audio/wav")


@app.put("/api/projects/{ident}")
def save(ident: str, payload: Save):
    with lock:
        project = read_project(ident)
        charts = [c.model_dump() for c in payload.charts]
        try:
            for chart in charts:
                engine.validate_chart(chart, project["analysis"]["duration"])
                chart["stats"] = engine.statistics(project["meta"], chart)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        project["charts"] = charts
        write_project(folder_for(ident), project)
        return project


@app.get("/api/projects/{ident}/export")
def export(ident: str):
    with lock:
        project = read_project(ident)
        try:
            data = engine.export(folder_for(ident), project)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="Mania-Chart-Studio.osz"'})


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
