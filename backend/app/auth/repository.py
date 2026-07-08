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


async def count_admins(db: AsyncSession) -> int:
    """统计 admin 角色用户数（用于 bootstrap 判断 + last-admin 保护）。"""
    res = await db.execute(select(User).where(User.role == "admin"))
    return len(res.scalars().all())
