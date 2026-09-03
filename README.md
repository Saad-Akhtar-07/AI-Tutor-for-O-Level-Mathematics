# AI Tutor for O Level Mathematics

An early-stage adaptive learning product for Cambridge O Level Mathematics (Syllabus D 4024). The long-term goal is to move beyond a generic question-answering chatbot by maintaining an explicit learner model and selecting the next pedagogical action from evidence of each student's understanding.

## Product vision

The planned tutoring loop is:

`Teach -> Ask -> Evaluate -> Update learner state -> Choose pedagogical action -> Respond -> Repeat`

The learner state will track concept mastery, answer quality, misconceptions, attempts, hint history, and difficulty signals. An adaptive tutoring policy will then choose an action such as a subtle hint, stronger hint, alternative explanation, analogy, easier question, harder question, prerequisite review, quiz, or progression to the next concept. The language model will generate the natural-language teaching response within those controls.

## Current prototype

This repository currently provides the content and interface foundation:

- A responsive React syllabus explorer covering 9 topics and 68 subtopics from Cambridge O Level Mathematics 4024.
- Topic and subtopic navigation, learning outcomes, syllabus notes, breadcrumbs, previous/next navigation, dark mode, and accessible typography.
- A Python pipeline that renders mathematics PDFs page by page and uses a vision-language model to extract semantic, structured JSON.
- Pydantic validation for headings, paragraphs, lists, tables, figures, and LaTeX mathematics.
- Resumable extraction with retry handling, atomic progress saves, failure reporting, and configurable model selection through OpenRouter.
- A frontend renderer for structured study notes and KaTeX mathematical notation.

The practice workspace now persists typed working and photographed solutions in PostgreSQL through an anonymous learner session. The adaptive learner model, tutoring-policy engine, and AI evaluation harness remain the next implementation milestones.

## Architecture

```text
Learning sources
      |
      v
PDF renderer -> Vision extraction -> Pydantic validation -> Structured JSON
                                                            |
                                                            v
React syllabus and study-note interface              [implemented]
                                                            |
                                                            v
Typed/image response storage                         [implemented]
                                                            |
                                                            v
Learner state -> Adaptive policy -> Tutor LLM -> Evaluator  [planned]
```

## Technology

- Frontend: React, Vite, React Router, KaTeX, Tailwind CSS tooling, Lucide icons
- Content pipeline: Python, PyMuPDF, Pydantic, Requests
- AI integration: OpenRouter-compatible multimodal chat-completions API
- Data format: schema-validated JSON organized by syllabus topic and subtopic

## Run the frontend

Prerequisites: Node.js 20 or later.

```bash
cd frontend
npm install
npm run dev
```

Create a production build with:

```bash
cd frontend
npm run build
```

## Set up PostgreSQL and run the content API

The current backend milestone stores the reviewed Probability questions, answers,
marking points, and notes in PostgreSQL. PostgreSQL 18 is configured locally on
port `5433`.

Create the backend's own virtual environment and install only its dependencies:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Run the one-time setup from a normal terminal. It securely prompts for the
existing `postgres` administrator password and a new password for the project
role; passwords are not echoed:

```powershell
.\backend\.venv\Scripts\python.exe scripts/setup_database.py
```

The setup creates only these local PostgreSQL objects:

- role: `ai_tutor_app`
- database: `ai_tutor`
- schema tables for topics, subtopics, question collections, questions,
  question parts, marking points, note documents, learner sessions, typed
  responses, and solution-image attachments

It then imports the existing Probability content, creates the learner-response
tables, and writes `DATABASE_URL` to
the Git-ignored `backend/.env` file. The command is safe to run again: schema migrations
and content imports are idempotent.

Start the API from the project root:

```powershell
backend\start.cmd
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm.cmd run dev
```

Vite proxies `/api` to `http://localhost:8000` during local development. Useful
checks are `http://localhost:8000/api/v1/health`,
`http://localhost:8000/api/v1/topics/8/question-summary`,
`http://localhost:8000/api/v1/topics/8/questions`, and
`http://localhost:8000/api/v1/subtopics/8.1/notes`.

Run the live backend regression test with:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Before starting a new feature, run every local release gate together:

```powershell
.\verify.cmd
```

### Why this first schema is intentionally small

Fields that need relationships or filtering are relational: a topic has
subtopics and question collections; a question has ordered parts; each part has
ordered marking points. Renderer-specific blocks (paragraphs, tables, Venn
diagrams, figures, and note sections) stay in PostgreSQL `JSONB`. This avoids an
over-complicated first schema while retaining the existing structured content.

The checked-in Probability JSON files currently act only as repeatable seed
inputs. React no longer imports them and reads runtime content through the
versioned API instead. Public API responses are contract-checked, and database
connections are served through a bounded PostgreSQL connection pool.

## Run the note-ingestion pipeline

Prerequisites: Python 3.10 or later.

```bash
python -m venv .venv
# Activate the environment for your operating system, then:
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, add an OpenRouter API key, place authorized source PDFs under `Notes_data/`, and run:

```bash
python scripts/parse_notes.py
python scripts/compile_subtopic_notes.py
```

Source PDFs and generated note extracts are intentionally excluded from version control. Only use and publish learning material for which you have the necessary rights.

## Build-phase roadmap

1. Complete and quality-check the structured content pipeline for the selected MVP topics.
2. Add diagnostic questions and an explicit per-concept learner-state model.
3. Implement the rule-based adaptive tutoring policy and tutor response generation.
4. Add session persistence and progress visualization.
5. Build an evaluator for mathematical correctness, grounding, personalization, and pedagogical action quality.
6. Test complete learner journeys, refine the interface, deploy the MVP, and record the demonstration.

## Status

This is an active hackathon prototype. The repository accurately separates implemented capabilities from the planned adaptive tutoring system.
