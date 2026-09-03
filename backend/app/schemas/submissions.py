from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ResponseStatus(str, Enum):
    draft = "draft"
    ready_for_review = "ready_for_review"


class LearnerSessionResponse(BaseModel):
    id: UUID
    created_at: datetime


class StudentResponseUpdate(BaseModel):
    typed_work: str = Field(default="", max_length=20_000)
    status: ResponseStatus = ResponseStatus.draft

    @field_validator("typed_work")
    @classmethod
    def reject_null_characters(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("typed_work cannot contain null characters")
        return value


class AttachmentResponse(BaseModel):
    id: UUID
    original_filename: str
    media_type: str
    byte_size: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    created_at: datetime
    content_url: str


class StudentResponseResponse(BaseModel):
    id: UUID
    question_part_id: str
    typed_work: str
    status: ResponseStatus
    revision: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime
    ready_at: datetime | None = None
    attachments: list[AttachmentResponse]


class StudentResponseList(BaseModel):
    responses: list[StudentResponseResponse]
