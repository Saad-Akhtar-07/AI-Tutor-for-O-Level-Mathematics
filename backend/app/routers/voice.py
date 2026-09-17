from typing import Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import database
from ..repositories.submissions import session_exists
from ..services import speech, transcription
from ..services.voice_admission import admit

router = APIRouter(prefix="/api/v1/learner-sessions/{session_id}/voice", tags=["Voice"])


class SpeechRequest(BaseModel):
    source_type: Literal["chat", "review"]
    source_id: UUID
    voice: Literal["af_heart", "bf_emma"] = "af_heart"
    segment: int = Field(default=0, ge=0, le=100)


def public_source(session_id: UUID, request: SpeechRequest) -> str:
    table, field = ("tutor_chat_turns", "tutor_message") if request.source_type == "chat" else ("tutor_reviews", "feedback")
    # Table and field come only from the fixed allowlist above. No private snapshot.
    with database.pool.connection() as connection:
        row = connection.execute(f"SELECT {field} AS text FROM {table} WHERE id=%s AND learner_session_id=%s AND status='completed'",
                                 (request.source_id, session_id)).fetchone()
    if not row or not row["text"]:
        raise HTTPException(404, "Completed tutor reply not found in this session.")
    return row["text"]


@router.post("/transcriptions")
def transcribe(session_id: UUID, recording: UploadFile = File(...), question_part_id: str = Form(..., max_length=200), accurate: bool = Form(False)):
    try:
        with database.pool.connection() as connection:
            if not session_exists(connection, session_id):
                raise HTTPException(404, "Learner session not found")
            if not connection.execute("SELECT id FROM question_parts WHERE id=%s", (question_part_id,)).fetchone():
                raise HTTPException(404, "Question part not found")
        data = recording.file.read(transcription.MAX_BYTES + 1)
        admit(session_id, 'transcription')
        return transcription.transcribe(data, accurate)
    finally:
        recording.file.close()


@router.post("/prepare")
def prepare(session_id: UUID, request: SpeechRequest):
    text = public_source(session_id, request)
    admit(session_id, 'speech')
    return speech.prepare(text)


@router.post("/speech")
def read_aloud(session_id: UUID, request: SpeechRequest):
    text = public_source(session_id, request)
    admit(session_id, 'speech')
    segments = speech.prepare(text)["segments"]
    if request.segment >= len(segments):
        raise HTTPException(422, "Speech segment not found")
    audio = speech.synthesize(session_id, request.source_id, segments[request.segment], request.voice)
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
