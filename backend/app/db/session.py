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
from .models import Base

_engine = create_async_engine(settings.database_url, future=True, echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """开发期：直接 create_all。生产用 Alembic 迁移。"""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
