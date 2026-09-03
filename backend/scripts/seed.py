import argparse
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from backend.app.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTION_FILE = (
    PROJECT_ROOT / "frontend" / "src" / "data" / "questions" / "probability.json"
)
NOTES_DIR = PROJECT_ROOT / "frontend" / "src" / "data" / "notes"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_question_bank(bank: dict) -> None:
    questions = bank["questions"]
    if bank["question_count"] != len(questions):
        raise ValueError("question_count does not match the number of questions")
    if bank["total_marks"] != sum(question["total_marks"] for question in questions):
        raise ValueError("collection total_marks does not match question totals")
    for question in questions:
        part_marks = sum(part["marks"] for part in question["parts"])
        if question["total_marks"] != part_marks:
            raise ValueError(
                f"{question['id']} total_marks does not match its question parts"
            )


def database_part_id(question_id: str, source_part_id: str) -> str:
    """Make source-local part IDs globally stable across question collections."""
    return f"{question_id}:{source_part_id}"


def seed(database_url: str) -> dict[str, int]:
    bank = load_json(QUESTION_FILE)
    validate_question_bank(bank)
    notes = [load_json(NOTES_DIR / f"8.{number}.json") for number in range(1, 4)]

    with psycopg.connect(database_url) as connection:
        topic_id = connection.execute(
            """
            INSERT INTO topics (syllabus_number, title)
            VALUES ('8', 'Probability')
            ON CONFLICT (syllabus_number) DO UPDATE
            SET title = EXCLUDED.title, updated_at = NOW()
            RETURNING id
            """
        ).fetchone()[0]

        subtopic_ids: dict[str, int] = {}
        for note in notes:
            subtopic_ids[note["subtopic_code"]] = connection.execute(
                """
                INSERT INTO subtopics (topic_id, syllabus_code, title)
                VALUES (%s, %s, %s)
                ON CONFLICT (syllabus_code) DO UPDATE
                SET topic_id = EXCLUDED.topic_id,
                    title = EXCLUDED.title,
                    updated_at = NOW()
                RETURNING id
                """,
                (topic_id, note["subtopic_code"], note["subtopic_title"]),
            ).fetchone()[0]

        connection.execute(
            """
            INSERT INTO question_collections (
                id, topic_id, schema_version, title, subject, source_edition,
                source_files, review_status, total_marks
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET topic_id = EXCLUDED.topic_id,
                schema_version = EXCLUDED.schema_version,
                title = EXCLUDED.title,
                subject = EXCLUDED.subject,
                source_edition = EXCLUDED.source_edition,
                source_files = EXCLUDED.source_files,
                review_status = EXCLUDED.review_status,
                total_marks = EXCLUDED.total_marks,
                updated_at = NOW()
            """,
            (
                bank["collection_id"],
                topic_id,
                bank["schema_version"],
                bank["title"],
                bank["subject"],
                bank.get("source_edition"),
                Jsonb(bank.get("source_files", {})),
                bank.get("review_status"),
                bank["total_marks"],
            ),
        )

        part_count = 0
        marking_point_count = 0
        for question_position, question in enumerate(bank["questions"], start=1):
            connection.execute(
                """
                INSERT INTO questions (
                    id, collection_id, question_number, position, title,
                    syllabus_codes, source_pages, prompt_blocks, total_marks
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET collection_id = EXCLUDED.collection_id,
                    question_number = EXCLUDED.question_number,
                    position = EXCLUDED.position,
                    title = EXCLUDED.title,
                    syllabus_codes = EXCLUDED.syllabus_codes,
                    source_pages = EXCLUDED.source_pages,
                    prompt_blocks = EXCLUDED.prompt_blocks,
                    total_marks = EXCLUDED.total_marks,
                    updated_at = NOW()
                """,
                (
                    question["id"],
                    bank["collection_id"],
                    question["number"],
                    question_position,
                    question["title"],
                    question.get("syllabus_codes", []),
                    Jsonb(question.get("source_pages", {})),
                    Jsonb(question.get("prompt", [])),
                    question["total_marks"],
                ),
            )

            expected_part_ids = [
                database_part_id(question["id"], part["id"])
                for part in question["parts"]
            ]
            # Early seed versions stored source-local IDs such as q01.a. Remove
            # those rows before their positions are claimed by globally stable IDs.
            connection.execute(
                """
                DELETE FROM question_parts
                WHERE question_id = %s AND NOT (id = ANY(%s))
                """,
                (question["id"], expected_part_ids),
            )

            for part_position, part in enumerate(question["parts"], start=1):
                mark_scheme = part["mark_scheme"]
                part_id = database_part_id(question["id"], part["id"])
                connection.execute(
                    """
                    INSERT INTO question_parts (
                        id, question_id, position, label, marks, prompt_blocks,
                        answer_suffix, model_answer
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET question_id = EXCLUDED.question_id,
                        position = EXCLUDED.position,
                        label = EXCLUDED.label,
                        marks = EXCLUDED.marks,
                        prompt_blocks = EXCLUDED.prompt_blocks,
                        answer_suffix = EXCLUDED.answer_suffix,
                        model_answer = EXCLUDED.model_answer,
                        updated_at = NOW()
                    """,
                    (
                        part_id,
                        question["id"],
                        part_position,
                        part.get("label", ""),
                        part["marks"],
                        Jsonb(part.get("prompt", [])),
                        part.get("answer_suffix"),
                        mark_scheme["answer"],
                    ),
                )
                connection.execute(
                    "DELETE FROM marking_points WHERE question_part_id = %s",
                    (part_id,),
                )
                for point_position, point in enumerate(
                    mark_scheme.get("marking_points", []), start=1
                ):
                    connection.execute(
                        """
                        INSERT INTO marking_points (
                            question_part_id, position, code, description
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (part_id, point_position, point["code"], point["text"]),
                    )
                    marking_point_count += 1
                part_count += 1

        for note in notes:
            connection.execute(
                """
                INSERT INTO notes_documents (subtopic_id, content_version, sections)
                VALUES (%s, '1.0', %s)
                ON CONFLICT (subtopic_id) DO UPDATE
                SET content_version = EXCLUDED.content_version,
                    sections = EXCLUDED.sections,
                    updated_at = NOW()
                """,
                (subtopic_ids[note["subtopic_code"]], Jsonb(note["sections"])),
            )

    return {
        "topics": 1,
        "subtopics": len(notes),
        "questions": len(bank["questions"]),
        "question_parts": part_count,
        "marking_points": marking_point_count,
        "notes_documents": len(notes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed reviewed Probability content")
    parser.add_argument("--database-url", help="Override DATABASE_URL")
    args = parser.parse_args()
    database_url = args.database_url or get_settings().database_url
    counts = seed(database_url)
    print("Seeded " + ", ".join(f"{value} {key}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
