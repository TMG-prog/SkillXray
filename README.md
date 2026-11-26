# SkillXray

SkillXray is a mobile-first career readiness application that helps job seekers understand how close they are to meeting the requirements of their target roles. Users upload a resume, see which skills they already demonstrate, compare their profile against a target role, and get recommendations for the gaps they still need to close.

## Current Progress

- **Implemented:** The app uploads resumes to Supabase Storage, then sends the selected file and target role to the authenticated FastAPI `/analyze` endpoint.
- **Implemented:** The FastAPI pipeline parses PDF/DOCX, extracts and normalizes skills, compares them with role requirements, and returns readiness, covered skills, gaps, and warnings.
- **In progress:** Persisting analysis results and completing the learning recommendations workflow.
- **Expo Go setup:** The README now documents how to run the app on a device with Expo Go. A standalone app-store release is not configured yet.
- **Deployment configuration required:** Set the Expo API URL and configure the FastAPI service with Supabase auth and pipeline artifacts before running end-to-end.
- **Demo analysis:** Set `EXPO_PUBLIC_USE_MOCK_ANALYSIS=1` in `.env` or `.env.local` and restart Expo to show clearly labeled sample results without uploading the selected resume or calling the model. Remove the setting or set it to `0` to restore real analysis.

---



## Core Features

**1. Resume Upload.** Users upload a PDF or Word document from the mobile app. The file is stored in Supabase Storage and linked to the authenticated user profile.

**2. Skill and Readiness Analysis.** Uploading a resume triggers a processing workflow that checks it against a target role or inferred profile, then calculates an overall readiness score.

**3. Gap Reporting.** The app highlights skills that are missing, weak, or underrepresented, so the user sees exactly where to improve.

**4. Learning Recommendations.** Identified gaps are turned into an actionable learning plan. Recommendation links open curated course-detail pages directly; when no exact course is curated for a skill, the app shows that no course link is available instead of sending users to a provider homepage or search page. Curated resources can display NITA-accredited, University-backed, Free/Open Access, or Industry Certification badges only after an administrator records an official HTTP(S) evidence source; the URL is a review aid, not automatic accreditation verification. Prices and certificate fees vary by provider and course.

**5. Progress Tracking.** Users can track their learning and course engagement over time.

---

## System Architecture

The separate [administration console](./admin_app/README.md) provides account, taxonomy, dataset and
learning-resource management; its setup and operational limitations are documented there.

```
┌──────────────────────┐       ┌──────────────────────────┐
│  Mobile app          │──────▶│  Supabase                │
│  React Native · Expo │       │  Auth · Postgres · Storage│
└──────────┬───────────┘       └──────────────────────────┘
           │ Bearer token + resume file
           ▼
┌──────────────────────────┐
│  Analysis API            │  Python · FastAPI
│  parse · extract · match │  JobBERT · ESCO · SBERT
└──────────────────────────┘
```

### Frontend Layer
Built with React Native and Expo. It provides authentication, resume upload, analysis display, course tracking, and recommendations. Application state is managed through a context layer so analysis results are shared across screens without duplicating data-fetching logic.

### Data and Storage Layer
Supabase provides authentication, user profiles, resume metadata, analysis records, skill-gap records, and learning/course tracking data.

### Processing Layer
The app calls the FastAPI `/analyze` endpoint with the resume file, target role, and Supabase access token. FastAPI validates the user token, parses the document, and runs the skill and readiness pipeline.

### Business Logic Layer
Service modules handle uploading a resume, requesting analysis, polling for status, retrieving skill gaps, and storing readiness data in app state. They keep client-side logic separate from the UI.

### Model Layer
The API adapts the notebook-derived v2 scorer to the mobile response contract. It extracts resume skills, compares them with the selected role profile, and returns readiness, per-skill evidence, and weighted gaps. Recognized resume headings preserve evidence provenance: evidence found only in Education receives half credit, while a skill also evidenced in Experience or Projects receives full credit. If no known headings are detected, the existing scoring is retained and a warning is returned. Database-backed market trends compare dated postings across a 90-day recent window and the preceding 275-day baseline, with deduplication, minimum support, smoothing, classifications, and sample-posting evidence. The app persists each full report with its `skill_analyses` record and reloads the user's recent history from Supabase.

---

## Technology Stack

