"""Settings loaded from environment (.env). See .env.example."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    decision_date: str = os.getenv("DECISION_DATE", "2024-12-31")
    cache_dir: Path = Path(os.getenv("MAID_CACHE_DIR", "data/cache"))


def get_settings() -> Settings:
    return Settings()
