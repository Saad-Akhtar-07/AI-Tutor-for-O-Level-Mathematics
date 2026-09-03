-- Durable learner input for the tutoring loop.
-- Sessions are anonymous in the hackathon MVP. Their UUID acts as the browser's
-- private handle until account authentication is added.

CREATE TABLE learner_sessions (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE student_responses (
    id UUID PRIMARY KEY,
    learner_session_id UUID NOT NULL REFERENCES learner_sessions(id) ON DELETE CASCADE,
    question_part_id TEXT NOT NULL REFERENCES question_parts(id) ON DELETE RESTRICT,
    typed_work TEXT NOT NULL DEFAULT '',
    status VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready_for_review')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ready_at TIMESTAMPTZ,
    UNIQUE (learner_session_id, question_part_id)
);

CREATE INDEX student_responses_session_idx
    ON student_responses (learner_session_id, updated_at DESC);
CREATE INDEX student_responses_part_idx
    ON student_responses (question_part_id);

CREATE TABLE response_attachments (
    id UUID PRIMARY KEY,
    student_response_id UUID NOT NULL REFERENCES student_responses(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    media_type VARCHAR(50) NOT NULL
        CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    sha256 CHAR(64) NOT NULL,
    image_data BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_response_id, sha256)
);

CREATE INDEX response_attachments_response_idx
    ON response_attachments (student_response_id, created_at);
