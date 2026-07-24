"""V3.5 Admin 批量操作测试（5 个）。

覆盖：
- 批量启用 / 禁用
- 批量配额覆盖
- 批量设置订阅
- 不能 disable 自己保护
- 超过 100 个返回 400
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
    tmp = tempfile.mkdtemp(prefix="t2g_v35_batch_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db, override_database_url
    from app.main import create_app

    tmp = tempfile.mkdtemp(prefix="t2g_v35_test_")
    db_path = Path(tmp) / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url
    override_database_url(url)

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 预建 admin 用户
        from app.auth.password import hash_password
        from app.auth.repository import create_user, mark_email_verified
        from app.db.session import get_session
        async with get_session() as db:
            try:
                u = await create_user(
                    db,
                    email="v35admin@example.com",
                    username="v35admin",
                    hashed_password=hash_password("admin-pwd-123"),
                    role="admin",
                    status="active",
                )
                await mark_email_verified(db, u)
            except Exception:
                pass
        yield c


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login_admin(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={
        "email": "v35admin@example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


async def _create_normal_user(client: AsyncClient) -> str:
    """建普通用户，返回 user_id。"""
    from app.auth.password import hash_password
    from app.auth.repository import create_user, mark_email_verified
    from app.db.session import get_session

    email = f"v35-{uuid.uuid4().hex[:8]}@example.com"
    async with get_session() as db:
        u = await create_user(
            db,
            email=email,
            username="normal",
            hashed_password=hash_password("password123"),
            role="user",
            status="active",
        )
        await mark_email_verified(db, u)
        return u.id


@pytest.mark.asyncio
async def test_batch_disable_users(client):
    """admin 批量禁用 3 个用户。"""
    admin_token = await _login_admin(client)
    user_ids = [await _create_normal_user(client) for _ in range(3)]

    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={"user_ids": user_ids, "action": "disable"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["affected"] == 3
    assert data["skipped"] == 0

    # 验证：用户都被禁用了
    for uid in user_ids:
        r2 = await client.get(f"/api/admin/users/{uid}", headers=_auth_headers(admin_token))
        assert r2.json()["user"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_batch_enable_users(client):
    """admin 批量启用用户。"""
    admin_token = await _login_admin(client)
    user_ids = [await _create_normal_user(client) for _ in range(2)]

    # 先禁用
    await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={"user_ids": user_ids, "action": "disable"},
    )
    # 再启用
    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={"user_ids": user_ids, "action": "enable"},
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 2


@pytest.mark.asyncio
async def test_batch_set_quota(client):
    """admin 批量设置配额覆盖。"""
    admin_token = await _login_admin(client)
    user_ids = [await _create_normal_user(client) for _ in range(3)]

    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={
            "user_ids": user_ids,
            "action": "set_quota",
            "payload": {"daily_graph_limit_override": 50},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["affected"] == 3

    # 验证
    r2 = await client.get(f"/api/admin/users/{user_ids[0]}", headers=_auth_headers(admin_token))
    assert r2.json()["subscription"]["daily_graph_limit_override"] == 50


@pytest.mark.asyncio
async def test_batch_set_subscription(client):
    """admin 批量设置订阅。"""
    admin_token = await _login_admin(client)
    user_ids = [await _create_normal_user(client) for _ in range(2)]

    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={
            "user_ids": user_ids,
            "action": "set_subscription",
            "payload": {"plan_code": "pro", "period_days": 30},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["affected"] == 2

    # 验证
    r2 = await client.get(f"/api/admin/users/{user_ids[0]}", headers=_auth_headers(admin_token))
    assert r2.json()["subscription"]["plan_code"] == "pro"


@pytest.mark.asyncio
async def test_batch_cannot_disable_self(client):
    """不能在批量操作中 disable 自己。"""
    admin_token = await _login_admin(client)
    me = await client.get("/api/auth/me", headers=_auth_headers(admin_token))
    admin_id = me.json()["id"]
    other_id = await _create_normal_user(client)

    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={"user_ids": [admin_id, other_id], "action": "disable"},
    )
    assert r.status_code == 400
    assert "自己" in r.json()["detail"]


@pytest.mark.asyncio
async def test_batch_limit_100(client):
    """超过 100 个返回 400。"""
    admin_token = await _login_admin(client)
    # 构造 101 个假 id
    fake_ids = [uuid.uuid4().hex for _ in range(101)]

    r = await client.post(
        "/api/admin/users/batch",
        headers=_auth_headers(admin_token),
        json={"user_ids": fake_ids, "action": "disable"},
    )
    # 101 个 id 走 pydantic Field(max_length=100) 校验
    assert r.status_code == 422
