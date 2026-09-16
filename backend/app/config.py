from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


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
    openrouter_timeout_seconds: float = Field(default=22, gt=0, le=30)
    openrouter_chat_fallback_models: list[str] = Field(default_factory=list)
    openrouter_evaluation_fallback_models: list[str] = Field(default_factory=list)
    openrouter_vision_fallback_models: list[str] = Field(default_factory=list)
    tutor_chat_budget_seconds: float = Field(default=35, gt=0, le=45)
    tutor_review_budget_seconds: float = Field(default=65, gt=0, le=80)
    ai_text_provider: Literal["auto", "groq", "openrouter"] = "auto"
    ai_vision_provider: Literal["auto", "groq", "openrouter"] = "openrouter"
    groq_api_key: str = ""
    groq_chat_model: str = "openai/gpt-oss-20b"
    groq_evaluation_model: str = "openai/gpt-oss-120b"
    groq_vision_model: str = ""

    def requested_text_model(self, stage: Literal["chat", "evaluation"]) -> str:
        if self.groq_api_key and self.ai_text_provider != "openrouter":
            return "groq/" + getattr(self, f"groq_{stage}_model")
        return getattr(self, f"openrouter_{stage}_model")


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
        # Older installations used 90 seconds *per attempt*. Keep their env
        # compatible while enforcing the browser/recovery deadline contract.
        openrouter_timeout_seconds=min(30, float(
            os.getenv("OPENROUTER_TIMEOUT_SECONDS", "22")
        )),
        **{
            f"openrouter_{stage}_fallback_models": list(dict.fromkeys(
                model.strip() for model in os.getenv(
                    f"OPENROUTER_{stage.upper()}_FALLBACK_MODELS", ""
                ).split(",") if model.strip()
            ))[:2]
            for stage in ("chat", "evaluation", "vision")
        },
        tutor_chat_budget_seconds=float(os.getenv("TUTOR_CHAT_BUDGET_SECONDS", "35")),
        tutor_review_budget_seconds=float(os.getenv("TUTOR_REVIEW_BUDGET_SECONDS", "65")),
        ai_text_provider=os.getenv("AI_TEXT_PROVIDER", "auto").strip().lower(),
        ai_vision_provider=os.getenv("AI_VISION_PROVIDER", "openrouter").strip().lower(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_chat_model=os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-20b").strip(),
        groq_evaluation_model=os.getenv("GROQ_EVALUATION_MODEL", "openai/gpt-oss-120b").strip(),
        groq_vision_model=os.getenv("GROQ_VISION_MODEL", "").strip(),
    )
