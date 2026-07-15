"""Alipay webhook 异步通知端点。

无 auth（Alipay 服务器直接 POST），靠 RSA2 验签确保来源真实。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import actions, repository as audit_repo
from ..auth.deps import extract_request_meta
from ..db.session import get_session as _get_db_session
from ..payment.subscription import handle_alipay_notify_use_case

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/alipay", response_class=PlainTextResponse)
async def alipay_notify(request: Request):
    """Alipay 异步通知。

    Alipay 会以 application/x-www-form-urlencoded POST 所有参数。
    验签通过后激活订阅，返回 "success"（纯文本）。
    """
    # 手动解析 form data，避免 python-multipart 依赖
    body = await request.body()
    from urllib.parse import parse_qs
    parsed = parse_qs(body.decode("utf-8"))
    notify_data = {k: v[0] for k, v in parsed.items()}

    async with _get_db_session() as db:
        ok = await handle_alipay_notify_use_case(db, notify_data)

    if ok:
        # 审计（best-effort）
        out_trade_no = notify_data.get("out_trade_no", "")
        try:
            async with _get_db_session() as db:
                from ..payment.repository import get_order_by_trade_no
                order = await get_order_by_trade_no(db, out_trade_no)
                if order:
                    await audit_repo.create_audit(
                        db,
                        actor_id=order.user_id,
                        actor_email=None,
                        action=actions.ORDER_PAID,
                        target_type="subscription_order",
                        target_id=order.id,
                        metadata={"plan_code": order.plan_code, "amount_cents": order.amount_cents},
                    )
        except Exception as e:
            log.warning("[alipay-notify] audit write failed: %s", e)
        return PlainTextResponse("success")
    return PlainTextResponse("fail")
