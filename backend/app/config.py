"""集中配置（从 env 读取）。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 加载 backend/.env（如果存在）
_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env", override=False)


def _cors_origins() -> list[str]:
    return os.getenv("CORS_ORIGINS", "*").split(",")


def _db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{_BASE / 'data' / 'talk2graph.db'}",
    )


@dataclass
class Settings:
    base_dir: Path = _BASE
    data_dir: Path = _BASE / "data"
    log_dir: Path = _BASE / "logs"
    database_url: str = field(default_factory=_db_url)
    default_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_PROVIDER", "zhipu"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: list[str] = field(default_factory=_cors_origins)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
