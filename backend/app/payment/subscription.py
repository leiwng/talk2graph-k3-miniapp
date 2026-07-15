"""订阅业务逻辑：订单创建 / webhook 幂等处理 / 月续期。

借鉴 Lumiton subscription_service.py：
- handle_alipay_notify_use_case 幂等（标记 subscription_applied）
- _add_calendar_month 用 monthrange 正确处理月末
- 金额校验
"""
from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SubscriptionOrder, SubscriptionPlan
from . import repository as pay_repo

log = logging.getLogger(__name__)


def _add_calendar_month(start: datetime) -> datetime:
    """从 start 加 1 个日历月。正确处理月末（如 1/31 + 1 月 = 2/28 或 2/29）。"""
    year = start.year + (1 if start.month == 12 else 0)
    month = start.month + 1 if start.month < 12 else 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start.day, last_day)
    return start.replace(year=year, month=month, day=day)


def _compute_period(existing_end: datetime | None, paid_at: datetime) -> tuple[datetime, datetime]:
    """计算订阅期间。

    - 若现有订阅未过期：从 current_period_end 续期（不丢失已付天数）
    - 否则从支付时间起算

    处理 timezone-aware 和 naive datetime 混合比较（SQLite 返回 naive）。
    """
    if existing_end is not None:
        # 统一为 aware（SQLite 返回 naive，按 UTC 解释）
        if existing_end.tzinfo is None:
            existing_end = existing_end.replace(tzinfo=timezone.utc)
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=timezone.utc)
        if existing_end > paid_at:
            start = existing_end
        else:
            start = paid_at
    else:
        start = paid_at
    end = _add_calendar_month(start)
    return start, end


async def create_order_use_case(
    db: AsyncSession,
    *,
    user_id: str,
    plan_code: str,
) -> tuple[SubscriptionOrder, str]:
    """创建订单 + 返回 Alipay 跳转 URL。

    返回 (order, pay_url)。
    """
    plan = await pay_repo.get_plan_by_code(db, plan_code)
    if plan is None:
        raise ValueError(f"plan not found: {plan_code}")
    if plan.price_cents == 0:
        raise ValueError(f"plan {plan_code} is free, no need to create order")

    order = await pay_repo.create_order(db, user_id=user_id, plan=plan)

    # 构造 Alipay 跳转 URL
    from .alipay import build_pay_url
    total_amount = f"{plan.price_cents / 100:.2f}"
    pay_url = build_pay_url(
        out_trade_no=order.provider_out_trade_no,
        total_amount=total_amount,
        subject=f"话图 T2G - {plan.name}",
        body=plan.description or "",
    )
    return order, pay_url


async def handle_alipay_notify_use_case(
    db: AsyncSession,
    notify_data: dict[str, str],
) -> bool:
    """处理 Alipay webhook 异步通知。

    幂等：通过 provider_payload.subscription_applied 标记避免重复激活。
    返回 True 表示处理成功（应答 Alipay "success"），False 表示忽略。
    """
    # 1. 验签
    from .alipay import verify_notification
    if not verify_notification(notify_data):
        log.warning("[alipay-notify] signature verification failed")
        return False

    # 2. 校验 app_id
    from ..config import settings
    if notify_data.get("app_id") != settings.alipay_app_id:
        log.warning(
            "[alipay-notify] app_id mismatch: expected=%s got=%s",
            settings.alipay_app_id,
            notify_data.get("app_id"),
        )
        return False

    # 3. 查订单
    out_trade_no = notify_data.get("out_trade_no", "")
    order = await pay_repo.get_order_by_trade_no(db, out_trade_no)
    if order is None:
        log.warning("[alipay-notify] order not found: %s", out_trade_no)
        return False

    # 4. 幂等：已处理过的订单不再处理
    if order.status == "paid":
        log.info("[alipay-notify] order already paid, skip: %s", out_trade_no)
        return True

    # 5. 校验 trade_status
    trade_status = notify_data.get("trade_status", "")
    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        log.info("[alipay-notify] non-success trade_status: %s", trade_status)
        return False

    # 6. 金额校验
    expected_amount = order.amount_cents / 100
    actual_amount_str = notify_data.get("total_amount", "0")
    try:
        actual_amount = float(actual_amount_str)
    except ValueError:
        log.warning("[alipay-notify] invalid total_amount: %s", actual_amount_str)
        return False
    if abs(actual_amount - expected_amount) > 0.01:
        log.warning(
            "[alipay-notify] amount mismatch: expected=%.2f got=%.2f",
            expected_amount,
            actual_amount,
        )
        return False

    # 7. 标记订单为 paid
    provider_transaction_id = notify_data.get("trade_no", "")
    await pay_repo.mark_order_paid(
        db,
        order,
        provider_transaction_id=provider_transaction_id,
        provider_payload={**notify_data, "subscription_applied": True},
    )

    # 8. 激活/续期用户订阅
    plan = await pay_repo.get_plan_by_code(db, order.plan_code)
    if plan is None:
        log.error("[alipay-notify] plan not found after payment: %s", order.plan_code)
        return False

    paid_at = order.paid_at or datetime.now(timezone.utc)
    existing_sub = await pay_repo.get_user_subscription(db, order.user_id)
    existing_end = existing_sub.current_period_end if existing_sub else None
    period_start, period_end = _compute_period(existing_end, paid_at)

    await pay_repo.upsert_user_subscription(
        db,
        user_id=order.user_id,
        plan=plan,
        current_period_start=period_start,
        current_period_end=period_end,
        source_order_id=order.id,
    )

    log.info(
        "[alipay-notify] subscription activated: user=%s plan=%s period=%s..%s",
        order.user_id,
        plan.code,
        period_start.isoformat(),
        period_end.isoformat(),
    )
    return True
