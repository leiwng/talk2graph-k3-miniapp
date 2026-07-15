"""付费路由：套餐查询 / 订阅状态 / 订单创建 / 订单查询 / 订单关闭。

F.2 阶段：Alipay 电脑网站支付 + 配额限流。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import CurrentUser, get_current_user
from ..payment import repository as pay_repo
from ..payment.entitlement import resolve_user_entitlement
from ..payment.subscription import create_order_use_case
from .deps import db_dep

router = APIRouter(prefix="/api/payment", tags=["payment"])


# ===================== Pydantic =====================


class PlanOut(BaseModel):
    code: str
    name: str
    description: str | None
    feature_bullets: list[str]
    price_cents: int
    currency: str
    period: str
    daily_graph_limit: int
    sort_order: int


class PlansResp(BaseModel):
    items: list[PlanOut]


class EntitlementOut(BaseModel):
    plan_code: str
    plan_name: str
    status: str  # free | active | expired
    daily_limit: int  # 0 = 无限
    used_today: int
    remaining: int  # -1 = 无限


class SubscriptionOut(BaseModel):
    plan: PlanOut
    entitlement: EntitlementOut
    current_period_start: datetime | None
    current_period_end: datetime | None


class CreateOrderReq(BaseModel):
    plan_code: str


class OrderOut(BaseModel):
    id: str
    plan_code: str
    amount_cents: int
    currency: str
    status: str
    provider: str
    provider_out_trade_no: str
    created_at: datetime
    paid_at: datetime | None
    expires_at: datetime | None
    closed_at: datetime | None


class CreateOrderResp(BaseModel):
    order: OrderOut
    pay_url: str


# ===================== 工具 =====================


def _to_plan_out(p) -> PlanOut:
    bullets = []
    if p.feature_bullets_json:
        try:
            bullets = json.loads(p.feature_bullets_json)
        except Exception:
            bullets = []
    return PlanOut(
        code=p.code,
        name=p.name,
        description=p.description,
        feature_bullets=bullets,
        price_cents=p.price_cents,
        currency=p.currency,
        period=p.period,
        daily_graph_limit=p.daily_graph_limit,
        sort_order=p.sort_order,
    )


def _to_order_out(o) -> OrderOut:
    return OrderOut(
        id=o.id,
        plan_code=o.plan_code,
        amount_cents=o.amount_cents,
        currency=o.currency,
        status=o.status,
        provider=o.provider,
        provider_out_trade_no=o.provider_out_trade_no,
        created_at=o.created_at,
        paid_at=o.paid_at,
        expires_at=o.expires_at,
        closed_at=o.closed_at,
    )


# ===================== 路由（公开） =====================


@router.get("/plans", response_model=PlansResp)
async def list_plans(db: AsyncSession = Depends(db_dep)) -> PlansResp:
    """公开端点：列出所有活跃套餐（landing / pricing 页用）。"""
    plans = await pay_repo.list_active_plans(db)
    return PlansResp(items=[_to_plan_out(p) for p in plans])


# ===================== 路由（需登录） =====================


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
) -> SubscriptionOut:
    """当前订阅 + 今日用量。"""
    ent = await resolve_user_entitlement(db, user.id)
    plan = await pay_repo.get_plan_by_code(db, ent.plan_code)
    sub = await pay_repo.get_user_subscription(db, user.id)

    return SubscriptionOut(
        plan=_to_plan_out(plan) if plan else _to_plan_out(_default_free_plan()),
        entitlement=EntitlementOut(
            plan_code=ent.plan_code,
            plan_name=ent.plan_name,
            status=ent.status,
            daily_limit=ent.daily_limit,
            used_today=ent.used_today,
            remaining=ent.remaining,
        ),
        current_period_start=sub.current_period_start if sub else None,
        current_period_end=sub.current_period_end if sub else None,
    )


@router.post("/orders", response_model=CreateOrderResp)
async def create_order(
    req: CreateOrderReq,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
) -> CreateOrderResp:
    """创建订单 -> 返回 Alipay 跳转 URL。"""
    try:
        order, pay_url = await create_order_use_case(
            db, user_id=user.id, plan_code=req.plan_code
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return CreateOrderResp(order=_to_order_out(order), pay_url=pay_url)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
) -> OrderOut:
    order = await pay_repo.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(404, detail="order not found")
    if order.user_id != user.id:
        raise HTTPException(404, detail="order not found")  # 防探测
    return _to_order_out(order)


@router.post("/orders/{order_id}/close", response_model=OrderOut)
async def close_order(
    order_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
) -> OrderOut:
    order = await pay_repo.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(404, detail="order not found")
    if order.user_id != user.id:
        raise HTTPException(404, detail="order not found")
    await pay_repo.close_order(db, order)
    await db.refresh(order)
    return _to_order_out(order)


def _default_free_plan():
    """plan 表未 seed 时的兜底。"""
    from ..db.models import SubscriptionPlan
    return SubscriptionPlan(
        code="free",
        name="免费版",
        description="试用，每日 5 张图",
        price_cents=0,
        currency="CNY",
        period="free",
        daily_graph_limit=5,
        status="active",
        sort_order=1,
    )
