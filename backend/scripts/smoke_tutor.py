"""Run one disposable, real OpenRouter image-review smoke test."""

from io import BytesIO

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
    session_id = None
    try:
        with TestClient(app) as client:
            bank = client.get("/api/v1/topics/8/questions").json()
            question = next(item for item in bank["questions"] if item["number"] == 5)
            part_id = question["parts"][0]["id"]
            session_id = client.post("/api/v1/learner-sessions").json()["id"]
            upload = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/attachments",
                files={"image": ("smoke-working.png", solution_image(), "image/png")},
            )
            upload.raise_for_status()
            ready = client.put(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}",
                json={"typed_work": "", "status": "ready_for_review"},
            )
            ready.raise_for_status()
            reviewed = client.post(
                f"/api/v1/learner-sessions/{session_id}/responses/{part_id}/reviews",
                json={
                    "expected_revision": ready.json()["revision"],
                    "intent": "check",
                },
            )
            reviewed.raise_for_status()
            result = reviewed.json()
            print(
                "Tutor smoke review passed: "
                f"status={result['status']}, assessment={result['assessment']}, "
                f"marks={result['marks_awarded']}/{result['marks_maximum']}, "
                f"action={result['action']}"
            )
    finally:
        if session_id is not None:
            with psycopg.connect(get_settings().database_url) as connection:
                connection.execute(
                    "DELETE FROM learner_sessions WHERE id = %s", (session_id,)
                )


if __name__ == "__main__":
    main()
