---
title: SkillXray
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: "3.10"
app_file: app.py
pinned: false
---

# SkillXray: CV skill-gap analysis

Upload a CV, choose a target role, and get a readiness score plus the skills that current job postings ask for and the CV does not show.
Skills are extracted with the JobBERT checkpoints, mapped to ESCO, and matched with the v22 notebook scorer. The selected rule is exact ESCO matches or semantic similarity between extracted spans and requirement/posting phrases at the saved 0.81 threshold; taxonomy inheritance, context windows and z-score matching remain disabled because the notebook did not select those custom rules.

## What is in this folder

| file | what it is |
|---|---|
| `app.py` | the Gradio web app |
| `skillxray.py` | the scoring pipeline, assembled from the notebook cells (each section says which cells) |
| `requirements.txt` | dependencies (CPU torch) |
| `export_from_notebook.py` | **paste into a notebook cell**; it collects your data files into `skillxray_data.zip` |
| `.gitattributes` | sends parquet/npy/csv to Git LFS, which Hugging Face needs for files over 10 MB |

The model weights are **not** in this folder: the JobBERT and configured sentence-transformer checkpoints download from the Hub on first start. What is missing is your *data*
(ESCO files, embeddings, tuned configs, frozen profiles). That lives on your Drive, so you export it once:

The linker model is selected by `models/linker/linker_config.json`. For non-default models, the cached ESCO index must
be named `models/sbert/esco_term_embeddings_<model-id-with-slashes-replaced-by-underscores>.npy` (for example,
`esco_term_embeddings_BAAI_bge-large-en-v1.5.npy` for `BAAI/bge-large-en-v1.5`). The legacy
`all-MiniLM-L6-v2` model uses `esco_term_embeddings.npy`. Keep the index generated for that model; a same-row-count
index from another encoder is not compatible.

## Deploy

1. **Export the data.** In the Colab session of the notebook (after `freeze_profiles()`), paste `export_from_notebook.py` into a cell and run it.
   It writes `skillxray_data.zip` to your SkillXray Drive folder. It lists every file it copied and flags any required file it could not find.
2. **Unzip it into this folder**, keeping the layout (`data/esco/...`, `models/...`, `results/...`, `data/processed/...`).
3. **Run the API used by the mobile app (local development):** the notebook export is already expected in its documented
   directory layout (`data/esco`, `models`, `results`, and `data/processed`). From `Backend/`, install the Python
   requirements if needed, set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and the server-only
   `SUPABASE_SERVICE_ROLE_KEY` in the backend process environment, then run:
   ```bash
   python -m pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   The FastAPI API loads `app/notebook_pipeline.py`, an adapter over the notebook-derived `skillxray.py` v2 scorer.
   The service-role key is used only by the backend to read `public.job_postings`; never put it in the mobile app.
   The backend builds role profiles lazily from postings fetched in the last 30 days, using the notebook's 30-posting
   minimum, 20%/3-posting skill frequency thresholds, 40-skill cap, quality gate, and blocklist. Roles without enough
   usable postings fall back to their frozen or static profile with the reason included in analysis warnings.
   No JSearch/RapidAPI requests are made during analysis. It reads the exported files from these folders directly.
   Its first startup downloads the JobBERT and
   Sentence-Transformer model weights. Set the mobile app's `EXPO_PUBLIC_API_URL` to `http://localhost:8000` when app
   and API run on the same computer, or to the computer's LAN address when using Expo Go on a phone. Keep the Supabase
   anon key in the backend environment as `SUPABASE_ANON_KEY`; the app sends the signed-in user's access token.
   The live target-role picker reads the authenticated `/roles` endpoint, so it only offers roles this scorer can analyze.
   Demo mode continues to use the Supabase role catalog.
   Resume coverage follows the notebook's binary `covered` result; its per-skill reason, evidence, and gap confidence
   are also returned. Learning-plan gaps are ranked by their marginal gain to the same weighted CRI; the estimate
   accounts for ESCO descendants that can satisfy broader requirements and avoids counting those requirements twice.
   The plan also groups related ESCO skills, orders curated prerequisites first (broader and related links do not
   establish learning prerequisites), and links each step to a course,
   certification, or targeted course search. When extracted resume skills overlap role postings, co-occurrence evidence
   compares gap frequency in those postings with the role-wide rate; this is posting evidence, not candidate outcome
   data. Database-backed analysis also returns `market_intelligence`, computed from URI-linked skills in the last
   120 days of stored postings. It reports market classifications, missing core/common/emerging skills, owned
   declining skills, and a market-alignment score. Growth compares adjacent 30-day demand frequencies; metrics are
   cached for the backend process lifetime and can be scoped with `JSEARCH_COUNTRY`. The market view also includes
   role-specific skill trends: the latest 90 days are compared with the preceding 275 days, using smoothed posting
   shares, minimum support, and core/rising/stable/declining labels. Trend evidence includes counts, date windows,
   confidence, and up to three posting titles/dates/publishers. The market-history loader retains up to 365 days and
   deduplicates matching reposts per role and country, keeping the newest copy. Ambiguous or unlinked extracted terms
   are also grouped through known aliases (including GenAI/LLM-application variants) and reported separately from
   ESCO-linked skills. Labels are never used as ESCO identifiers.
   Optional explicit learning prerequisites can be added in `results/skill_prerequisites.json` as a JSON object
   mapping each skill's ESCO URI to an array of prerequisite skill URIs. ESCO broader/narrower and related-skill
   links are displayed as taxonomy relationships, not verified learning prerequisites.
