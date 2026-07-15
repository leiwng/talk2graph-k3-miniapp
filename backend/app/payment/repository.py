"""Plan / Order / UserSubscription CRUD。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import DSLSnapshot, Session, SubscriptionOrder, SubscriptionPlan, UserSubscription


# ===================== Plan =====================


async def get_plan_by_code(db: AsyncSession, code: str) -> Optional[SubscriptionPlan]:
    res = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code).limit(1))
    return res.scalars().first()


async def list_active_plans(db: AsyncSession) -> list[SubscriptionPlan]:
    res = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.status == "active")
        .order_by(SubscriptionPlan.sort_order)
    )
    return list(res.scalars().all())


# ===================== Order =====================


def _gen_out_trade_no() -> str:
    """商户订单号：T2G{timestamp}{uuid8}。UNIQUE 索引保证唯一。"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"T2G{ts}{uuid.uuid4().hex[:8]}"


async def create_order(
    db: AsyncSession,
    *,
    user_id: str,
    plan: SubscriptionPlan,
    expires_in_minutes: int = 15,
) -> SubscriptionOrder:
    """创建 pending 订单。"""
    now = datetime.now(timezone.utc)
    order = SubscriptionOrder(
        id=uuid.uuid4().hex,
        user_id=user_id,
        plan_id=plan.code,
        plan_code=plan.code,
        amount_cents=plan.price_cents,
        currency=plan.currency,
        status="pending",
        provider="alipay",
        provider_out_trade_no=_gen_out_trade_no(),
        expires_at=now + timedelta(minutes=expires_in_minutes),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def get_order_by_id(db: AsyncSession, order_id: str) -> Optional[SubscriptionOrder]:
    return await db.get(SubscriptionOrder, order_id)


async def get_order_by_trade_no(db: AsyncSession, out_trade_no: str) -> Optional[SubscriptionOrder]:
    res = await db.execute(
        select(SubscriptionOrder).where(SubscriptionOrder.provider_out_trade_no == out_trade_no).limit(1)
    )
    return res.scalars().first()


async def mark_order_paid(
    db: AsyncSession,
    order: SubscriptionOrder,
    *,
    provider_transaction_id: str,
    provider_payload: dict,
) -> None:
    """标记订单为已支付。幂等：若已 paid 则不重复更新。"""
    if order.status == "paid":
        return
    order.status = "paid"
    order.provider_transaction_id = provider_transaction_id
    import json
    order.provider_payload_json = json.dumps(provider_payload, ensure_ascii=False)
    order.paid_at = datetime.now(timezone.utc)
    await db.commit()


async def close_order(db: AsyncSession, order: SubscriptionOrder) -> None:
    """关闭未支付订单。"""
    if order.status != "pending":
        return
    order.status = "closed"
    order.closed_at = datetime.now(timezone.utc)
    await db.commit()


# ===================== UserSubscription =====================


async def get_user_subscription(db: AsyncSession, user_id: str) -> Optional[UserSubscription]:
    """查询用户当前订阅记录。无记录 = free 用户。"""
    res = await db.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id).limit(1)
    )
    return res.scalars().first()


async def upsert_user_subscription(
    db: AsyncSession,
    *,
    user_id: str,
    plan: SubscriptionPlan,
    current_period_start: datetime,
    current_period_end: datetime,
    source_order_id: str,
) -> UserSubscription:
    """激活/续期用户订阅。若已有记录则更新，否则新建。"""
    sub = await get_user_subscription(db, user_id)
    if sub is None:
        sub = UserSubscription(
            id=uuid.uuid4().hex,
            user_id=user_id,
            plan_id=plan.code,
            plan_code=plan.code,
            status="active",
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            source_order_id=source_order_id,
        )
        db.add(sub)
    else:
        sub.plan_id = plan.code
        sub.plan_code = plan.code
        sub.status = "active"
        sub.current_period_start = current_period_start
        sub.current_period_end = current_period_end
        sub.source_order_id = source_order_id
    await db.commit()
    await db.refresh(sub)
    return sub


# ===================== 配额计数 =====================


async def count_user_snapshots_today(db: AsyncSession, user_id: str) -> int:
    """统计用户今日成功画图次数（snapshot 数）。

    配额计数维度：当日 dsl_snapshot 表里通过 user_id -> session_id 关联的行数。
    LLM 失败不产生 snapshot，因此失败不扣配额。
    """
    from sqlalchemy import func as sa_func
    # SQLite 的 DATE() 函数处理 created_at（server 返回 UTC）
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    res = await db.execute(
        select(sa_func.count(DSLSnapshot.id))
        .select_from(DSLSnapshot)
        .join(Session, Session.id == DSLSnapshot.session_id)
        .where(Session.user_id == user_id)
        .where(sa_func.date(DSLSnapshot.created_at) == today)
    )
    return int(res.scalar() or 0)
