#!/usr/bin/env python3
"""
SkillXray: JSearch -> Supabase job_postings ingestion worker.

Port of the notebook's 17a (fetch_postings / _select / quota handling). Run it on a schedule (cron, GitHub Actions, Render/Railway cron).
It only fetches and stores postings; building profiles from them is a separate job.

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   server-side only, never in a browser or the app
  RAPIDAPI_KEY                              sent as the x-api-key header (same variable name as the notebook)
Optional: JSEARCH_COUNTRY (default us), JSEARCH_MONTHLY_QUOTA (200), QUOTA_RESERVE (10), JSEARCH_DATE_POSTED (month)

Examples:
  python ingest_postings.py --roles software --target 40        # smoke test: one role, about 4-7 requests
  python ingest_postings.py --max-roles 3                       # the 3 stalest roles

Monthly schedule: .github/workflows/monthly-jsearch-ingest.yml runs this on the 1st of each month.
"""
import argparse, datetime as dt, hashlib, logging, math, os, re, sys, time
import requests
from supabase import create_client

JSEARCH_URL = "https://api.openwebninja.com/jsearch/search"
MIN_DESCRIPTION_CHARS = 400
MIN_ROLE_POSTINGS = 30            # LIVE_MIN_POSTINGS in the notebook: below this a role is "short" and gets the relaxed tier + synonym queries
EXPAND_MAX_PAGES = 4
RECENT_DAYS = 60                  # postings fetched within this window count as "already have" for dedupe and for the target
PAUSE_S = 0.3

# synonym queries are stored in job_roles.extra_queries (seeded from the notebook's ROLE_EXTRA_QUERIES)
RELAXED_GENERIC = {"specialist", "analyst", "manager", "engineer", "officer", "senior", "junior", "assistant", "coordinator",
                   "administrator", "representative", "associate", "lead", "executive", "technical", "information", "technology",
                   "service", "services", "systems", "system", "network", "data", "and", "the", "for", "with", "support",
                   "end", "back", "front", "full", "stack"}
RELAXED_KEEP = {"support"}

log = logging.getLogger("ingest")


# ----------------------------------------------------------------------------- config
def cfg_from_env():
    return {
        "country": os.environ.get("JSEARCH_COUNTRY", "us").lower(),
        "quota": int(os.environ.get("JSEARCH_MONTHLY_QUOTA", "200")),
        "reserve": int(os.environ.get("QUOTA_RESERVE", "10")),
        "date_posted": os.environ.get("JSEARCH_DATE_POSTED", "month"),
        "api_key": os.environ.get("RAPIDAPI_KEY"),
    }


# ----------------------------------------------------------------------------- role catalogue (from job_roles)
def load_catalogue(sb):
    rows = sb.table("job_roles").select(
        "id, model_role, search_query, title_pattern, extra_queries, match_order, last_ingested_at"
    ).not_.is_("model_role", "null").not_.is_("search_query", "null").not_.is_("title_pattern", "null").execute().data
    rows = [r for r in rows if r.get("model_role") and r.get("title_pattern") and r.get("search_query")]
    rows.sort(key=lambda r: (r["match_order"] is None, r["match_order"] or 0))      # role_of_title: FIRST match wins, so order matters
    for r in rows:
        r["_rx"] = re.compile(r["title_pattern"], re.I)
    return rows


def role_of_title(title, catalogue):
    t = str(title or "")
    for r in catalogue:
        if r["_rx"].search(t):
            return r["model_role"]
    return None


def role_vocab(row):
    """Distinctive words of a role (name, query, pattern words) minus generic title words. Used only for unmapped titles."""
    pat = re.sub(r"\\[a-zA-Z]", " ", row["title_pattern"] or "")
    words = set(re.findall(r"[a-z]{3,}", f'{row["model_role"]} {row["search_query"]} {pat}'.lower()))
    return {w for w in words if w not in RELAXED_GENERIC or w in RELAXED_KEEP}


# ----------------------------------------------------------------------------- selecting postings (the notebook's _select)
def normalize(p):
    """One JSearch item -> flat posting. The full item is kept as raw."""
    title = (p.get("job_title") or "").strip()
    comp = (p.get("employer_name") or "").strip()
    desc = (p.get("job_description") or "").strip()
    jid = str(p.get("job_id") or "") or f"{title}|{comp}"
    if len(jid) > 255:
        jid = "sha256:" + hashlib.sha256(jid.encode("utf-8")).hexdigest()
    loc = ", ".join(x for x in (p.get("job_city"), p.get("job_state"), p.get("job_country")) if x)
    return {"id": jid, "title": title, "company": comp, "description": desc, "location": loc,
            "posted_at": p.get("job_posted_at_datetime_utc") or None, "apply_url": p.get("job_apply_link") or None,
            "publisher": p.get("job_publisher") or None, "raw": p}


def dedupe_key(title, company, desc):
    return f"{title.lower()}|{company.lower()}|{desc[:80].lower()}"


