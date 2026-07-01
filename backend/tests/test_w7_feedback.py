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
    from app.db.session import init_db
    from app.main import create_app

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# error_kind 分类
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refuse_error_kind_in_message(client):
    """LLM 输出 {"error": ...} 时，assistant 消息应带 error_kind=refuse。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(
        MockProvider(handler=lambda m: json.dumps({"error": "暂不支持抛物线及其准线"}, ensure_ascii=False))
    )
    try:
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "画抛物线 y²=2x"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error_kind"] == "refuse"
        assert "抛物线" in body["raw_reason"]
        assert "话图" in body["error"]  # 产品话术

        # 消息列表里 assistant 消息应该带 error_kind
        msgs = (await client.get(f"/api/session/{sid}/messages")).json()
        last_assistant = [m for m in msgs if m["role"] == "assistant"][-1]
        assert last_assistant["error_kind"] == "refuse"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_solve_error_kind_in_message(client):
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
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "矛盾指令"})
        assert r.status_code == 422

        msgs = (await client.get(f"/api/session/{sid}/messages")).json()
        last_assistant = [m for m in msgs if m["role"] == "assistant"][-1]
        assert last_assistant["error_kind"] == "solve"
    finally:
        set_provider_override(None)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_good(client):
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
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "AB=5"})

        r = await client.post(
            f"/api/session/{sid}/feedback",
            json={"rating": "good"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rating"] == "good"
        assert body["id"] > 0

        # 列表查询
        r = await client.get("/api/admin/feedback?days=1")
        data = r.json()
        assert data["total"] >= 1
        assert data["good"] >= 1
        assert data["items"][0]["rating"] == "good"
        assert data["items"][0]["nl"] == "AB=5"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_feedback_bad_with_comment(client):
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
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "线段 AB=7"})

        r = await client.post(
            f"/api/session/{sid}/feedback",
            json={"rating": "bad", "comment": "线段画反了"},
        )
        assert r.status_code == 200

        r = await client.get("/api/admin/feedback?days=1")
        items = r.json()["items"]
        bad = [x for x in items if x["rating"] == "bad"]
        assert bad
        assert bad[0]["comment"] == "线段画反了"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_feedback_invalid_rating(client):
    r = await client.post("/api/session", json={})
    sid = r.json()["id"]
    r = await client.post(
        f"/api/session/{sid}/feedback",
        json={"rating": "love"},  # 非法
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_feedback_jsonl_export(client):
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
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "AB=3"})
        await client.post(f"/api/session/{sid}/feedback", json={"rating": "good"})

        r = await client.get("/api/admin/feedback.jsonl?days=1")
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
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持函数图像 y=2x+1 的绘制")
    assert "函数图像" in s
    assert "💡" in s


def test_refuse_message_parabola():
    from app.api.chat import _make_refuse_message

    s = _make_refuse_message("暂不支持抛物线及其准线的作图")
    assert "抛物线" in s or "圆锥曲线" in s


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
