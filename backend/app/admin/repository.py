"""Admin 仓储：用户列表 / 详情 / 改 status/role / 配额覆盖 / 订阅覆盖 / 套餐管理。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
    DSLSnapshot,
    Session,
    SubscriptionPlan,
    User,
    UserSubscription,
)


# ===================== 用户列表 + 详情 =====================


async def list_users(
    db: AsyncSession,
    *,
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[User], int]:
    """分页查询用户列表。返回 (rows, total)。"""
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if search:
        like = f"%{search}%"
        stmt = stmt.where(User.email.like(like) | User.username.like(like))
        count_stmt = count_stmt.where(User.email.like(like) | User.username.like(like))
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
        count_stmt = count_stmt.where(User.status == status)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, int(total)


async def get_user_detail(db: AsyncSession, user_id: str) -> Optional[User]:
    return await db.get(User, user_id)


async def count_user_sessions(db: AsyncSession, user_id: str) -> int:
    res = await db.execute(
        select(func.count(Session.id)).where(Session.user_id == user_id)
    )
    return int(res.scalar() or 0)


async def count_user_snapshots(db: AsyncSession, user_id: str) -> int:
    """用户历史成功画图次数（含所有天数）。"""
    res = await db.execute(
        select(func.count(DSLSnapshot.id))
        .select_from(DSLSnapshot)
        .join(Session, Session.id == DSLSnapshot.session_id)
        .where(Session.user_id == user_id)
    )
    return int(res.scalar() or 0)


# ===================== 用户属性更新 =====================


async def update_user_status(db: AsyncSession, user: User, new_status: str) -> User:
    user.status = new_status
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_role(db: AsyncSession, user: User, new_role: str) -> User:
    user.role = new_role
    await db.commit()
    await db.refresh(user)
    return user


# ===================== 配额 + 订阅覆盖 =====================


async def set_user_quota_override(
    db: AsyncSession, user_id: str, daily_limit_override: Optional[int]
) -> Optional[UserSubscription]:
    """设置 per-user 配额覆盖。None = 用 plan 默认值；0 = 无限。

    若用户无订阅记录则创建一条 free 记录。
    """
    import uuid

    sub = await _get_or_create_subscription(db, user_id)
    sub.daily_graph_limit_override = daily_limit_override
    await db.commit()
    await db.refresh(sub)
    return sub


async def set_user_subscription(
    db: AsyncSession,
    user_id: str,
    *,
    plan_code: str,
    status: str = "active",
    period_days: Optional[int] = None,
) -> Optional[UserSubscription]:
    """直接给用户设置订阅（admin 操作，不走支付流程）。

    period_days=None 且 status=active -> 当前周期 1 年（enterprise）
    period_days=30 -> 1 个月（pro）
    """
    from datetime import timedelta

    sub = await _get_or_create_subscription(db, user_id, plan_code=plan_code)
    sub.plan_code = plan_code
    sub.plan_id = plan_code
    sub.status = status
    if status == "active":
        now = datetime.now(timezone.utc)
        sub.current_period_start = now
        if period_days is not None:
            sub.current_period_end = now + timedelta(days=period_days)
        else:
            # 无限（enterprise）
            sub.current_period_end = None
    await db.commit()
    await db.refresh(sub)
    return sub


async def _get_or_create_subscription(
    db: AsyncSession, user_id: str, plan_code: str = "free"
) -> UserSubscription:
    """获取或创建用户订阅记录。"""
    import uuid

    res = await db.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id).limit(1)
    )
    sub = res.scalars().first()
    if sub is None:
        sub = UserSubscription(
            id=uuid.uuid4().hex,
            user_id=user_id,
            plan_id=plan_code,
            plan_code=plan_code,
            status="free",
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


# ===================== 套餐管理 =====================


async def list_plans(db: AsyncSession) -> list[SubscriptionPlan]:
    res = await db.execute(
        select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
    )
    return list(res.scalars().all())


async def update_plan(
    db: AsyncSession, plan: SubscriptionPlan, **fields
) -> SubscriptionPlan:
    """更新 plan 字段。允许字段：name/description/price_cents/daily_graph_limit/status/sort_order。"""
    allowed = {
        "name", "description", "price_cents", "daily_graph_limit",
        "status", "sort_order", "period",
    }
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(plan, k, v)
    await db.commit()
    await db.refresh(plan)
    return plan


# ============================================================================
# V3.5：批量操作
# ============================================================================


BATCH_LIMIT = 100  # 单次批量操作上限


async def batch_update_user_status(
    db: AsyncSession, user_ids: list[str], new_status: str
) -> int:
    """批量更新用户状态。返回实际更新数（跳过不存在的）。"""
    if len(user_ids) > BATCH_LIMIT:
        raise ValueError(f"batch limit exceeded: {len(user_ids)} > {BATCH_LIMIT}")
    count = 0
    for uid in user_ids:
        u = await db.get(User, uid)
        if u is None:
            continue
        u.status = new_status
        count += 1
    await db.commit()
    return count


async def batch_set_quota_override(
    db: AsyncSession, user_ids: list[str], daily_limit_override: Optional[int]
) -> int:
    """批量设置 per-user 配额覆盖。"""
    if len(user_ids) > BATCH_LIMIT:
        raise ValueError(f"batch limit exceeded: {len(user_ids)} > {BATCH_LIMIT}")
    count = 0
    for uid in user_ids:
        sub = await _get_or_create_subscription(db, uid)
        sub.daily_graph_limit_override = daily_limit_override
        count += 1
    await db.commit()
    return count


async def batch_set_subscription(
    db: AsyncSession,
    user_ids: list[str],
    *,
    plan_code: str,
    status: str = "active",
    period_days: Optional[int] = None,
) -> int:
    """批量设置订阅。"""
    if len(user_ids) > BATCH_LIMIT:
        raise ValueError(f"batch limit exceeded: {len(user_ids)} > {BATCH_LIMIT}")
    from datetime import datetime, timedelta, timezone

    count = 0
    for uid in user_ids:
        sub = await _get_or_create_subscription(db, uid, plan_code=plan_code)
        sub.plan_code = plan_code
        sub.plan_id = plan_code
        sub.status = status
        if status == "active":
            now = datetime.now(timezone.utc)
            sub.current_period_start = now
            if period_days is not None:
                sub.current_period_end = now + timedelta(days=period_days)
            else:
                sub.current_period_end = None
        count += 1
    await db.commit()
    return count
