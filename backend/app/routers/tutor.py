import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from ..config import get_settings
from ..database import get_connection, pool
from ..repositories import chat as chat_repository
from ..repositories import reviews as review_repository
from ..repositories import submissions as submission_repository
from ..schemas.tutor import (
    ReviewRequest,
    TutorChatRequest,
    TutorChatTurnList,
    TutorChatTurnResponse,
    TutorReviewList,
    TutorReviewResponse,
)
from ..services.openrouter import OpenRouterError
from ..services.tutor import (
    POLICY_VERSION,
    PROMPT_VERSION,
    CHAT_PROMPT_VERSION,
    choose_policy,
    run_tutor_chat,
    run_tutor_models,
)


router = APIRouter(prefix="/api/v1", tags=["AI tutor"])
DatabaseConnection = Annotated[Connection, Depends(get_connection)]
logger = logging.getLogger(__name__)


def require_session(connection: Connection, session_id: UUID) -> None:
    if not submission_repository.session_exists(connection, session_id):
        raise HTTPException(status_code=404, detail="Learner session not found")
    # The longest permitted model budget is 80s. A 120s lease also allows
    # persistence overhead, and recovers abandoned work after a process restart.
    for table in ("tutor_reviews", "tutor_chat_turns"):
        connection.execute(
            f"""UPDATE {table} SET status = 'failed', error_code = 'interrupted',
                error_message = 'This request was interrupted. Your work is saved; please retry.',
                completed_at = NOW()
                WHERE learner_session_id = %s AND status IN ('pending', 'processing')
                AND COALESCE(started_at, created_at) < NOW() - INTERVAL '120 seconds'""",
            (session_id,),
        )


@router.post(
    "/learner-sessions/{session_id}/responses/{question_part_id}/reviews",
    response_model=TutorReviewResponse,
)
def review_response(
    session_id: UUID,
    question_part_id: str,
    request: ReviewRequest,
) -> dict:
    with pool.connection() as connection:
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
                settings.requested_text_model("evaluation"),
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
        with pool.connection() as connection:
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
                claimed_at=review["started_at"],
            )
            if completed is None:
                raise HTTPException(status_code=409, detail="This request was interrupted; refresh to load its saved state.")
            connection.commit()
            return review_repository.public_payload(completed)
    except OpenRouterError as error:
        logger.warning("AI tutor review failed (%s): %s", error.code, error)
        public_messages = {
            "missing_api_key": "AI review is not configured yet. Your answer is still saved.",
            "provider_rate_limited": (
                "The tutor is busy right now. Your answer is saved. "
                "Try again shortly, or continue with the lesson notes."
            ),
            "provider_data_policy": (
                "No AI endpoint matches the current student-data privacy policy. "
                "Your answer is still saved."
            ),
        }
        public_message = public_messages.get(
            error.code,
            "We couldn't review this attempt right now. Your answer is still saved.",
        )
        with pool.connection() as connection:
            review_repository.fail_review(connection, review["id"], error.code, public_message, claimed_at=review["started_at"])
            connection.commit()
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error.code
            in {"missing_api_key", "provider_error", "provider_rate_limited", "provider_timeout", "provider_busy"}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=http_status, detail=public_message) from error
    except HTTPException:
        raise
    except Exception:
        logger.exception("Tutor processing failed unexpectedly")
        with pool.connection() as connection:
            review_repository.fail_review(connection, review["id"], "internal_error", "Your work is saved. Please retry the review.", claimed_at=review["started_at"])
        raise HTTPException(status_code=503, detail="The tutor could not finish. Please retry your saved request.")


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


@router.post(
    "/learner-sessions/{session_id}/question-parts/{question_part_id}/chat-turns",
    response_model=TutorChatTurnResponse,
)
def create_chat_turn(
    session_id: UUID,
    question_part_id: str,
    request: TutorChatRequest,
) -> dict:
    with pool.connection() as connection:
        require_session(connection, session_id)
        settings = get_settings()
        try:
            creation = chat_repository.create_turn(
                connection,
                session_id,
                question_part_id,
                request.client_message_id,
                request.message,
                settings.requested_text_model("chat"),
                CHAT_PROMPT_VERSION,
            )
        except chat_repository.ChatNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except chat_repository.ChatConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except chat_repository.ChatRateLimited as error:
            raise HTTPException(status_code=429, detail=str(error)) from error

        connection.commit()
        turn = creation.turn
        if turn["status"] == "completed":
            return chat_repository.public_payload(turn)
        if turn["status"] == "processing":
            raise HTTPException(status_code=409, detail="This message is already being answered.")
        if not chat_repository.claim_turn(connection, turn["id"]):
            raise HTTPException(status_code=409, detail="This message is already being answered.")
        turn = chat_repository.get_turn(connection, turn["id"])
        connection.commit()

    try:
        model_result = run_tutor_chat(
            settings, turn["context_snapshot"], turn["learner_message"]
        )
        with pool.connection() as connection:
            completed = chat_repository.complete_turn(
                connection,
                turn["id"],
                tutor_message=model_result.reply.message,
                teaching_move=model_result.reply.teaching_move,
                should_revise_work=model_result.reply.should_revise_work,
                actual_model=model_result.actual_model,
                usage=model_result.usage,
                claimed_at=turn["started_at"],
            )
            submission_repository.touch_session(connection, session_id)
            if completed is None:
                raise HTTPException(status_code=409, detail="This request was interrupted; refresh to load its saved state.")
            connection.commit()
            return chat_repository.public_payload(completed)
    except OpenRouterError as error:
        logger.warning("AI tutor chat failed (%s): %s", error.code, error)
        public_messages = {
            "missing_api_key": "AI tutoring is not configured yet. Your message is saved.",
            "provider_rate_limited": (
                "The tutor is busy right now. Your message is saved. "
                "Try again shortly, or continue with the lesson notes."
            ),
            "provider_data_policy": (
                "The tutor is unavailable right now. Your message is saved. "
                "You can continue with the lesson notes."
            ),
        }
        public_message = public_messages.get(
            error.code,
            "I couldn't answer just now. Your message is saved; please retry.",
        )
        with pool.connection() as connection:
            chat_repository.fail_turn(connection, turn["id"], error.code, public_message, claimed_at=turn["started_at"])
            connection.commit()
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error.code
            in {"missing_api_key", "provider_error", "provider_rate_limited", "provider_timeout", "provider_busy"}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=http_status, detail=public_message) from error
    except HTTPException:
        raise
    except Exception:
        logger.exception("Tutor processing failed unexpectedly")
        with pool.connection() as connection:
            chat_repository.fail_turn(connection, turn["id"], "internal_error", "Your message is saved. Please retry.", claimed_at=turn["started_at"])
        raise HTTPException(status_code=503, detail="The tutor could not finish. Please retry your saved request.")


@router.get(
    "/learner-sessions/{session_id}/chat-turns",
    response_model=TutorChatTurnList,
)
def learner_chat_turns(
    session_id: UUID,
    connection: DatabaseConnection,
    topic_number: str | None = Query(default=None, max_length=10),
) -> dict:
    require_session(connection, session_id)
    return {"turns": chat_repository.list_turns(connection, session_id, topic_number)}
