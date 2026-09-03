-- Minimal content schema for the Probability MVP.
-- Relational columns hold fields we query and relate. JSONB is reserved for
-- flexible renderer blocks such as tables, diagrams, and formatted notes.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topics (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    syllabus_number VARCHAR(10) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subtopics (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_id BIGINT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    syllabus_code VARCHAR(20) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS question_collections (
    id TEXT PRIMARY KEY,
    topic_id BIGINT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    schema_version VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    source_edition TEXT,
    source_files JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_status TEXT,
    total_marks INTEGER NOT NULL CHECK (total_marks >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES question_collections(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    syllabus_codes TEXT[] NOT NULL DEFAULT '{}',
    source_pages JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
    total_marks INTEGER NOT NULL CHECK (total_marks >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (collection_id, question_number),
    UNIQUE (collection_id, position)
);

CREATE INDEX IF NOT EXISTS questions_collection_idx
    ON questions (collection_id, position);
CREATE INDEX IF NOT EXISTS questions_syllabus_codes_gin_idx
    ON questions USING GIN (syllabus_codes);

CREATE TABLE IF NOT EXISTS question_parts (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    marks INTEGER NOT NULL CHECK (marks >= 0),
    prompt_blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
    answer_suffix TEXT,
    model_answer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (question_id, position)
);

CREATE INDEX IF NOT EXISTS question_parts_question_idx
    ON question_parts (question_id, position);

CREATE TABLE IF NOT EXISTS marking_points (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_part_id TEXT NOT NULL REFERENCES question_parts(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    code VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    UNIQUE (question_part_id, position)
);

CREATE INDEX IF NOT EXISTS marking_points_part_idx
    ON marking_points (question_part_id, position);

CREATE TABLE IF NOT EXISTS notes_documents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subtopic_id BIGINT NOT NULL UNIQUE REFERENCES subtopics(id) ON DELETE CASCADE,
    content_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
