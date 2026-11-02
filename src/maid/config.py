"""Settings loaded from environment (.env). See .env.example."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""), repr=False)
    base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))
    decision_date: str = field(default_factory=lambda: os.getenv("DECISION_DATE", "2025-03-31"))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("MAID_CACHE_DIR", "data/cache")))


def get_settings() -> Settings:
    return Settings()
