# AI Tutor for O Level Mathematics

An AI-powered learning experience for Cambridge O Level Mathematics (Syllabus D
4024) that evaluates a student's working, gives progressive guidance, and uses
Socratic conversation instead of behaving like an answer-generating chatbot.

- **Hackathon:** AI Hackathon Pakistan 2026
- **Project ID:** P01403
- **Institution:** National University of Sciences and Technology (NUST), Islamabad
- **MVP scope:** Probability — syllabus sections 8.1, 8.2, and 8.3

## The problem

Students often receive only a final score or a complete worked answer. That does
not identify where their reasoning went wrong, and immediately revealing the
solution removes the opportunity to learn through a productive attempt.

This project builds a controlled tutoring loop around reviewed curriculum
content:

`Study -> Attempt -> Evaluate -> Guide -> Retry -> Discuss`

The evaluator checks the learner's exact submitted revision against private
marking criteria. A separate tutoring policy then chooses an appropriate level
of guidance, while the conversational tutor helps the learner reason forward
without awarding marks or revealing the final answer.

## Working Probability MVP

The repository contains one complete vertical slice of the product:

- A responsive React syllabus explorer representing all 9 topics and 68
  subtopics in Cambridge O Level Mathematics 4024.
- Structured Probability lessons for sections 8.1–8.3 with headings, worked
  examples, tables, diagrams, examiner tips, and KaTeX mathematics.
- A reviewed bank of 20 Probability questions containing 53 assessable parts,
  82 marking points, and 115 marks in total.
- Typed working with automatic saving and restoration after refresh.
- Uploads of photographed solutions in JPEG, PNG, or WebP format.
- Vision-first transcription for image attempts followed by structured,
  mark-scheme-grounded evaluation.
- Immutable review attempts tied to the exact response revision that was
  assessed.
- Deterministic progressive guidance that escalates from a guiding question to
  a targeted hint or worked next step.
- Persisted, question-scoped Socratic chat grounded in the question, learner
  work, latest review, marking criteria, and recent conversation.
- Explicit answer reveal: normal question responses do not expose private
  answers or marking points.
- Dark mode, responsive navigation, accessible typography, and clear loading
  and failure states.

## What makes it different

### It evaluates the working, not only the final answer

Learners can type a solution or photograph handwritten work. The review records
the evidence used for each mark and returns student-safe feedback.

### Marking and teaching are separate responsibilities

The structured evaluator assesses a frozen response snapshot. The tutoring
policy decides the next pedagogical action, and the chat model explains or asks
questions without changing the review or claiming to award marks.

### Guidance becomes stronger across attempts

The hint level is selected deterministically from the learner's prior attempts.
This makes the behaviour more predictable and auditable than asking a language
model to control the entire tutoring process.

### Curriculum content is reviewed and structured

Questions, notes, diagrams, answers, and marking points use stable identifiers
and validated schemas. The model is grounded in this content rather than being
asked to invent a question or marking scheme.

## Demonstration journey

1. Open Topic 8 and choose **Practice Probability**.
2. Select a question part and enter typed working or attach a solution image.
3. Choose **Check with AI** to save and evaluate that exact revision.
4. Read the awarded marks, feedback, and next hint.
5. Revise the response and submit another attempt to receive stronger guidance.
6. Ask the Socratic tutor a follow-up question about the active problem.
7. Refresh or revisit the question to see the saved work, reviews, and chat.

## Architecture

```text
Authorized learning sources
          |
          v
PDF rendering -> Vision extraction -> Pydantic validation -> Structured content
                                                               |
                                                               v
React + Vite UI <---- versioned REST API ----> FastAPI
                                                |
                                                v
                                           PostgreSQL
                                    content, attempts, images,
                                      reviews, and tutor chat
                                                |
                                                v
                                    OpenRouter-compatible models
                                   transcription, evaluation, chat
```

Important runtime boundaries:

- The browser never receives database credentials or private marking data.
- PostgreSQL connections are managed through a bounded application pool.
- Uploaded images are decoded, orientation-corrected, resized for model use,
  stripped of EXIF metadata, and deduplicated by SHA-256.
- AI responses must satisfy strict Pydantic schemas before reaching the learner.
- Duplicate review and chat requests are idempotent, and provider failures can
  be retried safely.
- Per-session limits protect the public AI endpoints from accidental overuse.

## Technology

- **Frontend:** React 19, Vite, React Router, KaTeX, Tailwind CSS tooling,
  Lucide icons
- **Backend:** Python, FastAPI, Pydantic, Psycopg, Pillow
- **Database:** PostgreSQL with ordered, idempotent SQL migrations
- **AI:** OpenRouter-compatible multimodal chat-completions models
- **Content pipeline:** PyMuPDF, vision extraction, schema validation, resumable
  processing
