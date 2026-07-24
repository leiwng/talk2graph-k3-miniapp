"""P0 - 历史会话侧抽屉测试（6 个）。

覆盖：
- PATCH /api/session/{sid} 重命名会话
- PATCH 跨用户 404 防探测
- PATCH 空 title 400
- GET /api/sessions 返回 message_count + last_user_nl
- 首次 chat 成功后自动写入 title（取首条 NL 前 200 字）
- chat 后不覆盖用户已重命名的 title
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
    tmp = tempfile.mkdtemp(prefix="t2g_p0_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db, override_database_url
    from app.main import create_app

    # 强制每次测试用独立 db（避免并发 db lock）
    tmp = tempfile.mkdtemp(prefix="t2g_p0_test_")
    db_path = Path(tmp) / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url
    override_database_url(url)

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 预建普通用户 + enterprise 订阅（无限配额）
        from app.auth.password import hash_password
        from app.auth.repository import create_user
        from app.db.session import get_session
        from app.db.models import UserSubscription

        async with get_session() as db:
            try:
                u = await create_user(
                    db,
                    email="p0test@example.com",
                    username="p0test",
                    hashed_password=hash_password("password123"),
                    role="user",
                    status="active",
                )
                # P1 V2-F.3：测试场景跳过邮箱验证
                from app.auth.repository import mark_email_verified
                await mark_email_verified(db, u)
                db.add(UserSubscription(
                    id=uuid.uuid4().hex,
                    user_id=u.id,
                    plan_id="enterprise",
                    plan_code="enterprise",
                    status="active",
                    daily_graph_limit_override=0,
                ))
                await db.commit()
            except Exception:
                pass
        yield c


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={
        "email": "p0test@example.com", "password": "password123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _unique_email() -> str:
    return f"p0-{uuid.uuid4().hex[:8]}@example.com"


async def _register_other_user(client: AsyncClient) -> str:
    """注册另一个用户，返回 token。"""
    email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "username": "other",
    })
    assert r.status_code == 201, r.text
    return r.json()["token"]


@pytest.mark.asyncio
async def test_rename_session(client):
    """PATCH /api/session/{sid} 改 title。"""
    token = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token), json={})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r2 = await client.patch(
        f"/api/session/{sid}", headers=_auth_headers(token),
        json={"title": "我的等腰三角形"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["title"] == "我的等腰三角形"


@pytest.mark.asyncio
async def test_rename_session_cross_user_404(client):
    """跨用户重命名返回 404 防探测。"""
    token_a = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token_a), json={})
    sid = r.json()["id"]

    token_b = await _register_other_user(client)
    r2 = await client.patch(
        f"/api/session/{sid}", headers=_auth_headers(token_b),
        json={"title": "篡改"},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_rename_session_empty_title_400(client):
    """PATCH 空 title 返回 400。"""
    token = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token), json={})
    sid = r.json()["id"]

    r2 = await client.patch(
        f"/api/session/{sid}", headers=_auth_headers(token),
        json={"title": "   "},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_list_sessions_returns_message_count_and_last_nl(client):
    """GET /api/sessions 返回 message_count + last_user_nl。"""
    token = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token), json={})
    sid = r.json()["id"]

    # 添加 3 条消息：2 user + 1 assistant
    await client.post(
        f"/api/session/{sid}/feedback", headers=_auth_headers(token),
        json={"rating": "good"},
    )  # feedback 不算 message，跳过

    # 直接用 repo.add_message 加消息（不走 chat 避免触发 LLM）
    from app.db.session import get_session
    from app.session.repo import add_message
    async with get_session() as db:
        await add_message(db, sid, role="user", content="画一个等边三角形 ABC 边长为 4")
        await add_message(db, sid, role="assistant", content="{}")
        await add_message(db, sid, role="user", content="改成红色")

    r2 = await client.get("/api/sessions", headers=_auth_headers(token))
    assert r2.status_code == 200, r2.text
    items = r2.json()
    assert len(items) >= 1
    item = next(s for s in items if s["id"] == sid)
    assert item["message_count"] == 3
    # last_user_nl 应是最后一条 user 消息
    assert item["last_user_nl"] == "改成红色"


CANNED_DSL = {
    "version": "0.1",
    "objects": [
        {"id": "A", "kind": "point"},
        {"id": "B", "kind": "point"},
        {"id": "C", "kind": "point"},
        {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
        {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
        {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
    ],
    "constraints": [
        {"type": "equilateral", "polygon": "tri"},
        {"type": "length", "segment": "AB", "value": 4},
    ],
    "labels": {"A": "A", "B": "B", "C": "C"},
}


@pytest.mark.asyncio
async def test_chat_auto_writes_title(client):
    """首次 chat 成功后自动写入 title（取首条 NL 前 200 字）。"""
    import json as _json
    from app.api import chat as chat_module
    from app.llm.mock import MockProvider
    chat_module.set_provider_override(
        MockProvider(handler=lambda m: _json.dumps(CANNED_DSL, ensure_ascii=False))
    )

    token = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token), json={})
    sid = r.json()["id"]
    assert r.json()["title"] is None

    nl = "画一个边长为 4 的等边三角形 ABC"
    r2 = await client.post(
        f"/api/session/{sid}/chat", headers=_auth_headers(token),
        json={"nl": nl, "provider": None},
    )
    assert r2.status_code == 200, r2.text

    # 重新 GET session 看 title
    r3 = await client.get(f"/api/session/{sid}", headers=_auth_headers(token))
    assert r3.status_code == 200
    assert r3.json()["title"] == nl  # NL 不超过 200 字，应完整保留

    chat_module.set_provider_override(None)


@pytest.mark.asyncio
async def test_chat_does_not_overwrite_user_title(client):
    """用户已重命名 title 时，chat 后不覆盖。"""
    import json as _json
    from app.api import chat as chat_module
    from app.llm.mock import MockProvider
    chat_module.set_provider_override(
        MockProvider(handler=lambda m: _json.dumps(CANNED_DSL, ensure_ascii=False))
    )

    token = await _login(client)
    r = await client.post("/api/session", headers=_auth_headers(token), json={})
    sid = r.json()["id"]

    # 先重命名
    await client.patch(
        f"/api/session/{sid}", headers=_auth_headers(token),
        json={"title": "我的课件"},
    )

    # chat
    r2 = await client.post(
        f"/api/session/{sid}/chat", headers=_auth_headers(token),
        json={"nl": "画一个圆 O 半径为 5", "provider": None},
    )
    assert r2.status_code == 200, r2.text

    # title 应保持用户设置的值
    r3 = await client.get(f"/api/session/{sid}", headers=_auth_headers(token))
    assert r3.json()["title"] == "我的课件"

    chat_module.set_provider_override(None)
