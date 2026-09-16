# Mathematics Tutor API

This backend is the runtime boundary between React and PostgreSQL. The browser
never receives database credentials and never connects directly to PostgreSQL.

## Local setup

From the project root:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

`backend/.env` contains the local `DATABASE_URL` and is ignored by Git. The
checked-in `backend/.env.example` documents the required values.

## Run

Use either:

```powershell
backend\start.cmd
```

or:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The API listens at `http://127.0.0.1:8000`. Interactive documentation is at
`http://127.0.0.1:8000/docs`.

## Current endpoints

- `GET /api/v1/health`
- `GET /api/v1/topics/{topic_number}/question-summary`
- `GET /api/v1/topics/{topic_number}/questions`
- `GET /api/v1/question-parts/{question_part_id}/solution`
- `GET /api/v1/subtopics/{subtopic_code}/notes`
- `POST /api/v1/learner-sessions`
- `GET /api/v1/learner-sessions/{session_id}/responses`
- `PUT /api/v1/learner-sessions/{session_id}/responses/{question_part_id}`
- `POST /api/v1/learner-sessions/{session_id}/responses/{question_part_id}/attachments`
- `GET /api/v1/learner-sessions/{session_id}/attachments/{attachment_id}/content`
- `DELETE /api/v1/learner-sessions/{session_id}/attachments/{attachment_id}`
- `POST /api/v1/learner-sessions/{session_id}/responses/{question_part_id}/reviews`
- `GET /api/v1/learner-sessions/{session_id}/reviews`
- `GET /api/v1/learner-sessions/{session_id}/reviews/{review_id}`

All public responses are validated with Pydantic contracts before being sent to
React. PostgreSQL connections come from an application-managed connection pool.

## Verify

With PostgreSQL running and seeded:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

The integration test exercises the real database through FastAPI and verifies
question counts, marks, parts, notes, learner input, immutable tutor reviews,
idempotency, image snapshots, missing-content behavior, and health. Model calls
are replaced with deterministic fakes during automated tests.

For a quick database-only invariant check:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.verify
```

The project-root `verify.cmd` combines compilation, API integration tests,
database invariants, and the frontend production build.

Database changes belong in ordered files under `database/migrations/`. Reviewed
content is imported by `backend.scripts.seed`; future learner attempts and AI
state can be added through new migrations without rewriting these content tables.

## Learner input storage

The browser creates an anonymous learner session and keeps its unguessable UUID
in local storage. Typed working is auto-saved per question part with a revision
number and restored after refresh. A response can also contain up to four JPEG,
PNG, or WebP solution images of at most 8 MB each.

Uploads are decoded as images, orientation-corrected, re-encoded without EXIF
metadata, and deduplicated before their bytes and AI-friendly metadata are stored
in PostgreSQL. Changing text or attachments increments the response revision
and returns it to `draft`; `ready_for_review` allows that exact revision to enter
the tutor loop. Anonymous UUIDs are an MVP mechanism;
account authentication should replace them before handling real student data in
production.

## AI tutor reviews

Configure `GROQ_API_KEY` and `OPENROUTER_API_KEY` in `backend/.env`.
`AI_TEXT_PROVIDER=auto` prefers Groq for chat and assessment when its key is set;
OpenRouter free models provide backup and image transcription. See the complete
free-only configuration in [the root README](../README.md#3-configure-the-ai-provider)
and [.env.example](.env.example). Restart the API after changing settings.

Every submitted revision creates one immutable `tutor_reviews` snapshot. If the
attempt contains images, the backend first creates bounded 2048-pixel copies and
asks a vision model to transcribe only visible work. A second, structured call
evaluates the typed work plus transcription against the private mark scheme.
Typed-only attempts skip the vision call. A deterministic policy then exposes a
guiding question, targeted hint, or worked next step based on prior attempts.

The normal question-bank response no longer includes answers. Mark schemes load
only when the learner explicitly reveals one. Review endpoints return
student-safe feedback and never return the internal snapshot or evaluation.

### Socratic tutor chat

The question-side tutor also supports persisted, question-part-scoped chat. Each
turn is grounded in the reviewed question, private marking criteria, the learner's
current typed work, latest assessment, and up to 12 recent completed turns. The
chat model is teaching-only: it cannot award marks or mutate review records, and
its strict response schema forbids claiming that a reply reveals the final answer.
Learner messages survive refresh, failed provider calls remain retryable, duplicate
client message IDs are idempotent, and chat is limited to 30 turns per session per
10 minutes.

The provider client enforces deadlines across retries (35s chat, 65s review by
default), two attempts per stage, output token limits and privacy-preserving
OpenRouter fallbacks. It retries invalid structured results before returning an
error. Slow provider calls hold no database pool connection. Per-process admission
control allows six concurrent provider calls and fails excess requests quickly.
Rate-limit cooldowns are per provider account and process; multi-worker deployments
still share the upstream account quota.

Polling recovers saved results after refresh or a lost POST response. Requests
abandoned by a process restart expire after 120 seconds and can be retried with the
same immutable snapshot/idempotency key. Unexpected exceptions also mark requests
failed. Chat creation is serialized per learner session to prevent duplicate inserts.

OpenRouter's `data_collection` setting applies only to OpenRouter routing. Groq
uses its own data policy and account controls. Defaults remain `deny`; some free
OpenRouter models may be unavailable under that policy. Never silently relax it.

Run the disposable real-provider check:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.smoke_tutor --text-only
```

Omit `--text-only` for photo transcription + assessment + chat. The script checks
an expected correct answer, prints timings and removes only its synthetic session.
It uses real free-tier quota. Automated tests use fake providers and exercise
outages, timeouts, schema failures, rate limits, persistence and concurrent retries.
