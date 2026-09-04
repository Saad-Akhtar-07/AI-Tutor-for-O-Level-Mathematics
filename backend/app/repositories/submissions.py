from uuid import UUID, uuid4

from psycopg import Connection


def create_session(connection: Connection) -> dict:
    return connection.execute(
        """
        INSERT INTO learner_sessions (id)
        VALUES (%s)
        RETURNING id, created_at
        """,
        (uuid4(),),
    ).fetchone()


def session_exists(connection: Connection, session_id: UUID) -> bool:
    row = connection.execute(
        "SELECT 1 FROM learner_sessions WHERE id = %s", (session_id,)
    ).fetchone()
    return row is not None


def touch_session(connection: Connection, session_id: UUID) -> None:
    connection.execute(
        "UPDATE learner_sessions SET last_seen_at = NOW() WHERE id = %s",
        (session_id,),
    )


def part_exists(connection: Connection, question_part_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM question_parts WHERE id = %s", (question_part_id,)
    ).fetchone()
    return row is not None


def _attachment_payload(attachment: dict, session_id: UUID) -> dict:
    return {
        "id": attachment["id"],
        "original_filename": attachment["original_filename"],
        "media_type": attachment["media_type"],
        "byte_size": attachment["byte_size"],
        "width": attachment["width"],
        "height": attachment["height"],
        "created_at": attachment["created_at"],
        "content_url": (
            f"/api/v1/learner-sessions/{session_id}/attachments/"
            f"{attachment['id']}/content"
        ),
    }


def _response_payload(
    connection: Connection, response: dict, session_id: UUID
) -> dict:
    attachments = connection.execute(
        """
        SELECT id, original_filename, media_type, byte_size, width, height, created_at
        FROM response_attachments
        WHERE student_response_id = %s
        ORDER BY created_at, id
        """,
        (response["id"],),
    ).fetchall()
    return {
        **response,
        "attachments": [
            _attachment_payload(attachment, session_id) for attachment in attachments
        ],
    }


def get_response(
    connection: Connection, session_id: UUID, question_part_id: str
) -> dict | None:
    response = connection.execute(
        """
        SELECT id, question_part_id, typed_work, status, revision,
               created_at, updated_at, ready_at
        FROM student_responses
        WHERE learner_session_id = %s AND question_part_id = %s
        """,
        (session_id, question_part_id),
    ).fetchone()
    if response is None:
        return None
    return _response_payload(connection, response, session_id)


def list_responses(
    connection: Connection, session_id: UUID, topic_number: str | None
) -> list[dict]:
    filters = ["sr.learner_session_id = %s"]
    parameters: list[object] = [session_id]
    if topic_number is not None:
        filters.append("t.syllabus_number = %s")
        parameters.append(topic_number)
    responses = connection.execute(
        f"""
        SELECT sr.id, sr.question_part_id, sr.typed_work, sr.status, sr.revision,
               sr.created_at, sr.updated_at, sr.ready_at
        FROM student_responses sr
        JOIN question_parts qp ON qp.id = sr.question_part_id
        JOIN questions q ON q.id = qp.question_id
        JOIN question_collections qc ON qc.id = q.collection_id
        JOIN topics t ON t.id = qc.topic_id
        WHERE {' AND '.join(filters)}
        ORDER BY sr.updated_at DESC
        """,
        parameters,
    ).fetchall()
    return [
        _response_payload(connection, response, session_id) for response in responses
    ]


def upsert_response(
    connection: Connection,
    session_id: UUID,
    question_part_id: str,
    typed_work: str,
    status: str,
) -> dict:
    response = connection.execute(
        """
        INSERT INTO student_responses (
            id, learner_session_id, question_part_id, typed_work, status, ready_at
        )
        VALUES (%s, %s, %s, %s, %s, CASE WHEN %s = 'ready_for_review' THEN NOW() END)
        ON CONFLICT (learner_session_id, question_part_id) DO UPDATE
        SET typed_work = EXCLUDED.typed_work,
            status = EXCLUDED.status,
            revision = student_responses.revision + 1,
            updated_at = NOW(),
            ready_at = CASE
                WHEN EXCLUDED.status = 'ready_for_review' THEN COALESCE(student_responses.ready_at, NOW())
                ELSE NULL
            END
        RETURNING id, question_part_id, typed_work, status, revision,
                  created_at, updated_at, ready_at
        """,
        (uuid4(), session_id, question_part_id, typed_work, status, status),
    ).fetchone()
    touch_session(connection, session_id)
    return _response_payload(connection, response, session_id)


def ensure_response(
    connection: Connection, session_id: UUID, question_part_id: str
) -> dict:
    existing = get_response(connection, session_id, question_part_id)
    if existing is not None:
        return existing
    return upsert_response(connection, session_id, question_part_id, "", "draft")


def count_attachments(connection: Connection, response_id: UUID) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM response_attachments WHERE student_response_id = %s",
        (response_id,),
    ).fetchone()
    return row["count"]


def add_attachment(
    connection: Connection,
    response_id: UUID,
    original_filename: str,
    media_type: str,
    image_data: bytes,
    width: int,
    height: int,
    sha256: str,
) -> UUID:
    existing = connection.execute(
        """
        SELECT id FROM response_attachments
        WHERE student_response_id = %s AND sha256 = %s
        """,
        (response_id, sha256),
    ).fetchone()
    if existing is not None:
        return existing["id"]
    attachment_id = uuid4()
    connection.execute(
        """
        INSERT INTO response_attachments (
            id, student_response_id, original_filename, media_type, byte_size,
            width, height, sha256, image_data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            attachment_id,
            response_id,
            original_filename,
            media_type,
            len(image_data),
            width,
            height,
            sha256,
            image_data,
        ),
    )
    connection.execute(
        """
        UPDATE student_responses
        SET status = 'draft', revision = revision + 1,
            updated_at = NOW(), ready_at = NULL
        WHERE id = %s
        """,
        (response_id,),
    )
    return attachment_id


def get_attachment_content(
    connection: Connection, session_id: UUID, attachment_id: UUID
) -> dict | None:
    return connection.execute(
        """
        SELECT ra.original_filename, ra.media_type, ra.image_data
        FROM response_attachments ra
        JOIN student_responses sr ON sr.id = ra.student_response_id
        WHERE ra.id = %s AND sr.learner_session_id = %s
        """,
        (attachment_id, session_id),
    ).fetchone()


def delete_attachment(
    connection: Connection, session_id: UUID, attachment_id: UUID
) -> bool:
    deleted = connection.execute(
        """
        DELETE FROM response_attachments ra
        USING student_responses sr
        WHERE ra.id = %s
          AND ra.student_response_id = sr.id
          AND sr.learner_session_id = %s
        RETURNING ra.id, ra.student_response_id
        """,
        (attachment_id, session_id),
    ).fetchone()
    if deleted is not None:
        connection.execute(
            """
            UPDATE student_responses
            SET status = 'draft', revision = revision + 1,
                updated_at = NOW(), ready_at = NULL
            WHERE id = %s
            """,
            (deleted["student_response_id"],),
        )
        touch_session(connection, session_id)
    return deleted is not None
