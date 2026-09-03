from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


class Settings(BaseModel):
    database_url: str
    cors_origins: list[str]


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
    return Settings(database_url=database_url, cors_origins=origins)
