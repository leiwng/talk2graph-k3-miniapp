"""W7：error_kind 分类 + Feedback API + 拒绝消息友好化。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_w7_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    """V2-F.1 后 /api/admin/* 要求 admin token，fixture 内预建 admin 用户。"""
    from app.db.session import init_db, get_session
    from app.main import create_app
    from app.auth.password import hash_password
    from app.auth.repository import create_user, mark_email_verified

    app = create_app()
    await init_db()
    async with get_session() as db:
        try:
            u = await create_user(
                db,
                email="w7admin@example.com",
                username="w7admin",
                hashed_password=hash_password("admin-pwd-123"),
                role="admin",
                status="active",
            )
            # P1 V2-F.3：测试场景跳过邮箱验证
            await mark_email_verified(db, u)
        except Exception:
            pass
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_headers(client):
    """登录拿 admin token，返回 headers dict。"""
    r = await client.post("/api/auth/login", json={
        "email": "w7admin@example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client):
    """创建普通用户 + 登录拿 token。"""
    import uuid
    from app.auth.password import hash_password
    from app.auth.repository import create_user, mark_email_verified
    from app.db.session import get_session

    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    async with get_session() as db:
        u = await create_user(
            db,
            email=email,
            username="testuser",
            hashed_password=hash_password("password123"),
            role="user",
            status="active",
        )
        # P1 V2-F.3：测试场景跳过邮箱验证
        await mark_email_verified(db, u)

    r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# error_kind 分类
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refuse_error_kind_in_message(client, auth_headers):
    """LLM 输出 {"error": ...} 时，assistant 消息应带 error_kind=refuse。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(
        MockProvider(handler=lambda m: json.dumps({"error": "暂不支持抛物线及其准线"}, ensure_ascii=False))
    )
    try:
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "画抛物线 y²=2x"}, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error_kind"] == "refuse"
        assert "抛物线" in body["raw_reason"]
        assert "话图" in body["error"]  # 产品话术

        # 消息列表里 assistant 消息应该带 error_kind
        msgs = (await client.get(f"/api/session/{sid}/messages", headers=auth_headers)).json()
        last_assistant = [m for m in msgs if m["role"] == "assistant"][-1]
        assert last_assistant["error_kind"] == "refuse"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_solve_error_kind_in_message(client, auth_headers):
    """求解失败时，message.error_kind = solve。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    contradictory = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 3},
            {"type": "length", "segment": "AB", "value": 5},
        ],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(
        MockProvider(handler=lambda m: json.dumps(contradictory, ensure_ascii=False))
    )
    try:
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "矛盾指令"}, headers=auth_headers)
        assert r.status_code == 422

        msgs = (await client.get(f"/api/session/{sid}/messages", headers=auth_headers)).json()
        last_assistant = [m for m in msgs if m["role"] == "assistant"][-1]
        assert last_assistant["error_kind"] == "solve"
    finally:
        set_provider_override(None)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_good(client, auth_headers, admin_headers):
    """成功画图后老师点 👍。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    canned = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 5}],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(MockProvider(handler=lambda m: json.dumps(canned, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "AB=5"}, headers=auth_headers)

        r = await client.post(
            f"/api/session/{sid}/feedback",
            json={"rating": "good"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rating"] == "good"
        assert body["id"] > 0

        # 列表查询
        r = await client.get("/api/admin/feedback?days=1", headers=admin_headers)
        data = r.json()
        assert data["total"] >= 1
        assert data["good"] >= 1
        assert data["items"][0]["rating"] == "good"
        assert data["items"][0]["nl"] == "AB=5"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_feedback_bad_with_comment(client, auth_headers, admin_headers):
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    canned = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 7}],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(MockProvider(handler=lambda m: json.dumps(canned, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "线段 AB=7"}, headers=auth_headers)

        r = await client.post(
            f"/api/session/{sid}/feedback",
            json={"rating": "bad", "comment": "线段画反了"},
            headers=auth_headers,
        )
        assert r.status_code == 200

        r = await client.get("/api/admin/feedback?days=1", headers=admin_headers)
        items = r.json()["items"]
        bad = [x for x in items if x["rating"] == "bad"]
        assert bad
        assert bad[0]["comment"] == "线段画反了"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_feedback_invalid_rating(client, auth_headers):
    r = await client.post("/api/session", json={}, headers=auth_headers)
    sid = r.json()["id"]
    r = await client.post(
        f"/api/session/{sid}/feedback",
        json={"rating": "love"},  # 非法
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_feedback_jsonl_export(client, auth_headers, admin_headers):
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    canned = {
        "version": "0.1",
        "objects": [{"id": "A", "kind": "point"}, {"id": "B", "kind": "point"},
                    {"id": "AB", "kind": "segment", "a": "A", "b": "B"}],
        "constraints": [{"type": "length", "segment": "AB", "value": 3}],
        "labels": {"A": "A", "B": "B"},
    }
    set_provider_override(MockProvider(handler=lambda m: json.dumps(canned, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "AB=3"}, headers=auth_headers)
        await client.post(f"/api/session/{sid}/feedback", json={"rating": "good"}, headers=auth_headers)

        r = await client.get("/api/admin/feedback.jsonl?days=1", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/x-ndjson")
        lines = [l for l in r.text.strip().split("\n") if l]
        assert lines
        parsed = json.loads(lines[0])
        assert parsed["rating"] in ("good", "bad")
    finally:
        set_provider_override(None)


# ---------------------------------------------------------------------------
# Refuse message friendly formatter
# ---------------------------------------------------------------------------

def test_refuse_message_function_image():
    """V2-B 起函数图像已支持。若 LLM 出于其它原因给出 refuse，
    _make_refuse_message 会走通用头部（含"函数图像"能力描述）。"""
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("这个题描述太复杂，暂不支持")
    # 通用头部应当声明我们支持函数图像
    assert "函数图像" in s
    assert "💡" in s


def test_refuse_message_ellipse_hyperbola():
    """V2-B：椭圆 / 双曲线 一般式（隐式）仍拒。"""
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持椭圆 x²/9+y²/4=1 的绘制")
    assert "椭圆" in s or "双曲线" in s or "隐式" in s


def test_refuse_message_3d():
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持立体几何（四棱锥）作图")
    assert "立体几何" in s


def test_refuse_message_chart():
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持柱状图等统计图表")
    assert "统计图表" in s


def test_refuse_message_coord():
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持基于坐标 A(2,3) 的描述")
    assert "坐标" in s


# W11: 几何变换已支持，原本的 transform_rotate/transform_reflect 拒绝测试已删除。
# 变换现在走正常 DSL 路径（transformed_polygon / transformed_point），不再触发 refuse。
