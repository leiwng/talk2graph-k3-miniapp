"""鉴权依赖：CurrentUser 模型 + get_current_user + require_admin。

借鉴 Lumiton api/auth.py，但精简掉 4 模式（none/password/jwt/auto），只保留 JWT 模式。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import db_dep
from . import jwt_token, repository
from .jwt_token import TokenError


class CurrentUser(BaseModel):
    """解码后的当前用户（不包含敏感字段）。"""

    id: str
    email: str
    username: str
    role: str  # 'user' | 'admin'
    status: str  # 'active' | 'disabled'
    auth_version: str


# ===================== Request 元信息（audit 用） =====================


def extract_request_meta(request: Request) -> tuple[Optional[str], Optional[str]]:
    """提取 (ip, user_agent)。审计日志用。"""
    # 优先取 X-Forwarded-For（反向代理场景），fallback 到 client.host
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


# ===================== 鉴权 Depends =====================


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(db_dep),
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """从 Authorization: Bearer <token> 提取并校验当前用户。

    401 触发条件：
      - 无 Authorization header
      - 格式不是 Bearer
      - token 解码失败（签名错误/过期）
      - DB 中查不到该用户
      - user.status != 'active'
      - auth_version 不匹配（用户改密后旧 token 失效）
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    forbidden_error = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="账号已被禁用",
    )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise credentials_error
    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = jwt_token.decode_token(token)
    except TokenError:
        raise credentials_error from None

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = await repository.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_error

    if user.status != "active":
        raise forbidden_error

    # auth_version 校验（改密后旧 token 失效）
    expected = jwt_token.auth_version(user)
    if payload.get("auth_version") != expected:
        raise credentials_error

    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        status=user.status,
        auth_version=expected,
    )


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(db_dep),
    authorization: Optional[str] = Header(None),
) -> Optional[CurrentUser]:
    """可选鉴权：有 token 则校验，无 token 返回 None。

    用于"未登录也能用，但登录后走归属"的端点（如 session POST/GET）。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt_token.decode_token(token)
    except TokenError:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = await repository.get_user_by_id(db, user_id)
    if user is None or user.status != "active":
        return None
    expected = jwt_token.auth_version(user)
    if payload.get("auth_version") != expected:
        return None
    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        status=user.status,
        auth_version=expected,
    )


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求当前用户是 admin。"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
