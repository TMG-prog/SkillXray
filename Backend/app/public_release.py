# ==============================================================================
# 22. Publish a monthly release to Supabase
# ==============================================================================
# Paste into the notebook after monthly_release() / freeze_profiles() has written release_YYYY-MM-DD.parquet + .json to LIVE_DIR.
# Needs:  pip install psycopg2-binary   and a Colab Secret  SUPABASE_DB_URL  (the *session pooler* connection string from
#         Supabase > Connect; the direct db.<ref>.supabase.co host is IPv6-only unless you bought the IPv4 add-on, and Colab is often IPv4).
# Never put the DB password or the service_role key in the notebook text, and never in the web/app code: the app uses the anon key + RLS.
import os, json, glob, math, datetime
import pandas as pd

_REQ_COLS = ['role', 'esco_uri', 'esco_label', 'in_esco', 'n_docs', 'freq', 'weight', 'n_postings']

def _py(x):
    """numpy / NaN -> plain Python (None for NaN), so psycopg2 can adapt it."""
    if x is None: return None
    if hasattr(x, 'item'): x = x.item()
    if isinstance(x, float) and math.isnan(x): return None
    return x

def check_release(prof, manifest):
    """Problems that should stop a publish. Empty list = fine."""
    bad = [c for c in _REQ_COLS if c not in prof.columns]
    if bad: return [f"release file is missing columns: {bad}"]
    out = []
    if prof.duplicated(['role', 'esco_uri']).any(): out.append("duplicate (role, skill) rows")
    for role, g in prof.groupby('role'):
        info = (manifest.get('roles') or {}).get(role)
        if not info or info.get('source') == 'static': out.append(f"{role}: in the parquet but not a live profile in the manifest")
        if abs(g['weight'].sum() - 1) > 1e-3: out.append(f"{role}: weights sum to {g['weight'].sum():.4f}, not 1")
        if not g['freq'].between(0, 1).all(): out.append(f"{role}: freq outside (0, 1]")
        if info and info.get('n_requirements') not in (None, len(g)): out.append(f"{role}: manifest says {info['n_requirements']} requirements, file has {len(g)}")
    return out

def publish_release_to_supabase(pipeline_version, release_tag=None, period=None, country=None, force=False, dry_run=False):
    """Load one release into Supabase in a single transaction (all roles or none).
    - Re-running the same file replaces those roles; roles already stored for the same month are left alone, so a quota-limited month
      can be filled over several runs.
    - `pipeline_version` (notebook version / git hash) is required: it is what tells you later whether two months are comparable."""
    files = sorted(glob.glob(os.path.join(LIVE_DIR, 'release_*.json')))
    assert files, f"no release_*.json in {LIVE_DIR}: run monthly_release() first"
    jpath = next((f for f in files if release_tag and release_tag in f), files[-1])
    tag = os.path.basename(jpath)[len('release_'):-len('.json')]
    manifest = json.load(open(jpath)); prof = pd.read_parquet(jpath.replace('.json', '.parquet'))
    if 'audited' not in prof.columns:
        print("note: this release has no `audited` column; storing False"); prof['audited'] = False

    problems = check_release(prof, manifest)
    if problems and not force:
        raise ValueError("not publishing:\n  " + "\n  ".join(problems) + "\n(fix the release, or pass force=True)")

    built = datetime.date.fromisoformat(tag)
    period = period or built.replace(day=1)
    countries = {i.get('country') for i in manifest['roles'].values() if i.get('country')}
    country = (country or (countries.pop() if len(countries) == 1 else globals().get('JSEARCH_COUNTRY', 'us'))).lower()[:2]
    cfg = {'extraction': json.loads(json.dumps(globals().get('EXTRACTION_CFG', {}), default=list)),
           'link': json.loads(json.dumps(globals().get('LINK_CFG', {}), default=list)),
           'skillxray_fixes': globals().get('FX_FINAL'), 'skillxray_settings': globals().get('FINAL'),
           'release_tag': tag, 'date_posted': globals().get('JSEARCH_DATE_POSTED', 'month')}

    rr_rows, rq_rows = [], []
    for role, info in manifest['roles'].items():
        n_req = int((prof['role'] == role).sum())
        rr_rows.append([role, info.get('source') or 'static', f"{tag}T00:00:00Z", _py(info.get('n_postings')), _py(info.get('median_skills')),
                        n_req, _py(info.get('n_unaudited')), info.get('reason'), pipeline_version, json.dumps(cfg)])
    for r in prof.itertuples(index=False):
        rq_rows.append([r.role, str(r.esco_uri), str(r.esco_label), bool(r.in_esco), int(r.n_docs), float(r.freq), float(r.weight), bool(r.audited)])

    print(f"release {tag} -> period {period}, country {country}: {len(rr_rows)} roles ({sum(1 for r in rr_rows if r[5] > 0)} with requirements), "
          f"{len(rq_rows)} requirement rows, pipeline_version={pipeline_version!r}")
    if problems: print("FORCED despite:", problems)
    if dry_run:
        print("dry run: nothing written"); return

    import psycopg2
    from psycopg2.extras import execute_values
    url = os.environ.get('SUPABASE_DB_URL') or _secret('SUPABASE_DB_URL')
    assert url, "set the Colab Secret SUPABASE_DB_URL"
    conn = psycopg2.connect(url, connect_timeout=15)
    try:
        with conn:                                   # commit if everything below works, roll back on any error
            with conn.cursor() as cur:
                cur.execute("""insert into public.releases (period, country, date_posted, published)
                               values (%s, %s, %s, false)
                               on conflict (period, country) do update set date_posted = excluded.date_posted, published = false
                               returning release_id""", (period, country, cfg['date_posted']))
                rid = cur.fetchone()[0]
                cur.execute("delete from public.role_releases where release_id = %s and role = any(%s)", (rid, [r[0] for r in rr_rows]))  # cascades
                execute_values(cur, """insert into public.role_releases
                    (release_id, role, source, built_at, n_postings, median_skills, n_requirements, n_unaudited, fallback_reason, pipeline_version, config)
                    values %s""", [[rid, *r] for r in rr_rows])
                if rq_rows:
                    execute_values(cur, """insert into public.role_requirements
                        (release_id, role, skill_uri, skill_label, in_esco, n_docs, freq, weight, audited) values %s""", [[rid, *r] for r in rq_rows])
                cur.execute("update public.releases set published = true where release_id = %s", (rid,))
        print(f"published release_id {rid}")
        return rid
    finally:
        conn.close()

# ---- how to use it
# 1. monthly_release()                                                    (notebook, as before)
# 2. publish_release_to_supabase('v18_eval_fixed', dry_run=True)         (checks the file, prints what would be written)
# 3. publish_release_to_supabase('v18_eval_fixed')                       (writes, one transaction)