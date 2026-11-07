"""Settings loaded from environment (.env). See .env.example."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "ollama"), repr=False)
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen2.5-32k"))
    decision_date: str = field(default_factory=lambda: os.getenv("DECISION_DATE", "2025-03-31"))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("MAID_CACHE_DIR", "data/cache")))
    sec_user_agent: str = field(default_factory=lambda: os.getenv("SEC_USER_AGENT", ""))


def get_settings() -> Settings:
    return Settings()
