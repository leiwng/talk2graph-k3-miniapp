"""异步数据库引擎 / Session 管理。"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..auth.password import hash_password
from ..config import settings
from .migrations import ensure_schema
from .models import ANONYMOUS_USER_ID, Base, User

log = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url, future=True, echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def _bootstrap_anonymous_user(session: AsyncSession) -> None:
    """创建内置 anonymous 用户（幂等）。

    未登录用户创建的会话归属此用户，保留试用体验。
    """
    existing = await session.get(User, ANONYMOUS_USER_ID)
    if existing is not None:
        return
    session.add(
        User(
            id=ANONYMOUS_USER_ID,
            email="anonymous@local",
            username="anonymous",
            # 不可登录：随机密码（bcrypt hash 已是固定随机串；不会有人拿这个邮箱去登录）
            hashed_password=hash_password(uuid.uuid4().hex),
            role="user",
            status="disabled",  # 禁用，禁止匿名用户登录
        )
    )
    await session.commit()
    log.info("[db-bootstrap] created anonymous user %s", ANONYMOUS_USER_ID)


async def _attach_orphan_sessions(session: AsyncSession) -> None:
    """把 user_id IS NULL 的 session 全部归属到 anonymous user（幂等）。"""
    res = await session.execute(
        text("UPDATE session SET user_id = :uid WHERE user_id IS NULL"),
        {"uid": ANONYMOUS_USER_ID},
    )
    if res.rowcount and res.rowcount > 0:
        log.info("[db-bootstrap] attached %d orphan session(s) to anonymous user", res.rowcount)
    await session.commit()


async def _bootstrap_admin(session: AsyncSession) -> None:
    """首次启动且无 admin 时，按 env 创建管理员账号（幂等）。

    生产部署：在 .env 里配置 T2G_BOOTSTRAP_ADMIN_EMAIL + T2G_BOOTSTRAP_ADMIN_PASSWORD，
    启动后该账号可登录进 /api/admin/* 端点。账号创建成功后这两个 env 可删除。
    """
    # 已有 admin 则跳过
    res = await session.execute(
        select(User).where(User.role == "admin").limit(1)
    )
    if res.scalars().first() is not None:
        return

    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if not email or not password:
        # 未配置 bootstrap admin env：跳过（开发期可手动改 DB 加 admin）
        return

    session.add(
        User(
            id=uuid.uuid4().hex,
            email=email,
            username="admin",
            hashed_password=hash_password(password),
            role="admin",
            status="active",
        )
    )
    await session.commit()
    log.info(
        "[db-bootstrap] created bootstrap admin user email=%s (remove env after first login)",
        email,
    )


async def init_db() -> None:
    """开发期：create_all + 自动迁移补列 + bootstrap 用户。生产期同样适用 SQLite。"""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # create_all 不会给已存在表加新列，需要单独走 ensure_schema
    await ensure_schema(_engine)
    # bootstrap：anonymous user + 把 NULL session 归属到 anonymous + 启动 admin
    async with _SessionLocal() as s:
        await _bootstrap_anonymous_user(s)
        await _attach_orphan_sessions(s)
        await _bootstrap_admin(s)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with _SessionLocal() as s:
        yield s


def get_engine():
    return _engine


def override_database_url(url: str) -> None:
    """测试用：在导入前替换 DB URL。"""
    global _engine, _SessionLocal
    _engine = create_async_engine(url, future=True, echo=False)
    _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def get_session_local():
    """获取当前 sessionmaker（用于覆盖 db_dep）。"""
    return _SessionLocal
