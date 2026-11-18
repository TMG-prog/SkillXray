# SkillXray administration

This is a separate FastAPI web service for authorized administrators. It manages account names and bans,
job roles, staged ESCO changes, job postings, private dataset files, and learning resources. It uses
Supabase Auth for password sign-in and checks `admin_members` for every privileged request. The
service-role key stays on the server. Sessions are held in browser memory and require sign-in again
after a page reload or token expiry.

## Setup

1. Apply the repository's existing Supabase migrations in order, then
   `supabase/migrations/20261117000000_admin_console.sql`. The project must already have `profiles`
   and `job_roles`, including the columns used by the mobile app and posting ingestion. Check their
   schema and permissions in your actual Supabase project; those table definitions are not in this checkout.
   The Supabase API maximum row setting must be at least 500 for complete catalog pagination.
2. Create or select an existing Supabase Auth user and, as a trusted project owner, run this in the
   Supabase SQL editor using that user's UUID:

   ```sql
   insert into public.admin_members (user_id)
   values ('00000000-0000-0000-0000-000000000000')
   on conflict do nothing;
   ```

   Replace the placeholder UUID. Delete that membership in SQL to revoke admin access. Never expose
   the service-role key or grant membership through client-side code.
3. From the repository root, install `admin_app/requirements.txt` in a Python environment, set
   `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` as server environment
   variables, and run:

   ```powershell
   python -m pip install -r admin_app\requirements.txt
   python -m uvicorn admin_app.server:app --host 127.0.0.1 --port 8001
   ```

   Open `http://127.0.0.1:8001`. Do not put keys in frontend files or commit them. For remote use,
   place the service behind HTTPS with restricted network access; do not expose an HTTP listener
   directly to the internet. Use the same Supabase project for the mobile app, analysis API and admin.

## Operations and limitations

- Suspending uses Supabase Auth's 100-year ban; reactivation removes the ban. Administrators cannot
  be suspended from this console. An existing JWT may continue to work until it expires, including
  on direct Supabase requests: this is not immediate revocation. Verify your project policies and
  session behavior before relying on suspension for urgent access control.
- Account search scans Auth users and profile names across pages, so it may be slow for large projects.
- Roles affect the Supabase role catalog and posting ingestion configuration. Adding a role does not
  create a model profile or make it available in the live analysis API.
- ESCO edits are **staged**, not applied to the live scorer. Export the JSON change set, review it and
  manually apply its records to a versioned copy of the corresponding ESCO CSVs. Validate all required
  fields and referential integrity, rebuild the model's ESCO term embedding index with the configured
  encoder, regenerate any dependent artifacts/profiles, and test before deploying the complete set.
  No automated importer or rebuild is provided. The browse view reports missing source files, including
  `occupations_en.csv` if it is not installed. Export is a snapshot; coordinate concurrent edits.
- Posting imports upsert by provider and external ID. Optional CSV columns are `company`, `description`,
  `location`, `posted_at`, `apply_url`, `publisher`, and `country`; omitted fields are cleared on
  matching rows. Role links and ingestion metadata (`job_role_id`, `dedupe_key`, `raw_data`) are cleared
  for imported rows, and their fetch timestamp is refreshed. Restart the analysis backend after posting
  changes to clear its process-lifetime caches. Private dataset files are stored in the `admin-datasets`
  bucket; they are not automatically ingested, analyzed or used for training.
- Published resources are used by analysis only after setting `LEARNING_RESOURCES_CATALOG=1` on the
  analysis backend with `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Without it, existing built-in resources
  are used. With it enabled, an unavailable or invalid catalog causes analysis to fail rather than
  silently returning stale resources. Unmatched skills use the existing course-search fallback.
- JSearch postings are fetched automatically, not from this console. The workflow
  `.github/workflows/monthly-jsearch-ingest.yml` runs `Backend/app/ingest_postings.py` at 03:00 UTC on the
  1st of each month (and on demand from the GitHub Actions tab). Apply
  `supabase/migrations/20261118000000_jsearch_ingestion_status.sql`, then add the repository secrets
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `RAPIDAPI_KEY`. Optional repository variables are
  `JSEARCH_MONTHLY_QUOTA` (default 200), `QUOTA_RESERVE` (10) and `JSEARCH_COUNTRY` (us). The run stops
  when the quota reserve is reached and fetches the least recently ingested roles first. **Datasets →
  Monthly JSearch ingestion** shows quota use, recent runs and each role's last fetch; set the same
  `JSEARCH_MONTHLY_QUOTA`/`QUOTA_RESERVE` in this server's environment so the quota figure matches.
  Restart the analysis backend after a run to clear its process-lifetime caches.

## Tests

From the repository root, with the backend test dependencies installed:

```powershell
$env:PYTHONPATH = 'Backend;.'
python -m pytest -q admin_app\test_server.py Backend\tests\test_learning_catalog.py Backend\tests\test_notebook_pipeline.py
```

These tests mock Supabase; they do not prove the migration or APIs work against a live project.
