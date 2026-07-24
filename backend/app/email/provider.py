"""邮件 Provider 抽象 + Resend / SMTP / Console 实现 + 模板渲染。"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from .. import config as _config

log = logging.getLogger(__name__)


def _settings():
    """动态获取 settings 实例（处理测试 reload(config) 后引用更新的场景）。"""
    return _config.settings


class EmailMessage:
    """简单邮件消息。"""

    def __init__(self, to: str, subject: str, html: str):
        self.to = to
        self.subject = subject
        self.html = html


class EmailProvider(ABC):
    """邮件 Provider 抽象。"""

    name: str = "abstract"

    @abstractmethod
    async def send(self, msg: EmailMessage) -> None:
        """发送邮件。失败抛 EmailSendError。"""
        ...


    async def send_best_effort(self, msg: EmailMessage) -> bool:
        """best-effort 发送：失败仅 warning，返回是否成功。"""
        try:
            await self.send(msg)
            return True
        except Exception as e:
            log.warning(
                "[email] send failed: provider=%s to=%s subject=%s err=%s",
                self.name, msg.to, msg.subject, e,
            )
            return False


class EmailSendError(Exception):
    """邮件发送失败。"""


# ============================================================================
# Resend 实现（开发期）
# ============================================================================


class ResendProvider(EmailProvider):
    """Resend（https://resend.com）：开发期默认 Provider。

    免费额度：3000 封/月，100 封/天。
    需要 RESEND_API_KEY 环境变量。

    发件人地址默认 onboarding@resend.dev（Resend 免费版要求），
    配置 RESEND_FROM_EMAIL 后用配置值。
    """

    name = "resend"
    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    async def send(self, msg: EmailMessage) -> None:
        if not self.api_key:
            raise EmailSendError("RESEND_API_KEY not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.from_email,
                    "to": [msg.to],
                    "subject": msg.subject,
                    "html": msg.html,
                },
            )
            if r.status_code >= 400:
                raise EmailSendError(f"resend api error: {r.status_code} {r.text[:200]}")


# ============================================================================
# 控制台日志 Provider（开发/测试用，不发真实邮件）
# ============================================================================


class ConsoleProvider(EmailProvider):
    """控制台日志 Provider：把邮件内容打到 logger。

    测试和开发期默认用这个，避免误发邮件。
    """

    name = "console"

    async def send(self, msg: EmailMessage) -> None:
        log.info(
            "[email-console] to=%s subject=%s\n%s",
            msg.to, msg.subject, msg.html,
        )


# ============================================================================
# SMTP Provider（生产期：腾讯企业邮箱 / 飞书企业邮箱 / 阿里云邮件推送 等）
# ============================================================================


class SMTPProvider(EmailProvider):
    """通用 SMTP Provider。

    适用于任何标准 SMTP 服务器：
    - 腾讯企业邮箱：smtp.qq.com:465（SSL）或 smtp.exmail.qq.com:465
    - 飞书企业邮箱：smtp.feishu.cn:465（SSL）
    - 阿里云邮件推送：smtpdm.aliyun.com:465（SSL）或 80（STARTTLS）
    - Gmail：smtp.gmail.com:465（SSL）

    使用 stdlib smtplib + asyncio.to_thread 包装为异步，避免引入 aiosmtplib 依赖。
    """

    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    async def send(self, msg: EmailMessage) -> None:
        if not self.host or not self.username or not self.password:
            raise EmailSendError("SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD not configured")

        # 在独立线程跑同步 SMTP 调用，避免阻塞事件循环
        await asyncio.to_thread(self._send_sync, msg)

    def _send_sync(self, msg: EmailMessage) -> None:
        """同步发送邮件。smtplib 不支持 async，用 to_thread 包装。"""
        mime = MIMEMultipart("alternative")
        mime["From"] = self.from_email
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        mime.attach(MIMEText(msg.html, "html", "utf-8"))

        try:
            if self.use_tls:
                # 465 端口：SSL 直连
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=15) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.from_email, [msg.to], mime.as_string())
            else:
                # 587/25 端口：STARTTLS
                with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(self.from_email, [msg.to], mime.as_string())
        except Exception as e:
            raise EmailSendError(f"SMTP send failed: {e}") from e


_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    """获取邮件 Provider 单例。

    优先级按 settings.email_provider：
    - "resend"：ResendProvider（需要 RESEND_API_KEY）
    - "smtp"：SMTPProvider（需要 SMTP_HOST/USERNAME/PASSWORD）
    - "console"（默认）：ConsoleProvider，仅打日志不发邮件
    """
    global _provider
    if _provider is not None:
        return _provider

    s = _settings()
    provider_name = (s.email_provider or "console").lower()

    if provider_name == "resend" and s.email_resend_api_key:
        from_email = s.email_from or "onboarding@resend.dev"
        _provider = ResendProvider(
            api_key=s.email_resend_api_key,
            from_email=from_email,
        )
    elif provider_name == "smtp" and s.smtp_host and s.smtp_username:
        _provider = SMTPProvider(
            host=s.smtp_host,
            port=s.smtp_port,
            username=s.smtp_username,
            password=s.smtp_password,
            from_email=s.email_from or s.smtp_username,
            use_tls=s.smtp_use_tls,
        )
    else:
        _provider = ConsoleProvider()
    return _provider


def set_email_provider(p: EmailProvider | None) -> None:
    """测试用：注入自定义 Provider。"""
    global _provider
    _provider = p
