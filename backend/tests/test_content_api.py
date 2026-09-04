import base64
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.schemas.tutor import EvaluationResult, SocraticReply, VisionTranscription
from backend.app.services.openrouter import OpenRouterError
from backend.app.services.tutor import TutorChatResult, TutorModelResult


def test_probability_content_contract(monkeypatch) -> None:
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
        first_part = question_bank["questions"][0]["parts"][0]
        assert "mark_scheme" not in first_part
        solution = client.get(f"/api/v1/question-parts/{first_part['id']}/solution")
        assert solution.status_code == 200
        assert solution.json()["question_part_id"] == first_part["id"]
        assert solution.json()["answer"]

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
            assert ready.json()["revision"] == 3
            assert len(ready.json()["attachments"]) == 1

            model_calls = []

            def fake_tutor_models(settings, snapshot, images):
                model_calls.append({"snapshot": snapshot, "images": images})
                return TutorModelResult(
                    vision=VisionTranscription(
                        transcription="P(T > 40) = 18/50 = 0.36",
                        readability="clear",
                        uncertain_fragments=[],
                    ),
                    evaluation=EvaluationResult(
                        assessment="partial",
                        marks_awarded=0,
                        readability="clear",
                        observed_work="P(T > 40) = 18/50 = 0.36",
                        criteria=[],
                        primary_error=None,
                        positive_observation="You wrote a complete probability calculation.",
                        guiding_question="Which interval does this part ask you to identify?",
                        next_step_hint="Compare the frequencies to find the modal interval.",
                        confidence=0.95,
                    ),
                    actual_vision_model="test-vision",
                    actual_evaluation_model="test-evaluator",
                    usage={"vision": {}, "evaluation": {}},
                )

            monkeypatch.setattr(
                "backend.app.routers.tutor.run_tutor_models", fake_tutor_models
            )
            reviewed = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/reviews",
                json={"expected_revision": 3, "intent": "check"},
            )
            assert reviewed.status_code == 200
            assert reviewed.json()["status"] == "completed"
            assert reviewed.json()["hint_level"] == 1
            assert reviewed.json()["marks_maximum"] == first_part["marks"]
            assert len(model_calls) == 1
            assert len(model_calls[0]["images"]) == 1
            assert model_calls[0]["snapshot"]["mark_scheme"]["answer"]

            duplicate_review = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/reviews",
                json={"expected_revision": 3, "intent": "check"},
            )
            assert duplicate_review.status_code == 200
            assert duplicate_review.json()["id"] == reviewed.json()["id"]
            assert len(model_calls) == 1

            history = client.get(
                f"/api/v1/learner-sessions/{session_id}/reviews",
                params={"topic_number": "8"},
            )
            assert history.status_code == 200
            assert history.json()["reviews"][0]["feedback"]

            chat_calls = []

            def fake_tutor_chat(settings, snapshot, learner_message):
                chat_calls.append(
                    {"snapshot": snapshot, "learner_message": learner_message}
                )
                return TutorChatResult(
                    reply=SocraticReply(
                        message=(
                            "Start with the denominator: how many counters are "
                            "available before the first draw?"
                        ),
                        teaching_move="ask_question",
                        should_revise_work=True,
                        reveals_final_answer=False,
                    ),
                    actual_model="test-chat-model",
                    usage={},
                )

            monkeypatch.setattr(
                "backend.app.routers.tutor.run_tutor_chat", fake_tutor_chat
            )
            chat_message_id = uuid4()
            chatted = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={
                    "client_message_id": str(chat_message_id),
                    "message": "I do not know how to begin.",
                },
            )
            assert chatted.status_code == 200
            assert chatted.json()["status"] == "completed"
            assert chatted.json()["response_revision"] is None
            assert chatted.json()["teaching_move"] == "ask_question"
            assert len(chat_calls) == 1
            assert chat_calls[0]["snapshot"]["learner_work"]["typed_work"] == ""
            assert chat_calls[0]["snapshot"]["private_mark_scheme"]["answer"]

            duplicate_chat = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={
                    "client_message_id": str(chat_message_id),
                    "message": "I do not know how to begin.",
                },
            )
            assert duplicate_chat.status_code == 200
            assert duplicate_chat.json()["id"] == chatted.json()["id"]
            assert len(chat_calls) == 1

            follow_up = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={
                    "client_message_id": str(uuid4()),
                    "message": "Should I count all of the counters?",
                },
            )
            assert follow_up.status_code == 200
            assert len(chat_calls) == 2
            assert chat_calls[1]["snapshot"]["conversation"] == [{
                "learner": "I do not know how to begin.",
                "tutor": chatted.json()["tutor_message"],
            }]

            chat_history = client.get(
                f"/api/v1/learner-sessions/{session_id}/chat-turns",
                params={"topic_number": "8"},
            )
            assert chat_history.status_code == 200
            assert len(chat_history.json()["turns"]) == 2

            def unavailable_tutor_chat(settings, snapshot, learner_message):
                raise OpenRouterError("temporary test outage", code="provider_error")

            monkeypatch.setattr(
                "backend.app.routers.tutor.run_tutor_chat", unavailable_tutor_chat
            )
            retry_message_id = uuid4()
            failed_chat = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={
                    "client_message_id": str(retry_message_id),
                    "message": "Can we try a smaller step?",
                },
            )
            assert failed_chat.status_code == 503

            monkeypatch.setattr(
                "backend.app.routers.tutor.run_tutor_chat", fake_tutor_chat
            )
            retried_chat = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={
                    "client_message_id": str(retry_message_id),
                    "message": "Can we try a smaller step?",
                },
            )
            assert retried_chat.status_code == 200
            assert retried_chat.json()["status"] == "completed"
            assert retried_chat.json()["client_message_id"] == str(retry_message_id)

            blank_chat = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/"
                f"{other_part_id}/chat-turns",
                json={"client_message_id": str(uuid4()), "message": "   "},
            )
            assert blank_chat.status_code == 422

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
