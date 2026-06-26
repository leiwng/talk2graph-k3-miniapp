"""W3 测试：DSL diff + 会话仓库 + API 端到端。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# 必须在 import app.* 之前设置 DB URL
@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_test_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


from app.dsl import DSL, DSLPatchError, apply_patch


# ---------------------------------------------------------------------------
# 1. DSL diff
# ---------------------------------------------------------------------------

def _base_dsl() -> DSL:
    return DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 5}],
        "labels": {"A": "A", "B": "B"},
    })


def test_patch_replace_constraint_value():
    dsl = _base_dsl()
    new = apply_patch(dsl, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 8}
    ]})
    assert new.constraints[0].value == 8
    # 原对象不变
    assert dsl.constraints[0].value == 5


def test_patch_add_point_and_segment():
    dsl = _base_dsl()
    new = apply_patch(dsl, {"ops": [
        {"op": "add", "path": "/objects/-", "value": {"id": "C", "kind": "point"}},
        {"op": "add", "path": "/objects/-", "value": {
            "id": "AC", "kind": "segment", "a": "A", "b": "C"
        }},
        {"op": "add", "path": "/constraints/-", "value": {
            "type": "length", "segment": "AC", "value": 3
        }},
    ]})
    assert any(o.id == "C" for o in new.objects)
    assert len(new.constraints) == 2


def test_patch_remove_constraint():
    dsl = _base_dsl()
    new = apply_patch(dsl, {"ops": [{"op": "remove", "path": "/constraints/0"}]})
    assert new.constraints == []


def test_patch_invalid_path():
    dsl = _base_dsl()
    with pytest.raises(DSLPatchError):
        apply_patch(dsl, {"ops": [{"op": "replace", "path": "/nope/0", "value": 1}]})


def test_patch_results_in_invalid_dsl():
    dsl = _base_dsl()
    # 删除 A 点 — segment AB 会变野
    with pytest.raises(DSLPatchError):
        apply_patch(dsl, {"ops": [{"op": "remove", "path": "/objects/0"}]})


def test_patch_replace_into_dict_label():
    dsl = _base_dsl()
    new = apply_patch(dsl, {"ops": [
        {"op": "replace", "path": "/labels/A", "value": "甲"}
    ]})
    assert new.labels["A"] == "甲"


# ---------------------------------------------------------------------------
# 2. 会话仓库：undo/redo
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    from app.db.session import init_db, get_session
    await init_db()
    async with get_session() as s:
        yield s


@pytest.mark.asyncio
async def test_session_create_and_snapshots(db):
    from app.session import repo

    s = await repo.create_session(db, llm_provider="zhipu", title="测试会话")
    sid = s.id

    d1 = _base_dsl()
    snap1 = await repo.push_snapshot(db, sid, d1, solution={"residual": 0.0})
    assert snap1.seq == 1

    # 修改一次
    d2 = apply_patch(d1, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 10}
    ]})
    snap2 = await repo.push_snapshot(db, sid, d2)
    assert snap2.seq == 2

    cur = await repo.current_snapshot(db, sid)
    assert cur.seq == 2
    assert cur.dsl.constraints[0].value == 10


@pytest.mark.asyncio
async def test_undo_redo_flow(db):
    from app.session import repo

    s = await repo.create_session(db)
    sid = s.id
    d1 = _base_dsl()
    await repo.push_snapshot(db, sid, d1)
    d2 = apply_patch(d1, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 8}
    ]})
    await repo.push_snapshot(db, sid, d2)
    d3 = apply_patch(d2, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 12}
    ]})
    await repo.push_snapshot(db, sid, d3)

    # current = 3
    cur = await repo.current_snapshot(db, sid)
    assert cur.seq == 3 and cur.dsl.constraints[0].value == 12

    # undo -> seq 2
    u = await repo.undo(db, sid)
    assert u.seq == 2 and u.dsl.constraints[0].value == 8

    # undo -> seq 1
    u = await repo.undo(db, sid)
    assert u.seq == 1 and u.dsl.constraints[0].value == 5

    # redo -> seq 2
    r = await repo.redo(db, sid)
    assert r.seq == 2 and r.dsl.constraints[0].value == 8

    # 在 seq=2 push 新 → 截断 seq=3
    d4 = apply_patch(u.dsl, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 99}
    ]})
    # 这里 u 还指向 seq=1，应当从 current（=2）派生
    cur = await repo.current_snapshot(db, sid)
    assert cur.seq == 2
    d4 = apply_patch(cur.dsl, {"ops": [
        {"op": "replace", "path": "/constraints/0/value", "value": 99}
    ]})
    new = await repo.push_snapshot(db, sid, d4)
    assert new.seq == 3
    # 不能再 redo
    r2 = await repo.redo(db, sid)
    assert r2 is None
    hist = await repo.history(db, sid)
    assert hist == [1, 2, 3]


# ---------------------------------------------------------------------------
# 3. API 端到端（Mock LLM）
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db
    from app.main import create_app

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_api_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_api_providers(client):
    r = await client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    names = [p["name"] for p in data["providers"]]
    assert "zhipu" in names and "volcengine" in names and "deepseek" in names
    # default 取决于 env DEFAULT_PROVIDER；只要在三家之一即可
    assert data["default"] in names


@pytest.mark.asyncio
async def test_api_chat_full_flow(client):
    """完整流程：创建会话 → chat（mock LLM 返回 DSL）→ 求解 → 渲染 → undo → redo → export.svg。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    canned_v1 = {
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
    # 第二轮是 patch：把边长改成 6
    canned_patch = {
        "ops": [{"op": "replace", "path": "/constraints/1/value", "value": 6}],
        "rationale": "把边长改成 6",
    }

    call = {"n": 0}

    def handler(messages):
        call["n"] += 1
        if call["n"] == 1:
            return json.dumps(canned_v1, ensure_ascii=False)
        return json.dumps(canned_patch, ensure_ascii=False)

    set_provider_override(MockProvider(handler=handler))
    try:
        # 创建会话
        r = await client.post("/api/session", json={"llm_provider": "mock"})
        assert r.status_code == 200
        sid = r.json()["id"]

        # 第一轮：完整 DSL
        r = await client.post(f"/api/session/{sid}/chat",
                              json={"nl": "画一个等边三角形 边长 4"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["seq"] == 1
        assert "<svg" in body["svg"]
        assert body["solution"]["residual"] < 1e-4
        assert body["solution"]["coordinates"]["A"]

        # 第二轮：patch
        r = await client.post(f"/api/session/{sid}/chat",
                              json={"nl": "把边长改成 6"})
        assert r.status_code == 200, r.text
        body2 = r.json()
        assert body2["seq"] == 2
        assert body2["dsl"]["constraints"][1]["value"] == 6

        # 获取当前 DSL
        r = await client.get(f"/api/session/{sid}/dsl")
        assert r.json()["seq"] == 2

        # 历史
        r = await client.get(f"/api/session/{sid}/history")
        assert r.json()["seqs"] == [1, 2]

        # 撤销
        r = await client.post(f"/api/session/{sid}/undo")
        assert r.json()["seq"] == 1
        assert r.json()["dsl"]["constraints"][1]["value"] == 4

        # 重做
        r = await client.post(f"/api/session/{sid}/redo")
        assert r.json()["seq"] == 2

        # 导出 SVG
        r = await client.get(f"/api/export/{sid}.svg")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg")
        assert b"<svg" in r.content

        # 消息历史
        r = await client.get(f"/api/session/{sid}/messages")
        msgs = r.json()
        # 2 user + 2 assistant
        assert len(msgs) == 4
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant", "user", "assistant"]

        # 删除会话
        r = await client.delete(f"/api/session/{sid}")
        assert r.status_code == 200
        r = await client.get(f"/api/session/{sid}")
        assert r.status_code == 404

    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_api_direct_patch(client):
    """属性面板：不走 LLM，直接 POST /patch。"""
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
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "线段 AB 长 5"})
        assert r.json()["seq"] == 1

        # 属性面板：改长度
        r = await client.post(
            f"/api/session/{sid}/patch",
            json={"ops": [{"op": "replace", "path": "/constraints/0/value", "value": 11}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["seq"] == 2
        # 实际坐标体现
        coords = body["solution"]["coordinates"]
        import math
        d = math.hypot(coords["A"][0] - coords["B"][0],
                       coords["A"][1] - coords["B"][1])
        assert abs(d - 11) < 1e-3
    finally:
        set_provider_override(None)
