# AI O Level Mathematics Tutor - Project Progress

Last updated: 1 September 2026

Hackathon scope: Cambridge O Level Mathematics (Syllabus D 4024)

Current MVP topic: Probability (Topic 8)

## 1. Product goal

Build an AI mathematics tutor that does more than answer questions. The intended learning loop is:

`Teach -> Ask -> Evaluate -> Update learner state -> Choose the next teaching action -> Respond -> Repeat`

The hackathon MVP is intentionally limited to Probability so that one topic can be completed end to end before the system is expanded to the rest of the syllabus.

## 2. Current status

| Area | Status | Evidence / result |
|---|---|---|
| Product idea and MVP scope | Complete | O Level Mathematics tutor, with Probability selected for the first complete learning journey. |
| Frontend foundation | Complete | React/Vite interface with responsive syllabus navigation, topic and subtopic pages, breadcrumbs, previous/next navigation, dark mode, and KaTeX rendering. |
| Syllabus structure | Complete | 9 topics and 68 subtopics are represented. Probability is divided into 8.1, 8.2, and 8.3. |
| Notes ingestion pipeline | Complete for the current Probability sources | PDFs are rendered as images, parsed by a vision model, validated with Pydantic, and saved as resumable structured JSON. The reported notes milestone was completed on 24 August 2026. |
| Probability notes | Complete, redesigned, and production-ready | 27 parsed pages are bundled explicitly for Vercel: 8.1 has 5 pages/42 blocks, 8.2 has 3 pages/35 blocks, and 8.3 has 19 pages/200 blocks. Learners see continuous study chapters with a concept-based lesson outline, worked-example and examiner-tip summaries, callouts, tables, figures, and KaTeX mathematics; PDF page boundaries remain internal metadata only. |
| Practice-question sources | Collected, not parsed | `probability I.pdf` contains 20 numbered questions over 18 pages. Its mark scheme contains 17 pages and 115 total marks. |
| Structured question bank | Complete for Probability I | All 20 questions, 53 assessable parts, source-page references, diagrams/tables, final answers, mark codes, and marking guidance are stored in reviewed JSON. The dataset validates to 115 marks. |
| Interactive assessment | Complete for the tutor MVP | The Probability workspace accepts typed/image work, creates immutable review attempts, restores feedback after refresh, and prevents duplicate evaluation of the same revision. |
| Content database and API | Complete for current Probability content | PostgreSQL schema, repeatable migrations/seeding, and a modular FastAPI read API cover Probability topics/subtopics, 20 questions, 53 parts, 82 marking points, and 3 note documents. Direct API and Vite-proxy requests are verified against the local PostgreSQL 18 database. |
| Adaptive tutor AI | Complete for the basic MVP | Image attempts use vision-first transcription, all attempts receive schema-validated marking, and a deterministic policy escalates from guiding questions to stronger hints. |

### Implementation update - 3 September 2026: AI tutor MVP

- Added immutable `tutor_reviews` and AI-ready review-image snapshots keyed to an
  exact response revision.
- Added a two-stage image path: vision transcription first, followed by a strict
  structured evaluation. Typed-only attempts skip the vision call.
- Added progressive deterministic hint levels, persisted feedback history,
  duplicate-request protection, revision conflict checks, provider failure
  recovery, and a small per-session review limit.
- Removed answers and marking points from the normal question-bank response;
  mark schemes now load only after an explicit learner reveal.
- Replaced the hard-coded demo tutor with the live backend review flow and
  feedback restoration after refresh.
- Added automated policy and full API review tests without spending model calls.

### Implementation update - 4 September 2026: Socratic tutor conversation

- Replaced the removed demo composer with live, persisted AI tutor chat scoped to
  the active learner session and question part.
- Grounded each turn in the reviewed question, private marking criteria, current
  typed work, latest assessment, and bounded recent conversation history.
- Kept marking and teaching responsibilities separate: chat cannot award marks or
  mutate immutable reviews, and the structured tutor response must guide without
  revealing the final answer.
- Added idempotent message submission, safe provider failures with retry, a
  30-turn-per-10-minute session limit, restored history after refresh, optimistic
  UI feedback, and a multiline accessible composer.

### Implementation update - 3 September 2026

- Added anonymous learner sessions whose UUID is retained by the browser for the
  hackathon MVP, without introducing premature account/authentication work.
