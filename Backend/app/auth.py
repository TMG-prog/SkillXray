"""Supabase sign-in check + a small per-user rate limit.

The app sends its Supabase access token as 'Authorization: Bearer <token>'. We ask Supabase who the token belongs to
(GET {SUPABASE_URL}/auth/v1/user), which works for any Supabase key type and needs no secret on this server beyond the
public anon key. Set REQUIRE_AUTH=0 only for local testing.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

import httpx
from fastapi import HTTPException

from . import config as C

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "1") != "0"
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_cache: dict[str, tuple[str, float]] = {}
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def startup_check():
    if REQUIRE_AUTH and not (SUPABASE_URL and SUPABASE_ANON_KEY):
        raise RuntimeError("Auth is on but SUPABASE_URL / SUPABASE_ANON_KEY are not set. "
                           "Set them as secrets, or set REQUIRE_AUTH=0 for local testing.")


def current_user(authorization: str | None) -> str:
    if not REQUIRE_AUTH:
        return "anonymous"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    now = time.time()
    hit = _cache.get(token)
    if hit and hit[1] > now:
        return hit[0]
    try:
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/user", timeout=10,
                      headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY})
    except httpx.HTTPError:
        raise HTTPException(503, "Could not reach the sign-in service. Try again.")
    if r.status_code != 200 or not r.json().get("id"):
        raise HTTPException(401, "Invalid or expired token.")
    uid = r.json()["id"]
    if len(_cache) > 5000:
        _cache.clear()
    _cache[token] = (uid, now + 60)
    return uid


def check_rate(user: str):
    now = time.time()
    with _lock:
        q = _hits[user]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= C.RATE_LIMIT_PER_MIN:
            raise HTTPException(429, "Too many analyses in a minute. Please wait a little and try again.")
        q.append(now)
