"""V2-F.2 支付测试（8 个）。

覆盖：
- 创建订单返回 alipay 跳转 URL
- 关闭未支付订单
- Alipay webhook 验签通过 + 幂等更新
- Alipay webhook 验签失败拒绝
- 金额不匹配拒绝
- 月续期：未过期订阅从 current_period_end 续期
- 配额生效：支付成功后立即解锁
- 订单查询 + 防探测

测试用真实 RSA2 密钥对（cryptography 库生成），不依赖沙箱。
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_pay_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(scope="session", autouse=True)
def _setup_alipay_keys(tmp_path_factory):
    """生成测试用 RSA2 密钥对，写入临时文件，设到 env。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    tmp = tmp_path_factory.mktemp("alipay_keys")

    # 生成密钥对
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    # 序列化为 PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # 写入文件
    priv_file = tmp / "app_private_key.pem"
    priv_file.write_text(private_pem)
    pub_file = tmp / "alipay_public_key.pem"
    pub_file.write_text(public_pem)

    # 设 env
    os.environ["ALIPAY_APP_ID"] = "2021000123456789"
    os.environ["ALIPAY_APP_PRIVATE_KEY_FILE"] = str(priv_file)
    os.environ["ALIPAY_PUBLIC_KEY_FILE"] = str(pub_file)
    os.environ["ALIPAY_GATEWAY_URL"] = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    os.environ["ALIPAY_NOTIFY_URL"] = "https://test.example.com/api/webhooks/alipay"
    os.environ["ALIPAY_RETURN_URL"] = "https://test.example.com/account/subscription"

    # 重新加载 settings（让 env 生效）
    import importlib
    from app import config as config_mod
    importlib.reload(config_mod)
    from app.db import session as session_mod
    importlib.reload(session_mod)

    yield

    # 清理 env
    for key in ["ALIPAY_APP_ID", "ALIPAY_APP_PRIVATE_KEY_FILE", "ALIPAY_PUBLIC_KEY_FILE"]:
        os.environ.pop(key, None)


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db
    from app.main import create_app

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"pay-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "testuser",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"], email


