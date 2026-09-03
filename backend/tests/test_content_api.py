import base64

from fastapi.testclient import TestClient
import psycopg

from backend.app.config import get_settings
from backend.app.main import app


def test_probability_content_contract() -> None:
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "database": "connected"}

        summary = client.get("/api/v1/topics/8/question-summary")
        assert summary.status_code == 200
        assert summary.json() == {"question_count": 20, "total_marks": 115}

        question_response = client.get("/api/v1/topics/8/questions")
        assert question_response.status_code == 200
        question_bank = question_response.json()
        assert question_bank["question_count"] == len(question_bank["questions"]) == 20
        assert sum(question["total_marks"] for question in question_bank["questions"]) == 115
        assert sum(len(question["parts"]) for question in question_bank["questions"]) == 53
        assert question_bank["questions"][0]["title"] == "Grouped times and probability"

        for code, expected_sections in {"8.1": 1, "8.2": 1, "8.3": 2}.items():
            note_response = client.get(f"/api/v1/subtopics/{code}/notes")
            assert note_response.status_code == 200
            notes = note_response.json()
            assert notes["subtopic_code"] == code
            assert len(notes["sections"]) == expected_sections

        assert client.get("/api/v1/topics/1/questions").status_code == 404

        session_id = None
        try:
            session_response = client.post("/api/v1/learner-sessions")
            assert session_response.status_code == 201
            session_id = session_response.json()["id"]
            part_id = question_bank["questions"][0]["parts"][0]["id"]
            other_part_id = question_bank["questions"][0]["parts"][1]["id"]

            empty_review = client.put(
                f"/api/v1/learner-sessions/{session_id}/responses/{other_part_id}",
                json={"typed_work": "", "status": "ready_for_review"},
            )
            assert empty_review.status_code == 422

            invalid_image = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/attachments",
                files={"image": ("not-an-image.png", b"not an image", "image/png")},
            )
            assert invalid_image.status_code == 422

            saved = client.put(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}",
                json={"typed_work": "P(T > 40) = 18/50 = 0.36", "status": "draft"},
            )
            assert saved.status_code == 200
            assert saved.json()["typed_work"].endswith("0.36")
            assert saved.json()["revision"] == 1

            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
            uploaded = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/attachments",
                files={"image": ("working.png", png, "image/png")},
            )
            assert uploaded.status_code == 201
            attachment = uploaded.json()["attachments"][0]
            assert attachment["media_type"] == "image/png"
            assert attachment["width"] == attachment["height"] == 1

            duplicate = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/attachments",
                files={"image": ("duplicate.png", png, "image/png")},
            )
            assert duplicate.status_code == 201
            assert len(duplicate.json()["attachments"]) == 1

            image = client.get(attachment["content_url"])
            assert image.status_code == 200
            assert image.headers["content-type"] == "image/png"

            ready = client.put(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}",
                json={
                    "typed_work": "P(T > 40) = 18/50 = 0.36",
                    "status": "ready_for_review",
                },
            )
            assert ready.status_code == 200
            assert ready.json()["status"] == "ready_for_review"
            assert ready.json()["revision"] == 2
            assert len(ready.json()["attachments"]) == 1

            restored = client.get(
                f"/api/v1/learner-sessions/{session_id}/responses",
                params={"topic_number": "8"},
            )
            assert restored.status_code == 200
            assert restored.json()["responses"][0]["question_part_id"] == part_id

            removed = client.delete(
                f"/api/v1/learner-sessions/{session_id}/attachments/{attachment['id']}"
            )
            assert removed.status_code == 204
        finally:
            if session_id is not None:
                with psycopg.connect(get_settings().database_url) as cleanup:
                    cleanup.execute(
                        "DELETE FROM learner_sessions WHERE id = %s", (session_id,)
                    )
