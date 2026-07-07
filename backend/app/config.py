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


def _debug_ui() -> bool:
    return os.getenv("T2G_DEBUG_UI", "false").lower() in ("true", "1", "yes")


def _fallback_providers() -> list[str] | None:
    """从 env 读 fallback chain，逗号分隔。

    留空时由 LLMRouter 自行选前 3 个 enabled provider。
    """
    raw = os.getenv("T2G_FALLBACK_PROVIDERS", "").strip()
    if not raw:
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


@dataclass
class Settings:
    base_dir: Path = _BASE
    data_dir: Path = _BASE / "data"
    log_dir: Path = _BASE / "logs"
    database_url: str = field(default_factory=_db_url)
    default_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_PROVIDER", "zhipu"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: list[str] = field(default_factory=_cors_origins)
    # 生产/调试 UI 切换：false 时前端隐藏 Provider 切换、对象面板等
    debug_ui: bool = field(default_factory=_debug_ui)
    # LLM fallback chain（最多 3 个），None = 自动从 enabled 选前 3
    fallback_providers: list[str] | None = field(default_factory=_fallback_providers)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
