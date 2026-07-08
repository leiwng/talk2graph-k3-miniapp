"""审计日志查询（admin only）。

写入逻辑在 audit/repository.py，路由内显式调用 audit_repo.create_audit / fire_and_forget。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import CurrentUser, require_admin
from ..audit import repository as audit_repo
from .deps import db_dep

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


class AuditLogOut(BaseModel):
    id: int
    actor_id: Optional[str]
    actor_email: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    metadata: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


class AuditLogListResp(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


@router.get("", response_model=AuditLogListResp)
async def list_audit_logs(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(db_dep),
):
    """分页查询审计日志（仅 admin）。"""
    rows, total = await audit_repo.list_logs(
        db,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    import json

    items = []
    for r in rows:
        meta = None
        if r.metadata_json:
            try:
                meta = json.loads(r.metadata_json)
            except Exception:
                meta = None
        items.append(
            AuditLogOut(
                id=r.id,
                actor_id=r.actor_id,
                actor_email=r.actor_email,
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                metadata=meta,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                created_at=r.created_at,
            )
        )
    return AuditLogListResp(items=items, total=total, limit=limit, offset=offset)
