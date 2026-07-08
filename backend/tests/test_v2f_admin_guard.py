"""V2-F.1 Admin 鉴权测试（2 个）。

V2-F.1 后 /api/admin/* 要求 admin 角色。
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
    tmp = tempfile.mkdtemp(prefix="t2g_test_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db, get_session
    from app.main import create_app
    from app.auth.password import hash_password
    from app.auth.repository import create_user

    app = create_app()
    await init_db()
    # 建 admin 用户
    async with get_session() as db:
        try:
            await create_user(
                db,
                email="guard-admin@example.com",
                username="admin",
                hashed_password=hash_password("admin-pwd-123"),
                role="admin",
                status="active",
            )
        except Exception:
            pass
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"guard-{uuid.uuid4().hex[:8]}@example.com"


async def _register_normal_user(client: AsyncClient) -> str:
    """注册一个普通用户（role=user），返回 token。"""
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "user",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"]


async def _login_admin(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={
        "email": "guard-admin@example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.mark.asyncio
async def test_admin_stats_requires_admin(client):
    """普通 user 访问 /api/admin/stats 应 403。"""
    user_token = await _register_normal_user(client)
    r = await client.get("/api/admin/stats", headers=_auth_headers(user_token))
    assert r.status_code == 403
    assert "管理员" in r.json()["detail"]


@pytest.mark.asyncio
async def test_admin_with_admin_role_succeeds(client):
    """admin 角色访问 /api/admin/stats 通过。"""
    admin_token = await _login_admin(client)
    r = await client.get("/api/admin/stats", headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sessions" in data
    assert "providers" in data
