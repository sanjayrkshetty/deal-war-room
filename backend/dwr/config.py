"""Environment-backed settings (`dwr/config.py`).

All external touchpoints are env-pinned: DB path, Groq key, model IDs
(Groq rotates model names — never hardcode them in pipeline code).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_db_path() -> Path:
    env_path = os.environ.get("DWR_DB_PATH")
    if env_path:
        return Path(env_path)
    # Default outside OneDrive-synced trees: %LOCALAPPDATA%\dwr\dwr.db
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return root / "dwr" / "dwr.db"


class Settings(BaseSettings):
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    db_path: Path = Field(default_factory=_default_db_path)
    model_triage: str = Field(default="llama-3.1-8b-instant", alias="DWR_MODEL_TRIAGE")
    model_synthesis: str = Field(
        default="llama-3.3-70b-versatile", alias="DWR_MODEL_SYNTH"
    )

    model_config = {"populate_by_name": True, "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
