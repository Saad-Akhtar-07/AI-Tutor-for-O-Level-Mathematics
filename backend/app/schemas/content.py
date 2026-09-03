from typing import Any

from pydantic import BaseModel, Field


JsonBlock = dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    database: str


class QuestionSummaryResponse(BaseModel):
    question_count: int = Field(ge=0)
    total_marks: int = Field(ge=0)


class MarkingPointResponse(BaseModel):
    code: str
    text: str


class MarkSchemeResponse(BaseModel):
    answer: str
    marking_points: list[MarkingPointResponse]


class QuestionPartResponse(BaseModel):
    id: str
    label: str
    marks: int = Field(ge=0)
    prompt: list[JsonBlock]
    answer_suffix: str | None = None
    mark_scheme: MarkSchemeResponse


class QuestionResponse(BaseModel):
    id: str
    number: int = Field(ge=1)
    title: str
    syllabus_codes: list[str]
    source_pages: dict[str, list[int]]
    prompt: list[JsonBlock]
    parts: list[QuestionPartResponse]
    total_marks: int = Field(ge=0)


class QuestionBankResponse(BaseModel):
    schema_version: str
    collection_id: str
    title: str
    subject: str
    source_edition: str | None = None
    source_files: dict[str, str]
    question_count: int = Field(ge=0)
    total_marks: int = Field(ge=0)
    review_status: str | None = None
    questions: list[QuestionResponse]


class NotesDocumentResponse(BaseModel):
    subtopic_code: str
    subtopic_title: str
    topic_number: str
    sections: list[JsonBlock]