The remaining Hugging Face Gradio deployment steps below describe a separate demo deployment, not the FastAPI endpoint
called by the Expo app. This checkout does not contain the Gradio `app.py` entry point; follow those steps only in the
Space repository that contains that app.

4. **Create the Space** at huggingface.co/new-space (SDK: Gradio, hardware: CPU basic), then:
   ```bash
   git clone https://huggingface.co/spaces/<you>/<space-name>
   cp -r <this folder>/. <space-name>/ && cd <space-name>
   git lfs install
   git add . && git commit -m "SkillXray" && git push
   ```
5. Watch the **Logs** tab. The first build installs packages; the first start downloads the models and takes a few minutes.

## Updating the job-market postings

The supplied `public.job_roles` table remains the role catalog; individual ads are stored separately in `public.job_postings`. Apply `supabase/migrations/20261104150000_job_postings.sql` after `public.job_roles` is present, followed by `supabase/migrations/20261115160000_job_posting_trend_support.sql` to add the ingestion dedupe key and trend lookup indexes. Run `app/ingest_postings.py` with the server-side Supabase service-role key and JSearch key to refresh postings. The API reads those stored rows and builds profiles at runtime; it does not call JSearch and does not require notebook-generated profile releases for roles that pass the data-quality checks.

The notebook's `freeze_profiles()` export remains available as the fallback for roles with insufficient recent postings.

## Notes

- **Privacy:** CVs are handled in memory only and are not logged or saved. Say so to users, and prefer a private Space while testing.
- **ESCO:** this app redistributes ESCO data; keep the attribution in the app footer.
- **Memory/speed:** CPU basic (16 GB) is enough. Models load once at start-up; each CV takes a few seconds. Free Spaces sleep when idle.
- **Reproducibility:** `requirements.txt` is not pinned to the versions your notebook ran with. The notebook prints them in section 1 ("note these with your results"); pin `torch`, `transformers` and `sentence-transformers` to those for identical scores.
- **Where the code came from:** `skillxray.py` packages the notebook's resume extraction, ESCO linking, and v22 matching inference; Drive access, tuning, gold-set evaluation, and live JSearch fetching stay in the notebook and do not run in the API.
  The notebook's section 19 soft-skill context head is experimental and does not export a trained checkpoint, so it is not loaded by the app. Files are never written at start-up, and a requirement with no saved
  z-score statistics uses the notebook's own default values (reported in the app) instead of stopping.
