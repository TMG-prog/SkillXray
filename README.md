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

## Problem Statement

Many job seekers do not know which of their skills are actually relevant to the roles they are applying for. They often:

- submit applications without understanding how their experience maps to job requirements
- struggle to identify missing skills
- do not know what to study next
- lose motivation because they cannot see progress clearly

This creates a gap between candidate capability and job-market demand. SkillXray reduces that uncertainty by turning resume content into a structured readiness view.

---


## Core Features

**1. Resume Upload.** Users upload a PDF or Word document from the mobile app. The file is stored in Supabase Storage and linked to the authenticated user profile.

**2. Skill and Readiness Analysis.** Uploading a resume triggers a processing workflow that checks it against a target role or inferred profile, then calculates an overall readiness score.

**3. Gap Reporting.** The app highlights skills that are missing, weak, or underrepresented, so the user sees exactly where to improve.

**4. Learning Recommendations.** Identified gaps are turned into recommendations for relevant skills or learning resources, so the result is an actionable plan rather than a passive report.

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
The API adapts the notebook-derived v2 scorer to the mobile response contract. It extracts resume skills, compares them with the selected role profile, and returns readiness, per-skill evidence, and weighted gaps. Database-backed market trends compare dated postings across a 90-day recent window and the preceding 275-day baseline, with deduplication, minimum support, smoothing, classifications, and sample-posting evidence. The app persists each full report with its `skill_analyses` record and reloads the user's recent history from Supabase.

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
