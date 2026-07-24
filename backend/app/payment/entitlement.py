"""配额解析 + chat 配额检查。

- resolve_user_entitlement(user_id) -> UserEntitlement：解析用户当前套餐 + 配额 + 今日用量
- ensure_user_can_send_chat(user_id) -> UserEntitlement：抛 QuotaExceededError 如超限

配额计数维度：当日 dsl_snapshot 表里通过 user_id -> session_id 关联的行数（成功画图次数）。
LLM 失败不产生 snapshot，因此失败不扣配额。

plan.daily_graph_limit 可 admin SQL 调整；UserSubscription.daily_graph_limit_override 可 per-user 覆盖。
entitlement 读取时加 5 分钟内存缓存（避免每次 chat 都查 DB）。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import UserSubscription
from . import repository as pay_repo

log = logging.getLogger(__name__)

# 5 分钟内存缓存：plan.daily_graph_limit + override 值
_CACHE_TTL_SECONDS = 300
_limit_cache: dict[str, tuple[float, int]] = {}  # key=user_id -> (expires_at, daily_limit)


class QuotaExceededError(Exception):
    """配额超限异常。"""

    def __init__(self, used: int, limit: int, plan_code: str):
        self.used = used
        self.limit = limit
        self.plan_code = plan_code
        super().__init__(f"quota exceeded: used {used}/{limit} (plan={plan_code})")


@dataclass
class UserEntitlement:
    """用户当前订阅 + 配额状态。"""

    plan_code: str  # 'free' | 'pro' | 'enterprise'
    plan_name: str
    status: str  # 'free' | 'active' | 'expired'
    daily_limit: int  # 0 = 无限
    used_today: int
    remaining: int  # -1 = 无限（daily_limit=0）

    @property
    def is_unlimited(self) -> bool:
        return self.daily_limit == 0

    @property
    def is_blocked(self) -> bool:
        """今日配额已用完（limit > 0 且 used >= limit）。"""
        return self.daily_limit > 0 and self.used_today >= self.daily_limit


def _is_subscription_active(sub: Optional[UserSubscription]) -> bool:
    """判断订阅是否有效（status=active 且未过期）。

    处理 timezone-aware 和 naive datetime 混合比较（SQLite 返回 naive）。
    """
    if sub is None:
        return False
    if sub.status != "active":
        return False
    if sub.current_period_end is not None:
        now = datetime.now(timezone.utc)
        period_end = sub.current_period_end
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        if now > period_end:
            return False
    return True


async def resolve_user_entitlement(db: AsyncSession, user_id: str) -> UserEntitlement:
    """解析用户当前订阅 + 配额 + 今日用量。"""
    sub = await pay_repo.get_user_subscription(db, user_id)

    if sub is not None and _is_subscription_active(sub):
        # 有效付费订阅
        plan = await pay_repo.get_plan_by_code(db, sub.plan_code)
        if plan is None:
            plan = await pay_repo.get_plan_by_code(db, "free")
    else:
        # free 用户（无订阅记录 / 订阅过期 / 订阅状态非 active）
        plan = await pay_repo.get_plan_by_code(db, "free")

    # plan 仍为 None 时用默认值（DB 未 seed 时兜底）
    plan_code = plan.code if plan else "free"
    plan_name = plan.name if plan else "免费版"
    plan_daily_limit = plan.daily_graph_limit if plan else 5

    # per-user 覆盖（admin 可调）；带 5 分钟缓存
    cached = _limit_cache.get(user_id)
    now_ts = time.time()
    if cached is not None and cached[0] > now_ts:
        daily_limit = cached[1]
    else:
        daily_limit = plan_daily_limit
        if sub is not None and sub.daily_graph_limit_override is not None:
            daily_limit = sub.daily_graph_limit_override
        _limit_cache[user_id] = (now_ts + _CACHE_TTL_SECONDS, daily_limit)

    # 今日已用
    used_today = await pay_repo.count_user_snapshots_today(db, user_id)

    # 订阅状态
    if sub is not None and _is_subscription_active(sub):
        status = "active"
    elif sub is not None and sub.status == "active" and sub.current_period_end is not None:
        # 订阅已过期
        status = "expired"
    else:
        status = "free"

    remaining = -1 if daily_limit == 0 else max(0, daily_limit - used_today)

    return UserEntitlement(
        plan_code=plan_code,
        plan_name=plan_name,
        status=status,
        daily_limit=daily_limit,
        used_today=used_today,
        remaining=remaining,
    )


async def ensure_user_can_send_chat(db: AsyncSession, user_id: str) -> UserEntitlement:
    """检查用户今日配额是否充足。超限抛 QuotaExceededError。"""
    ent = await resolve_user_entitlement(db, user_id)
    if ent.is_blocked:
        raise QuotaExceededError(
            used=ent.used_today,
            limit=ent.daily_limit,
            plan_code=ent.plan_code,
        )
    return ent


def invalidate_user_cache(user_id: str) -> None:
    """P2：admin 改完用户配额后调，让下次 resolve 立即拿新值。

    缓存 key 是 user_id；不存在的 key 也不报错。
    """
    _limit_cache.pop(user_id, None)
