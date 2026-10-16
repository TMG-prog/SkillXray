# SkillXray

SkillXray is a mobile-first career readiness application that helps job seekers understand how close they are to meeting the requirements of their target roles. Users upload a resume, see which skills they already demonstrate, compare their profile against a target role, and get recommendations for the gaps they still need to close.

## Current Progress

- **Implemented:** Expo/React Native app structure, Supabase client integration, resume upload and parsing workflow, and a FastAPI skill-extraction service.
- **Implemented:** Supabase `parse-resume` Edge Function parses PDF/DOCX files, calls the model service, and stores extracted skills.
- **In progress:** ESCO normalization, role-to-resume skill-gap comparison, readiness scoring, and the complete recommendations workflow.
- **Deployed:** The skill-extraction model API is hosted on [Hugging Face Spaces](https://huggingface.co/spaces/Tracymgprog/skillxray-api).
- **Expo Go setup:** The README now documents how to run the app on a device with Expo Go. A standalone app-store release is not configured yet.
- **Backend verification pending:** The production Supabase function connection and complete app-to-model flow are not confirmed here.

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

Run the app on a phone using Expo Go by following the [Expo Go setup](#run-the-app-with-expo-go) below. Deno is only needed if you are developing the Supabase Edge Function locally.

### Model API

The Dockerfile in `Backend/` starts `main:app` on port `7860`. The service requires `SKILL_MODEL_ID` and `MODEL_API_KEY`; set `HF_TOKEN` only if the model repository is private. For local development, set these environment variables and run `uvicorn main:app --reload --port 7860` from `Backend/`.

---

## Environment Configuration

Configure the Expo app with its public Supabase project values:

```bash
EXPO_PUBLIC_SUPABASE_URL=your_project_url
EXPO_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

Put these in the project-root `.env` for local Expo development. The `EXPO_PUBLIC_` values are bundled into the app and are not secrets. Never put a Supabase service-role key or model API key in the mobile app.

## Run the App with Expo Go

This starts the development version of SkillXray on a physical phone; it does not publish the app to an app store.

1. Install [Expo Go](https://expo.dev/go) on your Android or iPhone.
2. Create the project-root `.env` file with the Supabase URL and anon key shown above.
3. In a terminal at the project root, install dependencies and start Expo:

    ```bash
    npm install
    npx expo start
    ```

4. Connect your phone and computer to the same Wi-Fi network. Open Expo Go on Android and scan the QR code shown in the terminal or browser. On iPhone, scan the QR code with the Camera app and open it in Expo Go.
5. To connect when the phone and computer cannot reach each other over the local network, stop the server and run `npx expo start --tunnel`, then scan the new QR code.

For resume skill extraction to work, the Supabase `parse-resume` Edge Function must also be deployed and configured to call the [deployed model API](https://huggingface.co/spaces/Tracymgprog/skillxray-api). Keep `MODEL_URL` and `MODEL_API_KEY` in Supabase function secrets, not in the Expo app.


