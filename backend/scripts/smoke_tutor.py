"""Run disposable real-provider review/chat checks; never use real student work."""

import argparse
from io import BytesIO
from time import monotonic
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import psycopg

from backend.app.config import get_settings
from backend.app.main import app


def solution_image() -> bytes:
    image = Image.new("RGB", (1400, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=52)
    draw.text((55, 70), "There are no green pencils.", fill="black", font=font)
    draw.text((55, 180), "P(green) = 0 / 22 = 0", fill="black", font=font)
    draw.text((55, 300), "Answer: 0", fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-only", action="store_true", help="Skip image transcription")
    args = parser.parse_args()
    session_id = None
    try:
        with TestClient(app) as client:
            bank = client.get("/api/v1/topics/8/questions").json()
            question = next(item for item in bank["questions"] if item["number"] == 5)
            part_id = question["parts"][0]["id"]
            session_id = client.post("/api/v1/learner-sessions").json()["id"]
            if not args.text_only:
                upload = client.post(
                    f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/attachments",
                    files={"image": ("smoke-working.png", solution_image(), "image/png")},
                )
                upload.raise_for_status()
            ready = client.put(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}",
                json={"typed_work": "P(green) = 0 / 22 = 0" if args.text_only else "", "status": "ready_for_review"},
            )
            ready.raise_for_status()
            started = monotonic()
            reviewed = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/reviews",
                json={
                    "expected_revision": ready.json()["revision"],
                    "intent": "check",
                },
            )
            reviewed.raise_for_status()
            result = reviewed.json()
            assert result["status"] == "completed" and result["assessment"] == "correct", "Synthetic correct answer was not assessed correctly"
            assert result["marks_awarded"] == result["marks_maximum"] == 1
            print(
                "Tutor smoke review passed: "
                f"status={result['status']}, assessment={result['assessment']}, "
                f"marks={result['marks_awarded']}/{result['marks_maximum']}, "
                f"action={result['action']}, elapsed={monotonic() - started:.2f}s",
                flush=True,
            )
            started = monotonic()
            chat = client.post(
                f"/api/v1/learner-sessions/{session_id}/question-parts/{part_id}/chat-turns",
                json={"client_message_id": str(uuid4()), "message": "How can I recognise an impossible event?"},
            )
            chat.raise_for_status()
            assert chat.json()["status"] == "completed" and chat.json()["tutor_message"]
            print(f"Tutor smoke chat passed: elapsed={monotonic() - started:.2f}s", flush=True)
    finally:
        if session_id is not None:
            with psycopg.connect(get_settings().database_url) as connection:
                connection.execute(
                    "DELETE FROM learner_sessions WHERE id = %s", (session_id,)
                )


if __name__ == "__main__":
    main()
