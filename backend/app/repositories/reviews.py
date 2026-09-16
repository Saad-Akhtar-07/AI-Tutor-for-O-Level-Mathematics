from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from ..services.images import prepare_ai_image


class ReviewNotFound(ValueError):
    pass


class ReviewConflict(ValueError):
    pass


class ReviewRateLimited(ValueError):
    pass


@dataclass(frozen=True)
class ReviewCreation:
    review: dict[str, Any]
    created: bool


def _public_payload(row: dict[str, Any]) -> dict[str, Any]:
    evaluation = row.get("evaluation") or {}
    snapshot = row["snapshot"]
    return {
        "id": row["id"],
        "question_part_id": row["question_part_id"],
        "response_revision": row["response_revision"],
        "attempt_number": row["attempt_number"],
        "intent": row["intent"],
        "status": row["status"],
        "assessment": evaluation.get("assessment"),
        "marks_awarded": evaluation.get("marks_awarded"),
        "marks_maximum": snapshot["target_part"]["marks"],
        "action": row.get("policy_action"),
        "hint_level": row.get("hint_level"),
        "feedback": row.get("public_feedback"),
        "error_message": row.get("error_message"),
        "created_at": row["created_at"],
        "completed_at": row.get("completed_at"),
    }


def get_review(connection: Connection, review_id: UUID) -> dict[str, Any] | None:
    return connection.execute(
        "SELECT * FROM tutor_reviews WHERE id = %s", (review_id,)
    ).fetchone()


def get_review_for_session(
    connection: Connection, session_id: UUID, review_id: UUID
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM tutor_reviews
        WHERE id = %s AND learner_session_id = %s
        """,
        (review_id, session_id),
    ).fetchone()
    return _public_payload(row) if row else None


def create_review(
    connection: Connection,
    session_id: UUID,
    question_part_id: str,
    expected_revision: int,
    intent: str,
    requested_vision_model: str,
    requested_evaluation_model: str,
    prompt_version: str,
    policy_version: str,
) -> ReviewCreation:
    response = connection.execute(
        """
        SELECT sr.id, sr.typed_work, sr.status, sr.revision,
               qp.question_id, qp.label, qp.marks, qp.prompt_blocks,
               qp.answer_suffix, qp.model_answer,
               q.title AS question_title, q.question_number,
               q.syllabus_codes, q.prompt_blocks AS question_prompt
        FROM student_responses sr
        JOIN question_parts qp ON qp.id = sr.question_part_id
        JOIN questions q ON q.id = qp.question_id
        WHERE sr.learner_session_id = %s AND sr.question_part_id = %s
        FOR UPDATE OF sr
        """,
        (session_id, question_part_id),
    ).fetchone()
    if response is None:
        raise ReviewNotFound("Student response not found")
    if response["revision"] != expected_revision:
        raise ReviewConflict("This answer changed before the review started. Submit it again.")
    if response["status"] != "ready_for_review":
        raise ReviewConflict("Save this answer as ready for review first.")

    existing = connection.execute(
        """
        SELECT * FROM tutor_reviews
        WHERE student_response_id = %s AND response_revision = %s
        """,
        (response["id"], expected_revision),
    ).fetchone()
    if existing is not None:
        return ReviewCreation(existing, False)

    recent_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM tutor_reviews
        WHERE learner_session_id = %s
          AND created_at > NOW() - INTERVAL '10 minutes'
        """,
        (session_id,),
    ).fetchone()["count"]
    if recent_count >= 12:
        raise ReviewRateLimited("Please wait a few minutes before requesting another review.")

    marking_points = connection.execute(
        """
        SELECT code, description
        FROM marking_points
        WHERE question_part_id = %s
        ORDER BY position
        """,
        (question_part_id,),
    ).fetchall()
    attachment_rows = connection.execute(
        """
        SELECT media_type, image_data, width, height, sha256
        FROM response_attachments
        WHERE student_response_id = %s
        ORDER BY created_at, id
        """,
        (response["id"],),
    ).fetchall()
    prepared_images = [prepare_ai_image(bytes(item["image_data"])) for item in attachment_rows]

    previous = connection.execute(
        """
        SELECT evaluation, policy_action, hint_level
        FROM tutor_reviews
        WHERE learner_session_id = %s AND question_part_id = %s
          AND status = 'completed'
        ORDER BY attempt_number DESC
        LIMIT 1
        """,
        (session_id, question_part_id),
    ).fetchone()

    attempt_number = connection.execute(
        """
        SELECT COUNT(*) + 1 AS attempt_number
        FROM tutor_reviews
        WHERE learner_session_id = %s AND question_part_id = %s
        """,
        (session_id, question_part_id),
    ).fetchone()["attempt_number"]
    snapshot = {
        "question": {
            "id": response["question_id"],
            "number": response["question_number"],
            "title": response["question_title"],
            "syllabus_codes": response["syllabus_codes"],
            "stimulus": response["question_prompt"],
        },
        "target_part": {
            "id": question_part_id,
            "label": response["label"],
            "marks": response["marks"],
            "prompt": response["prompt_blocks"],
            "answer_suffix": response["answer_suffix"],
        },
        "mark_scheme": {
            "answer": response["model_answer"],
            "marking_points": [
                {"code": point["code"], "description": point["description"]}
                for point in marking_points
            ],
        },
        "learner_work": {
            "typed_work": response["typed_work"],
            "images": [
                {
                    "position": position,
                    "media_type": item.media_type,
                    "sha256": item.sha256,
                    "width": item.width,
                    "height": item.height,
                }
                for position, item in enumerate(prepared_images)
            ],
        },
        "previous_review": (
            {
                "evaluation": previous["evaluation"],
                "policy_action": previous["policy_action"],
                "hint_level": previous["hint_level"],
            }
            if previous
            else None
        ),
    }

    review_id = uuid4()
    row = connection.execute(
        """
        INSERT INTO tutor_reviews (
            id, learner_session_id, student_response_id, question_part_id,
            response_revision, attempt_number, intent, snapshot,
            requested_vision_model, requested_evaluation_model,
            prompt_version, policy_version
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            review_id,
            session_id,
            response["id"],
            question_part_id,
            expected_revision,
            attempt_number,
            intent,
            Jsonb(snapshot),
            requested_vision_model if prepared_images else None,
            requested_evaluation_model,
            prompt_version,
            policy_version,
        ),
    ).fetchone()
    for position, item in enumerate(prepared_images):
        connection.execute(
            """
            INSERT INTO tutor_review_images (
                id, tutor_review_id, position, media_type, byte_size,
                width, height, sha256, image_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(), review_id, position, item.media_type, len(item.data),
                item.width, item.height, item.sha256, item.data,
            ),
        )
    return ReviewCreation(row, True)


