"""异步数据库引擎 / Session 管理。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from .migrations import ensure_schema
from .models import Base

_engine = create_async_engine(settings.database_url, future=True, echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """开发期：create_all + 自动迁移补列。生产期同样适用 SQLite。"""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # create_all 不会给已存在表加新列，需要单独走 ensure_schema
    await ensure_schema(_engine)


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
