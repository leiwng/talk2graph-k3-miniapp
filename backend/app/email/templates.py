"""邮件模板渲染。

简单字符串模板（不引入 jinja2）。两套：
1. 验证码邮件
2. 密码重置链接邮件
"""
from __future__ import annotations

from ..config import settings


def render_verification_code_email(code: str, purpose: str = "register") -> tuple[str, str]:
    """渲染验证码邮件。返回 (subject, html)。

    purpose: register（注册验证）/ reset（重置密码验证）
    """
    if purpose == "reset":
        subject = "【话图 T2G】您的密码重置验证码"
        title = "密码重置验证码"
        body = "您正在重置密码。请使用以下验证码完成操作："
    else:
        subject = "【话图 T2G】您的注册验证码"
        title = "邮箱验证码"
        body = "您正在注册话图 T2G。请使用以下验证码完成邮箱验证："

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<body style="font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; color: #0f172a; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #3b82f6; margin: 0 0 8px;">话图 T2G</h2>
  <p style="color: #475569; font-size: 14px; margin: 0 0 24px;">{title}</p>
  <p style="font-size: 14px; line-height: 1.6;">{body}</p>
  <div style="text-align: center; margin: 24px 0; padding: 16px; background: #dbeafe; border-radius: 8px;">
    <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #3b82f6; font-family: 'SF Mono', Menlo, monospace;">{code}</span>
  </div>
  <p style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
    验证码 15 分钟内有效。<br/>
    如果不是您本人操作，请忽略此邮件。
  </p>
</body>
</html>"""
    return subject, html


def render_password_reset_email(reset_url: str) -> tuple[str, str]:
    """渲染密码重置链接邮件。返回 (subject, html)。"""
    subject = "【话图 T2G】重置您的密码"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<body style="font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; color: #0f172a; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #3b82f6; margin: 0 0 8px;">话图 T2G</h2>
  <p style="color: #475569; font-size: 14px; margin: 0 0 24px;">密码重置</p>
  <p style="font-size: 14px; line-height: 1.6;">您正在重置密码。请点击下方按钮完成操作：</p>
  <div style="text-align: center; margin: 24px 0;">
    <a href="{reset_url}" style="display: inline-block; padding: 10px 24px; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500;">重置密码</a>
  </div>
  <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; word-break: break-all;">
    或复制以下链接到浏览器：<br/>
    <a href="{reset_url}" style="color: #3b82f6;">{reset_url}</a>
  </p>
  <p style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
    链接 30 分钟内有效。<br/>
    如果不是您本人操作，请忽略此邮件。
  </p>
</body>
</html>"""
    return subject, html


def build_reset_url(token: str) -> str:
    """构造前端密码重置链接。"""
    base = settings.password_reset_base_url or "/reset-password"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}token={token}"