- Added PostgreSQL response records keyed to stable question-part IDs, including
  typed working, draft/ready-for-review state, revision numbers, and timestamps.
- Added image attachments with an 8 MB limit, a four-image limit per response,
  dimensions, real detected MIME type, SHA-256 deduplication, and database-backed
  content retrieval.
- Image uploads are decoded, orientation-corrected, and re-encoded without EXIF
  metadata before storage; only JPEG, PNG, and WebP are accepted.
- The practice composer now auto-saves text after a short pause, supports manual
  save, camera/gallery selection, previews, deletion, errors, and saved-state
  feedback. Saved work is restored on refresh and across question navigation.
- “Check with AI” now persists the complete response as `ready_for_review` before
  the existing demo tutor runs, creating the correct boundary for the real AI
  evaluator to replace later.
- Extended the live integration test through session creation, validation,
  saving, upload normalization/deduplication, retrieval, review readiness,
  restoration, and deletion. The backend test and production frontend build pass.

### Implementation update - 31 August 2026

- The complete hand-reviewed Probability I dataset is now stored in `frontend/src/data/questions/probability.json`.
- The question source and mark scheme were visually checked page by page before transcription.
- The reusable frontend route `/topic/:topicNumber/practice` provides the same question-and-tutor workspace for every syllabus topic. Probability loads all 20 reviewed questions with 53 answer parts and 115 marks; topics without a question bank show an intentional empty state.
- Tables, card sets, bag contents, Venn diagrams, and cumulative-frequency graph paper are reconstructed as responsive frontend elements.
- Every assessable part includes an answer area and a button that reveals its answer and examiner marking points.
- The question workspace now keeps the active question part beside an AI tutor panel, with demo hints, concept explanations, approach checks, and a chat composer.
- Answer input now supports larger working areas, retained drafts while navigating, and a compact set of high-value maths symbols without the complexity of handwriting recognition, uploads, or a full equation keyboard.
- Tutor responses are deliberately labelled as demo behavior; connecting them to approved notes, mark schemes, learner state, and a real model remains a backend milestone.
- Every topic overview, subtopic tab, desktop sidebar, and mobile selector links to its topic practice workspace.
- The production frontend build passes. Automatic answer marking, saved attempts, hints, and learner-state updates are the next milestone.

### Implementation update - 1 September 2026

- Added a minimal PostgreSQL content schema with relational topics, subtopics,
  question collections, questions, ordered parts, and ordered marking points.
- Kept renderer-oriented question and note blocks in `JSONB` so tables, diagrams,
  LaTeX, and extracted page content can evolve without premature table sprawl.
- Added an idempotent migration and Probability seed importer covering all 20
  questions, 53 parts, 115 marks, 82 marking points, and notes for 8.1-8.3.
- Added a FastAPI backend with health, topic-question, and subtopic-note endpoints.
- Replaced React's static content imports with cached API requests and explicit
  loading, missing-content, and backend-unavailable states.
- Added a secure local setup script for the `ai_tutor_app` role and `ai_tutor`
  database on PostgreSQL 18 port 5433. It writes the URL only to Git-ignored `backend/.env`.
- Separated the backend into its own `.venv`, `.env`, dependency manifest,
  route layer, and repository layer; verified the complete React-to-API-to-database path.
- Hardened the full-stack boundary with `/api/v1` routes, Pydantic response
  contracts, a bounded PostgreSQL connection pool, stable global question-part
  IDs, request timeouts, pinned frontend dependency ranges, and a live API test.

## 3. Probability content currently available

### Notes

- `Notes_data/Probability/1-ProbabilityToolkit.pdf`: parsed successfully into 13 pages.
- `Notes_data/Probability/2-ProbabilityDiagrams (Tree&Venn.pdf`: parsed successfully into 14 pages.
- Both outputs have `processing_status: completed` and no failed pages.
- The compiled note bundles are already loaded by the frontend for subtopics 8.1, 8.2, and 8.3.

### Questions and answers

- `Questions_data/Probability/probability I.pdf`: 20 numbered questions, 18 PDF pages.
- `Questions_data/Probability/probability I - mark scheme.pdf`: matching answer/mark-scheme rows, 17 PDF pages, 115 marks in total.
- The source includes single-event probability, complementary probability, combined events, replacement/no-replacement sampling, conditional paths, Venn diagrams, cards, frequency tables, and some statistics content.

Important observations from inspecting the PDFs:

