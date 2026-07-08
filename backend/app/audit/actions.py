"""审计 action 字符串常量。集中定义避免拼写错误。"""
from __future__ import annotations

# === 认证 ===
AUTH_REGISTER_SUCCESS = "auth.register.success"
AUTH_LOGIN_SUCCESS = "auth.login.success"
AUTH_LOGIN_FAILED = "auth.login.failed"
AUTH_LOGOUT = "auth.logout"
AUTH_PASSWORD_CHANGED = "auth.password.changed"
AUTH_PASSWORD_RESET = "auth.password.reset"  # F.3 接 SMTP 后启用

# === 业务 ===
CHAT_SEND = "chat.send"
SESSION_DELETE = "session.delete"

# === 管理（F.2/F.3 接 admin 操作后启用）===
USER_ADMIN_UPDATE = "user.admin.update"
USER_ADMIN_DISABLE = "user.admin.disable"

# === 付费（F.2 接 Alipay 后启用）===
ORDER_CREATE = "order.create"
ORDER_PAID = "order.paid"
ORDER_CLOSE = "order.close"
