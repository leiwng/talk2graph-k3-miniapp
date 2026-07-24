"""V2-F.1 审计日志测试（5 个）。"""
from __future__ import annotations

import asyncio
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
        # 在 init_db 后直接建一个 admin 用户（绕开 env bootstrap）
        from app.auth.password import hash_password
        from app.auth.repository import create_user, mark_email_verified
        from app.db.session import get_session

        async with get_session() as db:
            try:
                u = await create_user(
                    db,
                    email="admin@audit-test.example.com",
                    username="admin",
                    hashed_password=hash_password("admin-pwd-123"),
                    role="admin",
                    status="active",
                )
                # P1 V2-F.3：测试场景跳过邮箱验证
                await mark_email_verified(db, u)
            except Exception:
                pass  # 已存在则跳过
        yield c


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"audit-{uuid.uuid4().hex[:8]}@test.example"


async def _register(client: AsyncClient, email: str | None = None) -> tuple[str, str]:
    email = email or _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "alice",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"], email


async def _admin_token(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={
        "email": "admin@audit-test.example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.mark.asyncio
async def test_audit_create_and_list(client):
    """注册 → 审计写入一条；admin 查询能拿到。"""
    admin_token = await _admin_token(client)

    # 普通用户注册（触发审计写入）
    _, user_email = await _register(client)

    # admin 查询审计日志
    r2 = await client.get("/api/audit-log", headers=_auth_headers(admin_token))
    assert r2.status_code == 200
    data = r2.json()
    assert data["total"] >= 1
    actions = [item["action"] for item in data["items"]]
    assert "auth.register.success" in actions

    # 过滤：只看 register
    r3 = await client.get(
        "/api/audit-log?action=auth.register.success",
        headers=_auth_headers(admin_token),
    )
    assert r3.status_code == 200
    items = r3.json()["items"]
    assert all(item["action"] == "auth.register.success" for item in items)
    assert any(item["actor_email"] == user_email for item in items)


@pytest.mark.asyncio
async def test_audit_filter_by_actor(client):
    """按 actor_id 过滤。"""
    admin_token = await _admin_token(client)
    user_token, user_email = await _register(client)

    # 从 me 拿到 user_id
    me = await client.get("/api/auth/me", headers=_auth_headers(user_token))
    user_id = me.json()["id"]

    r = await client.get(
        f"/api/audit-log?actor_id={user_id}",
        headers=_auth_headers(admin_token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(item["actor_id"] == user_id for item in items)


@pytest.mark.asyncio
async def test_audit_best_effort_does_not_block(client):
    """审计写入失败不应阻塞主流程。

    通过 monkeypatch db.commit 让它抛异常，验证 create_audit 内部 try/except 捕获。
    """
    from app.audit import repository as audit_repo
    from app.db.session import get_session

    # 用一个会抛错的 db 调用 create_audit
    class BadDB:
        def add(self, *args, **kwargs):
            return None
        async def commit(self):
            raise RuntimeError("simulated DB failure")

    # 不应抛异常
    await audit_repo.create_audit(
        BadDB(),  # type: ignore[arg-type]
        actor_id="x",
        actor_email="x@test.example",
        action="test.best_effort",
    )


@pytest.mark.asyncio
async def test_audit_chat_send_fire_and_forget(client):
    """chat.send fire-and-forget 写入审计。直接测 audit_repo.fire_and_forget。"""
    from app.audit import actions, repository as audit_repo
    from app.db.session import get_session

    task = audit_repo.fire_and_forget(
        actions.CHAT_SEND,
        actor_id="some-user-id",
        actor_email="user@test.example",
        metadata={"sid": "fake-sid", "nl_length": 42, "provider": "mock"},
    )
    assert isinstance(task, asyncio.Task)
    await task  # 等任务完成

    # 验证写入
    async with get_session() as db:
        rows, total = await audit_repo.list_logs(db, action=actions.CHAT_SEND, limit=10)
    assert total >= 1
    assert rows[0].action == actions.CHAT_SEND
    import json
    meta = json.loads(rows[0].metadata_json)
    assert meta["nl_length"] == 42


@pytest.mark.asyncio
async def test_audit_log_admin_only(client):
    """非 admin 用户访问 /api/audit-log 应 403。"""
    user_token, _ = await _register(client)
    r = await client.get("/api/audit-log", headers=_auth_headers(user_token))
    assert r.status_code == 403
