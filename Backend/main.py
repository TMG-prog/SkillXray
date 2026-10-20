"""
Skill extraction service. The Supabase edge function posts the resume text here
and saves the result itself, so this service never touches Supabase.

POST /extract   {"text": "..."}   ->   {"skills": ["python", "sql", ...]}
"""
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from transformers import pipeline

MODEL_ID = os.environ["SKILL_MODEL_ID"]  # your Hugging Face model id
HF_TOKEN = os.environ.get("HF_TOKEN")  # only needed for a private model
API_KEY = os.environ["MODEL_API_KEY"]  # same value as MODEL_API_KEY in Supabase

extractor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global extractor
    # Raw token output (no aggregation): B/I tags are merged below using offsets.
    extractor = pipeline("token-classification", model=MODEL_ID, token=HF_TOKEN)
    yield


app = FastAPI(lifespan=lifespan)


class ExtractRequest(BaseModel):
    text: str


def chunk(text: str, size: int = 1000):
    # Small chunks keep each piece under the model's 512-token limit.
    i = 0
    while i < len(text):
        end = min(i + size, len(text))
        if end < len(text):
            space = text.rfind(" ", i, end)
            if space > i + size // 2:
                end = space
        yield text[i:end]
        i = end


def spans_from_tokens(tokens, text):
    spans, cur = [], None
    for t in tokens:
        label = str(t["entity"]).upper()
        if label.startswith("B"):
            cur = {"start": t["start"], "end": t["end"], "scores": [float(t["score"])]}
            spans.append(cur)
        elif label.startswith("I") and cur and t["start"] - cur["end"] <= 2:
            cur["end"] = t["end"]
            cur["scores"].append(float(t["score"]))
        else:
            cur = None
    for s in spans:
        skill = text[s["start"]:s["end"]].strip(" ,.;:()[]\u2022-")
        yield skill, sum(s["scores"]) / len(s["scores"])


@app.get("/health")
def health():
    return {"ok": extractor is not None}


@app.post("/extract")
def extract(req: ExtractRequest, authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, API_KEY):
        raise HTTPException(401, "Unauthorized.")

    text = " ".join(req.text.split())
    pieces = list(chunk(text))[:60]
    if not pieces:
        return {"skills": []}

    found = {}
    for piece, tokens in zip(pieces, extractor(pieces, batch_size=16)):
        for skill, score in spans_from_tokens(tokens, piece):
            if not (2 <= len(skill) <= 60):
                continue
            key = skill.lower()
            if key not in found or score > found[key][1]:
                found[key] = (skill, score)

    ranked = sorted(found.values(), key=lambda s: -s[1])
    return {"skills": [skill for skill, _ in ranked]}