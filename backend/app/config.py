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


def _jwt_secret() -> str:
    """JWT HS256 签名密钥。

    生产期必须替换为长随机串（如 `openssl rand -hex 32`）。
    开发期用默认值便于本地启动。
    """
    return os.getenv("T2G_JWT_SECRET", "dev-only-change-in-prod-please-use-32+-chars")


def _jwt_expiry_seconds() -> int:
    return int(os.getenv("T2G_JWT_EXPIRY_SECONDS", "86400"))  # 默认 24h


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
    # V2-F.1：JWT 配置
    jwt_secret: str = field(default_factory=_jwt_secret)
    jwt_expiry_seconds: int = field(default_factory=_jwt_expiry_seconds)
    # V2-F.1：bootstrap admin（首次启动且无 admin 时按 env 创建管理员，账号创建后可删除这两个 env）
    bootstrap_admin_email: str | None = field(
        default_factory=lambda: os.getenv("T2G_BOOTSTRAP_ADMIN_EMAIL") or None
    )
    bootstrap_admin_password: str | None = field(
        default_factory=lambda: os.getenv("T2G_BOOTSTRAP_ADMIN_PASSWORD") or None
    )
    # V2-F.2：Alipay 电脑网站支付
    alipay_app_id: str = field(default_factory=lambda: os.getenv("ALIPAY_APP_ID", ""))
    alipay_app_private_key_file: str = field(
        default_factory=lambda: os.getenv("ALIPAY_APP_PRIVATE_KEY_FILE", "")
    )
    alipay_public_key_file: str = field(
        default_factory=lambda: os.getenv("ALIPAY_PUBLIC_KEY_FILE", "")
    )
    alipay_notify_url: str = field(
        default_factory=lambda: os.getenv(
            "ALIPAY_NOTIFY_URL", "https://t2g.yinhour.com/api/webhooks/alipay"
        )
    )
    alipay_return_url: str = field(
        default_factory=lambda: os.getenv(
            "ALIPAY_RETURN_URL", "https://t2g.yinhour.com/account/subscription"
        )
    )
    alipay_gateway_url: str = field(
        default_factory=lambda: os.getenv(
            "ALIPAY_GATEWAY_URL",
            "https://openapi-sandbox.dl.alipaydev.com/gateway.do",  # 默认沙箱
        )
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
