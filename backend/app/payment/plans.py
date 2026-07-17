"""套餐定义 + 启动 seed。

PLAN_SEEDS 是代码层的默认值（开发期 + 首次启动 seed 用）。
admin 可通过 SQL 修改 subscription_plan 表调整配额（5 分钟内存缓存后生效）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SubscriptionPlan

log = logging.getLogger(__name__)


PLAN_SEEDS: list[dict[str, Any]] = [
    {
        "code": "free",
        "name": "免费版",
        "description": "试用，每日 5 张图",
        "feature_bullets_json": json.dumps(
            ["每日 5 张几何图", "全部几何约束", "SVG / PNG / PDF 导出"], ensure_ascii=False
        ),
        "price_cents": 0,
        "currency": "CNY",
        "period": "free",
        "daily_graph_limit": 5,
        "status": "active",
        "sort_order": 1,
    },
    {
        "code": "pro",
        "name": "月度会员",
        "description": "每日 30 张图，老师推荐",
        "feature_bullets_json": json.dumps(
            ["每日 30 张图", "全部几何约束", "SVG / PNG / PDF 导出", "优先使用最佳模型"], ensure_ascii=False
        ),
        "price_cents": 2900,  # ¥29
        "currency": "CNY",
        "period": "calendar_month",
        "daily_graph_limit": 30,
        "status": "active",
        "sort_order": 2,
    },
    {
        "code": "enterprise",
        "name": "企业版",
        "description": "联系销售",
        "feature_bullets_json": json.dumps(
            ["无限画图", "团队协作", "API 接入", "专属客服"], ensure_ascii=False
        ),
        "price_cents": 0,
        "currency": "CNY",
        "period": "contract",
        "daily_graph_limit": 0,
        "status": "active",
        "sort_order": 3,
    },
]


async def seed_plans_if_empty(session: AsyncSession) -> None:
    """启动时若 subscription_plan 表为空，插入 PLAN_SEEDS。幂等。"""
    res = await session.execute(__import__("sqlalchemy").select(SubscriptionPlan).limit(1))
    if res.scalars().first() is not None:
        return
    for seed in PLAN_SEEDS:
        session.add(SubscriptionPlan(**seed))
    await session.commit()
    log.info("[db-bootstrap] seeded %d subscription plans", len(PLAN_SEEDS))
