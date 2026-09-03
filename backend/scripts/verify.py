import psycopg
from psycopg.rows import dict_row

from backend.app.config import get_settings


EXPECTED_COUNTS = {
    "questions": 20,
    "parts": 53,
    "marking_points": 82,
    "notes_documents": 3,
    "total_marks": 115,
    "invalid_part_ids": 0,
}


def main() -> None:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM questions) AS questions,
                (SELECT COUNT(*) FROM question_parts) AS parts,
                (SELECT COUNT(*) FROM marking_points) AS marking_points,
                (SELECT COUNT(*) FROM notes_documents) AS notes_documents,
                (SELECT COALESCE(SUM(total_marks), 0) FROM questions) AS total_marks,
                (
                    SELECT COUNT(*)
                    FROM question_parts qp
                    JOIN questions q ON q.id = qp.question_id
                    WHERE qp.id NOT LIKE q.id || ':%'
                ) AS invalid_part_ids
            """
        ).fetchone()

    mismatches = {
        key: {"expected": expected, "actual": counts[key]}
        for key, expected in EXPECTED_COUNTS.items()
        if counts[key] != expected
    }
    if mismatches:
        raise SystemExit(f"Database verification failed: {mismatches}")
    print("Database verified: " + ", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