| Area | Technology |
|---|---|
| Mobile app | React Native, Expo, Expo Router, TypeScript |
| State management | React Context |
| Backend services | Supabase (Auth, Postgres, Storage) |
| Analysis API | FastAPI |
| Skill extraction | JobBERT (`jjzha/jobbert_skill_extraction`) |
| Semantic matching | Sentence-BERT (`all-MiniLM-L6-v2`) |
| NLP preprocessing | spaCy (`en_core_web_sm`) |
| Skills taxonomy | ESCO (skills, occupations, occupation-skill relations) |
| ML environment | Google Colab (GPU), Google Drive |

---

## Machine Learning Pipeline

The ML component turns free-text resumes and job postings into structured, comparable skill data.

```
Raw text → Cleaning → JobBERT extraction → Span post-processing → ESCO normalization → Skill-gap comparison
```

**1. Text cleaning.** The Kaggle job-posting text lost its sentence and bullet boundaries when HTML was stripped, so sentences run together (`"...sales.Responsible for..."`). Cleaning restores those boundaries. Resumes separate bullets with plain newlines, so newlines are treated as boundaries for resumes only. Text is deliberately not lowercased: JobBERT is a cased model, and the boundary-recovery rule depends on case.

**2. Skill extraction.** Text is split into sentences with spaCy and passed through JobBERT, using `aggregation_strategy="first"` so words are not split into subword fragments such as `##R`.

**3. Span post-processing.**
- Entities split at a comma or conjunction are merged, so matching sees the full phrase. This stopped *"conception"* matching ESCO's *"pregnancy"* skill. Short list items such as *Python and SQL* stay separate.
- Stray leading and trailing punctuation or conjunctions are stripped.
- Filler-only spans (*"Ensures"*, *"maintains"*) are dropped. This matches on surface text, not `lemma_`, because spaCy does not lemmatize mistagged proper nouns.
- Spans must contain a noun or a recognized soft-skill verb, so verb-led skills such as *"Led"* or *"Audited"* are kept.

**4. ESCO normalization.** Every ESCO preferred and alternative label is embedded once with Sentence-BERT and cached. Each extracted span is matched to its nearest ESCO term by cosine similarity. Spans scoring below the threshold (default 0.6) stay unmatched instead of being forced onto a wrong concept.

**5. Skill-gap comparison.** Both a candidate's and a job's skills are expressed as ESCO concepts, so the gap is the set of required concepts the candidate lacks, with similarity-weighted credit for partial overlaps. This stage is in progress.

### Datasets

