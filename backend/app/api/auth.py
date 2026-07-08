"""用户认证路由：注册 / 登录 / 登出 / me / refresh / 改密。

F.1 阶段：邮箱+密码登录，无邮箱验证码（F.3 接 SMTP 后启用）。
JWT HS256 + auth_version 失效机制。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import actions, repository as audit_repo
from ..auth import jwt_token, repository as user_repo
from ..auth.deps import CurrentUser, extract_request_meta, get_current_user
from ..auth.password import hash_password, verify_password
from .deps import db_dep

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ===================== Pydantic 请求/响应模型 =====================


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    username: str = Field(min_length=1, max_length=100)


class LoginReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ChangePasswordReq(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: str
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime


class AuthResp(BaseModel):
    token: str
    user: UserOut


class MessageResp(BaseModel):
    message: str


# ===================== 工具 =====================


def _to_user_out(u) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        username=u.username,
        role=u.role,
        status=u.status,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


async def _audit_login_fail(
    db: AsyncSession, request: Request, email: str, reason: str
) -> None:
    """登录失败时记审计（best-effort）。"""
    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=None,
        actor_email=email,
        action=actions.AUTH_LOGIN_FAILED,
        metadata={"reason": reason},
        ip_address=ip,
        user_agent=ua,
    )


# ===================== 路由 =====================


@router.post("/register", response_model=AuthResp, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterReq, request: Request, db: AsyncSession = Depends(db_dep)):
    """注册新用户（F.1 不验证邮箱；F.3 接 SMTP 后加验证码步骤）。

    新用户默认 role=user, status=active。
    """
    # 简单邮箱格式二次校验（pydantic EmailStr 已经校验，但 bcrypt 较慢，提前过滤明显错误）
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")

    try:
        user = await user_repo.create_user(
            db,
            email=req.email,
            username=req.username,
            hashed_password=hash_password(req.password),
            role="user",
            status="active",
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="该邮箱已被注册",
        ) from None

    # 审计：注册成功
    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=user.id,
        actor_email=user.email,
        action=actions.AUTH_REGISTER_SUCCESS,
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email},
        ip_address=ip,
        user_agent=ua,
    )

    token = jwt_token.create_access_token(user)
    return AuthResp(token=token, user=_to_user_out(user))


@router.post("/login", response_model=AuthResp)
async def login(req: LoginReq, request: Request, db: AsyncSession = Depends(db_dep)):
    """邮箱+密码登录。"""
    user = await user_repo.get_user_by_email(db, req.email)

    if user is None:
        await _audit_login_fail(db, request, req.email, "user_not_found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")

    if not verify_password(req.password, user.hashed_password):
        await _audit_login_fail(db, request, req.email, "invalid_password")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")

    if user.status != "active":
        await _audit_login_fail(db, request, req.email, "disabled")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    # 登录成功：更新 last_login_at + 写审计
    await user_repo.update_last_login(db, user)
    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=user.id,
        actor_email=user.email,
        action=actions.AUTH_LOGIN_SUCCESS,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    token = jwt_token.create_access_token(user)
    return AuthResp(token=token, user=_to_user_out(user))


@router.post("/logout", response_model=MessageResp)
async def logout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
):
    """登出。客户端清 token；服务端记审计（best-effort）。"""
    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=user.id,
        actor_email=user.email,
        action=actions.AUTH_LOGOUT,
        ip_address=ip,
        user_agent=ua,
    )
    return MessageResp(message="已登出")


@router.get("/me", response_model=UserOut)
async def me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
):
    """返回当前登录用户信息（不含订阅/配额；F.2 加 entitlement 字段）。"""
    full_user = await user_repo.get_user_by_id(db, user.id)
    if full_user is None or full_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用"
        )
    return _to_user_out(full_user)


@router.post("/refresh", response_model=AuthResp)
async def refresh(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
):
    """用旧 token 换新 token（重置 24h 过期）。auth_version 不变才能换。"""
    full_user = await user_repo.get_user_by_id(db, user.id)
    if full_user is None or full_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用"
        )
    token = jwt_token.create_access_token(full_user)
    return AuthResp(token=token, user=_to_user_out(full_user))


@router.post("/change-password", response_model=MessageResp)
async def change_password(
    req: ChangePasswordReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
):
    """改密。改完后 password_changed_at 更新，旧 token 全失效。"""
    full_user = await user_repo.get_user_by_id(db, user.id)
    if full_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录"
        )

    if not verify_password(req.old_password, full_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="旧密码不正确"
        )

    await user_repo.update_password(db, full_user, hash_password(req.new_password))

    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=user.id,
        actor_email=user.email,
        action=actions.AUTH_PASSWORD_CHANGED,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    return MessageResp(message="密码已修改，请重新登录")
