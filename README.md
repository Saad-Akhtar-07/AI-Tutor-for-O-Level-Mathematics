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

The adaptive learner model, tutoring-policy engine, interactive assessment loop, persistence layer, and AI evaluation harness are the next implementation milestones.

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
