"""管理类路由：LLM 用量统计、系统状态、反馈查询、用户管理、套餐管理。

V2-F.1：所有路由要求 admin 角色（Depends(require_admin)）。
P2 V3.3：扩展用户管理（列表/详情/改 status-role/配额覆盖/订阅覆盖）+ 套餐管理。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..admin import repository as admin_repo
from ..auth.deps import CurrentUser, require_admin
from ..db.models import DSLSnapshot, Feedback, Message, Session, SubscriptionPlan, User
from ..payment import repository as pay_repo
from ..payment.entitlement import invalidate_user_cache
from .deps import db_dep

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ===================== Pydantic 模型 =====================


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: str
    status: str
    email_verified: bool
    wechat_nickname: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserListResp(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


class UserDetailResp(BaseModel):
    user: UserOut
    sessions_count: int
    snapshots_count: int
    subscription: Optional[dict] = None


class UpdateUserReq(BaseModel):
    """更新用户字段。所有字段可选。"""
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    status: Optional[str] = Field(
        None, pattern="^(active|disabled|pending_email_verification)$"
    )


class QuotaOverrideReq(BaseModel):
    """per-user 配额覆盖。None=用 plan 默认；0=无限；正整数=每日 N 张。"""
    daily_graph_limit_override: Optional[int] = Field(None, ge=0)


class SetSubscriptionReq(BaseModel):
    plan_code: str
    status: str = Field("active", pattern="^(active|expired|free)$")
    period_days: Optional[int] = Field(None, ge=1)


class PlanOut(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    price_cents: int
    period: str
    daily_graph_limit: int
    status: str
    sort_order: int


class PlanListResp(BaseModel):
    items: list[PlanOut]


class UpdatePlanReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = Field(None, ge=0)
    daily_graph_limit: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(active|archived)$")
    sort_order: Optional[int] = Field(None, ge=0)


# V3.5 批量操作请求
class BatchActionReq(BaseModel):
    """批量操作请求。

    action: enable / disable / set_quota / set_subscription
    - enable/disable: 改 user.status
    - set_quota: 配额覆盖（payload.daily_graph_limit_override）
    - set_subscription: 设置订阅（payload.plan_code + payload.period_days）
    """
    user_ids: list[str] = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(enable|disable|set_quota|set_subscription)$")
    payload: dict = Field(default_factory=dict)


class BatchActionResp(BaseModel):
    action: str
    affected: int
    skipped: int
    message: str


# ===================== 工具 =====================


def _to_user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        username=u.username,
        role=u.role,
        status=u.status,
        email_verified=u.email_verified_at is not None,
        wechat_nickname=u.wechat_nickname,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


# ===================== 旧端点：stats / feedback / feedback.jsonl =====================


@router.get("/stats")
async def stats(
    days: int = 7,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> dict:
    """近 N 天的用量统计。"""
    since = datetime.utcnow() - timedelta(days=days)

    n_sessions = (
        await db.execute(select(func.count(Session.id)).where(Session.created_at >= since))
    ).scalar_one()

    n_msgs = (
        await db.execute(select(func.count(Message.id)).where(Message.created_at >= since))
    ).scalar_one()

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

    n_snapshots = (
        await db.execute(
            select(func.count(DSLSnapshot.id)).where(DSLSnapshot.created_at >= since)
        )
    ).scalar_one()

    # P2：总用户数 + 已验证邮箱数 + 付费用户数
    n_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    n_verified = (
        await db.execute(
            select(func.count(User.id)).where(User.email_verified_at.is_not(None))
        )
    ).scalar_one()

    return {
        "since": since.isoformat(),
        "days": days,
        "sessions": int(n_sessions or 0),
        "messages": int(n_msgs or 0),
        "snapshots": int(n_snapshots or 0),
        "users": int(n_users or 0),
        "verified_users": int(n_verified or 0),
        "providers": per_provider,
    }


@router.get("/feedback")
async def list_feedback(
    days: int = 30,
    limit: int = 1000,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
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
    days: int = 30,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
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


# ============================================================================
# P2 V3.3：用户管理
# ============================================================================


@router.get("/users", response_model=UserListResp)
async def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> UserListResp:
    """分页查询用户列表。支持搜索（email/username）+ role + status 过滤。"""
    if limit > 500:
        limit = 500
    rows, total = await admin_repo.list_users(
        db, search=search, role=role, status=status, limit=limit, offset=offset
    )
    return UserListResp(
        items=[_to_user_out(u) for u in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=UserDetailResp)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> UserDetailResp:
    """用户详情。含会话数 / 画图数 / 订阅信息。"""
    target = await admin_repo.get_user_detail(db, user_id)
    if target is None:
        raise HTTPException(404, detail="用户不存在")

    sessions_count = await admin_repo.count_user_sessions(db, user_id)
    snapshots_count = await admin_repo.count_user_snapshots(db, user_id)

    sub = await pay_repo.get_user_subscription(db, user_id)
    subscription = None
    if sub is not None:
        subscription = {
            "plan_code": sub.plan_code,
            "status": sub.status,
            "daily_graph_limit_override": sub.daily_graph_limit_override,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }

    return UserDetailResp(
        user=_to_user_out(target),
        sessions_count=sessions_count,
        snapshots_count=snapshots_count,
        subscription=subscription,
    )


@router.patch("/users/{user_id}", response_model=UserDetailResp)
async def update_user(
    user_id: str,
    req: UpdateUserReq,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> UserDetailResp:
    """更新用户 role / status。

    安全保护：
    - admin 不能改自己的 role（防止误降权）
    - 不能把最后一个 admin 改成 user（防止失去管理员）
    """
    target = await admin_repo.get_user_detail(db, user_id)
    if target is None:
        raise HTTPException(404, detail="用户不存在")

    # 改 role 保护
    if req.role is not None and req.role != target.role:
        # 不能改自己的 role
        if user.id == target.id:
            raise HTTPException(400, detail="不能修改自己的角色")
        # 降级最后一个 admin
        if target.role == "admin" and req.role == "user":
            admin_count = await admin_repo.count_admins(db)  # type: ignore[attr-defined]
            # fallback：直接查
            from sqlalchemy import func as sa_func
            res = await db.execute(
                select(sa_func.count(User.id)).where(User.role == "admin")
            )
            admin_count = int(res.scalar() or 0)
            if admin_count <= 1:
                raise HTTPException(400, detail="不能降级最后一个管理员")
        await admin_repo.update_user_role(db, target, req.role)

    # 改 status 保护
    if req.status is not None and req.status != target.status:
        # 不能 disable 自己
        if user.id == target.id and req.status == "disabled":
            raise HTTPException(400, detail="不能禁用自己的账号")
        await admin_repo.update_user_status(db, target, req.status)

    # 重新拉取最新数据
    target = await admin_repo.get_user_detail(db, user_id)
    assert target is not None
    return await get_user_detail(user_id, db, user)


@router.put("/users/{user_id}/quota", response_model=dict)
async def set_user_quota(
    user_id: str,
    req: QuotaOverrideReq,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> dict:
    """设置 per-user 配额覆盖。None=用 plan 默认；0=无限；正整数=每日 N 张。"""
    target = await admin_repo.get_user_detail(db, user_id)
    if target is None:
        raise HTTPException(404, detail="用户不存在")

    # 不能给自己设置 0（无限），防止误操作（其实允许，但提示）
    sub = await admin_repo.set_user_quota_override(
        db, user_id, req.daily_graph_limit_override
    )
    # 立即失效缓存
    invalidate_user_cache(user_id)

    return {
        "user_id": user_id,
        "daily_graph_limit_override": sub.daily_graph_limit_override if sub else None,
        "message": "配额已更新，立即生效",
    }


@router.put("/users/{user_id}/subscription", response_model=dict)
async def set_user_subscription(
    user_id: str,
    req: SetSubscriptionReq,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> dict:
    """直接给用户设置订阅（admin 操作，不走支付流程）。

    常见用法：批量给某学校老师开 pro / 给个别 enterprise。
    """
    target = await admin_repo.get_user_detail(db, user_id)
    if target is None:
        raise HTTPException(404, detail="用户不存在")

    plan = await pay_repo.get_plan_by_code(db, req.plan_code)
    if plan is None:
        raise HTTPException(400, detail=f"套餐不存在: {req.plan_code}")

    sub = await admin_repo.set_user_subscription(
        db,
        user_id,
        plan_code=req.plan_code,
        status=req.status,
        period_days=req.period_days,
    )
    invalidate_user_cache(user_id)

    return {
        "user_id": user_id,
        "plan_code": sub.plan_code if sub else None,
        "status": sub.status if sub else None,
        "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "message": "订阅已更新，立即生效",
    }


# ============================================================================
# P2 V3.3：套餐管理
# ============================================================================


@router.get("/plans", response_model=PlanListResp)
async def list_plans(
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> PlanListResp:
    """列出所有套餐（含 archived）。"""
    plans = await admin_repo.list_plans(db)
    return PlanListResp(
        items=[
            PlanOut(
                code=p.code,
                name=p.name,
                description=p.description,
                price_cents=p.price_cents,
                period=p.period,
                daily_graph_limit=p.daily_graph_limit,
                status=p.status,
                sort_order=p.sort_order,
            )
            for p in plans
        ]
    )


@router.patch("/plans/{code}", response_model=PlanOut)
async def update_plan(
    code: str,
    req: UpdatePlanReq,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> PlanOut:
    """更新套餐字段。允许字段：name/description/price_cents/daily_graph_limit/status/sort_order。

    改 daily_graph_limit 后所有该 plan 用户立即生效（不需要重启 backend）。
    """
    plan = await pay_repo.get_plan_by_code(db, code)
    if plan is None:
        raise HTTPException(404, detail=f"套餐不存在: {code}")

    updated = await admin_repo.update_plan(db, plan, **req.model_dump(exclude_unset=True))

    # 失效所有该 plan 用户的配额缓存
    # 简单实现：清空整个缓存（plan 改动不频繁）
    from ..payment.entitlement import _limit_cache
    _limit_cache.clear()

    return PlanOut(
        code=updated.code,
        name=updated.name,
        description=updated.description,
        price_cents=updated.price_cents,
        period=updated.period,
        daily_graph_limit=updated.daily_graph_limit,
        status=updated.status,
        sort_order=updated.sort_order,
    )


# ============================================================================
# V3.5：批量操作
# ============================================================================


@router.post("/users/batch", response_model=BatchActionResp)
async def batch_update_users(
    req: BatchActionReq,
    db: AsyncSession = Depends(db_dep),
    user: CurrentUser = Depends(require_admin),
) -> BatchActionResp:
    """批量操作用户。

    支持 action：
    - enable / disable：改 user.status
    - set_quota：配额覆盖（payload.daily_graph_limit_override: None / 0 / 正整数）
    - set_subscription：设置订阅（payload.plan_code + payload.period_days）

    安全保护：
    - 单次最多 100 个用户
    - 不能 disable 自己（防止误锁死）
    - 改完配额/订阅后立即清缓存
    """
    # 安全：不能 disable 自己
    if req.action == "disable" and user.id in req.user_ids:
        raise HTTPException(400, detail="不能在批量操作中禁用自己的账号")

    # 校验 user_ids 总数
    if len(req.user_ids) > 100:
        raise HTTPException(400, detail="单次批量操作最多 100 个用户")

    # 先查实际存在的用户数
    existing_count = 0
    for uid in req.user_ids:
        u = await admin_repo.get_user_detail(db, uid)
        if u is not None:
            existing_count += 1

    affected = 0
    try:
        if req.action == "enable":
            affected = await admin_repo.batch_update_user_status(db, req.user_ids, "active")
        elif req.action == "disable":
            affected = await admin_repo.batch_update_user_status(db, req.user_ids, "disabled")
        elif req.action == "set_quota":
            raw = req.payload.get("daily_graph_limit_override")
            if raw is not None:
                if not isinstance(raw, int) or raw < 0:
                    raise HTTPException(400, detail="daily_graph_limit_override 必须是 null / 0 / 正整数")
            affected = await admin_repo.batch_set_quota_override(db, req.user_ids, raw)
        elif req.action == "set_subscription":
            plan_code = req.payload.get("plan_code")
            if not plan_code:
                raise HTTPException(400, detail="payload.plan_code 必填")
            plan = await pay_repo.get_plan_by_code(db, plan_code)
            if plan is None:
                raise HTTPException(400, detail=f"套餐不存在: {plan_code}")
            period_days = req.payload.get("period_days")
            status = req.payload.get("status", "active")
            affected = await admin_repo.batch_set_subscription(
                db, req.user_ids,
                plan_code=plan_code,
                status=status,
                period_days=period_days,
            )
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from None

    # 清缓存（让配额/订阅变更立即生效）
    for uid in req.user_ids:
        invalidate_user_cache(uid)

    skipped = existing_count - affected
    return BatchActionResp(
        action=req.action,
        affected=affected,
        skipped=skipped,
        message=f"已处理 {affected} 个用户" + (f"，跳过 {skipped} 个不存在" if skipped > 0 else ""),
    )