def select_postings(raw_jobs, row, catalogue, policy="strict", known_ids=frozenset(), known_keys=frozenset()):
    """raw jobs -> (kept, rejection counts). policy 'strict': title maps to this role. 'relaxed': also titles that map to NO role
    but contain a distinctive word of the role. A title that maps to a DIFFERENT role is rejected under both."""
    role, vocab = row["model_role"], role_vocab(row)
    seen_ids, seen_keys, kept, rej = set(known_ids), set(known_keys), [], {}
    def no(reason): rej[reason] = rej.get(reason, 0) + 1
    for p in raw_jobs:
        if len(p["description"]) < MIN_DESCRIPTION_CHARS:
            no("short_description"); continue
        mapped = role_of_title(p["title"], catalogue)
        if mapped == role:
            tier = "role"
        elif mapped is None:
            if policy == "relaxed" and set(re.findall(r"[a-z]{3,}", p["title"].lower())) & vocab:
                tier = "relaxed"
            else:
                no("unmapped_title"); continue
        else:
            no("other_role"); continue
        key = dedupe_key(p["title"], p["company"], p["description"])
        if p["id"] in seen_ids or key in seen_keys:
            no("duplicate"); continue
        seen_ids.add(p["id"]); seen_keys.add(key)
        kept.append({**p, "title_match": tier, "dedupe_key": key})
    return kept, rej


# ----------------------------------------------------------------------------- quota (counter lives in the database)
def month_tag():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


def quota_used(sb):
    r = sb.table("jsearch_usage").select("requests").eq("month", month_tag()).execute().data
    return int(r[0]["requests"]) if r else 0


def bump_quota(sb):
    sb.rpc("bump_jsearch_usage", {"p_month": month_tag()}).execute()


class QuotaExhausted(Exception):
    pass


# ----------------------------------------------------------------------------- JSearch
def _get_json(headers, params, tries=4, timeout=90):
    for k in range(tries):
        try:
            r = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if k < tries - 1:
                time.sleep(2 ** k * 2.0); continue
            raise
        if r.status_code in (429, 500, 502, 503, 504) and k < tries - 1:
            time.sleep(2 ** k * 2.0); continue
        r.raise_for_status()
        return r.json()


def search(sb, cfg, query, page):
    """One paid request. The counter is bumped after a successful response."""
    if cfg["quota"] - quota_used(sb) <= cfg["reserve"]:
        raise QuotaExhausted(f"quota reserve reached ({quota_used(sb)}/{cfg['quota']} used this month)")
    js = _get_json({"x-api-key": cfg["api_key"]},
                   {"query": query, "page": page, "num_pages": 1, "country": cfg["country"], "date_posted": cfg["date_posted"]})
    bump_quota(sb)
    return js


# ----------------------------------------------------------------------------- one role
def fetch_existing(sb, role):
    """ids and dedupe keys of this role's postings fetched in the last RECENT_DAYS (paged: the API returns at most 1000 rows)."""
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)).isoformat()
    ids, keys, start = set(), set(), 0
    while True:
        rows = (sb.table("job_postings").select("external_id, dedupe_key").eq("role_key", role)
                .gte("fetched_at", since).range(start, start + 999).execute().data)
        for r in rows:
            ids.add(r["external_id"])
            if r.get("dedupe_key"): keys.add(r["dedupe_key"])
        if len(rows) < 1000: break
        start += 1000
    return ids, keys


