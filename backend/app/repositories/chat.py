from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb


MAX_RECENT_TURNS = 12
CHAT_RATE_LIMIT = 30


class ChatNotFound(ValueError):
    pass


class ChatConflict(ValueError):
    pass


class ChatRateLimited(ValueError):
    pass


@dataclass(frozen=True)
class ChatCreation:
    turn: dict[str, Any]
    created: bool


def public_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "client_message_id": row["client_message_id"],
        "question_part_id": row["question_part_id"],
        "response_revision": row.get("response_revision"),
        "learner_message": row["learner_message"],
        "tutor_message": row.get("tutor_message"),
        "teaching_move": row.get("teaching_move"),
        "should_revise_work": row.get("should_revise_work"),
        "status": row["status"],
        "error_message": row.get("error_message"),
        "created_at": row["created_at"],
        "completed_at": row.get("completed_at"),
    }


def create_turn(
    connection: Connection,
    session_id: UUID,
    question_part_id: str,
    client_message_id: UUID,
    learner_message: str,
    requested_model: str,
    prompt_version: str,
) -> ChatCreation:
    message = learner_message.strip()
    existing = connection.execute(
        """
        SELECT * FROM tutor_chat_turns
        WHERE learner_session_id = %s AND client_message_id = %s
        """,
        (session_id, client_message_id),
    ).fetchone()
    if existing is not None:
        if (
            existing["question_part_id"] != question_part_id
            or existing["learner_message"] != message
        ):
            raise ChatConflict("This message identifier was already used.")
        return ChatCreation(existing, False)

    recent_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM tutor_chat_turns
        WHERE learner_session_id = %s
          AND created_at > NOW() - INTERVAL '10 minutes'
        """,
        (session_id,),
    ).fetchone()["count"]
    if recent_count >= CHAT_RATE_LIMIT:
        raise ChatRateLimited(
            "You have sent several messages. Pause briefly, then continue learning."
        )

    part = connection.execute(
        """
        SELECT qp.id, qp.label, qp.marks, qp.prompt_blocks, qp.answer_suffix,
               qp.model_answer, q.id AS question_id, q.title AS question_title,
               q.question_number, q.syllabus_codes,
               q.prompt_blocks AS question_prompt
        FROM question_parts qp
        JOIN questions q ON q.id = qp.question_id
        WHERE qp.id = %s
        """,
        (question_part_id,),
    ).fetchone()
    if part is None:
        raise ChatNotFound("Question part not found")

    response = connection.execute(
        """
        SELECT sr.typed_work, sr.revision,
               (SELECT COUNT(*) FROM response_attachments ra
                WHERE ra.student_response_id = sr.id) AS attachment_count
        FROM student_responses sr
        WHERE learner_session_id = %s AND question_part_id = %s
        """,
        (session_id, question_part_id),
    ).fetchone()
    marking_points = connection.execute(
        """
        SELECT code, description
        FROM marking_points
        WHERE question_part_id = %s
        ORDER BY position
        """,
        (question_part_id,),
    ).fetchall()
    latest_review = connection.execute(
        """
        SELECT response_revision, evaluation, policy_action, hint_level,
               public_feedback
        FROM tutor_reviews
        WHERE learner_session_id = %s AND question_part_id = %s
          AND status = 'completed'
        ORDER BY attempt_number DESC
        LIMIT 1
        """,
        (session_id, question_part_id),
    ).fetchone()
    recent_turns = connection.execute(
        """
        SELECT learner_message, tutor_message
        FROM tutor_chat_turns
        WHERE learner_session_id = %s AND question_part_id = %s
          AND status = 'completed'
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (session_id, question_part_id, MAX_RECENT_TURNS),
    ).fetchall()

    snapshot = {
        "question": {
            "id": part["question_id"],
            "number": part["question_number"],
            "title": part["question_title"],
            "syllabus_codes": part["syllabus_codes"],
            "stimulus": part["question_prompt"],
        },
        "target_part": {
            "id": part["id"],
            "label": part["label"],
            "marks": part["marks"],
            "prompt": part["prompt_blocks"],
            "answer_suffix": part["answer_suffix"],
        },
        "private_mark_scheme": {
            "answer": part["model_answer"],
            "marking_points": [
                {"code": item["code"], "description": item["description"]}
                for item in marking_points
            ],
        },
        "learner_work": {
            "typed_work": response["typed_work"] if response else "",
            "revision": response["revision"] if response else None,
            "attachment_count": response["attachment_count"] if response else 0,
        },
        "latest_review": (
            {
                "reviewed_response_revision": latest_review["response_revision"],
                "evaluation": latest_review["evaluation"],
                "policy_action": latest_review["policy_action"],
                "hint_level": latest_review["hint_level"],
                "feedback_already_shown": latest_review["public_feedback"],
            }
            if latest_review
            else None
        ),
        "conversation": [
            {
                "learner": item["learner_message"],
                "tutor": item["tutor_message"],
            }
            for item in reversed(recent_turns)
        ],
    }
    turn = connection.execute(
        """
        INSERT INTO tutor_chat_turns (
            id, client_message_id, learner_session_id, question_part_id,
            response_revision, learner_message, context_snapshot,
            requested_model, prompt_version
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            uuid4(),
            client_message_id,
            session_id,
            question_part_id,
            response["revision"] if response else None,
            message,
            Jsonb(snapshot),
            requested_model,
            prompt_version,
        ),
    ).fetchone()
    return ChatCreation(turn, True)


def claim_turn(connection: Connection, turn_id: UUID) -> bool:
    row = connection.execute(
        """
        UPDATE tutor_chat_turns
        SET status = 'processing', started_at = NOW(),
            error_code = NULL, error_message = NULL, completed_at = NULL
        WHERE id = %s AND status IN ('pending', 'failed')
        RETURNING id
        """,
        (turn_id,),
    ).fetchone()
    return row is not None


def get_turn(connection: Connection, turn_id: UUID) -> dict[str, Any] | None:
    return connection.execute(
        "SELECT * FROM tutor_chat_turns WHERE id = %s", (turn_id,)
    ).fetchone()


def complete_turn(
    connection: Connection,
    turn_id: UUID,
    *,
    tutor_message: str,
    teaching_move: str,
    should_revise_work: bool,
    actual_model: str,
    usage: dict[str, Any],
) -> dict[str, Any]:
    return connection.execute(
        """
        UPDATE tutor_chat_turns
        SET status = 'completed', tutor_message = %s, teaching_move = %s,
            should_revise_work = %s, actual_model = %s, usage = %s,
            completed_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            tutor_message,
            teaching_move,
            should_revise_work,
            actual_model,
            Jsonb(usage),
            turn_id,
        ),
    ).fetchone()


def fail_turn(
    connection: Connection, turn_id: UUID, error_code: str, error_message: str
) -> None:
    connection.execute(
        """
        UPDATE tutor_chat_turns
        SET status = 'failed', error_code = %s, error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (error_code[:80], error_message[:500], turn_id),
    )


def list_turns(
    connection: Connection, session_id: UUID, topic_number: str | None
) -> list[dict[str, Any]]:
    filters = ["tc.learner_session_id = %s"]
    parameters: list[Any] = [session_id]
    if topic_number is not None:
        filters.append("t.syllabus_number = %s")
        parameters.append(topic_number)
    rows = connection.execute(
        f"""
        SELECT tc.*
        FROM tutor_chat_turns tc
        JOIN question_parts qp ON qp.id = tc.question_part_id
        JOIN questions q ON q.id = qp.question_id
        JOIN question_collections qc ON qc.id = q.collection_id
        JOIN topics t ON t.id = qc.topic_id
        WHERE {' AND '.join(filters)}
        ORDER BY tc.created_at, tc.id
        """,
        parameters,
    ).fetchall()
    return [public_payload(row) for row in rows]
