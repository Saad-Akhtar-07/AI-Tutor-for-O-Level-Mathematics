-- Persisted, question-scoped Socratic conversations.
-- Assessment remains in tutor_reviews; chat turns teach from that evidence but
-- never award marks or mutate an immutable review.

CREATE TABLE tutor_chat_turns (
    id UUID PRIMARY KEY,
    client_message_id UUID NOT NULL,
    learner_session_id UUID NOT NULL REFERENCES learner_sessions(id) ON DELETE CASCADE,
    question_part_id TEXT NOT NULL REFERENCES question_parts(id) ON DELETE RESTRICT,
    response_revision INTEGER CHECK (response_revision > 0),
    learner_message TEXT NOT NULL CHECK (
        char_length(learner_message) BETWEEN 1 AND 1000
    ),
    tutor_message TEXT,
    teaching_move VARCHAR(40),
    should_revise_work BOOLEAN,
    context_snapshot JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    requested_model TEXT NOT NULL,
    actual_model TEXT,
    prompt_version VARCHAR(40) NOT NULL,
    usage JSONB,
    error_code VARCHAR(80),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (learner_session_id, client_message_id)
);

CREATE INDEX tutor_chat_turns_session_idx
    ON tutor_chat_turns (learner_session_id, created_at);
CREATE INDEX tutor_chat_turns_part_idx
    ON tutor_chat_turns (learner_session_id, question_part_id, created_at);
