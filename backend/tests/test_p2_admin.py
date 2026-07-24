"""P2 V3.3 Admin 管理界面测试（8 个）。

覆盖：
- list_users 分页 + 搜索 + 过滤
- get_user_detail 含会话数 / 画图数 / 订阅
- update_user role（含 last-admin 保护 / 不能改自己 role）
- update_user status（不能 disable 自己）
- set_user_quota_override 配额覆盖立即生效
- set_user_subscription 直接给用户设置订阅
- list_plans + update_plan 改 daily_graph_limit
- 非 admin 用户访问 403
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
    tmp = tempfile.mkdtemp(prefix="t2g_p2_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db, override_database_url
    from app.main import create_app

    tmp = tempfile.mkdtemp(prefix="t2g_p2_test_")
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
                    email="p2admin@example.com",
                    username="p2admin",
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


def _unique_email() -> str:
    return f"p2-{uuid.uuid4().hex[:8]}@example.com"


async def _login_admin(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={
        "email": "p2admin@example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


async def _create_normal_user(client: AsyncClient, email: str | None = None) -> tuple[str, str]:
    """建普通用户，返回 (user_id, token)。"""
    from app.auth.password import hash_password
    from app.auth.repository import create_user, mark_email_verified, get_user_by_email
    from app.db.session import get_session

    email = email or _unique_email()
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
        user_id = u.id

    r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return user_id, r.json()["token"]


# ============================================================================
# 测试 1：list_users 分页 + 搜索 + 过滤
# ============================================================================


@pytest.mark.asyncio
async def test_list_users(client):
    """admin 能列出用户。"""
    admin_token = await _login_admin(client)
    await _create_normal_user(client)

    r = await client.get("/api/admin/users?limit=10", headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and "total" in data
    assert data["total"] >= 2  # admin + 普通用户


@pytest.mark.asyncio
async def test_list_users_search_by_email(client):
    """搜索 email 能过滤。"""
    admin_token = await _login_admin(client)
    email = f"searchable-{uuid.uuid4().hex[:8]}@example.com"
    await _create_normal_user(client, email=email)

    r = await client.get(
        f"/api/admin/users?search={email}",
        headers=_auth_headers(admin_token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(u["email"] == email for u in items)


# ============================================================================
# 测试 2：get_user_detail
# ============================================================================


@pytest.mark.asyncio
async def test_get_user_detail(client):
    """admin 能看用户详情。"""
    admin_token = await _login_admin(client)
    user_id, _ = await _create_normal_user(client)

    r = await client.get(f"/api/admin/users/{user_id}", headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["id"] == user_id
    assert "sessions_count" in data
    assert "snapshots_count" in data


@pytest.mark.asyncio
async def test_get_user_detail_404(client):
    """不存在的 user_id 返回 404。"""
    admin_token = await _login_admin(client)
    r = await client.get(
        "/api/admin/users/nonexistent-user-id",
        headers=_auth_headers(admin_token),
    )
    assert r.status_code == 404


# ============================================================================
# 测试 3：update_user role（last-admin 保护）
# ============================================================================


@pytest.mark.asyncio
async def test_update_user_role_to_admin(client):
    """admin 能把普通用户升为 admin。"""
    admin_token = await _login_admin(client)
    user_id, _ = await _create_normal_user(client)

    r = await client.patch(
        f"/api/admin/users/{user_id}",
        headers=_auth_headers(admin_token),
        json={"role": "admin"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_cannot_demote_last_admin(client):
    """不能把最后一个 admin 降为 user。"""
    admin_token = await _login_admin(client)
    # 用 me 拿当前 admin 的 id
    me = await client.get("/api/auth/me", headers=_auth_headers(admin_token))
    admin_id = me.json()["id"]

    r = await client.patch(
        f"/api/admin/users/{admin_id}",
        headers=_auth_headers(admin_token),
        json={"role": "user"},
    )
    # 不能改自己 role + last-admin 保护
    assert r.status_code == 400


# ============================================================================
# 测试 4：update_user status（不能 disable 自己）
# ============================================================================


@pytest.mark.asyncio
async def test_cannot_disable_self(client):
    """不能禁用自己。"""
    admin_token = await _login_admin(client)
    me = await client.get("/api/auth/me", headers=_auth_headers(admin_token))
    admin_id = me.json()["id"]

    r = await client.patch(
        f"/api/admin/users/{admin_id}",
        headers=_auth_headers(admin_token),
        json={"status": "disabled"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_disable_other_user(client):
    """能禁用其他用户。"""
    admin_token = await _login_admin(client)
    user_id, _ = await _create_normal_user(client)

    r = await client.patch(
        f"/api/admin/users/{user_id}",
        headers=_auth_headers(admin_token),
        json={"status": "disabled"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["status"] == "disabled"

    # 重新启用
    r2 = await client.patch(
        f"/api/admin/users/{user_id}",
        headers=_auth_headers(admin_token),
        json={"status": "active"},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["status"] == "active"


# ============================================================================
# 测试 5：set_user_quota_override 配额覆盖
# ============================================================================


@pytest.mark.asyncio
async def test_set_quota_override(client):
    """admin 设置 per-user 配额覆盖，立即生效。"""
    admin_token = await _login_admin(client)
    user_id, user_token = await _create_normal_user(client)

    # 设置配额为 100/天
    r = await client.put(
        f"/api/admin/users/{user_id}/quota",
        headers=_auth_headers(admin_token),
        json={"daily_graph_limit_override": 100},
    )
    assert r.status_code == 200, r.text
    assert r.json()["daily_graph_limit_override"] == 100

    # 用户查 entitlement 应反映 100
    r2 = await client.get(
        "/api/payment/subscription",
        headers=_auth_headers(user_token),
    )
    assert r2.status_code == 200
    ent = r2.json()["entitlement"]
    assert ent["daily_limit"] == 100


# ============================================================================
# 测试 6：set_user_subscription 直接给用户设置订阅
# ============================================================================


@pytest.mark.asyncio
async def test_set_user_subscription(client):
    """admin 直接给用户开 pro 套餐。"""
    admin_token = await _login_admin(client)
    user_id, user_token = await _create_normal_user(client)

    r = await client.put(
        f"/api/admin/users/{user_id}/subscription",
        headers=_auth_headers(admin_token),
        json={"plan_code": "pro", "status": "active", "period_days": 30},
    )
    assert r.status_code == 200, r.text
    assert r.json()["plan_code"] == "pro"

    # 用户查 entitlement 应反映 pro
    r2 = await client.get(
        "/api/payment/subscription",
        headers=_auth_headers(user_token),
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["plan"]["code"] == "pro"
    assert data["entitlement"]["daily_limit"] == 30  # pro = 30/天


# ============================================================================
# 测试 7：list_plans + update_plan
# ============================================================================


@pytest.mark.asyncio
async def test_list_plans(client):
    """列出所有套餐。"""
    admin_token = await _login_admin(client)
    r = await client.get("/api/admin/plans", headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    codes = {p["code"] for p in items}
    assert "free" in codes
    assert "pro" in codes
    assert "enterprise" in codes


@pytest.mark.asyncio
async def test_update_plan_daily_graph_limit(client):
    """admin 改 plan.daily_graph_limit 后用户立即生效。"""
    admin_token = await _login_admin(client)
    user_id, user_token = await _create_normal_user(client)

    # 先把用户切到 free + 移除 override
    await client.put(
        f"/api/admin/users/{user_id}/quota",
        headers=_auth_headers(admin_token),
        json={"daily_graph_limit_override": None},
    )

    # 改 free 套餐配额从 5 -> 8
    r = await client.patch(
        "/api/admin/plans/free",
        headers=_auth_headers(admin_token),
        json={"daily_graph_limit": 8},
    )
    assert r.status_code == 200, r.text
    assert r.json()["daily_graph_limit"] == 8

    # 用户查 entitlement 应反映 8
    r2 = await client.get(
        "/api/payment/subscription",
        headers=_auth_headers(user_token),
    )
    assert r2.status_code == 200
    ent = r2.json()["entitlement"]
    assert ent["daily_limit"] == 8

    # 改回 5（避免污染其他测试）
    await client.patch(
        "/api/admin/plans/free",
        headers=_auth_headers(admin_token),
        json={"daily_graph_limit": 5},
    )


# ============================================================================
# 测试 8：非 admin 用户访问返回 403
# ============================================================================


@pytest.mark.asyncio
async def test_non_admin_cannot_access(client):
    """普通用户访问 admin 端点返回 403。"""
    _, user_token = await _create_normal_user(client)
    r = await client.get("/api/admin/users", headers=_auth_headers(user_token))
    assert r.status_code == 403

    r2 = await client.get("/api/admin/plans", headers=_auth_headers(user_token))
    assert r2.status_code == 403


# ============================================================================
# 测试 9：stats 加总用户数 + 已验证邮箱数
# ============================================================================


@pytest.mark.asyncio
async def test_stats_includes_user_counts(client):
    """stats 端点返回 users + verified_users 字段。"""
    admin_token = await _login_admin(client)
    await _create_normal_user(client)  # 已验证的普通用户

    r = await client.get("/api/admin/stats?days=7", headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "users" in data
    assert "verified_users" in data
    assert data["users"] >= 2  # admin + 普通用户
    assert data["verified_users"] >= 2