def ingest_role(sb, cfg, row, catalogue, target, dry_run=False):
    role = row["model_role"]
    ids, keys = fetch_existing(sb, role)
    have = len(ids)
    need = max(target - have, 0)
    stats = {"role": role, "had": have, "requests": 0, "raw": 0, "stored": 0, "rejected": {}}
    if need == 0:
        log.info("[%s] already has %d recent postings (target %d): nothing to fetch", role, have, target)
        return stats

    raw, queries_done = [], []
    def run_query(q, pages, policy):
        for page in range(1, pages + 1):
            js = search(sb, cfg, q, page); stats["requests"] += 1
            if page == 1 and not (js or {}).get("data") and (js or {}).get("status") not in (None, "OK", "ok"):
                raise RuntimeError(f"JSearch preflight failed: status={js.get('status')!r} error={js.get('error')!r}")
            data = (js or {}).get("data") or []
            if not data: break                                       # the API stops at the first empty page
            raw.extend(normalize(p) for p in data)
            if len(select_postings(raw, row, catalogue, policy, ids, keys)[0]) >= need: break
            time.sleep(PAUSE_S)
        queries_done.append(q)

    try:
        run_query(row["search_query"], math.ceil(need / 10) + 3, "strict")
        policy = "strict"
        kept, _ = select_postings(raw, row, catalogue, "strict", ids, keys)
        if have + len(kept) < MIN_ROLE_POSTINGS:                    # short: relaxed title tier, then synonym queries
            policy = "relaxed"
            for q in (row.get("extra_queries") or []):
                kept, _ = select_postings(raw, row, catalogue, policy, ids, keys)
                if have + len(kept) >= MIN_ROLE_POSTINGS: break
                run_query(q, EXPAND_MAX_PAGES, policy)
    except QuotaExhausted as e:
        log.warning("[%s] %s: storing what was fetched so far", role, e)
        policy = "relaxed" if len(raw) else "strict"
        stats["quota_hit"] = True

    kept, rej = select_postings(raw, row, catalogue, policy, ids, keys)
    kept = kept[:need]
    stats.update(raw=len(raw), stored=len(kept), rejected=rej, policy=policy)

    rows = [{
        "job_role_id": row["id"], "role_key": role, "provider": "jsearch", "external_id": p["id"],
        "title": p["title"][:255], "company": (p["company"] or None) and p["company"][:255],
        "description": p["description"], "location": p["location"][:255] or None,
        "posted_at": p["posted_at"], "apply_url": p["apply_url"], "publisher": (p["publisher"] or None) and p["publisher"][:255],
        "country": cfg["country"], "query": queries_done[0] if queries_done else row["search_query"],
        "title_match": p["title_match"], "dedupe_key": p["dedupe_key"], "raw_data": p["raw"],
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    } for p in kept]

    if not dry_run:
        for i in range(0, len(rows), 100):
            sb.table("job_postings").upsert(rows[i:i + 100], on_conflict="provider,external_id", ignore_duplicates=True).execute()
        if stats["requests"]:
            sb.table("job_roles").update({"last_ingested_at": dt.datetime.now(dt.timezone.utc).isoformat()}).eq("id", row["id"]).execute()
    log.info("[%s] requests=%d raw=%d stored=%d (had %d) policy=%s rejected=%s", role, stats["requests"], len(raw), len(rows), have, policy, rej)
    return stats


# ----------------------------------------------------------------------------- run log (shown read-only in the admin console)
def start_run(sb, trigger):
    try:
        return sb.table("ingestion_runs").insert({"trigger": trigger}).execute().data[0]["id"]
    except Exception as e:                                          # the log must never block ingestion
        log.warning("could not record the run (apply the ingestion_runs migration): %s", e)
        return None


def finish_run(sb, run_id, results, failed, error=None):
    if not run_id:
        return
    status = "failed" if error else "partial" if failed or any(s.get("quota_hit") for s in results) else "success"
    try:
        sb.table("ingestion_runs").update({
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": status,
            "requests_used": sum(s["requests"] for s in results), "postings_stored": sum(s["stored"] for s in results),
            "roles": [{k: s.get(k) for k in ("role", "had", "requests", "stored", "quota_hit")} for s in results] + failed,
            "error": error,
        }).eq("id", run_id).execute()
    except Exception as e:
        log.warning("could not update the run record: %s", e)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roles", nargs="*", help="model_role values to ingest (default: the stalest roles)")
    ap.add_argument("--max-roles", type=int, default=3, help="how many roles to process when --roles is not given")
    ap.add_argument("--target", type=int, default=100, help="recent postings wanted per role (about 10 postings per request)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and count quota, but write nothing to job_postings / job_roles")
    ap.add_argument("--trigger", default="manual", help="label stored with the run record, e.g. scheduled")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    cfg = cfg_from_env()
    for k, v in (("RAPIDAPI_KEY", cfg["api_key"]), ("SUPABASE_URL", os.environ.get("SUPABASE_URL")),
                 ("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))):
        if not v: sys.exit(f"set {k}")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    catalogue = load_catalogue(sb)
    if not catalogue: sys.exit("job_roles has no usable rows: run seed_job_roles.sql first")
    by_role = {r["model_role"]: r for r in catalogue}
    if args.roles:
        unknown = [r for r in args.roles if r not in by_role]
        if unknown: sys.exit(f"unknown model_role: {unknown}")
        todo = [by_role[r] for r in args.roles]
    else:
        todo = sorted(catalogue, key=lambda r: (r["last_ingested_at"] is not None, r["last_ingested_at"] or ""))[:args.max_roles]

    log.info("quota used this month: %d/%d (reserve %d) | roles: %s", quota_used(sb), cfg["quota"], cfg["reserve"], [r["model_role"] for r in todo])
    run_id = None if args.dry_run else start_run(sb, args.trigger)
    results, failed = [], []
    for row in todo:
        try:
            results.append(ingest_role(sb, cfg, row, catalogue, args.target, args.dry_run))
        except QuotaExhausted as e:
            log.warning("stopping: %s", e); break
        except Exception as e:                                      # one bad role must not stop the others
            log.error("[%s] failed: %s: %s", row["model_role"], type(e).__name__, e)
            failed.append({"role": row["model_role"], "error": f"{type(e).__name__}: {e}"[:300]})
    finish_run(sb, run_id, results, failed, "every role failed" if failed and not results else None)
    log.info("quota used this month: %d/%d", quota_used(sb), cfg["quota"])


if __name__ == "__main__":
    main()
