# SkillXray

SkillXray is a mobile-first career readiness application that helps job seekers understand how close they are to meeting the requirements of their target roles. Users upload a resume, see which skills they already demonstrate, compare their profile against a target role, and get recommendations for the gaps they still need to close.

## Current Progress

- **Implemented:** Expo/React Native app structure, Supabase client integration, resume upload and parsing workflow, and a FastAPI skill-extraction service.
- **Implemented:** Supabase `parse-resume` Edge Function parses PDF/DOCX files, calls the model service, and stores extracted skills.
- **In progress:** ESCO normalization, role-to-resume skill-gap comparison, readiness scoring, and the complete recommendations workflow.
- **Deployed:** The skill-extraction model API is hosted on [Hugging Face Spaces](https://huggingface.co/spaces/Tracymgprog/skillxray-api).
- **Deployment verification pending:** The production Supabase function connection and complete app-to-model flow are not confirmed here; follow the checklist below to verify them.

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
│  Model API               │  Python · FastAPI · JobBERT
│  (skill extraction)      │  (deployed on Hugging Face Spaces)
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

### Model Layer
A Python FastAPI service extracts skills from resume text with the configured token-classification model. ESCO normalization and skill-gap comparison are still in progress; the current parsing workflow stores extracted skills but does not yet complete the full readiness analysis.

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



## How the App Works

1. The user signs in.
2. They choose a resume file to upload.
3. The resume is saved to storage.
4. A resume record is created in the database.
5. The app invokes the `parse-resume` Edge Function.
6. The function extracts text from the PDF/DOCX, calls the model API, and saves extracted skills.
7. ESCO normalization, skill-gap comparison, readiness scoring, and recommendations are the next implementation steps.

The current implemented flow reaches resume skill extraction and storage; it does not yet complete the readiness-to-learning-plan cycle.

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
│       └── parse-resume/       # Deno Edge Function for resume processing
├── Backend/
│   ├── main.py                 # FastAPI skill-extraction endpoint
│   ├── Dockerfile              # container configuration (port 7860)
│   └── models/                 # local model artifacts
├── android/                    # Android native project
├── assets/                     # static assets
├── app.json                    # Expo configuration
├── package.json                # scripts and dependencies
└── tsconfig.json               # TypeScript config
```

---

## Development Setup

### Mobile app

Prerequisites: Node.js, npm, a Supabase project, and Deno (for Edge Function development).

```bash
npm install
npm start          # then choose an emulator, simulator, or physical device
npm run android
npm run ios
```

### Model API

The Dockerfile in `Backend/` starts `main:app` on port `7860`. The service requires `SKILL_MODEL_ID` and `MODEL_API_KEY`; set `HF_TOKEN` only if the model repository is private. For local development, set these environment variables and run `uvicorn main:app --reload --port 7860` from `Backend/`.

---

## Environment Configuration

Configure the Expo app with its public Supabase project values:

```bash
EXPO_PUBLIC_SUPABASE_URL=your_project_url
EXPO_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

Put these in the project-root `.env` for local Expo development or in the mobile build environment. Never put a Supabase service-role key in the mobile app. The Edge Function uses its server-side Supabase credentials and the model API secrets described below.

## Deployment Progress

### 1. Model API deployment

The skill-extraction API is deployed at [Tracymgprog/skillxray-api](https://huggingface.co/spaces/Tracymgprog/skillxray-api). Its API exposes `/health` and `/extract`. The checked-in Dockerfile is configured for this Hugging Face Space deployment. The Space secrets are:

- `SKILL_MODEL_ID`: Hugging Face model ID or accessible model repository.
- `MODEL_API_KEY`: a strong shared secret used to authorize requests from the Edge Function.
- `HF_TOKEN`: only if needed to download a private model.

The Space API base URL follows the Hugging Face format `https://tracymgprog-skillxray-api.hf.space`; the extraction endpoint configured in Supabase should be `https://tracymgprog-skillxray-api.hf.space/extract`. Check `https://tracymgprog-skillxray-api.hf.space/health` to verify the service reports `{"ok":true}`.

You can build and smoke-test the container locally before publishing:

```bash
docker build -t skillxray-model ./Backend
docker run --rm -p 7860:7860 -e SKILL_MODEL_ID=your-model-id -e MODEL_API_KEY=your-shared-secret skillxray-model
```

### 2. Connect the Supabase Edge Function

From the project root, link the Supabase CLI to the intended project and set the function secrets. Use the URL of the deployed `/extract` endpoint:

```bash
supabase link --project-ref <project-ref>
supabase secrets set MODEL_URL=https://tracymgprog-skillxray-api.hf.space/extract MODEL_API_KEY=<shared-secret>
supabase functions deploy parse-resume
```

The `MODEL_API_KEY` value must match the model Space secret. `MOCK_SKILLS` can optionally be set as a comma-separated test override; remove it to call the real model. Do not commit secret values.

### 3. Verify the end-to-end flow

1. Confirm the model service health endpoint reports ready.
2. Confirm the Supabase `parse-resume` function is deployed and has `MODEL_URL` and `MODEL_API_KEY` configured.
3. Sign in to the app, upload a text-based PDF or DOCX resume, and run parsing.
4. Confirm the function reports extracted skills and the skills are saved in Supabase.
5. Record the deployed Space URL and confirm whether the end-to-end test passed.

**Current deployment checkpoint:** the model API is deployed to Hugging Face Spaces. Confirm the Supabase function is configured with the Space URL and matching API key, then verify the full resume-upload-to-skill-storage flow.

### 4. Publish the mobile app

No EAS build configuration or app-store release details are checked in yet. Once the backend flow is verified, configure Expo EAS builds, provide the public Supabase environment values to the build, and complete the Android/iOS signing and store-submission steps. Add the build and store links here after release.


