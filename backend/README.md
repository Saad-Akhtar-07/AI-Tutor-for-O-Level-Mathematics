# Content API

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
- `GET /api/v1/subtopics/{subtopic_code}/notes`
- `POST /api/v1/learner-sessions`
- `GET /api/v1/learner-sessions/{session_id}/responses`
- `PUT /api/v1/learner-sessions/{session_id}/responses/{question_part_id}`
- `POST /api/v1/learner-sessions/{session_id}/responses/{question_part_id}/attachments`
- `GET /api/v1/learner-sessions/{session_id}/attachments/{attachment_id}/content`
- `DELETE /api/v1/learner-sessions/{session_id}/attachments/{attachment_id}`

All public responses are validated with Pydantic contracts before being sent to
React. PostgreSQL connections come from an application-managed connection pool.

## Verify

With PostgreSQL running and seeded:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

The integration test exercises the real database through FastAPI and verifies
question counts, marks, parts, notes, missing-content behavior, and health.

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
in PostgreSQL. `ready_for_review` marks the response state that should enter the
future tutor/evaluation loop. Anonymous UUIDs are an MVP mechanism;
account authentication should replace them before handling real student data in
production.
