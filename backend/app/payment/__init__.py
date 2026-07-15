"""付费 + 配额限流模块。

- alipay.py：RSA2 签名 / 验签 / 构造 alipay.trade.page.pay 跳转 URL
- plans.py：PLAN_SEEDS dict + seed_plans_if_empty 启动钩子
- repository.py：Plan/Order/UserSubscription CRUD
- subscription.py：订单创建 / webhook 幂等处理 / 月续期
- entitlement.py：resolve_user_entitlement + ensure_user_can_send_chat
"""
