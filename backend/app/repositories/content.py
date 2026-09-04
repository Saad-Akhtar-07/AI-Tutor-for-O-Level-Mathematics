from psycopg import Connection


def get_question_summary(connection: Connection, topic_number: str) -> dict:
    summary = connection.execute(
        """
        SELECT COUNT(q.id) AS question_count,
               COALESCE(SUM(q.total_marks), 0) AS total_marks
        FROM topics t
        LEFT JOIN question_collections qc ON qc.topic_id = t.id
        LEFT JOIN questions q ON q.collection_id = qc.id
        WHERE t.syllabus_number = %s
        GROUP BY t.id
        """,
        (topic_number,),
    ).fetchone()
    return summary or {"question_count": 0, "total_marks": 0}


def get_question_bank(connection: Connection, topic_number: str) -> dict | None:
    collection = connection.execute(
        """
        SELECT qc.id, qc.schema_version, qc.title, qc.subject,
               qc.source_edition, qc.source_files, qc.review_status,
               qc.total_marks
        FROM question_collections qc
        JOIN topics t ON t.id = qc.topic_id
        WHERE t.syllabus_number = %s
        ORDER BY qc.created_at
        LIMIT 1
        """,
        (topic_number,),
    ).fetchone()
    if collection is None:
        return None

    questions = connection.execute(
        """
        SELECT id, question_number, title, syllabus_codes, source_pages,
               prompt_blocks, total_marks
        FROM questions
        WHERE collection_id = %s
        ORDER BY position
        """,
        (collection["id"],),
    ).fetchall()
    question_ids = [question["id"] for question in questions]

    parts_by_question: dict[str, list[dict]] = {question_id: [] for question_id in question_ids}
    if question_ids:
        parts = connection.execute(
            """
            SELECT id, question_id, label, marks, prompt_blocks, answer_suffix
            FROM question_parts
            WHERE question_id = ANY(%s)
            ORDER BY question_id, position
            """,
            (question_ids,),
        ).fetchall()
        for part in parts:
            payload = {
                "id": part["id"],
                "label": part["label"],
                "marks": part["marks"],
                "prompt": part["prompt_blocks"],
            }
            if part["answer_suffix"] is not None:
                payload["answer_suffix"] = part["answer_suffix"]
            parts_by_question[part["question_id"]].append(payload)

    question_payloads = [
        {
            "id": question["id"],
            "number": question["question_number"],
            "title": question["title"],
            "syllabus_codes": question["syllabus_codes"],
            "source_pages": question["source_pages"],
            "prompt": question["prompt_blocks"],
            "parts": parts_by_question[question["id"]],
            "total_marks": question["total_marks"],
        }
        for question in questions
    ]

    return {
        "schema_version": collection["schema_version"],
        "collection_id": collection["id"],
        "title": collection["title"],
        "subject": collection["subject"],
        "source_edition": collection["source_edition"],
        "source_files": collection["source_files"],
        "question_count": len(question_payloads),
        "total_marks": collection["total_marks"],
        "review_status": collection["review_status"],
        "questions": question_payloads,
    }


def get_question_part_solution(connection: Connection, question_part_id: str) -> dict | None:
    part = connection.execute(
        """
        SELECT id, model_answer
        FROM question_parts
        WHERE id = %s
        """,
        (question_part_id,),
    ).fetchone()
    if part is None:
        return None
    points = connection.execute(
        """
        SELECT code, description
        FROM marking_points
        WHERE question_part_id = %s
        ORDER BY position
        """,
        (question_part_id,),
    ).fetchall()
    return {
        "question_part_id": part["id"],
        "answer": part["model_answer"],
        "marking_points": [
            {"code": point["code"], "text": point["description"]}
            for point in points
        ],
    }


def get_notes(connection: Connection, subtopic_code: str) -> dict | None:
    note = connection.execute(
        """
        SELECT s.syllabus_code, s.title, t.syllabus_number,
               nd.sections
        FROM notes_documents nd
        JOIN subtopics s ON s.id = nd.subtopic_id
        JOIN topics t ON t.id = s.topic_id
        WHERE s.syllabus_code = %s
        """,
        (subtopic_code,),
    ).fetchone()
    if note is None:
        return None

    return {
        "subtopic_code": note["syllabus_code"],
        "subtopic_title": note["title"],
        "topic_number": note["syllabus_number"],
        "sections": note["sections"],
    }
