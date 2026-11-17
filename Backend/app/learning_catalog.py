"""Published administrator-managed learning resources for recommendations."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

import httpx

log = logging.getLogger("skillxray.learning_catalog")
Resource = tuple[tuple[str, ...], str, str, str]


def published_resources() -> tuple[Resource, ...] | None:
    if os.getenv("LEARNING_RESOURCES_CATALOG", "0") != "1":
        return None
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("LEARNING_RESOURCES_CATALOG requires SUPABASE_URL and SUPABASE_ANON_KEY.")
    rows = []
    try:
        with httpx.Client(timeout=15, headers={"apikey": key, "Authorization": f"Bearer {key}"}) as client:
            while True:
                response = client.get(
                    f"{url}/rest/v1/learning_resources",
                    params={"select": "title,provider,url,keywords", "published": "eq.true",
                            "order": "priority.asc,id.asc", "limit": 500, "offset": len(rows)},
                )
                response.raise_for_status()
                page = response.json()
                if not isinstance(page, list):
                    raise ValueError("Learning resource catalog must return an array.")
                rows.extend(page)
                if len(page) < 500:
                    break
    except (httpx.HTTPError, ValueError):
        log.exception("Could not load the published learning resource catalog.")
        raise

    resources = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid learning resource catalog entry.")
        title, provider, link, keywords = (row.get(key) for key in ("title", "provider", "url", "keywords"))
        parsed = urlsplit(link) if isinstance(link, str) else None
        if (not isinstance(title, str) or not title.strip() or not isinstance(provider, str) or not provider.strip()
                or parsed is None or parsed.scheme not in ("http", "https") or not parsed.netloc
                or not isinstance(keywords, list) or not keywords
                or any(not isinstance(keyword, str) or not keyword.strip() for keyword in keywords)):
            raise ValueError("Invalid learning resource catalog entry.")
        resources.append((tuple(keyword.strip().casefold() for keyword in keywords), title, provider, link))
    return tuple(resources)
