"""LLM Provider 元信息路由。"""
from __future__ import annotations

from fastapi import APIRouter

from ..llm import get_router as llm_router

router = APIRouter(prefix="/api", tags=["providers"])


@router.get("/providers")
async def list_providers() -> dict:
    r = llm_router()
    return {"providers": r.list_available(), "default": r.default}
