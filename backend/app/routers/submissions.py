from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from psycopg import Connection

from ..database import get_connection
from ..repositories import submissions as submission_repository
from ..schemas.submissions import (
    LearnerSessionResponse,
    StudentResponseList,
    StudentResponseResponse,
    StudentResponseUpdate,
)
from ..services.images import InvalidSolutionImage, MAX_UPLOAD_BYTES, normalize_solution_image


router = APIRouter(prefix="/api/v1", tags=["learner input"])
DatabaseConnection = Annotated[Connection, Depends(get_connection)]
MAX_ATTACHMENTS_PER_RESPONSE = 4


def require_session(connection: Connection, session_id: UUID) -> None:
    if not submission_repository.session_exists(connection, session_id):
        raise HTTPException(status_code=404, detail="Learner session not found")


@router.post(
    "/learner-sessions",
    response_model=LearnerSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_learner_session(connection: DatabaseConnection) -> dict:
    return submission_repository.create_session(connection)


@router.get(
    "/learner-sessions/{session_id}/responses",
    response_model=StudentResponseList,
)
def learner_responses(
    session_id: UUID,
    connection: DatabaseConnection,
    topic_number: str | None = Query(default=None, max_length=10),
) -> dict:
    require_session(connection, session_id)
    submission_repository.touch_session(connection, session_id)
    return {
        "responses": submission_repository.list_responses(
            connection, session_id, topic_number
        )
    }


@router.put(
    "/learner-sessions/{session_id}/responses/{question_part_id}",
    response_model=StudentResponseResponse,
)
def save_learner_response(
    session_id: UUID,
    question_part_id: str,
    update: StudentResponseUpdate,
    connection: DatabaseConnection,
) -> dict:
    require_session(connection, session_id)
    if not submission_repository.part_exists(connection, question_part_id):
        raise HTTPException(status_code=404, detail="Question part not found")

    if update.status.value == "ready_for_review" and not update.typed_work.strip():
        existing = submission_repository.get_response(
            connection, session_id, question_part_id
        )
        if existing is None or not existing["attachments"]:
            raise HTTPException(
                status_code=422,
                detail="Add typed working or a solution image before submitting.",
            )

    return submission_repository.upsert_response(
        connection,
        session_id,
        question_part_id,
        update.typed_work,
        update.status.value,
    )


@router.post(
    "/learner-sessions/{session_id}/responses/{question_part_id}/attachments",
    response_model=StudentResponseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_response_attachment(
    session_id: UUID,
    question_part_id: str,
    connection: DatabaseConnection,
    image: UploadFile = File(...),
) -> dict:
    require_session(connection, session_id)
    if not submission_repository.part_exists(connection, question_part_id):
        raise HTTPException(status_code=404, detail="Question part not found")

    raw = await image.read(MAX_UPLOAD_BYTES + 1)
    await image.close()
    try:
        normalized = normalize_solution_image(raw)
    except InvalidSolutionImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    response = submission_repository.ensure_response(
        connection, session_id, question_part_id
    )
    if submission_repository.count_attachments(connection, response["id"]) >= MAX_ATTACHMENTS_PER_RESPONSE:
        raise HTTPException(
            status_code=422,
            detail=f"A response can contain at most {MAX_ATTACHMENTS_PER_RESPONSE} images.",
        )

    filename = Path(image.filename or "solution-image").name[:255]
    submission_repository.add_attachment(
        connection,
        response["id"],
        filename,
        normalized.media_type,
        normalized.data,
        normalized.width,
        normalized.height,
        normalized.sha256,
    )
    submission_repository.touch_session(connection, session_id)
    return submission_repository.get_response(connection, session_id, question_part_id)


@router.get(
    "/learner-sessions/{session_id}/attachments/{attachment_id}/content",
    response_class=Response,
)
def attachment_content(
    session_id: UUID, attachment_id: UUID, connection: DatabaseConnection
) -> Response:
    require_session(connection, session_id)
    attachment = submission_repository.get_attachment_content(
        connection, session_id, attachment_id
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Solution image not found")
    return Response(
        content=bytes(attachment["image_data"]),
        media_type=attachment["media_type"],
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/learner-sessions/{session_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_attachment(
    session_id: UUID, attachment_id: UUID, connection: DatabaseConnection
) -> Response:
    require_session(connection, session_id)
    if not submission_repository.delete_attachment(
        connection, session_id, attachment_id
    ):
        raise HTTPException(status_code=404, detail="Solution image not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
