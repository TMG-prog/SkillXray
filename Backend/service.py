"""SkillXray model service: a small HTTP API around skillxray.py, for a backend (e.g. a Supabase edge function) to call.

Run:   SKILLXRAY_API_KEY=some-long-secret uvicorn service:app --host 0.0.0.0 --port 8000
Call:  POST /score  {"text": "<cv text>", "role": "it support"}   with header  X-API-Key: some-long-secret
"""
import os
import threading
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

import skillxray as sx           # loads the models and data once, at start-up

API_KEY = os.environ.get("SKILLXRAY_API_KEY", "")
if not API_KEY:
    print("[!] SKILLXRAY_API_KEY is not set: the service accepts any caller. Fine on localhost, never on a public address.")

MAX_WORDS = 6000
_LOCK = threading.Lock()         # the models and their caches are shared; score one CV at a time
app = FastAPI(title="SkillXray")


class ScoreIn(BaseModel):
    text: str
    role: str


def _check(key: Optional[str]):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="bad or missing X-API-Key")


@app.get("/health")
def health():
    return {"ok": True, "roles": len(sx.available_roles())}


@app.get("/roles")
def roles(x_api_key: Optional[str] = Header(default=None)):
    _check(x_api_key)
    return {"roles": sx.available_roles()}


@app.post("/score")
def score(body: ScoreIn, x_api_key: Optional[str] = Header(default=None)):
    """Extract the CV's skills once, then score them against the role's profile (the same steps as sx.run_v2)."""
    _check(x_api_key)
    role = {r.lower(): r for r in sx.available_roles()}.get(body.role.strip().lower())
    if role is None:
        raise HTTPException(status_code=404, detail=f"unknown role {body.role!r}; see GET /roles")
    words = body.text.split()
    if len(words) < 30:
        raise HTTPException(status_code=422, detail="almost no text in the CV (a scanned PDF needs OCR first)")
    text = " ".join(words[:MAX_WORDS]) if len(words) > MAX_WORDS else body.text

    with _LOCK:
        prof, info = sx.get_profile(role)
        prof = prof.reset_index(drop=True)
        raw = sx.extract_docs([text], ['live'], sx.EXTRACTION_CFG)
        spans = sx.standardise_spans(raw) if len(raw) else None
        cand = sx.collapse_to_skills(spans) if spans is not None else sx.EMPTY_SKILLS
        tab = sx.match_v2(cand, spans, text, prof, phrases=sx._posting_phrases(role))
        tab['esco_uri'] = prof['esco_uri'].values
        unseen = set(sx.NS_SPANS.missing) | set(sx.NS_WIN.missing)

    readiness = float((tab['weight'] * tab['covered']).sum() / tab['weight'].sum())
    return {
        "role": role,
        "readiness": round(readiness, 3),
        "profile": {k: info.get(k) for k in ('source', 'release', 'n_postings', 'reason')},
        "n_words": len(words),
        "skills": [{"esco_uri": r.esco_uri, "name": r.esco_label, "in_esco": bool(r.in_esco)}
                   for r in cand.itertuples()],                       # everything extracted from the CV
        "requirements": [{"esco_uri": r.esco_uri, "name": r.esco_label, "importance": round(float(r.weight), 4),
                          "covered": bool(r.covered), "reason": r.reason, "evidence": r.closest_evidence,
                          "gap_confidence": float(r.gap_confidence), "uncalibrated": r.esco_label in unseen}
                         for r in tab.itertuples()],
    }
