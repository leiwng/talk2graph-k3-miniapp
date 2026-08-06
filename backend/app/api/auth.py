"""用户认证路由：注册 / 登录 / 登出 / me / refresh / 改密 / 邮箱验证码 / 微信 OAuth。

F.1 阶段：邮箱+密码登录。
P1 V2-F.3：邮箱验证码 + 密码重置链接 + 微信扫码登录。
JWT HS256 + auth_version 失效机制。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import actions, repository as audit_repo
from ..auth import jwt_token, repository as user_repo
from ..auth.deps import CurrentUser, extract_request_meta, get_current_user
from ..auth.password import hash_password, verify_password
from ..auth.verification_codes import (
    consume_reset_token,
    create_reset_token,
    create_verification_code,
    invalidate_all_codes,
    invalidate_all_reset_tokens,
    verify_code,
)
from ..auth.wechat import (
    WechatError,
    build_qrconnect_url,
    exchange_code_for_user,
    gen_state,
)
from ..auth.wechat_miniapp import jscode2session
from ..config import settings
from ..db.models import User
from ..email.provider import EmailMessage, get_email_provider
from ..email.templates import (
    build_reset_url,
    render_password_reset_email,
    render_verification_code_email,
)
from .deps import db_dep

log = logging.getLogger(__name__)
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
    # P1 V2-F.3：邮箱验证状态
    email_verified: bool = False
    wechat_nickname: Optional[str] = None


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
        email_verified=u.email_verified_at is not None,
        wechat_nickname=u.wechat_nickname,
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
    """注册新用户。

    P1 V2-F.3：
    - 用户创建后 status=pending_email_verification（不能 /chat 但能登）
    - 同时发送验证码到邮箱（best-effort）
    - 邮箱已注册但未验证 -> 重发验证码
    """
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")

    existing = await user_repo.get_user_by_email(db, req.email)
    if existing is not None:
        if existing.email_verified_at is None:
            # 未验证 -> 重发验证码
            try:
                code, _ = await create_verification_code(db, req.email, purpose="register")
                provider = get_email_provider()
                subject, html = render_verification_code_email(code, purpose="register")
                await provider.send_best_effort(EmailMessage(to=req.email, subject=subject, html=html))
            except ValueError as e:
                raise HTTPException(status_code=429, detail=str(e)) from None
            # 返回新的 token（让前端能继续验证流程）
            return AuthResp(token=jwt_token.create_access_token(existing), user=_to_user_out(existing))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="该邮箱已注册",
        )

    try:
        user = await user_repo.create_user(
            db,
            email=req.email,
            username=req.username,
            hashed_password=hash_password(req.password),
            role="user",
            status="pending_email_verification",  # P1 V2-F.3：待验证
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="该邮箱已被注册",
        ) from None

    # 发送验证码（best-effort；console provider 不实际发）
    try:
        code, _ = await create_verification_code(db, req.email, purpose="register")
        provider = get_email_provider()
        subject, html = render_verification_code_email(code, purpose="register")
        await provider.send_best_effort(EmailMessage(to=req.email, subject=subject, html=html))
    except ValueError as e:
        log.warning("[auth] send code rate-limited for new user %s: %s", req.email, e)
    except Exception as e:
        log.warning("[auth] send code failed for new user %s: %s", req.email, e)

    ip, ua = extract_request_meta(request)
    await audit_repo.create_audit(
        db,
        actor_id=user.id,
        actor_email=user.email,
        action=actions.AUTH_REGISTER_SUCCESS,
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "email_verified": False},
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

    if user.status == "disabled":
        await _audit_login_fail(db, request, req.email, "disabled")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    # P1 V2-F.3：pending_email_verification 状态能登但 /chat 拒绝（业务层限制）
    # 不在 login 时阻塞，让用户进 UI 后再做验证

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
    if full_user is None or full_user.status == "disabled":
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
    if full_user is None or full_user.status == "disabled":
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
    # 使所有重置令牌失效
    await invalidate_all_reset_tokens(db, full_user.id)

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


# ============================================================================
# P1 V2-F.3：邮箱验证码 + 密码重置 + 微信 OAuth
# ============================================================================


class SendCodeReq(BaseModel):
    email: EmailStr
    purpose: str = Field(default="register", pattern="^(register|reset)$")


class SendCodeResp(BaseModel):
    sent: bool
    message: str


@router.post("/send-verification-code", response_model=SendCodeResp)
async def send_verification_code(req: SendCodeReq, db: AsyncSession = Depends(db_dep)):
    """发送验证码到邮箱（注册 / 重置密码场景）。

    不需要登录。60s 内同一邮箱只能发 1 次。
    """
    try:
        code, _ = await create_verification_code(db, req.email, purpose=req.purpose)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e)) from None

    provider = get_email_provider()
    subject, html = render_verification_code_email(code, purpose=req.purpose)
    sent = await provider.send_best_effort(EmailMessage(to=req.email, subject=subject, html=html))
    return SendCodeResp(
        sent=sent,
        message="验证码已发送" if sent else "验证码发送失败，请稍后重试",
    )


class VerifyEmailReq(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


@router.post("/verify-email", response_model=AuthResp)
async def verify_email(req: VerifyEmailReq, db: AsyncSession = Depends(db_dep)):
    """校验验证码 + 标记邮箱已验证。返回新 token（含 email_verified=true）。"""
    ok = await verify_code(db, req.email, req.code, purpose="register")
    if not ok:
        raise HTTPException(status_code=422, detail="验证码不正确或已过期")

    user = await user_repo.get_user_by_email(db, req.email)
    if user is None:
        # 验证码对但用户不存在 - 不应发生（注册时先建用户再发码）
        raise HTTPException(status_code=404, detail="用户不存在")

    await user_repo.mark_email_verified(db, user)
    await invalidate_all_codes(db, req.email)

    # 颁发新 token（含 email_verified=true）
    return AuthResp(token=jwt_token.create_access_token(user), user=_to_user_out(user))


class ForgotPasswordReq(BaseModel):
    email: EmailStr


@router.post("/forgot-password", response_model=MessageResp)
async def forgot_password(req: ForgotPasswordReq, db: AsyncSession = Depends(db_dep)):
    """忘记密码：生成一次性重置令牌 + 发送重置链接邮件。

    不暴露邮箱是否存在（防探测）。即使邮箱不存在也返回成功。
    """
    user = await user_repo.get_user_by_email(db, req.email)
    if user is None:
        # 防探测：不暴露邮箱是否存在
        return MessageResp(message="如果该邮箱已注册，重置链接已发送")

    if not user.email_verified_at:
        # 邮箱未验证 - 拒绝重置（攻击者可能用别人的邮箱注册）
        return MessageResp(message="如果该邮箱已注册，重置链接已发送")

    token = await create_reset_token(db, user)
    reset_url = build_reset_url(token)
    provider = get_email_provider()
    subject, html = render_password_reset_email(reset_url)
    await provider.send_best_effort(EmailMessage(to=req.email, subject=subject, html=html))

    return MessageResp(message="如果该邮箱已注册，重置链接已发送")


class ResetPasswordReq(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/reset-password", response_model=MessageResp)
async def reset_password(req: ResetPasswordReq, db: AsyncSession = Depends(db_dep)):
    """使用一次性 token 重置密码。"""
    user = await consume_reset_token(db, req.token)
    if user is None:
        raise HTTPException(status_code=422, detail="重置链接无效或已过期")

    await user_repo.update_password(db, user, hash_password(req.new_password))
    # 使所有重置令牌失效（防重放）
    await invalidate_all_reset_tokens(db, user.id)

    return MessageResp(message="密码已重置，请用新密码登录")


class WechatLoginUrlResp(BaseModel):
    url: str
    state: str


@router.get("/wechat/login-url", response_model=WechatLoginUrlResp)
async def wechat_login_url():
    """获取微信扫码登录页 URL（前端打开或弹二维码）。"""
    state = gen_state()
    url = build_qrconnect_url(state)
    return WechatLoginUrlResp(url=url, state=state)


@router.get("/wechat/callback")
async def wechat_callback(code: str, state: str = "", db: AsyncSession = Depends(db_dep)):
    """微信扫码登录回调。

    流程：code -> access_token + 用户信息 -> 找/建用户 -> 颁 JWT -> 重定向前端。
    """
    if not settings.wechat_app_id:
        raise HTTPException(status_code=503, detail="微信登录未配置")

    try:
        wx_user = await exchange_code_for_user(code)
    except WechatError as e:
        log.warning("[auth] wechat oauth failed: %s", e)
        # 重定向前端错误页
        sep = "&" if "?" in settings.wechat_frontend_redirect_url else "?"
        return RedirectResponse(
            f"{settings.wechat_frontend_redirect_url}{sep}error=wechat_oauth_failed",
            status_code=302,
        )

    # 找/建用户
    user = await user_repo.get_user_by_wechat_openid(db, wx_user.openid)
    if user is None:
        # 直接创建新账号（按设计决策：未绑定 openid 时直接创建新账号）
        user = await user_repo.create_wechat_user(
            db,
            openid=wx_user.openid,
            unionid=wx_user.unionid,
            nickname=wx_user.nickname or "微信用户",
            avatar_url=wx_user.headimgurl,
        )

    # 更新 last_login_at
    await user_repo.update_last_login(db, user)

    # 颁 JWT
    token = jwt_token.create_access_token(user)

    # 重定向前端，token 通过 URL 参数传递
    sep = "&" if "?" in settings.wechat_frontend_redirect_url else "?"
    redirect = f"{settings.wechat_frontend_redirect_url}{sep}token={token}"
    return RedirectResponse(redirect, status_code=302)


class WechatMiniappLoginReq(BaseModel):
    code: str = Field(min_length=1)


@router.post("/wechat/miniapp", response_model=AuthResp)
async def wechat_miniapp_login(
    req: WechatMiniappLoginReq, db: AsyncSession = Depends(db_dep)
):
    """微信小程序登录：wx.login 的 code -> openid -> 找/建用户 -> 颁 JWT。

    与扫码回调同策略：未绑定 openid 时直接创建新账号。
    小程序无法获取昵称/头像（2022 后微信回收接口），昵称用占位。
    """
    if not settings.wechat_miniapp_app_id:
        raise HTTPException(status_code=503, detail="微信小程序登录未配置")

    try:
        session = await jscode2session(req.code)
    except WechatError as e:
        log.warning("[auth] wechat miniapp login failed: %s", e)
        raise HTTPException(status_code=502, detail=f"微信登录失败：{e.message}") from None

    user = await user_repo.get_user_by_wechat_openid(db, session.openid)
    if user is None:
        user = await user_repo.create_wechat_user(
            db,
            openid=session.openid,
            unionid=session.unionid,
            nickname=f"微信用户_{session.openid[:6]}",
        )

    await user_repo.update_last_login(db, user)

    token = jwt_token.create_access_token(user)
    return AuthResp(token=token, user=_to_user_out(user))