def _sign_notify_data(notify_data: dict[str, str]) -> str:
    """用测试私钥对 notify_data 签名，返回 base64 签名。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    # 读测试私钥
    priv_path = os.environ["ALIPAY_APP_PRIVATE_KEY_FILE"]
    private_pem = Path(priv_path).read_text()
    private_key = serialization.load_pem_private_key(
        private_pem.encode("utf-8"), password=None
    )

    # 排除 sign + sign_type，按 key 字典序拼接
    params_to_sign = {
        k: v for k, v in notify_data.items() if k not in ("sign", "sign_type")
    }
    sign_string = "&".join(
        f"{k}={v}" for k, v in sorted(params_to_sign.items()) if v
    )

    signature = private_key.sign(
        sign_string.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _make_notify_payload(
    *,
    out_trade_no: str,
    total_amount: str,
    trade_no: str = "alipay-trade-123456",
    trade_status: str = "TRADE_SUCCESS",
    app_id: str = "2021000123456789",
) -> dict[str, str]:
    """构造 Alipay webhook 通知参数。"""
    data = {
        "app_id": app_id,
        "charset": "utf-8",
        "out_trade_no": out_trade_no,
        "trade_no": trade_no,
        "total_amount": total_amount,
        "trade_status": trade_status,
        "notify_id": str(uuid.uuid4().hex),
        "notify_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "sign_type": "RSA2",
    }
    data["sign"] = _sign_notify_data(data)
    return data


# ===================== 测试 =====================


@pytest.mark.asyncio
async def test_create_order_returns_pay_url(client):
    """创建 pro 订单返回 Alipay 跳转 URL。"""
    token, _ = await _register(client)
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "pay_url" in data
    assert "alipay" in data["pay_url"].lower() or "gateway" in data["pay_url"].lower()
    assert data["order"]["plan_code"] == "pro"
    assert data["order"]["amount_cents"] == 2900
    assert data["order"]["status"] == "pending"


@pytest.mark.asyncio
async def test_close_pending_order(client):
    """用户可主动关闭未支付订单。"""
    token, _ = await _register(client)
    # 创建订单
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    order_id = r.json()["order"]["id"]

    # 关闭
    r2 = await client.post(
        f"/api/payment/orders/{order_id}/close",
        headers=_auth_headers(token),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_webhook_verify_success_and_activate(client):
    """webhook 验签通过 -> 订单 paid + 用户订阅激活。"""
    token, email = await _register(client)

    # 先查 user_id
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    user_id = me.json()["id"]

    # 创建订单
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    order = r.json()["order"]
    out_trade_no = order["provider_out_trade_no"]

    # 构造 webhook 通知
    notify = _make_notify_payload(
        out_trade_no=out_trade_no,
        total_amount="29.00",
    )

    # 发 webhook
    r2 = await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 200
    assert r2.text.strip() == "success"

    # 验证订阅已激活
    r3 = await client.get("/api/payment/subscription", headers=_auth_headers(token))
    assert r3.status_code == 200
    sub = r3.json()
    assert sub["entitlement"]["plan_code"] == "pro"
    assert sub["entitlement"]["status"] == "active"
    assert sub["entitlement"]["daily_limit"] == 0  # pro 无限


@pytest.mark.asyncio
async def test_webhook_verify_failure_rejected(client):
    """验签失败 -> 返回 fail，订阅不激活。"""
    token, _ = await _register(client)
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    out_trade_no = r.json()["order"]["provider_out_trade_no"]

    # 用错误签名
    notify = _make_notify_payload(
        out_trade_no=out_trade_no,
        total_amount="29.00",
    )
    notify["sign"] = "invalid_signature_base64_xxx"

    r2 = await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.text.strip() == "fail"

    # 订阅未激活
    r3 = await client.get("/api/payment/subscription", headers=_auth_headers(token))
    assert r3.json()["entitlement"]["plan_code"] == "free"  # 仍是 free


@pytest.mark.asyncio
async def test_webhook_amount_mismatch_rejected(client):
    """金额不匹配 -> 拒绝。"""
    token, _ = await _register(client)
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    out_trade_no = r.json()["order"]["provider_out_trade_no"]

    # 金额不匹配（期望 29.00，实际 1.00）
    notify = _make_notify_payload(
        out_trade_no=out_trade_no,
        total_amount="1.00",
    )

    r2 = await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.text.strip() == "fail"


@pytest.mark.asyncio
async def test_webhook_idempotent(client):
    """重复 webhook 通知幂等（不重复激活）。"""
    token, _ = await _register(client)
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    out_trade_no = r.json()["order"]["provider_out_trade_no"]

    notify = _make_notify_payload(
        out_trade_no=out_trade_no,
        total_amount="29.00",
    )

    # 第一次：成功
    r1 = await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r1.text.strip() == "success"

    # 第二次：幂等，也返回 success
    r2 = await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.text.strip() == "success"

    # 订阅状态仍正常（不会重复续期）
    r3 = await client.get("/api/payment/subscription", headers=_auth_headers(token))
    sub = r3.json()
    assert sub["entitlement"]["status"] == "active"


@pytest.mark.asyncio
async def test_month_renewal_extends_period(client):
    """月续期：未过期订阅从 current_period_end 续期（不丢失已付天数）。"""
    from app.payment import repository as pay_repo
    from app.db.session import get_session
    from app.db.models import UserSubscription

    token, _ = await _register(client)
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    user_id = me.json()["id"]

    # 先建一个即将过期的订阅（current_period_end 设为现在 + 5 天）
    async with get_session() as db:
        existing_end = datetime.now(timezone.utc) + timedelta(days=5)
        db.add(UserSubscription(
            id=uuid.uuid4().hex,
            user_id=user_id,
            plan_id="pro",
            plan_code="pro",
            status="active",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=25),
            current_period_end=existing_end,
        ))
        await db.commit()

    # 创建新订单 + 支付
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token),
    )
    out_trade_no = r.json()["order"]["provider_out_trade_no"]

    notify = _make_notify_payload(
        out_trade_no=out_trade_no,
        total_amount="29.00",
    )
    await client.post(
        "/api/webhooks/alipay",
        data=notify,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # 验证：新 period_end 应从 existing_end + 1 月（不是从现在 + 1 月）
    r2 = await client.get("/api/payment/subscription", headers=_auth_headers(token))
    end_str = r2.json()["current_period_end"]
    new_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    if new_end.tzinfo is None:
        new_end = new_end.replace(tzinfo=timezone.utc)
    expected_end = _add_month(datetime.now(timezone.utc) + timedelta(days=5))
    # 允许 1 小时误差
    assert abs((new_end - expected_end).total_seconds()) < 3600


def _add_month(dt: datetime) -> datetime:
    import calendar
    year = dt.year + (1 if dt.month == 12 else 0)
    month = dt.month + 1 if dt.month < 12 else 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


@pytest.mark.asyncio
async def test_order_query_and_cross_user_404(client):
    """订单查询 + 防探测（cross-user 返回 404）。"""
    token_a, _ = await _register(client)
    token_b, _ = await _register(client)

    # A 创建订单
    r = await client.post(
        "/api/payment/orders",
        json={"plan_code": "pro"},
        headers=_auth_headers(token_a),
    )
    order_id = r.json()["order"]["id"]

    # A 查自己的订单
    r2 = await client.get(
        f"/api/payment/orders/{order_id}",
        headers=_auth_headers(token_a),
    )
    assert r2.status_code == 200

    # B 查 A 的订单 -> 404
    r3 = await client.get(
        f"/api/payment/orders/{order_id}",
        headers=_auth_headers(token_b),
    )
    assert r3.status_code == 404
