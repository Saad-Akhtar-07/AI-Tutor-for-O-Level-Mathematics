"""
config.py – centralised configuration for the note-parser pipeline.

All settings are read from environment variables (populated via .env).
No secrets are hard-coded here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file:
#   scripts/note_parser/config.py → scripts/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


# ── API ───────────────────────────────────────────────────────────────────────

OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# Model can be overridden via env; falls back to the agreed default.
OPENROUTER_MODEL: str = os.environ.get("OPENROUTER_MODEL", "stealth/ox-alpha")


# ── PDF rendering ─────────────────────────────────────────────────────────────

# Scale factor when rasterising PDF pages (higher = sharper for small maths).
PDF_RENDER_SCALE: float = float(os.environ.get("PDF_RENDER_SCALE", "2.5"))


# ── Retry behaviour ───────────────────────────────────────────────────────────

MAX_RETRIES: int = 3
RETRY_BASE_SECONDS: float = 2.0   # doubles each attempt: 2 s → 4 s → 8 s


# ── Paths ─────────────────────────────────────────────────────────────────────

NOTES_DATA_DIR: Path = _PROJECT_ROOT / "Notes_data"
PARSED_NOTES_DIR: Path = _PROJECT_ROOT / "parsed_notes"


# ── Schema version (bump this if the JSON format changes) ─────────────────────

SCHEMA_VERSION: str = "1.0"
