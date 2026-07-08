"""JWT HS256 token 签发与校验。

借鉴 Lumiton api/jwt_auth.py 的 auth_version 失效机制：
- payload 含 auth_version claim（从 user.password_changed_at || updated_at || created_at 派生）
- 改密后 password_changed_at 更新 → auth_version 变化 → 旧 token validate 失败
- 不需要维护 token 黑名单
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import jwt

from ..config import settings
from ..db.models import User

ALGORITHM = "HS256"


def _to_unix_ts(dt: datetime | None) -> int:
    """datetime → unix timestamp（None 视为 0）。"""
    if dt is None:
        return 0
    if dt.tzinfo is None:
        # SQLAlchemy 默认返回 naive datetime（按 server local time 解释）
        return int(dt.replace(tzinfo=timezone.utc).astimezone(timezone.utc).timestamp())
    return int(dt.astimezone(timezone.utc).timestamp())


def auth_version(user: User) -> str:
    """从 user 派生 auth_version 字符串。

    改密时 password_changed_at 更新 → auth_version 变 → 旧 token 失效。
    """
    # 优先级：password_changed_at > updated_at > created_at
    base = user.password_changed_at or user.updated_at or user.created_at
    return str(_to_unix_ts(base))


def create_access_token(user: User) -> str:
    """签发 JWT。"""
    now = int(datetime.now(timezone.utc).timestamp())
    payload: dict[str, Any] = {
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "auth_version": auth_version(user),
        "iat": now,
        "exp": now + settings.jwt_expiry_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


class TokenError(Exception):
    """JWT 校验失败统一异常。"""


class TokenExpiredError(TokenError):
    """token 已过期。"""


class TokenInvalidError(TokenError):
    """签名无效 / payload 不合法 / auth_version 不匹配。"""


def decode_token(token: str, expected_auth_version: str | None = None) -> dict[str, Any]:
    """解码 + 验签 + 验过期。

    expected_auth_version: 若传入则比对 payload 中的 auth_version，不匹配抛 TokenInvalidError
    （用于 get_current_user 在 DB 查到 user 后做最终校验）
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"invalid token: {e}") from e

    if expected_auth_version is not None:
        if payload.get("auth_version") != expected_auth_version:
            raise TokenInvalidError("auth_version mismatch (password changed?)")
    return payload


def decode_token_unsafe(token: str) -> Mapping[str, Any] | None:
    """解码不抛异常；用于 BestCase 场景（如 logger 提取 user_id）。
    失败返回 None。
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_exp": False, "require": ["sub"]},
        )
    except jwt.InvalidTokenError:
        return None