- Page numbers cannot be used to pair questions with answers. A question can continue on another page, two questions can share one page, and mark-scheme rows break at different positions.
- Normal PDF text extraction is incomplete. It loses or misorders some fractions, inequalities, equations, table structure, Venn diagrams, graphs, and card diagrams. Vision extraction is therefore required, with the PDF text layer used only as supporting evidence.
- Some numbered questions mix Probability with Statistics. Each subpart should receive its own syllabus tags instead of assigning one topic to the entire question.
- The paper is labelled for examinations up to 2025, while the frontend syllabus targets 2025-2027. Every extracted item should therefore be checked against the current 8.1-8.3 outcomes before it is exposed to learners.
- The PDFs contain third-party branding/watermarks. Source rights and redistribution permission must be checked before question text or cropped images are shipped publicly.

## 4. Recommended target data model

The existing note schema should be reused for common content blocks, but questions need a separate assessment schema. A canonical item should resemble the following shape:

```json
{
  "id": "probability-001",
  "source": {
    "collection": "Probability I",
    "question_number": "1",
    "question_pages": [2],
    "mark_scheme_pages": [2]
  },
  "syllabus_tags": ["8.1"],
  "secondary_tags": ["9.3"],
  "stimulus": [],
  "parts": [
    {
      "id": "probability-001-a",
      "label": "a",
      "prompt": [],
      "marks": 1,
      "answer_format": "interval",
      "assets": [],
      "mark_scheme": {
        "final_answers": [],
        "mark_points": [],
        "alternatives": [],
        "notes": [],
        "guidance": []
      }
    }
  ],
  "total_marks": 7,
  "skills": [],
  "difficulty": null,
  "quality": {
    "needs_review": true,
    "review_reasons": []
  }
}
```

Design rules:

- Give every question and subpart a stable internal ID; never use the page number as the ID.
- Preserve the printed source number separately for traceability.
- Represent text, LaTeX, tables, and figures as structured blocks rather than one large string.
- Support recursively nested parts such as `2(b)(i)`.
- Store printed marks and mark-scheme codes such as `M1`, `A1`, `B1`, `FT`, and `SC1` explicitly.
- Preserve acceptable alternatives and examiner abbreviations without asking the model to invent an explanation.
- Keep `difficulty` empty during extraction. Assign it later from evidence such as marks, required steps, prerequisite skills, and learner performance.
- Store diagrams as structured data where practical. Use a reviewed asset only when the visual cannot be reconstructed reliably.

## 5. Plan for converting the PDFs into parsed questions

### Phase 1 - Define and test the contract

1. Add Pydantic schemas for source metadata, question groups, recursive subparts, prompts, answer formats, figures/tables, mark points, alternatives, syllabus tags, and review flags.
2. Write one hand-reviewed golden JSON example containing a table, nested subparts, fractions, a diagram, and a multi-row mark scheme.
3. Add validation rules for unique IDs, valid subpart paths, positive marks, valid syllabus codes, and consistent question totals.

Deliverable: a versioned `question-schema-v1` and one accepted example.

### Phase 2 - Create two source extractors

1. Reuse the existing PDF renderer, OpenRouter client, retry logic, progress saving, and failure reporting.
2. Create a question-paper prompt that extracts question boundaries, shared stimulus, recursive subparts, exact wording, marks, tables, mathematical notation, and diagram descriptions/data.
3. Create a separate mark-scheme prompt that preserves table columns: question ID, answer, marks, AO element, notes, and guidance.
4. Give the vision model adjacent-page context when an item begins or ends at a page boundary, while requiring it to emit only the requested page's records.
5. Save page-level intermediate JSON before any merging so extraction can resume safely and mistakes can be traced to a source page.

Deliverables:

- `parsed_questions/Probability/question_pages.json`
- `parsed_questions/Probability/mark_scheme_pages.json`
- a failure report containing pages and fields requiring review

### Phase 3 - Assemble and pair records deterministically

1. Merge page fragments using the printed hierarchy: question number, part, and subpart (for example `2 -> b -> i`).
2. Build canonical keys such as `q02.b.i` and use them to join question parts to mark-scheme rows.
3. Do not use semantic similarity as the primary join. Use it only to flag a suspected numbering/extraction error.
4. Preserve source-page references on every merged part.
5. Split mixed-topic questions at subpart level and tag them against 8.1, 8.2, 8.3, or a secondary Statistics outcome.

