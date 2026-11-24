"""Admin-only HTTP service. Supabase service credentials never leave this process."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlsplit

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

log = logging.getLogger("skillxray.admin")
ROOT = Path(__file__).resolve().parent
ESCO_DIR = Path(os.getenv("ADMIN_ESCO_DIR", ROOT.parent / "Backend" / "data" / "esco"))
MAX_FILE_BYTES = 10 * 1024 * 1024
BUCKET = "admin-datasets"
app = FastAPI(title="SkillXray Administration", docs_url=None, redoc_url=None, openapi_url=None)


class Supabase:
    def __init__(self, url: str, anon_key: str, service_key: str):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise RuntimeError("SUPABASE_URL must be an HTTP(S) URL.")
        if not anon_key or not service_key:
            raise RuntimeError("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are required.")
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.service_key = service_key

    def request(self, method: str, path: str, *, token: str | None = None,
                service: bool = False, **kwargs) -> httpx.Response:
        key = self.service_key if service else self.anon_key
        headers = {"apikey": key, "Authorization": f"Bearer {token or key}"}
        headers.update(kwargs.pop("headers", {}))
        try:
            response = httpx.request(method, self.url + path, headers=headers, timeout=30, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("Supabase request failed: %s %s: %s", method, path.split("?")[0], type(exc).__name__)
            raise HTTPException(503, "Unable to reach Supabase.") from exc
        if not response.is_success:
            log.warning("Supabase request failed: %s %s (HTTP %s)", method, path.split("?")[0], response.status_code)
            if not service and response.status_code in (400, 401, 403):
                raise HTTPException(401, "Invalid or expired credentials.")
            if response.status_code in (400, 404, 409, 422):
                raise HTTPException(response.status_code, "Supabase rejected the request; check the submitted data.")
            raise HTTPException(502, "Supabase could not complete the request.")
        return response


@lru_cache(maxsize=1)
def gateway() -> Supabase:
    return Supabase(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", ""),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    )


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(ROOT / "app.js", media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet():
    return FileResponse(ROOT / "style.css", media_type="text/css")


@app.post("/api/login")
def login(body: Login, sb: Supabase = Depends(gateway)):
    result = sb.request("POST", "/auth/v1/token", params={"grant_type": "password"},
                        json={"email": body.email, "password": body.password}).json()
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise HTTPException(502, "Supabase returned an invalid session.")
    admin_user(f"Bearer {token}", sb)
    return {"access_token": token}


def admin_user(authorization: str | None = Header(default=None), sb: Supabase = Depends(gateway)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Administrator sign-in is required.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Administrator sign-in is required.")
    user = sb.request("GET", "/auth/v1/user", token=token).json()
    user_id = user.get("id")
    if not isinstance(user_id, str):
        raise HTTPException(401, "Invalid or expired session.")
    membership = sb.request("GET", "/rest/v1/admin_members", service=True,
                            params={"select": "user_id", "user_id": f"eq.{user_id}", "limit": "1"}).json()
    if not membership:
        raise HTTPException(403, "This account is not an administrator.")
    return user_id


def uuid_value(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(422, "Invalid identifier.") from exc


def table(sb: Supabase, method: str, name: str, *, params=None, data=None, upsert=False):
    prefer = "return=representation"
    if upsert:
        prefer += ",resolution=merge-duplicates"
    response = sb.request(method, f"/rest/v1/{name}", service=True, params=params,
                          json=data, headers={"Prefer": prefer})
    return response.json() if response.content else []


def table_all(sb: Supabase, name: str, params: dict):
    rows = []
    while True:
        page = table(sb, "GET", name, params={**params, "limit": 100, "offset": len(rows)})
        if not isinstance(page, list):
            raise HTTPException(502, "Supabase returned an invalid list.")
        rows.extend(page)
        if len(page) < 100:
            return rows


def require_row(rows):
    if not rows:
        raise HTTPException(404, "Record not found.")
    return rows


@app.get("/api/session")
def session(user_id: str = Depends(admin_user)):
    return {"user_id": user_id}


@app.get("/api/users")
def users(page: int = 1, search: str = "", user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    if page < 1:
        raise HTTPException(422, "Page must be positive.")
    term = search.strip().casefold()
    matches = []
    source_page = 1 if term else page
    while True:
        result = sb.request("GET", "/auth/v1/admin/users", service=True,
                            params={"page": source_page, "per_page": 50}).json()
        items = result.get("users", [])
        ids = [uuid_value(item["id"]) for item in items]
        profiles = table(sb, "GET", "profiles", params={
            "select": "id,full_name", "id": f"in.({','.join(ids)})"
        }) if ids else []
        names = {p["id"]: p.get("full_name") for p in profiles}
        for item in items:
            name = names.get(item["id"])
            if not term or term in f"{item.get('email') or ''} {name or ''}".casefold():
                matches.append({"id": item["id"], "email": item.get("email"), "full_name": name,
                                "banned_until": item.get("banned_until")})
        if not term:
            return {"users": matches, "page": page, "has_next": len(items) == 50}
        if len(matches) > page * 50 or len(items) < 50:
            return {"users": matches[(page - 1) * 50:page * 50], "page": page,
                    "has_next": len(matches) > page * 50}
        source_page += 1


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=80)


@app.put("/api/users/{target_id}/profile")
def update_profile(target_id: str, body: ProfileUpdate, user_id: str = Depends(admin_user),
                   sb: Supabase = Depends(gateway)):
    name = body.full_name.strip()
    if not name:
        raise HTTPException(422, "Name must not be blank.")
    result = table(sb, "POST", "profiles", params={"on_conflict": "id"},
                   data={"id": uuid_value(target_id), "full_name": name}, upsert=True)
    return {"profile": result}


class Suspension(BaseModel):
    suspended: bool


@app.put("/api/users/{target_id}/suspension")
def suspend_user(target_id: str, body: Suspension, user_id: str = Depends(admin_user),
                 sb: Supabase = Depends(gateway)):
    target_id = uuid_value(target_id)
    if body.suspended:
        members = table(sb, "GET", "admin_members", params={"select": "user_id", "user_id": f"eq.{target_id}"})
        if target_id == user_id or members:
            raise HTTPException(403, "Administrator accounts cannot be suspended here.")
    sb.request("PUT", f"/auth/v1/admin/users/{target_id}", service=True,
               json={"ban_duration": "876000h" if body.suspended else "none"})
    return {"suspended": body.suspended}


class JobRole(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    model_role: str | None = None
    search_query: str | None = None
    title_pattern: str | None = None


def clean_role(body: JobRole):
    values = body.model_dump()
    values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    if not values["title"]:
        raise HTTPException(422, "Role title must not be blank.")
    if values["title_pattern"]:
        try:
            re.compile(values["title_pattern"])
        except re.error as exc:
            raise HTTPException(422, "The title pattern is not a valid regular expression.") from exc
    return values


@app.get("/api/roles")
def roles(search: str = "", offset: int = 0, user_id: str = Depends(admin_user),
          sb: Supabase = Depends(gateway)):
    if offset < 0:
        raise HTTPException(422, "Offset must not be negative.")
    params = {"select": "id,title,description,model_role,search_query,title_pattern",
              "order": "title.asc", "limit": 50, "offset": offset}
    if search.strip():
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["title"] = f"ilike.*{term}*"
    return {"roles": table(sb, "GET", "job_roles", params=params)}


@app.post("/api/roles")
def create_role(body: JobRole, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"roles": table(sb, "POST", "job_roles", data=clean_role(body))}


@app.put("/api/roles/{role_id}")
def update_role(role_id: str, body: JobRole, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"roles": require_row(table(sb, "PATCH", "job_roles", params={"id": f"eq.{uuid_value(role_id)}"},
                                       data=clean_role(body)))}


@app.delete("/api/roles/{role_id}")
def delete_role(role_id: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"roles": require_row(table(sb, "DELETE", "job_roles", params={"id": f"eq.{uuid_value(role_id)}"}))}


ESCO_FILES = {
    "skill": "skills_en.csv",
    "occupation": "occupations_en.csv",
    "skill_relation": "skillSkillRelations_en.csv",
    "broader_relation": "broaderRelationsSkillPillar_en.csv",
}


@app.get("/api/esco/{kind}")
def esco(kind: str, search: str = "", offset: int = 0, user_id: str = Depends(admin_user)):
    if kind not in ESCO_FILES or offset < 0:
        raise HTTPException(422, "Invalid taxonomy type or offset.")
    path = ESCO_DIR / ESCO_FILES[kind]
    if not path.is_file():
        raise HTTPException(404, f"{ESCO_FILES[kind]} is not installed on this server.")
    term = search.strip().casefold()
    rows = []
    total = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if term and not any(term in str(value or "").casefold() for value in row.values()):
                continue
            if offset <= total < offset + 50:
                rows.append(row)
            total += 1
    return {"rows": rows, "total": total, "offset": offset}


class TaxonomyChange(BaseModel):
    kind: Literal["skill", "occupation", "skill_relation", "broader_relation"]
    operation: Literal["upsert", "delete"]
    record_key: str = Field(min_length=1, max_length=1000)
    record: dict = Field(default_factory=dict)


def validate_taxonomy_change(body: TaxonomyChange):
    required = {
        "skill": ("conceptUri",),
        "occupation": ("conceptUri",),
        "skill_relation": ("originalSkillUri", "relatedSkillUri", "relationType"),
        "broader_relation": ("conceptUri", "broaderUri"),
    }[body.kind]
    if any(not isinstance(body.record.get(field), str) or not body.record[field].strip() for field in required):
        raise HTTPException(422, f"Record requires: {', '.join(required)}.")
    key = "|".join(body.record[field].strip() for field in required)
    if body.record_key != key:
        raise HTTPException(422, "Record key must match the record identifiers joined by |.")
    if body.operation == "upsert" and body.kind in ("skill", "occupation"):
        if not str(body.record.get("preferredLabel", "")).strip():
            raise HTTPException(422, "A preferredLabel is required.")


@app.get("/api/taxonomy-changes")
def taxonomy_changes(user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"changes": table_all(sb, "admin_taxonomy_changes",
                                 {"select": "*", "order": "updated_at.desc,id.asc"})}


@app.put("/api/taxonomy-changes")
def stage_taxonomy(body: TaxonomyChange, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    validate_taxonomy_change(body)
    data = {**body.model_dump(), "updated_by": user_id}
    result = table(sb, "POST", "admin_taxonomy_changes", params={"on_conflict": "kind,record_key"},
                   data=data, upsert=True)
    return {"changes": result}


@app.delete("/api/taxonomy-changes/{change_id}")
def remove_taxonomy_change(change_id: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"changes": require_row(table(sb, "DELETE", "admin_taxonomy_changes",
                                         params={"id": f"eq.{uuid_value(change_id)}"}))}


@app.get("/api/taxonomy-export")
def export_taxonomy(user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    result = table_all(sb, "admin_taxonomy_changes", {"select": "*", "order": "updated_at.asc,id.asc"})
    content = json.dumps({"format": "skillxray-esco-changes-v1", "changes": result}, indent=2)
    return Response(content, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="esco-changes.json"'})


@app.get("/api/postings")
def postings(search: str = "", offset: int = 0, user_id: str = Depends(admin_user),
             sb: Supabase = Depends(gateway)):
    if offset < 0:
        raise HTTPException(422, "Offset must not be negative.")
    params = {"select": "id,title,company,role_key,provider,posted_at", "order": "created_at.desc",
              "limit": 50, "offset": offset}
    if search.strip():
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["title"] = f"ilike.*{term}*"
    return {"postings": table(sb, "GET", "job_postings", params=params)}


@app.post("/api/postings/import")
async def import_postings(file: UploadFile = File(...), user_id: str = Depends(admin_user),
                          sb: Supabase = Depends(gateway)):
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds the 10 MB limit.")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        required = {"provider", "external_id", "role_key", "title"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise HTTPException(422, "CSV must include provider, external_id, role_key and title.")
        allowed = required | {"company", "description", "location", "posted_at", "apply_url", "publisher", "country"}
        rows = []
        for row in reader:
            if len(rows) >= 1000:
                raise HTTPException(422, "Import at most 1,000 postings per file.")
            clean = {key: (row.get(key) or "").strip() or None for key in allowed}
            if any(not clean.get(key) for key in required):
                raise HTTPException(422, f"Row {len(rows) + 2} is missing a required field.")
            rows.append(clean)
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8 encoded.") from exc
    if not rows:
        raise HTTPException(422, "CSV contains no postings.")
    timestamp = datetime.now(timezone.utc).isoformat()
    for row in rows:
        row.update(job_role_id=None, dedupe_key=None, raw_data={}, fetched_at=timestamp, updated_at=timestamp)
    result = table(sb, "POST", "job_postings", params={"on_conflict": "provider,external_id"},
                   data=rows, upsert=True)
    return {"imported": len(result)}


@app.get("/api/ingestion")
def ingestion_status(user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    def attempt(name, params):
        try:
            return table(sb, "GET", name, params=params)
        except HTTPException as exc:
            if exc.status_code in (400, 404):
                return None
            raise

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = attempt("jsearch_usage", {"select": "requests", "month": f"eq.{month}"})
    runs = attempt("ingestion_runs", {"select": "*", "order": "started_at.desc", "limit": 5})
    roles = attempt("job_roles", {"select": "title,model_role,last_ingested_at", "model_role": "not.is.null",
                                  "order": "last_ingested_at.asc.nullsfirst", "limit": 100})
    return {
        "month": month,
        "quota": {"used": int(usage[0]["requests"]) if usage else 0,
                  "limit": int(os.getenv("JSEARCH_MONTHLY_QUOTA", "200")),
                  "reserve": int(os.getenv("QUOTA_RESERVE", "10"))},
        "schedule": "03:00 UTC on the 1st of every month",
        "runs": runs or [],
        "roles": roles or [],
        "setup_required": usage is None or runs is None,
    }


@app.delete("/api/postings/{posting_id}")
def delete_posting(posting_id: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"postings": require_row(table(sb, "DELETE", "job_postings", params={"id": f"eq.{uuid_value(posting_id)}"}))}


@app.get("/api/datasets")
def datasets(user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    files = []
    offset = 0
    while True:
        result = sb.request("POST", f"/storage/v1/object/list/{BUCKET}", service=True,
                            json={"limit": 100, "offset": offset,
                                  "sortBy": {"column": "name", "order": "asc"}}).json()
        if not isinstance(result, list):
            raise HTTPException(502, "Supabase returned an invalid file list.")
        files.extend(item for item in result if item.get("id"))
        if len(result) < 100:
            return {"files": files}
        offset += len(result)


def file_key(name: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}__[A-Za-z0-9._-]{1,120}", name):
        raise HTTPException(422, "Invalid dataset filename.")
    return name


@app.post("/api/datasets")
async def upload_dataset(file: UploadFile = File(...), user_id: str = Depends(admin_user),
                         sb: Supabase = Depends(gateway)):
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds the 10 MB limit.")
    if not data:
        raise HTTPException(422, "File is empty.")
    original = Path((file.filename or "dataset").replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original)[:120] or "dataset"
    name = f"{uuid.uuid4().hex}__{safe_name}"
    sb.request("POST", f"/storage/v1/object/{BUCKET}/{quote(name)}", service=True,
               content=data, headers={"Content-Type": "application/octet-stream", "x-upsert": "false"})
    return {"name": name}


@app.get("/api/datasets/{name}")
def download_dataset(name: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    name = file_key(name)
    result = sb.request("GET", f"/storage/v1/object/{BUCKET}/{quote(name)}", service=True)
    return Response(result.content, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{name.split("__", 1)[1]}"'})


@app.delete("/api/datasets/{name}")
def delete_dataset(name: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    name = file_key(name)
    result = sb.request("DELETE", f"/storage/v1/object/{BUCKET}", service=True, json={"prefixes": [name]}).json()
    require_row(result)
    return {"deleted": name}


class Resource(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    keywords: list[str] = Field(min_length=1, max_length=30)
    priority: int = 100
    published: bool = False
    trust_signals: list[Literal[
        "nita_accredited", "university_backed", "free_open_access", "industry_certification"
    ]] = Field(default_factory=list, max_length=4)
    trust_evidence_url: str | None = Field(default=None, max_length=2000)


def clean_resource(body: Resource):
    data = body.model_dump()
    for key in ("title", "provider", "url"):
        data[key] = data[key].strip()
    parsed = urlsplit(data["url"])
    if not data["title"] or not data["provider"] or parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(422, "A title, provider and valid HTTP(S) URL are required.")
    data["keywords"] = list(dict.fromkeys(word.strip().casefold() for word in data["keywords"] if word.strip()))
    if not data["keywords"]:
        raise HTTPException(422, "At least one keyword is required.")
    data["trust_signals"] = list(dict.fromkeys(data["trust_signals"]))
    evidence_url = (data["trust_evidence_url"] or "").strip()
    parsed_evidence = urlsplit(evidence_url) if evidence_url else None
    if data["trust_signals"] and (
        parsed_evidence is None
        or parsed_evidence.scheme not in ("http", "https")
        or not parsed_evidence.netloc
    ):
        raise HTTPException(422, "Trust signals require a valid HTTP(S) evidence URL.")
    data["trust_evidence_url"] = evidence_url or None
    return data


@app.get("/api/resources")
def resources(user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"resources": table_all(sb, "learning_resources",
                                   {"select": "*", "order": "priority.asc,title.asc,id.asc"})}


@app.post("/api/resources")
def create_resource(body: Resource, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"resources": table(sb, "POST", "learning_resources", data=clean_resource(body))}


@app.put("/api/resources/{resource_id}")
def update_resource(resource_id: str, body: Resource, user_id: str = Depends(admin_user),
                    sb: Supabase = Depends(gateway)):
    return {"resources": require_row(table(sb, "PATCH", "learning_resources",
                                           params={"id": f"eq.{uuid_value(resource_id)}"}, data=clean_resource(body)))}


@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: str, user_id: str = Depends(admin_user), sb: Supabase = Depends(gateway)):
    return {"resources": require_row(table(sb, "DELETE", "learning_resources",
                                           params={"id": f"eq.{uuid_value(resource_id)}"}))}