- **Testing:** Pytest integration and policy tests plus a production frontend
  build gate

## Run the complete application locally

### Prerequisites

- Python 3.10 or later
- Node.js 20.19 or later
- PostgreSQL (the local project configuration uses port `5433`)
- An OpenRouter API key for real AI reviews and chat

### 1. Install the backend

From the project root in PowerShell:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

### 2. Create and seed the database

Run the setup in a real terminal so the administrator and application-role
password prompts remain hidden:

```powershell
.\backend\.venv\Scripts\python.exe scripts/setup_database.py
```

The setup is safe to run again. It creates or updates the `ai_tutor_app` role,
creates the `ai_tutor` database, applies all migrations, imports the reviewed
Probability content, and writes `DATABASE_URL` and local CORS settings to the
Git-ignored `backend/.env` file.

If PostgreSQL is running on another port, pass it explicitly:

```powershell
.\backend\.venv\Scripts\python.exe scripts/setup_database.py --port 5432
```

### 3. Configure the AI provider

Open `backend/.env` and add:

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_VISION_MODEL=openrouter/free
OPENROUTER_EVALUATION_MODEL=openrouter/free
OPENROUTER_CHAT_MODEL=openrouter/free
OPENROUTER_DATA_COLLECTION=deny
OPENROUTER_TIMEOUT_SECONDS=90
```

The free router is convenient during development. For a reliable public demo,
pin tested, structured-output-capable model IDs instead of relying on
`openrouter/free`. Keep `OPENROUTER_DATA_COLLECTION=deny` unless users have made
an informed privacy choice.

### 4. Start the API

```powershell
backend\start.cmd
```

The API runs at `http://127.0.0.1:8000`. Interactive API documentation is
available at `http://127.0.0.1:8000/docs`.

### 5. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the local FastAPI
server.

## Verification

Run every release gate from the project root:

```powershell
.\verify.cmd
```

The verification command:

1. compiles the backend and setup scripts;
2. runs the backend integration and tutoring-policy tests;
3. verifies database counts, identifiers, and mark totals; and
4. creates the production frontend build.

The current verified dataset contains:

| Measure | Verified value |
|---|---:|
| Root questions | 20 |
| Assessable parts | 53 |
| Marking points | 82 |
| Total marks | 115 |
| Probability note documents | 3 |
| Invalid question-part identifiers | 0 |

Automated tests replace provider calls with deterministic fakes. After they
pass, a disposable real-provider smoke test can be run with:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.smoke_tutor
```

This test consumes provider requests, prints only a safe result summary, and
deletes its temporary learner session.

## Repository structure

```text
backend/
  app/                  FastAPI routes, schemas, repositories, and services
  scripts/              migrations, seeding, verification, and smoke testing
  tests/                API, policy, and provider-contract tests
database/migrations/    ordered PostgreSQL migrations
frontend/
  src/                  React interface, API clients, lessons, and questions
scripts/                local database setup and content-ingestion tools
```

## Current scope and limitations

This is a focused hackathon MVP, not a production service for children. The
complete AI-assisted journey currently covers Probability only. The wider
syllabus is represented for navigation and future expansion, but other topics do
not yet have equivalent reviewed question banks and tutor flows.

Anonymous browser sessions are suitable for demonstrating persistence but do
not replace real authentication. The current system records response history
and uses prior attempts to select hint strength; it does not yet maintain a full
per-concept mastery score or automatically choose the learner's next curriculum
item. A production release would also require hosted infrastructure, monitoring,
consent controls, safeguarding review, and broader evaluation with students and
teachers.

## Next steps

1. Add a per-concept learner model for mastery, misconceptions, confidence, and
   hint history.
2. Recommend the next question, prerequisite lesson, or difficulty level from
   learner evidence.
3. Add accounts and a learner progress dashboard.
4. Evaluate mathematical correctness, grounding, helpfulness, and hint leakage
   over a larger test set.
5. Deploy the application with managed PostgreSQL and pinned AI models.
6. Expand reviewed lessons and assessments across the remaining syllabus topics.

## Content rights and privacy

Source PDFs and working extracts are excluded from version control. Only use or
publish educational material for which redistribution is permitted. If any
credential has ever been committed, treat it as public and rotate it; deleting a
file does not remove it from Git history.

Student work sent for AI evaluation may be processed by an external model
provider. The application defaults to denying providers that retain data for
training, but a real deployment still requires clear consent and an appropriate
privacy policy.

## Project status

The Probability tutoring MVP is implemented and locally verified. It
demonstrates the core technical and pedagogical approach end to end while
keeping broader personalization, curriculum sequencing, authentication, and
deployment as explicit next milestones.
