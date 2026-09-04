import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from ..config import get_settings
from ..database import get_connection
from ..repositories import reviews as review_repository
from ..repositories import submissions as submission_repository
from ..schemas.tutor import ReviewRequest, TutorReviewList, TutorReviewResponse
from ..services.openrouter import OpenRouterError
from ..services.tutor import (
    POLICY_VERSION,
    PROMPT_VERSION,
    choose_policy,
    run_tutor_models,
)


router = APIRouter(prefix="/api/v1", tags=["AI tutor"])
DatabaseConnection = Annotated[Connection, Depends(get_connection)]
logger = logging.getLogger(__name__)


def require_session(connection: Connection, session_id: UUID) -> None:
    if not submission_repository.session_exists(connection, session_id):
        raise HTTPException(status_code=404, detail="Learner session not found")


@router.post(
    "/learner-sessions/{session_id}/responses/{question_part_id}/reviews",
    response_model=TutorReviewResponse,
)
def review_response(
    session_id: UUID,
    question_part_id: str,
    request: ReviewRequest,
    connection: DatabaseConnection,
) -> dict:
    require_session(connection, session_id)
    settings = get_settings()
    try:
        creation = review_repository.create_review(
            connection,
            session_id,
            question_part_id,
            request.expected_revision,
            request.intent.value,
            settings.openrouter_vision_model,
            settings.openrouter_evaluation_model,
            PROMPT_VERSION,
            POLICY_VERSION,
        )
    except review_repository.ReviewNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except review_repository.ReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except review_repository.ReviewRateLimited as error:
        raise HTTPException(status_code=429, detail=str(error)) from error

    connection.commit()
    review = creation.review
    if review["status"] == "completed":
        return review_repository.public_payload(review)
    if review["status"] == "processing":
        raise HTTPException(status_code=409, detail="This attempt is already being reviewed.")
    if not review_repository.claim_review(connection, review["id"]):
        raise HTTPException(status_code=409, detail="This attempt is already being reviewed.")

    review = review_repository.get_review(connection, review["id"])
    images = review_repository.get_review_images(connection, review["id"])
    prior_unsuccessful = review_repository.count_prior_unsuccessful(connection, review)
    connection.commit()

    try:
        model_result = run_tutor_models(settings, review["snapshot"], images)
        decision = choose_policy(model_result.evaluation, prior_unsuccessful)
        completed = review_repository.complete_review(
            connection,
            review["id"],
            vision_result=(
                model_result.vision.model_dump() if model_result.vision else None
            ),
            evaluation=model_result.evaluation.model_dump(),
            action=decision.action,
            hint_level=decision.hint_level,
            feedback=decision.feedback,
            actual_vision_model=model_result.actual_vision_model,
            actual_evaluation_model=model_result.actual_evaluation_model,
            usage=model_result.usage,
        )
        connection.commit()
        return review_repository.public_payload(completed)
    except OpenRouterError as error:
        logger.warning("OpenRouter tutor review failed (%s): %s", error.code, error)
        public_message = (
            "AI review is not configured yet. Your answer is still saved."
            if error.code == "missing_api_key"
            else "We couldn't review this attempt right now. Your answer is still saved."
        )
        review_repository.fail_review(connection, review["id"], error.code, public_message)
        connection.commit()
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error.code in {"missing_api_key", "provider_error"}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=http_status, detail=public_message) from error


@router.get(
    "/learner-sessions/{session_id}/reviews",
    response_model=TutorReviewList,
)
def learner_reviews(
    session_id: UUID,
    connection: DatabaseConnection,
    topic_number: str | None = Query(default=None, max_length=10),
) -> dict:
    require_session(connection, session_id)
    return {"reviews": review_repository.list_reviews(connection, session_id, topic_number)}


@router.get(
    "/learner-sessions/{session_id}/reviews/{review_id}",
    response_model=TutorReviewResponse,
)
def learner_review(
    session_id: UUID, review_id: UUID, connection: DatabaseConnection
) -> dict:
    require_session(connection, session_id)
    review = review_repository.get_review_for_session(connection, session_id, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Tutor review not found")
    return review
