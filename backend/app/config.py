from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(BACKEND_ROOT.parent / ".env")


class Settings(BaseModel):
    database_url: str
    cors_origins: list[str]
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_vision_model: str
    openrouter_evaluation_model: str
    openrouter_chat_model: str
    openrouter_data_collection: str
    openrouter_timeout_seconds: float


@lru_cache
def get_settings() -> Settings:
    import os

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Run `scripts/setup_database.py` with the "
            "backend virtual environment or add it to backend/.env."
        )

    origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]
    data_collection = os.getenv("OPENROUTER_DATA_COLLECTION", "deny").strip().lower()
    if data_collection not in {"allow", "deny"}:
        raise RuntimeError(
            "OPENROUTER_DATA_COLLECTION must be either 'allow' or 'deny'."
        )

    return Settings(
        database_url=database_url,
        cors_origins=origins,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
        ).strip(),
        openrouter_vision_model=os.getenv(
            "OPENROUTER_VISION_MODEL", "openrouter/free"
        ).strip(),
        openrouter_evaluation_model=os.getenv(
            "OPENROUTER_EVALUATION_MODEL", "openrouter/free"
        ).strip(),
        openrouter_chat_model=os.getenv(
            "OPENROUTER_CHAT_MODEL",
            os.getenv("OPENROUTER_EVALUATION_MODEL", "openrouter/free"),
        ).strip(),
        openrouter_data_collection=data_collection,
        openrouter_timeout_seconds=float(
            os.getenv("OPENROUTER_TIMEOUT_SECONDS", "90")
        ),
    )
