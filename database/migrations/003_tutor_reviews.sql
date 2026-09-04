-- Immutable AI review attempts for the Probability tutor MVP.

CREATE TABLE tutor_reviews (
    id UUID PRIMARY KEY,
    learner_session_id UUID NOT NULL REFERENCES learner_sessions(id) ON DELETE CASCADE,
    student_response_id UUID NOT NULL REFERENCES student_responses(id) ON DELETE CASCADE,
    question_part_id TEXT NOT NULL REFERENCES question_parts(id) ON DELETE RESTRICT,
    response_revision INTEGER NOT NULL CHECK (response_revision > 0),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    intent VARCHAR(20) NOT NULL CHECK (intent IN ('check', 'hint')),
    snapshot JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    vision_result JSONB,
    evaluation JSONB,
    policy_action VARCHAR(40),
    hint_level INTEGER CHECK (hint_level BETWEEN 0 AND 3),
    public_feedback TEXT,
    requested_vision_model TEXT,
    actual_vision_model TEXT,
    requested_evaluation_model TEXT NOT NULL,
    actual_evaluation_model TEXT,
    prompt_version VARCHAR(40) NOT NULL,
    policy_version VARCHAR(40) NOT NULL,
    usage JSONB,
    error_code VARCHAR(80),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (student_response_id, response_revision),
    UNIQUE (learner_session_id, question_part_id, attempt_number)
);

CREATE INDEX tutor_reviews_session_idx
    ON tutor_reviews (learner_session_id, created_at DESC);
CREATE INDEX tutor_reviews_part_idx
    ON tutor_reviews (learner_session_id, question_part_id, attempt_number DESC);

CREATE TABLE tutor_review_images (
    id UUID PRIMARY KEY,
    tutor_review_id UUID NOT NULL REFERENCES tutor_reviews(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    media_type VARCHAR(50) NOT NULL
        CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    sha256 CHAR(64) NOT NULL,
    image_data BYTEA NOT NULL,
    UNIQUE (tutor_review_id, position),
    UNIQUE (tutor_review_id, sha256)
);

CREATE INDEX tutor_review_images_review_idx
    ON tutor_review_images (tutor_review_id, position);
