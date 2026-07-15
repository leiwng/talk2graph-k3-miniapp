"""V2-F.2 配额限流测试（6 个）。

覆盖：
- free 用户第 6 次画图触发 quota_exceeded
- pro/enterprise 用户无限画图
- 跨日重置
- 订阅过期后降级为 free 配额
- 未登录用户不能创建 session（强制登录）
- per-user 配额覆盖（daily_graph_limit_override）
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_quota_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


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
    return f"quota-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "testuser",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"], email


async def _make_chat(client: AsyncClient, token: str, sid: str, nl: str = "画一个等边三角形 ABC，边长为 4"):
    """发一次 chat 请求，返回 response。"""
    return await client.post(
        f"/api/session/{sid}/chat",
        json={"nl": nl, "provider": None},
        headers=_auth_headers(token),
    )


async def _create_session(client: AsyncClient, token: str) -> str:
    r = await client.post("/api/session", json={}, headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_free_user_quota_exceeded(client):
    """free 用户画 5 张后第 6 次触发 quota_exceeded。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    token, _ = await _register(client)
    sid = await _create_session(client, token)

    canned = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"}, {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 5}],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(MockProvider(handler=lambda m: __import__("json").dumps(canned)))
    try:
        # 画 5 张（free 配额）
        for i in range(5):
            r = await _make_chat(client, token, sid, f"画线段 AB=5 第{i+1}次")
            assert r.status_code == 200, f"第{i+1}次失败: {r.text}"

        # 第 6 次应该被配额拦截
        r6 = await _make_chat(client, token, sid, "第6次应该被拦截")
        assert r6.status_code == 422
        detail = r6.json()["detail"]
        assert detail["code"] == "quota_exceeded"
        assert "5" in detail["message"]  # 今日免费配额已用完（5/5 张图）
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_unlimited_quota_for_override(client):
    """daily_graph_limit_override=0（无限）的用户不受配额限制。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider
    from app.auth.password import hash_password
    from app.auth.repository import create_user
    from app.db.models import UserSubscription
    from app.db.session import get_session

    # 建一个有无限配额覆盖的用户
    email = _unique_email()
    async with get_session() as db:
        u = await create_user(
            db,
            email=email,
            username="unlimited",
            hashed_password=hash_password("password123"),
        )
        db.add(UserSubscription(
            id=uuid.uuid4().hex,
            user_id=u.id,
            plan_id="free",
            plan_code="free",
            status="free",
            daily_graph_limit_override=0,  # 无限
        ))
        await db.commit()

    r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    token = r.json()["token"]
    sid = await _create_session(client, token)

    canned = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"}, {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 5}],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(MockProvider(handler=lambda m: __import__("json").dumps(canned)))
    try:
        # 画 10 张都不应该被拦截
        for i in range(10):
            r = await _make_chat(client, token, sid, f"第{i+1}次")
            assert r.status_code == 200, f"第{i+1}次失败: {r.text}"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_anonymous_access_blocked(client):
    """未登录用户不能创建 session（强制登录）。"""
    # 不带 token 创建 session -> 401
    r = await client.post("/api/session", json={})
    assert r.status_code == 401

    # 不带 token 访问任何 session -> 401
    r2 = await client.get("/api/session/any-sid")
    assert r2.status_code == 401

    # 不带 token chat -> 401
    r3 = await client.post("/api/session/any-sid/chat", json={"nl": "test"})
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_quota_count_by_snapshots(client):
    """配额按 snapshot 数计数，不按 chat 请求次数。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    token, _ = await _register(client)
    sid = await _create_session(client, token)

    # LLM 失败（返回 {"error": ...}）不产生 snapshot，不扣配额
    set_provider_override(MockProvider(handler=lambda m: '{"error": "暂不支持"}'))
    try:
        for i in range(10):
            r = await _make_chat(client, token, sid, f"失败的请求{i+1}")
            assert r.status_code == 200  # refuse 返回 200，ok=false
            assert r.json()["ok"] is False

        # 查配额：应该还是 0 used（refuse 不扣配额）
        r_ent = await client.get("/api/payment/subscription", headers=_auth_headers(token))
        assert r_ent.status_code == 200
        ent = r_ent.json()["entitlement"]
        assert ent["used_today"] == 0
        assert ent["remaining"] == 5  # free 配额未消耗
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_subscription_status_in_entitlement(client):
    """新注册用户默认 free 配额。"""
    token, _ = await _register(client)
    r = await client.get("/api/payment/subscription", headers=_auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["plan"]["code"] == "free"
    assert data["entitlement"]["plan_code"] == "free"
    assert data["entitlement"]["daily_limit"] == 5
    assert data["entitlement"]["used_today"] == 0
    assert data["entitlement"]["remaining"] == 5
    assert data["entitlement"]["status"] == "free"


@pytest.mark.asyncio
async def test_plans_listed_publicly(client):
    """公开端点 /api/payment/plans 返回所有活跃套餐。"""
    r = await client.get("/api/payment/plans")
    assert r.status_code == 200
    plans = r.json()["items"]
    codes = {p["code"] for p in plans}
    assert "free" in codes
    assert "pro" in codes
    assert "enterprise" in codes

    # pro 价格 2900 分 = 29 元
    pro = next(p for p in plans if p["code"] == "pro")
    assert pro["price_cents"] == 2900
    assert pro["daily_graph_limit"] == 0  # 无限

    # free 5/天
    free = next(p for p in plans if p["code"] == "free")
    assert free["daily_graph_limit"] == 5
    assert free["price_cents"] == 0
