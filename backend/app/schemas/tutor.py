from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewIntent(str, Enum):
    check = "check"
    hint = "hint"


class ReviewRequest(BaseModel):
    expected_revision: int = Field(gt=0)
    intent: ReviewIntent = ReviewIntent.check


class VisionTranscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcription: str = Field(max_length=20_000)
    readability: Literal["clear", "partially_clear", "unreadable"]
    uncertain_fragments: list[str] = Field(max_length=20)


class CriterionEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=40)
    status: Literal["met", "not_met", "unclear"]
    evidence: str = Field(max_length=1_000)


class PrimaryError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "conceptual_error",
        "calculation_error",
        "method_error",
        "misread_question",
        "incomplete_working",
        "answer_only",
        "notation_error",
        "unknown",
    ]
    target_concept: str = Field(max_length=200)
    description: str = Field(max_length=1_000)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment: Literal["correct", "partial", "incorrect", "unassessable"]
    marks_awarded: int = Field(ge=0)
    readability: Literal["clear", "partially_clear", "unreadable", "not_provided"]
    observed_work: str = Field(max_length=20_000)
    criteria: list[CriterionEvaluation] = Field(max_length=30)
    primary_error: PrimaryError | None
    positive_observation: str = Field(max_length=500)
    guiding_question: str = Field(max_length=500)
    next_step_hint: str = Field(max_length=1_000)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def keep_unassessable_results_safe(self):
        if self.assessment == "unassessable" and self.marks_awarded != 0:
            raise ValueError("unassessable work cannot receive marks")
        return self


class TutorReviewResponse(BaseModel):
    id: UUID
    question_part_id: str
    response_revision: int
    attempt_number: int
    intent: ReviewIntent
    status: Literal["pending", "processing", "completed", "failed"]
    assessment: str | None = None
    marks_awarded: int | None = None
    marks_maximum: int
    action: str | None = None
    hint_level: int | None = None
    feedback: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class TutorReviewList(BaseModel):
    reviews: list[TutorReviewResponse]
