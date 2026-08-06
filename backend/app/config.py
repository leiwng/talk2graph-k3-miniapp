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
    # LLM fallback chain（provider:model 列表，不设上限），None = 自动选全部 enabled
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
    # P1 V2-F.3：邮件（Resend）+ 微信 OAuth + 密码重置
    # 邮件 Provider：resend / smtp / console（默认，开发期不发真实邮件）
    email_provider: str = field(default_factory=lambda: os.getenv("EMAIL_PROVIDER", "console"))
    email_resend_api_key: str = field(
        default_factory=lambda: os.getenv("RESEND_API_KEY", "")
    )
    email_from: str = field(
        default_factory=lambda: os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    )
    # V3.5 SMTP Provider（生产期：腾讯企业邮箱 / 飞书企业邮箱 / 阿里云邮件推送）
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "465")))
    smtp_username: str = field(default_factory=lambda: os.getenv("SMTP_USERNAME", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_use_tls: bool = field(default_factory=lambda: os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"))
    # 密码重置链接基础 URL（前端路由）：默认 /reset-password
    password_reset_base_url: str = field(
        default_factory=lambda: os.getenv("PASSWORD_RESET_BASE_URL", "/reset-password")
    )
    # 微信开放平台 PC 扫码登录（开放平台 - 网站应用）
    wechat_app_id: str = field(default_factory=lambda: os.getenv("WECHAT_APP_ID", ""))
    wechat_app_secret: str = field(default_factory=lambda: os.getenv("WECHAT_APP_SECRET", ""))
    # 微信扫码回调 URL（后端端点 /api/auth/wechat/callback）
    wechat_redirect_uri: str = field(
        default_factory=lambda: os.getenv(
            "WECHAT_REDIRECT_URI",
            "https://t2g.yinhour.com/api/auth/wechat/callback",
        )
    )
    # 微信扫码成功后前端跳转 URL
    wechat_frontend_redirect_url: str = field(
        default_factory=lambda: os.getenv(
            "WECHAT_FRONTEND_REDIRECT_URL",
            "https://t2g.yinhour.com/wechat/callback",
        )
    )
    # 微信小程序登录（小程序 AppID，与开放平台网站应用不同）
    wechat_miniapp_app_id: str = field(
        default_factory=lambda: os.getenv("WECHAT_MINIAPP_APP_ID", "")
    )
    wechat_miniapp_app_secret: str = field(
        default_factory=lambda: os.getenv("WECHAT_MINIAPP_APP_SECRET", "")
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
