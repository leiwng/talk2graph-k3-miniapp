"""User 仓储层。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.email == email).limit(1))
    return res.scalars().first()


async def get_user_by_wechat_openid(db: AsyncSession, openid: str) -> Optional[User]:
    """通过微信 openid 查找用户。"""
    res = await db.execute(select(User).where(User.wechat_openid == openid).limit(1))
    return res.scalars().first()


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    hashed_password: str,
    role: str = "user",
    status: str = "active",
) -> User:
    """新建用户。email 唯一约束冲突时由调用方捕获 IntegrityError 转 422。"""
    import uuid

    u = User(
        id=uuid.uuid4().hex,
        email=email,
        username=username,
        hashed_password=hashed_password,
        role=role,
        status=status,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def create_wechat_user(
    db: AsyncSession,
    *,
    openid: str,
    unionid: Optional[str] = None,
    nickname: str,
    avatar_url: Optional[str] = None,
) -> User:
    """新建微信扫码登录用户。

    微信扫码用户没有 email/password（用占位 email 防止 UNIQUE 冲突）。
    """
    import uuid

    # 微信用户 email 占位：wechat_<openid8>@wechat.local
    # （User.email UNIQUE + INDEX，需要非空占位）
    fake_email = f"wechat_{openid[:8]}@wechat.local"
    u = User(
        id=uuid.uuid4().hex,
        email=fake_email,
        username=nickname or f"微信用户_{openid[:6]}",
        hashed_password="!wechat!",  # 不可用密码登录，占位
        role="user",
        status="active",
        wechat_openid=openid,
        wechat_unionid=unionid,
        wechat_nickname=nickname,
        wechat_avatar_url=avatar_url,
        email_verified_at=datetime.now(timezone.utc),  # 微信已实名，视为已验证
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def bind_wechat_to_user(
    db: AsyncSession, user: User, openid: str, unionid: Optional[str] = None,
    nickname: Optional[str] = None, avatar_url: Optional[str] = None,
) -> User:
    """给已存在的用户绑定微信 openid（保留邮箱账号）。"""
    user.wechat_openid = openid
    user.wechat_unionid = unionid
    if nickname:
        user.wechat_nickname = nickname
    if avatar_url:
        user.wechat_avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return user


async def update_password(db: AsyncSession, user: User, new_hashed_password: str) -> None:
    """更新密码 + 重置 password_changed_at（让旧 token 全失效）。"""
    user.hashed_password = new_hashed_password
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)  # 重新加载 updated_at（onupdate 自动改）等字段


async def update_last_login(db: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)  # 同上


async def mark_email_verified(db: AsyncSession, user: User) -> User:
    """标记邮箱已验证。同时把 status 从 pending_email_verification 改为 active。"""
    user.email_verified_at = datetime.now(timezone.utc)
    if user.status == "pending_email_verification":
        user.status = "active"
    await db.commit()
    await db.refresh(user)
    return user


async def count_admins(db: AsyncSession) -> int:
    """统计 admin 角色用户数（用于 bootstrap 判断 + last-admin 保护）。"""
    res = await db.execute(select(User).where(User.role == "admin"))
    return len(res.scalars().all())
