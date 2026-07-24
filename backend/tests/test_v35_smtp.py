"""V3.5 SMTPProvider 测试（3 个）。

不实际发邮件，只验证：
- Provider 选择逻辑（email_provider=smtp 时返回 SMTPProvider）
- 配置缺失时回退到 ConsoleProvider
- SMTPProvider._send_sync 在凭据缺失时抛 EmailSendError
"""
from __future__ import annotations

import pytest

from app.email.provider import (
    ConsoleProvider,
    EmailMessage,
    EmailProvider,
    EmailSendError,
    ResendProvider,
    SMTPProvider,
    get_email_provider,
    set_email_provider,
)


@pytest.fixture(autouse=True)
def _reset_email_provider(monkeypatch):
    """每个测试前清空 _provider 缓存 + 重置 settings 为 console，避免被其他测试残留影响。

    处理 test_v2f_auth.test_bootstrap_admin_on_first_startup reload(config_mod) 后
    settings 实例变更的问题：动态 import 拿最新 settings。
    """
    import importlib
    from app import config as config_mod
    importlib.reload(config_mod)
    settings = config_mod.settings
    monkeypatch.setattr(settings, "email_provider", "console")
    monkeypatch.setattr(settings, "email_resend_api_key", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_username", "")
    set_email_provider(None)
    yield
    set_email_provider(None)


def test_smtp_provider_init():
    """SMTPProvider 能正确初始化。"""
    p = SMTPProvider(
        host="smtp.feishu.cn",
        port=465,
        username="noreply@example.com",
        password="app-password",
        from_email="noreply@example.com",
        use_tls=True,
    )
    assert p.name == "smtp"
    assert p.host == "smtp.feishu.cn"
    assert p.port == 465


def test_get_email_provider_returns_smtp_when_configured(monkeypatch):
    """EMAIL_PROVIDER=smtp + 配置完整时返回 SMTPProvider。"""
    import importlib
    from app import config as config_mod
    importlib.reload(config_mod)
    settings = config_mod.settings
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.feishu.cn")
    monkeypatch.setattr(settings, "smtp_port", 465)
    monkeypatch.setattr(settings, "smtp_username", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_use_tls", True)

    set_email_provider(None)  # 清缓存
    p = get_email_provider()
    assert isinstance(p, SMTPProvider)
    set_email_provider(None)  # 清缓存恢复


def test_get_email_provider_fallback_to_console_when_smtp_misconfigured(monkeypatch):
    """EMAIL_PROVIDER=smtp 但 SMTP_HOST 缺失时回退到 ConsoleProvider。"""
    import importlib
    from app import config as config_mod
    importlib.reload(config_mod)
    settings = config_mod.settings
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "")  # 缺失
    monkeypatch.setattr(settings, "smtp_username", "")

    set_email_provider(None)
    p = get_email_provider()
    assert isinstance(p, ConsoleProvider)
    set_email_provider(None)


@pytest.mark.asyncio
async def test_smtp_send_raises_when_credentials_missing():
    """SMTPProvider 凭据缺失时 send 抛 EmailSendError。"""
    p = SMTPProvider(
        host="",  # 缺失
        port=465,
        username="",
        password="",
        from_email="noreply@example.com",
        use_tls=True,
    )
    msg = EmailMessage(to="user@example.com", subject="test", html="<p>hi</p>")
    with pytest.raises(EmailSendError):
        await p.send(msg)
