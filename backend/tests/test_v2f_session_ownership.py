"""V2-F.1 Session 归属校验测试（4 个）。

V2-F.1 后：登录用户只能访问自己的 session（404 而非 403，防探测）；
匿名 session（user_id=anonymous）任何人持 sid 可访问（保留试用体验）。
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
    return f"own-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "alice",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"], email


@pytest.mark.asyncio
async def test_session_owned_by_user(client):
    """用户 A 创建的 session，A 能访问。"""
    token_a, _ = await _register(client)
    r = await client.post("/api/session", headers=_auth_headers(token_a), json={})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    # A 自己访问
    r2 = await client.get(f"/api/session/{sid}", headers=_auth_headers(token_a))
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_session_cross_user_404(client):
    """用户 B 访问 A 的 session 返回 404（不是 403，防探测）。"""
    token_a, _ = await _register(client)
    r = await client.post("/api/session", headers=_auth_headers(token_a), json={})
    sid = r.json()["id"]

    token_b, _ = await _register(client)
    r2 = await client.get(f"/api/session/{sid}", headers=_auth_headers(token_b))
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_list_sessions_filtered_by_user(client):
    """GET /api/sessions 只返回当前用户的会话。"""
    token_a, _ = await _register(client)
    token_b, _ = await _register(client)
    # A 创建 2 个 session
    sid_a1 = (await client.post("/api/session", headers=_auth_headers(token_a), json={})).json()["id"]
    sid_a2 = (await client.post("/api/session", headers=_auth_headers(token_a), json={})).json()["id"]
    # B 创建 1 个 session
    sid_b1 = (await client.post("/api/session", headers=_auth_headers(token_b), json={})).json()["id"]

    # A 列表只看到自己的
    r_a = await client.get("/api/sessions", headers=_auth_headers(token_a))
    assert r_a.status_code == 200
    a_sids = {s["id"] for s in r_a.json()}
    assert sid_a1 in a_sids and sid_a2 in a_sids
    assert sid_b1 not in a_sids

    # B 列表只看到自己的
    r_b = await client.get("/api/sessions", headers=_auth_headers(token_b))
    b_sids = {s["id"] for s in r_b.json()}
    assert sid_b1 in b_sids
    assert sid_a1 not in b_sids and sid_a2 not in b_sids


@pytest.mark.asyncio
async def test_anonymous_session_accessible(client):
    """未登录用户创建的 session（user_id=anonymous）任何人持 sid 可访问。

    F.1 保留试用体验：未登录用户在落地页就能用，不需要注册。
    """
    # 未登录创建 session
    r = await client.post("/api/session", json={})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # 不带 token 也能访问
    r2 = await client.get(f"/api/session/{sid}")
    assert r2.status_code == 200

    # 登录用户也能访问（虽然不是自己的）
    token, _ = await _register(client)
    r3 = await client.get(f"/api/session/{sid}", headers=_auth_headers(token))
    assert r3.status_code == 200  # anonymous session 不做归属校验
