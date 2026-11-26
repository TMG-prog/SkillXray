"""SkillXray API endpoints."""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import auth
from . import config as C
from .notebook_pipeline import NotebookPipeline
from .pipeline import RoleNotFound
from .resume_parser import UnsupportedFile, extract_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("skillxray")

STATE = {"pipeline": None, "error": None}
INFER_LOCK = threading.Lock()      # one analysis at a time: the models already use every CPU core


def _load():
    try:
        STATE["pipeline"] = NotebookPipeline.load()
        # warm-up so the first real request is not slow
        with INFER_LOCK:
            p = STATE["pipeline"]
            roles = p.roles()["posting_roles"]
            if roles:
                p.analyze("Experience with Python, SQL and data analysis. Managed team projects.", roles[0])
    except Exception as e:                      # surfaced by /health instead of killing the server
        log.exception("pipeline failed to load")
        STATE["error"] = f"{type(e).__name__}: {e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.startup_check()
    if STATE["pipeline"] is None and os.getenv("SKIP_LOAD") != "1":
        threading.Thread(target=_load, daemon=True).start()
    yield


app = FastAPI(title="SkillXray API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


def user(authorization: str | None = Header(default=None)) -> str:
    return auth.current_user(authorization)


def _pipeline() -> NotebookPipeline:
    if STATE["error"]:
        raise HTTPException(500, "The analysis service failed to start. Check the server logs.")
    if STATE["pipeline"] is None:
        raise HTTPException(503, "The analysis service is still starting up. Try again in a minute.")
    return STATE["pipeline"]


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "error" if STATE["error"] else ("ok" if STATE["pipeline"] else "loading"),
            "error": STATE["error"]}


@app.get("/roles")
def roles(_: str = Depends(user)):
    return _pipeline().roles()


@app.get("/career-paths")
def career_paths(_: str = Depends(user)):
    return _pipeline().career_paths()


@app.get("/market/ict")
def ict_market(uid: str = Depends(user)):
    pipeline = _pipeline()
    provider = getattr(pipeline.engine, "_PROFILE_PROVIDER", None)
    if provider is None:
        raise HTTPException(503, "Database-backed market analysis is not configured.")
    auth.check_rate(uid)
    try:
        with INFER_LOCK:
            return provider.ict_market_analysis(C.ARTIFACTS / "data" / "esco")
    except (OSError, ValueError):
        log.exception("ICT market analysis failed")
        raise HTTPException(503, "ICT market analysis failed. Check ESCO files and server logs.")


@app.post("/analyze")
def analyze(role: str = Form(...), role_id: str | None = Form(None),
            file: UploadFile | None = File(None), text: str | None = Form(None),
            uid: str = Depends(user)):
    p = _pipeline()
    if (file is None) == (text is None or not text.strip()):
        raise HTTPException(400, "Send either a resume file or its text, not both and not neither.")

    if file is not None:
        limit = int(C.MAX_UPLOAD_MB * 1024 * 1024)
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"File is larger than {C.MAX_UPLOAD_MB:g} MB.")
        try:
            resume_text = extract_text(file.filename or "", data)
        except UnsupportedFile as e:
            raise HTTPException(415, str(e))
        except Exception:
            log.exception("could not parse upload")
            raise HTTPException(415, "Could not read this file. Try saving it again as PDF or DOCX.")
    else:
        resume_text = text

    auth.check_rate(uid)
    try:
        with INFER_LOCK:
            return p.analyze(resume_text, role, role_id)
    except RoleNotFound:
        raise HTTPException(404, f"No requirements are available for the role '{role}' yet.")
