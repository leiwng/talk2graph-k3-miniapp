"""审计日志仓储层。

写入走两条路径：
- `create_audit(db, ...)`: 同步等待，用于重要事件（登录/登出/改密）。失败仅 logger.warning。
- `fire_and_forget(...)`: 异步任务，用于高频事件（chat.send）。开独立 session 不影响请求。

借鉴 Lumiton AuditLogRepository 的 best-effort 模式：审计永不阻塞主流程。
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLog

log = logging.getLogger(__name__)


async def create_audit(
    db: AsyncSession,
    *,
    actor_id: Optional[str],
    actor_email: Optional[str],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """同步写一条审计日志。失败仅 warning，不抛异常。"""
    try:
        entry = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        log.warning("[audit] failed to write: action=%s actor=%s err=%s", action, actor_id, e)
        # 不 re-raise，主流程继续


async def list_logs(
    db: AsyncSession,
    *,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """分页查询审计日志（admin 用）。返回 (rows, total)。"""
    stmt = select(AuditLog)
    count_stmt = select(AuditLog.id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
        count_stmt = count_stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
        count_stmt = count_stmt.where(AuditLog.target_id == target_id)
    if start:
        stmt = stmt.where(AuditLog.created_at >= start)
        count_stmt = count_stmt.where(AuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AuditLog.created_at <= end)
        count_stmt = count_stmt.where(AuditLog.created_at <= end)

    # 用 func.count() 单独查总数（select 结果集的 rowcount 不可靠）
    count_select = select(func.count()).select_from(count_stmt.subquery())
    total_res = await db.execute(count_select)
    total = total_res.scalar() or 0

    stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    return rows, total


async def _fire_and_forget_inner(
    action: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    target_type: Optional[str],
    target_id: Optional[str],
    metadata: Optional[dict[str, Any]],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    """开独立 session 写审计。fire-and-forget 模式，不阻塞请求。"""
    # 局部 import 避免循环依赖（session.py 与本模块互相引用）
    from ..db.session import get_session

    try:
        async with get_session() as db:
            await create_audit(
                db,
                actor_id=actor_id,
                actor_email=actor_email,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )
    except Exception as e:
        log.warning("[audit] fire-and-forget failed: action=%s err=%s", action, e)


def fire_and_forget(
    action: str,
    *,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> asyncio.Task:
    """调度一个后台任务写审计。立即返回，不阻塞调用者。

    用于 chat.send 等高频事件。注意：路由返回后任务可能还没完成，
    所以 metadata 应只放轻量数据（如 sid + nl_length），不放原始 NL 内容。
    """
    return asyncio.create_task(
        _fire_and_forget_inner(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