Deliverable: `parsed_questions/Probability/probability-question-bank.json`.

### Phase 4 - Extract or reconstruct visual assets

1. Detect questions containing Venn diagrams, cumulative-frequency graphs, cards, or other meaningful figures.
2. Prefer structured representations that the frontend can render consistently, such as Venn-region values, table cells, card values, or graph axes/points.
3. If an image crop is temporarily necessary, store the crop with its question ID, source page, alt text, dimensions, and review status.
4. Never treat the watermark or page furniture as part of an educational asset.

Deliverable: reviewed assets/data referenced by stable IDs from the question bank.

### Phase 5 - Validate with code and human review

Automated gates:

- exactly 20 root questions are present;
- all expected part IDs are unique and paired;
- there are no orphan question parts or orphan mark-scheme rows;
- per-part marks agree between the question paper and mark scheme;
- per-question totals agree with printed totals;
- the full collection totals 115 marks;
- all LaTeX renders in KaTeX;
- every referenced asset exists;
- every item has at least one syllabus tag;
- all source page references are valid.

Human review should focus on fractions, inequalities, equations, diagrams, table boundaries, replacement/no-replacement wording, mark-scheme alternatives, and any item marked `needs_review`.

Acceptance criterion: 100% of the 20 questions and all mark-scheme rows pass automated checks and human review before frontend integration.

### Phase 6 - Publish a frontend-ready bundle

1. Compile only approved fields into a smaller frontend bundle.
2. Keep source/provenance and internal review data in the canonical backend dataset.
3. Add a Probability practice view with one question at a time, subpart navigation, marks, answer input, submit, and reviewed solution feedback.
4. Keep answers hidden until submission or an explicit reveal action.

Deliverable: an interactive Probability practice flow backed by reviewed data.

## 6. Recommended next AI milestone

After the question bank is reliable, the next AI component should be the assessment and learner-state loop, not a general chatbot.

1. Define a per-skill learner state for 8.1, 8.2, and 8.3: attempts, correctness, marks earned, hints used, misconceptions, confidence, and last-seen time.
2. Start with deterministic checking for exact values, fractions, percentages, intervals, and simple algebra.
3. Use an LLM evaluator only for working/reasoning that cannot be graded safely with rules. Ground it in the approved question and mark scheme, and require structured evidence for every awarded mark.
4. Implement a small rule-based tutoring policy that chooses among retry, hint, worked example, easier prerequisite question, similar question, or progression.
5. Let the tutor LLM verbalize the selected action using the approved notes and mark scheme; do not let it choose marks or invent syllabus content.
6. Persist attempts so the demo can show the learner improving across a short Probability journey.

## 7. Immediate implementation order

1. Build `question-schema-v1` and one golden example.
2. Adapt the existing vision pipeline into separate question and mark-scheme extractors.
3. Parse and review questions 1-3 as a pilot because they test shared pages, continuation, nested parts, tables, graphs, and mixed Probability/Statistics tags.
4. Correct the schema and prompts based on that pilot.
5. Parse all 20 questions, merge, validate against the 115-mark total, and complete human review.
6. Integrate the reviewed bundle into the frontend.
7. Begin the assessment and learner-state AI milestone.

## 8. Main risks and controls

| Risk | Control |
|---|---|
| Vision model availability or free-tier expiry | Keep the model configurable, record the model used per run, and make parsing resumable. Re-verify a currently available vision model before the full run. |
| Incorrect mathematics from OCR/vision | Validate structure in code, render LaTeX, compare questions with mark-scheme answers, and require human review for flagged expressions. |
| Wrong question/answer pairing | Join by canonical question/subpart IDs and validate all printed marks and totals. |
| Mixed-topic questions pollute the learner model | Tag at subpart level and keep secondary cross-topic tags. |
| Diagram loss | Parse diagrams into structured data or reviewed assets; never rely on plain PDF text extraction alone. |
| Model grades plausible but incorrect reasoning | Use deterministic grading first and constrain LLM grading to the approved mark scheme with auditable mark-point output. |
| Copyright or redistribution restrictions | Keep source PDFs and derived content private until permission is confirmed; publish only content the project is authorized to use. |

## 9. Definition of the Probability MVP

The Probability MVP is complete when a learner can study reviewed notes, attempt reviewed questions, receive marks and targeted feedback, have mastery updated for 8.1-8.3, receive an appropriate next action, and resume the same learning journey later.
