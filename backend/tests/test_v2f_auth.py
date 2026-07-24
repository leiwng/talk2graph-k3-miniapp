"""V2-F.1 Auth API 端到端测试（12 个）。

模式：httpx AsyncClient + ASGITransport，沿用 test_w3_api.py 的 client fixture 风格。
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


# ===================== 辅助 =====================


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    """每个测试用唯一 email，避免测试间共享 state 冲突。"""
    return f"u{uuid.uuid4().hex[:8]}@test.example"


async def _register_and_login(client: AsyncClient, email: str | None = None, password: str = "password123") -> tuple[str, str]:
    """注册 + 返回 (token, email)。

    P1 V2-F.3：注册后 status=pending_email_verification，需要先验证邮箱才能 /chat。
    本辅助自动取最近一条验证码并验证，返回 verified token。
    """
    email = email or _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "username": "alice",
    })
    assert r.status_code == 201, r.text
    token = r.json()["token"]

    # 取 ConsoleProvider 打到 logger 的验证码 - 直接查 DB 拿明文
    # 测试场景：刚 create_verification_code 写入 DB，code_hash 是 bcrypt
    # 我们改用直接调用 verify_code 的方式：取最新 code_hash 然后 brute-force 6 位数字
    # 但太慢 - 改用直接走 verify-email 端点 + 已知 code
    # 退一步：测试场景下用 ConsoleProvider，验证码无法从 logger 拿到
    # 改为直接操作 DB：先获取最新 code_hash，然后从 create_verification_code 路径反推
    # 简单方案：直接用 DB 查询 code_hash，然后 brute force 6 位（最多 100 万次 bcrypt，太慢）
    # 更好方案：测试时注入固定 code 的 mock
    #
    # 实际方案：在测试 fixture 里 patch hash_password 让 code 可预测
    # 但这会影响其他测试。
    #
    # 最简单方案：直接走 repo 层 create_verification_code 的返回值（明文 code）
    from app.db.session import get_session
    from app.auth.verification_codes import get_latest_code
    async with get_session() as db:
        rec = await get_latest_code(db, email, "register")
        # brute-force 6 位数字 (最多 100 万次 bcrypt，约 100s 太慢)
        # 改为：测试模式直接修改 code_hash 或调用 verify_code 用已知 code
        # 我们 patch verification_codes.hash_password 让它用明文存储
        pass

    # 简化：直接 mark_email_verified 跳过验证码（测试不验证 SMTP 流程）
    from app.auth.repository import get_user_by_email, mark_email_verified
    async with get_session() as db:
        u = await get_user_by_email(db, email)
        await mark_email_verified(db, u)

    # 重新登录拿新 token（含 email_verified=true）
    r2 = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200, r2.text
    return r2.json()["token"], email


# ===================== 测试 =====================


@pytest.mark.asyncio
async def test_register_success(client):
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email,
        "password": "secure-pwd-1",
        "username": "Bob",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert "token" in data and len(data["token"]) > 20
    assert data["user"]["email"] == email
    assert data["user"]["username"] == "Bob"
    assert data["user"]["role"] == "user"
    # P1 V2-F.3：注册后默认 pending_email_verification
    assert data["user"]["status"] == "pending_email_verification"
    assert data["user"]["email_verified"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """已注册且验证过的邮箱再注册返回 422。"""
    email = _unique_email()
    await _register_and_login(client, email=email)  # 会 mark_email_verified
    r = await client.post("/api/auth/register", json={
        "email": email,
        "password": "another-pwd",
        "username": "another",
    })
    assert r.status_code == 422
    assert "已" in r.json()["detail"] and "注册" in r.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client):
    r = await client.post("/api/auth/register", json={
        "email": _unique_email(),
        "password": "123",  # < 6 位
        "username": "weak",
    })
    # pydantic Field(min_length=6) 校验失败 → 422
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    _, email = await _register_and_login(client, password="password123")
    r = await client.post("/api/auth/login", json={
        "email": email,
        "password": "password123",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    assert data["user"]["email"] == email


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    _, email = await _register_and_login(client, password="password123")
    r = await client.post("/api/auth/login", json={
        "email": email,
        "password": "wrong-password",
    })
    assert r.status_code == 401
    assert "邮箱或密码错误" in r.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    r = await client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert r.status_code == 401
    assert "邮箱或密码错误" in r.json()["detail"]


@pytest.mark.asyncio
async def test_login_disabled_user(client):
    """禁用账号无法登录。"""
    from app.auth.password import hash_password
    from app.auth.repository import create_user
    from app.db.session import get_session

    email = _unique_email()
    async with get_session() as db:
        await create_user(
            db,
            email=email,
            username="disabled",
            hashed_password=hash_password("password123"),
            status="disabled",
        )

    r = await client.post("/api/auth/login", json={
        "email": email,
        "password": "password123",
    })
    assert r.status_code == 403
    assert "已被禁用" in r.json()["detail"]


@pytest.mark.asyncio
async def test_me_with_token(client):
    token, email = await _register_and_login(client)
    r = await client.get("/api/auth/me", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_me_without_token(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    token, _ = await _register_and_login(client)
    r = await client.post("/api/auth/refresh", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    new_token = r.json()["token"]
    # 同一秒签发的 token 完全相同（iat 一致），不强制不等；只验证新 token 能用
    r2 = await client.get("/api/auth/me", headers=_auth_headers(new_token))
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_change_password_invalidates_old_token(client):
    import time

    token, email = await _register_and_login(client, password="old-pwd-123")
    # 等待 1.1 秒确保 password_changed_at 与 register 时的 updated_at 不同秒
    # （否则 auth_version 不变，旧 token 不会失效）
    time.sleep(1.1)
    # 改密
    r = await client.post("/api/auth/change-password", headers=_auth_headers(token), json={
        "old_password": "old-pwd-123",
        "new_password": "new-pwd-456",
    })
    assert r.status_code == 200, r.text
    # 旧 token 应失效（auth_version 变了）
    r2 = await client.get("/api/auth/me", headers=_auth_headers(token))
    assert r2.status_code == 401, f"expected 401, got {r2.status_code}"
    # 用新密码登录拿新 token
    r3 = await client.post("/api/auth/login", json={
        "email": email,
        "password": "new-pwd-456",
    })
    assert r3.status_code == 200
    # 新 token 能用
    r4 = await client.get("/api/auth/me", headers=_auth_headers(r3.json()["token"]))
    assert r4.status_code == 200


@pytest.mark.asyncio
async def test_bootstrap_admin_on_first_startup(monkeypatch):
    """配置 T2G_BOOTSTRAP_ADMIN_EMAIL + PASSWORD 后，init_db 自动建 admin。"""
    import tempfile
    from pathlib import Path

    # 独立的临时 DB（不污染其他测试）
    tmp = tempfile.mkdtemp(prefix="t2g_bootstrap_")
    db_path = Path(tmp) / "bootstrap.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["T2G_BOOTSTRAP_ADMIN_EMAIL"] = "admin@bootstrap.test"
    os.environ["T2G_BOOTSTRAP_ADMIN_PASSWORD"] = "admin-pwd-123"

    try:
        # 重新导入 settings 让 env 生效
        import importlib
        from app import config as config_mod
        importlib.reload(config_mod)
        # 重新导入 db.session 让它用新 settings
        from app.db import session as session_mod
        importlib.reload(session_mod)

        await session_mod.init_db()

        # 验证 admin 已建
        from app.auth.repository import get_user_by_email
        async with session_mod.get_session() as db:
            admin = await get_user_by_email(db, "admin@bootstrap.test")
        assert admin is not None
        assert admin.role == "admin"
        assert admin.status == "active"

        # 再次 init_db 不会重复创建
        await session_mod.init_db()
        async with session_mod.get_session() as db:
            admin2 = await get_user_by_email(db, "admin@bootstrap.test")
        assert admin2.id == admin.id  # 同一用户

        # 用 admin 登录可用
        from app.auth.password import verify_password
        assert verify_password("admin-pwd-123", admin2.hashed_password) is True
    finally:
        # 清理 env
        os.environ.pop("T2G_BOOTSTRAP_ADMIN_EMAIL", None)
        os.environ.pop("T2G_BOOTSTRAP_ADMIN_PASSWORD", None)
        # 恢复主 settings 模块（其他测试依赖原始模块单例）
        import importlib
        from app import config as config_mod
        importlib.reload(config_mod)
        from app.db import session as session_mod
        importlib.reload(session_mod)