def claim_review(connection: Connection, review_id: UUID) -> bool:
    row = connection.execute(
        """
        UPDATE tutor_reviews
        SET status = 'processing', started_at = NOW(),
            error_code = NULL, error_message = NULL, completed_at = NULL
        WHERE id = %s AND status IN ('pending', 'failed')
        RETURNING id
        """,
        (review_id,),
    ).fetchone()
    return row is not None


def get_review_images(connection: Connection, review_id: UUID) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT position, media_type, image_data, width, height, sha256
        FROM tutor_review_images
        WHERE tutor_review_id = %s
        ORDER BY position
        """,
        (review_id,),
    ).fetchall()


def count_prior_unsuccessful(connection: Connection, review: dict[str, Any]) -> int:
    return connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM tutor_reviews
        WHERE learner_session_id = %s AND question_part_id = %s
          AND attempt_number < %s AND status = 'completed'
          AND evaluation->>'assessment' IN ('partial', 'incorrect')
        """,
        (
            review["learner_session_id"],
            review["question_part_id"],
            review["attempt_number"],
        ),
    ).fetchone()["count"]


def complete_review(
    connection: Connection,
    review_id: UUID,
    *,
    vision_result: dict[str, Any] | None,
    evaluation: dict[str, Any],
    action: str,
    hint_level: int,
    feedback: str,
    actual_vision_model: str | None,
    actual_evaluation_model: str,
    usage: dict[str, Any],
    claimed_at,
) -> dict[str, Any]:
    return connection.execute(
        """
        UPDATE tutor_reviews
        SET status = 'completed', vision_result = %s, evaluation = %s,
            policy_action = %s, hint_level = %s, public_feedback = %s,
            actual_vision_model = %s, actual_evaluation_model = %s,
            usage = %s, completed_at = NOW()
        WHERE id = %s AND status = 'processing' AND started_at = %s
        RETURNING *
        """,
        (
            Jsonb(vision_result) if vision_result is not None else None,
            Jsonb(evaluation), action, hint_level, feedback,
            actual_vision_model, actual_evaluation_model, Jsonb(usage), review_id, claimed_at,
        ),
    ).fetchone()


def fail_review(
    connection: Connection, review_id: UUID, error_code: str, error_message: str, *, claimed_at
) -> None:
    connection.execute(
        """
        UPDATE tutor_reviews
        SET status = 'failed', error_code = %s, error_message = %s,
            completed_at = NOW()
        WHERE id = %s AND status = 'processing' AND started_at = %s
        """,
        (error_code[:80], error_message[:500], review_id, claimed_at),
    )


def list_reviews(
    connection: Connection, session_id: UUID, topic_number: str | None
) -> list[dict[str, Any]]:
    filters = ["tr.learner_session_id = %s"]
    parameters: list[Any] = [session_id]
    if topic_number is not None:
        filters.append("t.syllabus_number = %s")
        parameters.append(topic_number)
    rows = connection.execute(
        f"""
        SELECT tr.*
        FROM tutor_reviews tr
        JOIN question_parts qp ON qp.id = tr.question_part_id
        JOIN questions q ON q.id = qp.question_id
        JOIN question_collections qc ON qc.id = q.collection_id
        JOIN topics t ON t.id = qc.topic_id
        WHERE {' AND '.join(filters)}
        ORDER BY tr.created_at, tr.id
        """,
        parameters,
    ).fetchall()
    return [_public_payload(row) for row in rows]


def public_payload(row: dict[str, Any]) -> dict[str, Any]:
    return _public_payload(row)
