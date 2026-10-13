# SkillXray

SkillXray is a mobile-first career readiness application that helps job seekers understand how close they are to meeting the requirements of their target roles. Users upload a resume, see which skills they already demonstrate, compare their profile against a target role, and get recommendations for the gaps they still need to close.

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

```
┌──────────────────────────┐
│  Mobile app              │  React Native · Expo · TypeScript
│  (auth, upload, reports) │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│  Supabase                │  Auth · Postgres · Storage
│  (data + file storage)   │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│  Edge Function           │  Deno · parse-resume
│  (processing workflow)   │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│  ML pipeline             │  Python · JobBERT · Sentence-BERT · ESCO
│  (skill extraction)      │  (developed in Colab, integration in progress)
└──────────────────────────┘
```

### Frontend Layer
Built with React Native and Expo. It provides authentication, resume upload, analysis display, course tracking, and recommendations. Application state is managed through a context layer so analysis results are shared across screens without duplicating data-fetching logic.

### Data and Storage Layer
Supabase provides authentication, user profiles, resume metadata, analysis records, skill-gap records, and learning/course tracking data.

### Processing Layer
Resume processing runs through Deno-based Supabase Edge Functions, which receive the uploaded resume reference, check processing status, and orchestrate the analysis workflow. This layer is the bridge between the app and the skill analysis process.

### Business Logic Layer
Service modules handle uploading a resume, requesting analysis, polling for status, retrieving skill gaps, and storing readiness data in app state. They keep client-side logic separate from the UI.

### ML Layer
A Python pipeline extracts skills from text and maps them onto the ESCO taxonomy. It is described in full below.

---

## Technology Stack

| Area | Technology |
|---|---|
| Mobile app | React Native, Expo, Expo Router, TypeScript |
| State management | React Context |
| Backend services | Supabase (Auth, Postgres, Storage) |
| Serverless processing | Supabase Edge Functions (Deno) |
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

### Results so far

| Dataset | Sample | Spans matched to ESCO |
|---|---|---|
| Job postings | 200 postings | ~84–85% |
| Resumes | 2,484 resumes | _to be recorded after the full run_ |

---

## How the App Works

1. The user signs in.
2. They choose a resume file to upload.
3. The resume is saved to storage.
4. A resume record is created in the database.
5. The app triggers the analysis process.
6. The backend processes the resume and creates a skill analysis record.
7. Skill gap rows are generated for missing or weak skills.
8. Overall readiness is calculated.
9. The app shows a skill-analysis report.
10. The user views recommendations and monitors progress.

This gives a complete cycle from input (resume) to insight (readiness) to action (learning plan).

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
│   └── functions/
│       └── parse-resume/       # Deno edge function for resume processing
├── ml/
│   └── SkillXray_ML_Pipeline.ipynb   # skill extraction + ESCO normalization (Colab)
├── android/                    # Android native project
├── assets/                     # static assets
├── app.json                    # Expo configuration
├── package.json                # scripts and dependencies
├── tsconfig.json               # TypeScript config
└── .env.example                # example environment variables
```

---

## Development Setup

### Mobile app

Prerequisites: Node.js, npm, Expo CLI, a Supabase project, and Deno (for edge function development).

```bash
npm install
npm start          # then choose an emulator, simulator, or physical device
npm run android
npm run ios
```

### ML pipeline

1. Open `ml/SkillXray_ML_Pipeline.ipynb` in Google Colab.
2. Set **Runtime → Change runtime type → GPU**.
3. Place the datasets under `MyDrive/SkillXray/data/` (`raw/postings.csv`, `raw/Resume.csv`, and the ESCO CSVs in `esco/`).
4. Run the install cells, **restart the session once**, then continue from the import check without re-running the installs.

---

## Environment Configuration

Create a `.env` file from `.env.example` and provide your Supabase values:

```bash
SUPABASE_URL=your_project_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

These are required for authentication, database access, storage, and edge function communication. The service role key bypasses row-level security: keep it server-side (edge functions only), never in the mobile app, and never commit `.env`.

---


---