- [LinkedIn Job Postings](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings) (Kaggle)
- [Resume Dataset](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset) (Kaggle)
- [ESCO](https://esco.ec.europa.eu/en/use-esco/download) classification, English, CSV



## How the App Works

1. The user signs in.
2. They choose a resume file to upload.
3. The resume is saved to storage.
4. A resume record is created in the database.
5. The app sends the resume file and selected target role to the authenticated FastAPI `/analyze` endpoint.
6. The backend parses the file, runs skill extraction and ESCO matching, scores role requirements, and returns readiness, matched skills, gaps, and warnings.
7. The app saves each result in the user's `skill_analyses` table and displays the newest result in its analysis screen. Open **History** to revisit an earlier result after uploading a new resume.

The resume file is stored in Supabase Storage. Analysis history is stored in Supabase, scoped to the signed-in user, and keeps the 50 most recent results in the app. Each `skill_analyses` row stores its resume/role references and readiness score; the full report is stored in the `result_data` JSONB column. Apply the migration in `supabase/migrations` before using persisted analysis history. The model pipeline processes the local file upload in memory.

On the analysis screen, **Download report (PDF)** exports the analysis currently displayed, including a selected historical analysis. The report includes available CV excerpts, gaps, recommendations, and market insights. On web it downloads directly; on Android and iOS, choose where to save or share it from the system share sheet. Reports contain personal information, so store and share them carefully. Older saved analyses may not contain detailed evidence.

---

## Data Model

- **User:** authenticated individual using the app
- **Resume:** uploaded document associated with a user
- **SkillAnalysis:** evaluation of a resume for a role or target profile
- **SkillGap:** a specific gap identified in an analysis
- **Course:** learning resource the user tracks or follows

---

## Project Structure

```text
SkillXray/
├── app/                        # app routes and UI screens
├── src/
│   ├── components/             # shared UI building blocks
│   ├── features/               # resume, analysis, course, recommendation modules
│   ├── services/               # API and backend integration logic
│   ├── state/                  # app-level state and context
│   ├── types/                  # TypeScript interfaces and models
│   └── lib/                    # config and shared services
├── supabase/
│   ├── config.toml             # Supabase local configuration
│   └── functions/
│       └── parse-resume/       # Optional Supabase Edge Function for skill extraction
├── Backend/
│   └── app/
│       ├── main.py             # FastAPI analysis API
│       └── pipeline.py         # Extraction, ESCO linking, and role matching
├── android/                    # Android native project
├── assets/                     # static assets
├── app.json                    # Expo configuration
├── package.json                # scripts and dependencies
└── tsconfig.json               # TypeScript config
```

---

## Development Setup

### Mobile app

Run the app on a phone using Expo Go by following the [Expo Go setup](#run-the-app-with-expo-go) below.

### Analysis API

The Expo app calls the FastAPI service in `Backend/app/main.py`. For local development, configure that service's Supabase authentication environment (`SUPABASE_URL` and `SUPABASE_ANON_KEY`) and its model/artifact requirements, then run `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `Backend/`.

The backend validates the Supabase access token against the Supabase project. Keep `SUPABASE_ANON_KEY` in the backend environment; do not put backend-only secrets in the Expo app.

---

## Environment Configuration

Configure the Expo app with its public Supabase project values:

```bash
EXPO_PUBLIC_SUPABASE_URL=your_project_url
EXPO_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
EXPO_PUBLIC_API_URL=http://your-backend-host:8000
```

Put these in the project-root `.env` for local Expo development. For a physical device, use your computer's LAN address instead of `localhost`. The `EXPO_PUBLIC_` values are bundled into the app and are not secrets. Never put a Supabase service-role key or model API key in the mobile app.

For password recovery, add `skillxray://reset-password` to the Supabase project's **Authentication → URL Configuration → Redirect URLs**. When testing in Expo Go, also allow the development redirect URI generated by Expo (`exp://.../--/reset-password`); its host and port can change between runs. The app reads the recovery session from the returned link before accepting a new password.

## Run the App with Expo Go

This starts the development version of SkillXray on a physical phone; it does not publish the app to an app store.

1. Install [Expo Go](https://expo.dev/go) on your Android or iPhone.
2. Create the project-root `.env` file with the Supabase URL, anon key, and analysis API URL shown above.
3. In a terminal at the project root, install dependencies and start Expo:

    ```bash
    npm install
    npx expo start
    ```

4. Connect your phone and computer to the same Wi-Fi network. Open Expo Go on Android and scan the QR code shown in the terminal or browser. On iPhone, scan the QR code with the Camera app and open it in Expo Go.
5. To connect when the phone and computer cannot reach each other over the local network, stop the server and run `npx expo start --tunnel`, then scan the new QR code.

The analysis API must be reachable from the phone and configured with the pipeline's required model and artifact files. In local development, allow the phone and computer to communicate over the same Wi-Fi network and set `EXPO_PUBLIC_API_URL` to the computer's LAN address.

---

## 5.2.3 Deployment and Reproducibility

### Deployment status and target

The documented, reproducible setup is a **local development/controlled test**, not a publicly hosted production service or a released mobile app. The React Native app runs in Expo Go on an Android or iOS device (or in a local web preview); the FastAPI analysis service runs on a developer-controlled computer. Supabase supplies hosted authentication, database, and storage services. For a phone test, the API must be reachable over the local network or through Expo's development tunnel.

This checkout does not identify a verified public API deployment, public Hugging Face Space, or app-store release. The Hugging Face Gradio instructions in `Backend/README.md` describe a separate demo; they are not the FastAPI endpoint used by the mobile app. Do not describe that demo as deployed from this checkout: its documented Gradio entry point is not present here.

### Installation and configuration

1. Use Node.js/npm, Python 3.10, a Supabase project, and the model/data artifacts exported from the analysis notebook. Place the exported artifacts in the `Backend/` layout (`data/esco/`, `models/`, `results/`, and `data/processed/`), or configure `ARTIFACTS_DIR` to point to their root. Model weights may be downloaded from their model hosts on first startup.
2. From the repository root, configure the Expo app in `.env`:

   ```dotenv
   EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
   EXPO_PUBLIC_SUPABASE_ANON_KEY=<supabase-anon-key>
   EXPO_PUBLIC_API_URL=http://<computer-lan-address>:8000
   ```

   These `EXPO_PUBLIC_` values are included in the app bundle; use only the Supabase anon key here, never a service-role key. Use `http://localhost:8000` only when the app and API run on the same computer.
3. Configure the API process environment with `SUPABASE_URL` and `SUPABASE_ANON_KEY` for sign-in token validation. To load current job-posting profiles from Supabase, also configure `SUPABASE_SERVICE_ROLE_KEY` on the backend only. Without a usable database profile, the pipeline can fall back to the available frozen or static role profiles. Apply the Supabase migrations required by the features being tested before using them.
4. In PowerShell, create the Python environment, install dependencies, and start the API from `Backend/`:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   `--reload` is for development, not a production process manager. Keep the terminal open and use its logs to diagnose startup or model-loading errors. The service validates Supabase access tokens; setting `REQUIRE_AUTH=0` is only suitable for isolated local testing.
5. In a second terminal at the repository root, install JavaScript dependencies and start Expo:

   ```powershell
   npm install
   npx expo start
   ```

   Scan the displayed QR code in Expo Go. If local network routing prevents the phone from reaching the computer, restart with `npx expo start --tunnel`; this tunnel is for development and does not host the API.

### Service connections and access

The mobile app signs users in through Supabase and sends the user's bearer access token to the API. The API validates it with Supabase Auth; resume analysis is served by `POST /analyze`. Resume uploads are processed by the API in memory, while the app's resume storage and analysis-history features use Supabase. Job postings, when enabled, are read by the backend using its server-only service-role key. Never place that key in Expo configuration, source control, or a client app. For a device test, grant access only to the intended tester accounts and avoid exposing the development API to the public internet.

### Verification

Wait for the API startup/model warm-up to finish, then check its health endpoint:

```powershell
curl.exe -sS http://localhost:8000/health
```

The expected response is `{"status":"ok","error":null}`. A `loading` response means startup is still in progress; an `error` response requires checking the backend logs and configuration.

For an authenticated end-to-end check, obtain a current Supabase access token by signing into the app. In PowerShell, set it only in the current terminal session, then request the available roles and analyze a test PDF or DOCX:

```powershell
$env:ACCESS_TOKEN = "<current-supabase-access-token>"
curl.exe -sS -H "Authorization: Bearer $env:ACCESS_TOKEN" http://localhost:8000/roles
curl.exe -sS -H "Authorization: Bearer $env:ACCESS_TOKEN" `
  -F "role=<role-returned-by-roles>" `
  -F "file=@C:\path\to\test-resume.pdf" `
  http://localhost:8000/analyze
```

The roles request should return a `posting_roles` list. A successful analysis should return the selected role, readiness score, covered skills, gaps, warnings, and learning plan. Use a test resume with permission to process it; do not paste access tokens or real resumes into logs or issue reports. The app can also be smoke-tested with `EXPO_PUBLIC_USE_MOCK_ANALYSIS=1`, but mock output is sample data and does **not** verify the API, authentication, or model pipeline.

### Recovery, rollback, and reproducibility record

If startup fails, check `/health` and the API terminal logs, verify that the artifact layout and required environment variables are present, and restart the API after correcting configuration. If only the API is unavailable, the mobile UI can still be started in clearly labeled mock mode for a UI smoke test; do not treat that as a successful analysis test. Before changing Supabase schema or deployed artifacts, retain an appropriate backup. To roll back a code deployment, redeploy the last known-good source revision and its matching artifacts/configuration; do not roll back by deleting user data or applying an unreviewed destructive migration.

For any private or public deployment made from this project, record the exact Git commit or release tag, artifact/configuration version, dependency versions, migration state, target host/device, startup settings, verification result, and rollback reference in **Section 5.6 (Release Record)**. This repository does not establish a deployed source version, so that record must be completed from the actual deployment rather than inferred from the current checkout. `Backend/requirements.txt` contains unpinned dependencies; exact reproduction of model scores requires recording and pinning the dependency and model revisions used for the release.
