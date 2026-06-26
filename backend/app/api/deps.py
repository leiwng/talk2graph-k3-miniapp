"""API 共享依赖。"""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_session as _get_db_session
from ..session import repo as repo_mod


async def db_dep() -> AsyncIterator[AsyncSession]:
    async with _get_db_session() as s:
        yield s


async def require_session(db: AsyncSession, sid: str):
    s = await repo_mod.get_session_by_id(db, sid)
    if s is None:
        raise HTTPException(404, detail=f"session not found: {sid}")
    return s
