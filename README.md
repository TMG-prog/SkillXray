# SkillXray

SkillXray is a mobile-first career readiness application built to help job seekers understand how close they are to meeting the requirements of their target roles. The app allows users to upload a resume, identify the skills they already demonstrate, compare their profile against a target role, and receive recommendations for the gaps they still need to close.

This project was created as a final-year software development project to explore how AI-assisted career guidance can be made accessible through a mobile app experience. Instead of relying on static job-seeker advice, SkillXray turns resume data into actionable insight that helps users make practical upskilling decisions.

---

## Problem Statement

Many job seekers do not know which of their skills are actually relevant to the roles they are applying for. They often:

- submit applications without understanding how their experience maps to job requirements
- struggle to identify missing skills
- do not know what to study next
- lose motivation because they cannot see progress clearly

This creates a gap between candidate capability and job-market demand. SkillXray aims to reduce that uncertainty by turning resume content into a structured readiness view.

---

## Project Aim

The core aim of SkillXray is to help users answer three practical questions:

1. How ready am I for the role I want?
2. Which skills do I already have?
3. What should I learn next to close the gap?

The application is designed to support this through an end-to-end workflow: resume upload, resume analysis, readiness calculation, gap identification, and recommendation delivery.

---

## Core Features

### 1. Resume Upload
Users can upload a PDF or Word document directly from the mobile app. The uploaded file is stored in Supabase storage and linked to the authenticated user profile.

### 2. Skill and Readiness Analysis
When the resume is uploaded, the system triggers a processing workflow that checks the resume against a target role or inferred profile. The app calculates an overall readiness score and identifies skill gaps.

### 3. Gap Reporting
The system highlights the skills that are missing, weak, or underrepresented. This gives the user a clear picture of the exact areas they need to improve.

### 4. Learning Recommendations
After the gaps are identified, the app presents recommendations that guide the user toward relevant skills or learning resources. This transforms the analysis from a passive result into an actionable growth plan.

### 5. Progress Tracking
The user can keep track of their learning and course engagement over time. This creates a loop in which the app supports both self-assessment and ongoing development.

---

## System Overview

SkillXray follows a layered architecture that separates the frontend experience from the backend processing and data services.

### Frontend Layer
The mobile app is built with React Native and Expo. It provides the user interface for:

- authentication
- resume upload
- analysis display
- course tracking
- recommendations

The application state is managed through a context layer so that analysis results can be shared across screens without duplicating data-fetching logic.

### Data and Storage Layer
Supabase is used for key application data, including:

- authentication
- user profiles
- resume metadata
- analysis records
- skill gap records
- learning/course tracking data

This gives the app a cloud-backed data layer with easy integration for both mobile and server-side workflows.

### Processing Layer
Resume processing is handled through Deno-based Supabase Edge Functions. These functions are responsible for receiving the uploaded resume reference, checking the processing status, and orchestrating the analysis workflow.

In the current project structure, this layer acts as the bridge between the client app and the skill analysis process. The function code is designed to be extended with more advanced resume parsing and recommendation logic in the future.

### Business Logic Layer
The app includes service modules that orchestrate calls such as:

- uploading a resume
- requesting analysis
- polling for status updates
- retrieving skill gaps
- storing readiness data in app state

These services isolate the client-side logic from the UI and help keep the application maintainable.

---

## How the App Works

The user journey is designed to be straightforward:

1. The user signs in.
2. They choose a resume file to upload.
3. The resume is saved to storage.
4. A resume record is created in the database.
5. The app triggers the analysis process.
6. The backend processes the resume and creates a skill analysis record.
7. Skill gap rows are generated for missing or weak skills.
8. Overall readiness is calculated.
9. The app shows a skill-analysis report to the user.
10. The user can view recommendations and monitor progress.

This creates a complete cycle from input (resume) to insight (skill readiness) to action (learning plan).

---

## Data Model (Conceptual)

The project is built around a few core entities:

- User: authenticated individual using the app
- Resume: uploaded document associated with a user
- SkillAnalysis: evaluation of a resume for a role or target profile
- SkillGap: specific gap identified in the analysis
- Course: learning resource user tracks or follows

These entities form the foundation for the resume-to-readiness pipeline.

---

## Technical Architecture

### Client-side
The mobile app uses:

- Expo for app packaging and runtime
- React Native for the UI layer
- TypeScript for type safety and maintainability
- Expo Router for screen navigation
- Context-based state management for analysis data

### Server-side / Backend
The backend processing layer uses:

- Supabase database
- Supabase storage
- Supabase Edge Functions with Deno

This combination provides a low-friction approach for building a full-stack prototype without needing a large custom backend from the start.

---



## Current Implementation Status

This project is structured as a functional prototype. Some parts of the system are mocked or placeholder-driven while the full AI-powered parsing pipeline is still being developed. The codebase already establishes the application flow and data model needed to support a real analysis engine in future iterations.

The main value of the current version is that it demonstrates the full product workflow:

- upload resume
- process data
- calculate readiness
- show skill gaps
- improve recommendations and tracking

---

## Project Structure

```text
SkillXray/
├── app/                            # app routes and UI screens
├── src/
│   ├── components/                 # shared UI building blocks
│   ├── features/                   # resume, analysis, course, and recommendation modules
│   ├── services/                   # API and backend integration logic
│   ├── state/                     # app-level state and context
│   ├── types/                     # TypeScript interfaces and models
│   ├── lib/                       # config and shared services
│   └── ...
├── supabase/
│   └── functions/
│       └── parse-resume/           # Deno edge function for resume processing
├── android/                        # Android native project
├── assets/                         # static assets
├── app.json                        # Expo configuration
├── babel.config.js                 # Babel config
├── package.json                    # project scripts and dependencies
├── tsconfig.json                   # TypeScript config
├── README.md                       # project documentation
├── .env.example                    # example environment variables
└── .gitignore
```

---

## Development Setup

### Prerequisites

- Node.js
- npm
- Expo CLI
- Supabase project
- Deno (for edge function development)

### Install dependencies

```bash
npm install
```

### Run the app

```bash
npm start
```

Then choose an emulator, simulator, or physical device connection.

### Run Android

```bash
npm run android
```

### Run iOS

```bash
npm run ios
```

---

## Environment Configuration

Create a `.env` file based on the project requirements and ensure all Supabase environment values are provided.

Example:

```bash
SUPABASE_URL=your_project_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

These values are required for authentication, database access, storage, and edge function communications.

---

## Future Work

This project has clear extension points for future development:

- improve resume parsing with NLP or LLM-based extraction
- connect to a job-role skill database such as ESCO or a curated taxonomy
- add smarter recommendation ranking based on user profile and job role
- introduce user dashboards for skill progression
- add a stronger AI recommendation engine to compare resumes to role requirements
- expand the role and course model for personalized pathways

---

## Conclusion

SkillXray is a practical final-year project that combines mobile application development, cloud services, and career guidance into a single product concept. It demonstrates how a software system can take raw resume content, transform it into meaningful skill insight, and provide the user with a more confident path toward employment readiness.

The project is valuable not only as a software engineering exercise, but also as a proof of concept for a broader idea: personalized skill intelligence for career development.

---

## License

This project is intended for academic and portfolio use unless otherwise stated by the project owner.
