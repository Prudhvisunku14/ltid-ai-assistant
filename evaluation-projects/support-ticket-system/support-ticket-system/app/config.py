"""Runtime settings, read from environment variables (optionally a .env file)."""
import os
from dataclasses import dataclass

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_path: str = "data/tickets.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    auto_classify_enabled: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.environ.get("DATABASE_PATH", "data/tickets.db"),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            auto_classify_enabled=_flag("AUTO_CLASSIFY_ENABLED", True),
        )
