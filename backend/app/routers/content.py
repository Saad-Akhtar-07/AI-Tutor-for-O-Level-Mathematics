from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from ..database import get_connection
from ..repositories import content as content_repository
from ..schemas.content import (
    HealthResponse,
    NotesDocumentResponse,
    QuestionBankResponse,
    QuestionSummaryResponse,
)


router = APIRouter(prefix="/api/v1")
DatabaseConnection = Annotated[Connection, Depends(get_connection)]


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(connection: DatabaseConnection) -> dict[str, str]:
    connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "connected"}


@router.get(
    "/topics/{topic_number}/question-summary",
    response_model=QuestionSummaryResponse,
    tags=["content"],
)
def topic_question_summary(topic_number: str, connection: DatabaseConnection) -> dict:
    return content_repository.get_question_summary(connection, topic_number)


@router.get(
    "/topics/{topic_number}/questions",
    response_model=QuestionBankResponse,
    tags=["content"],
)
def topic_questions(topic_number: str, connection: DatabaseConnection) -> dict:
    bank = content_repository.get_question_bank(connection, topic_number)
    if bank is None:
        raise HTTPException(status_code=404, detail="No question bank for this topic")
    return bank


@router.get(
    "/subtopics/{subtopic_code}/notes",
    response_model=NotesDocumentResponse,
    tags=["content"],
)
def subtopic_notes(subtopic_code: str, connection: DatabaseConnection) -> dict:
    notes = content_repository.get_notes(connection, subtopic_code)
    if notes is None:
        raise HTTPException(status_code=404, detail="No notes for this subtopic")
    return notes
