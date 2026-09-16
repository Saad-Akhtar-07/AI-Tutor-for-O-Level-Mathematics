from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app import database
from backend.app.routers import tutor
from backend.app.repositories import chat as chat_repository
from backend.app.main import app
from backend.app.schemas.tutor import SocraticReply
from backend.app.services.tutor import TutorChatResult


@pytest.fixture
def learner(monkeypatch):
    test_pool = ConnectionPool(get_settings().database_url, min_size=1, max_size=3,
                               kwargs={"row_factory": dict_row}, open=False)
    monkeypatch.setattr(database, "pool", test_pool)
    monkeypatch.setattr(tutor, "pool", test_pool)
    with TestClient(app) as client:
        session = client.post("/api/v1/learner-sessions").json()["id"]
        part = client.get("/api/v1/topics/8/questions").json()["questions"][0]["parts"][0]["id"]
        try:
            yield client, session, part
        finally:
            with psycopg.connect(get_settings().database_url) as connection:
                connection.execute("DELETE FROM learner_sessions WHERE id = %s", (session,))


def reply(*args):
    return TutorChatResult(SocraticReply(message="Which group has the greatest frequency?",
        teaching_move="ask_question", should_revise_work=False, reveals_final_answer=False), "test", {})


def test_unexpected_failure_is_retryable_and_releases_database(learner, monkeypatch):
    client, session, part = learner
    def fail(*args):
        stats = tutor.pool.get_stats()
        assert stats["pool_available"] == stats["pool_size"]
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr("backend.app.routers.tutor.run_tutor_chat", fail)
    path = f"/api/v1/learner-sessions/{session}/question-parts/{part}/chat-turns"
    payload = {"message": "Help me", "client_message_id": str(uuid4())}
    assert client.post(path, json=payload).status_code == 503
    history = client.get(f"/api/v1/learner-sessions/{session}/chat-turns").json()["turns"]
    assert history[0]["status"] == "failed"
    monkeypatch.setattr("backend.app.routers.tutor.run_tutor_chat", reply)
    retry = client.post(path, json=payload)
    assert retry.status_code == 200
    assert retry.json()["id"] == history[0]["id"]
    assert retry.json()["status"] == "completed"


def test_abandoned_turn_recovers_after_restart(learner, monkeypatch):
    client, session, part = learner
    monkeypatch.setattr("backend.app.routers.tutor.run_tutor_chat", reply)
    path = f"/api/v1/learner-sessions/{session}/question-parts/{part}/chat-turns"
    payload = {"message": "Help me", "client_message_id": str(uuid4())}
    turn = client.post(path, json=payload).json()
    with psycopg.connect(get_settings().database_url) as connection:
        connection.execute("""UPDATE tutor_chat_turns SET status='processing', tutor_message=NULL,
            started_at=NOW()-INTERVAL '3 minutes' WHERE id=%s""", (turn["id"],))
    history = client.get(f"/api/v1/learner-sessions/{session}/chat-turns").json()["turns"]
    assert history[0]["status"] == "failed"
    assert "interrupted" in history[0]["error_message"]
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as connection:
        old_claim = connection.execute("SELECT started_at FROM tutor_chat_turns WHERE id=%s", (turn["id"],)).fetchone()["started_at"]
    retried = client.post(path,json=payload)
    assert retried.status_code == 200
    assert retried.json()["id"] == turn["id"]
    # A late response from the abandoned worker must not overwrite a newer retry.
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as connection:
        assert chat_repository.complete_turn(connection, turn["id"], tutor_message="stale",
            teaching_move="ask_question", should_revise_work=False, actual_model="stale",
            usage={}, claimed_at=old_claim) is None
        chat_repository.fail_turn(connection,turn["id"],"stale","stale",claimed_at=old_claim)
    current = client.get(f"/api/v1/learner-sessions/{session}/chat-turns").json()["turns"][0]
    assert current["status"] == "completed" and current["tutor_message"] != "stale"


def test_simultaneous_duplicate_chat_does_not_duplicate_ai_call(learner, monkeypatch):
    client, session, part = learner
    entered, release = Event(), Event()
    calls = []
    def slow_reply(*args):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return reply()
    monkeypatch.setattr("backend.app.routers.tutor.run_tutor_chat", slow_reply)
    path = f"/api/v1/learner-sessions/{session}/question-parts/{part}/chat-turns"
    payload = {"message": "Help me", "client_message_id": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(client.post, path, json=payload)
        try:
            assert entered.wait(5)
            assert client.post(path, json=payload).status_code == 409
            assert client.get("/api/v1/health").status_code == 200
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
    assert len(calls) == 1
    assert len(client.get(f"/api/v1/learner-sessions/{session}/chat-turns").json()["turns"]) == 1
