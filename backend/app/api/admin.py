"""管理类路由：LLM 用量统计、系统状态。

无鉴权 MVP（部署在内网或仅老师可见）。生产环境如需鉴权，加 API key middleware。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import DSLSnapshot, Feedback, Message, Session
from .deps import db_dep

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def stats(
    days: int = 7, db: AsyncSession = Depends(db_dep)
) -> dict:
    """近 N 天的用量统计。"""
    since = datetime.utcnow() - timedelta(days=days)

    # 会话数
    n_sessions = (
        await db.execute(select(func.count(Session.id)).where(Session.created_at >= since))
    ).scalar_one()

    # 消息数
    n_msgs = (
        await db.execute(select(func.count(Message.id)).where(Message.created_at >= since))
    ).scalar_one()

    # 按 provider 汇总 tokens
    stmt = (
        select(
            Message.llm_provider,
            func.count(Message.id).label("calls"),
            func.coalesce(func.sum(Message.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(Message.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.avg(Message.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(Message.created_at >= since, Message.llm_provider.is_not(None))
        .group_by(Message.llm_provider)
    )
    per_provider = []
    for row in (await db.execute(stmt)).all():
        per_provider.append({
            "provider": row.llm_provider,
            "calls": int(row.calls or 0),
            "tokens_in": int(row.tokens_in or 0),
            "tokens_out": int(row.tokens_out or 0),
            "avg_latency_ms": float(row.avg_latency_ms or 0),
        })

    # 快照数 = 成功生成的图次数
    n_snapshots = (
        await db.execute(
            select(func.count(DSLSnapshot.id)).where(DSLSnapshot.created_at >= since)
        )
    ).scalar_one()

    return {
        "since": since.isoformat(),
        "days": days,
        "sessions": int(n_sessions or 0),
        "messages": int(n_msgs or 0),
        "snapshots": int(n_snapshots or 0),
        "providers": per_provider,
    }


@router.get("/feedback")
async def list_feedback(
    days: int = 30, limit: int = 1000, db: AsyncSession = Depends(db_dep)
) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(Feedback)
        .where(Feedback.created_at >= since)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
    )
    items = list((await db.execute(stmt)).scalars())
    out = [
        {
            "id": f.id,
            "session_id": f.session_id,
            "snapshot_seq": f.snapshot_seq,
            "rating": f.rating,
            "comment": f.comment,
            "nl": f.nl,
            "llm_provider": f.llm_provider,
            "created_at": f.created_at.isoformat(),
        }
        for f in items
    ]
    good = sum(1 for f in items if f.rating == "good")
    bad = sum(1 for f in items if f.rating == "bad")
    return {"since": since.isoformat(), "total": len(items), "good": good, "bad": bad, "items": out}


@router.get("/feedback.jsonl")
async def feedback_jsonl(
    days: int = 30, db: AsyncSession = Depends(db_dep)
) -> Response:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(Feedback)
        .where(Feedback.created_at >= since)
        .order_by(Feedback.created_at.asc())
    )
    items = list((await db.execute(stmt)).scalars())
    lines = []
    for f in items:
        lines.append(json.dumps({
            "id": f.id,
            "session_id": f.session_id,
            "snapshot_seq": f.snapshot_seq,
            "rating": f.rating,
            "comment": f.comment,
            "nl": f.nl,
            "dsl_json": json.loads(f.dsl_json) if f.dsl_json else None,
            "llm_provider": f.llm_provider,
            "created_at": f.created_at.isoformat(),
        }, ensure_ascii=False))
    return Response(
        "\n".join(lines) + ("\n" if lines else ""),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=feedback.jsonl"},
    )
