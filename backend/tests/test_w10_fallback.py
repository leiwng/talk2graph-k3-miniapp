"""W10 — patch fallback + DB schema 自动迁移 测试。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# 必须在 import app.* 之前设置 DB URL（与 test_w3_api 共用 session 范围）
@pytest.fixture(scope="module", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_w10_test_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    yield


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
# 1) DB 自动迁移
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_schema_adds_missing_column():
    """模拟旧版本 DB（没有 fallback 列）→ ensure_schema 自动 ALTER TABLE 添加。"""
    import aiosqlite

    tmp = tempfile.mkdtemp(prefix="t2g_w10_migrate_")
    db_path = Path(tmp) / "old.db"

    # 1. 用裸 SQL 建一个旧版 message 表（不含 fallback 列）
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            CREATE TABLE message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(64) NOT NULL,
                role VARCHAR(16) NOT NULL,
                content TEXT NOT NULL,
                error_kind VARCHAR(16),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()

    # 2. 用同一文件路径创建 engine，跑 ensure_schema
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.migrations import ensure_schema

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    await ensure_schema(engine)

    # 3. 验证 fallback 列已添加
    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("PRAGMA table_info(message)")
        cols = [row[1] for row in await cur.fetchall()]
    assert "fallback" in cols, f"fallback column not added. cols={cols}"

    # 4. 幂等：再跑一次不应报错
    await ensure_schema(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_schema_skips_when_table_missing():
    """目标表不存在时应跳过（不抛错）。"""
    tmp = tempfile.mkdtemp(prefix="t2g_w10_migrate_empty_")
    db_path = Path(tmp) / "empty.db"

    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.migrations import ensure_schema

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    # 空 DB；不应抛错
    await ensure_schema(engine)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 2) patch fallback
# ---------------------------------------------------------------------------

# 第一轮 LLM 返回：合法的 DSL（建立一个等边三角形）
_INIT_DSL = {
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

# 第二轮（坏 patch）：删了点 A，但 segment AB/CA 还引用它 → apply_patch 抛 patch_invalid_dsl
_BAD_PATCH = {
    "ops": [{"op": "remove", "path": "/objects/0"}],
    "rationale": "删 A（实际会破坏 DSL）",
}

# fallback 重画：边长改为 6 的等边三角形
_REDRAW_DSL = {
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
        {"type": "length", "segment": "AB", "value": 6},
    ],
    "labels": {"A": "A", "B": "B", "C": "C"},
}


@pytest.mark.asyncio
async def test_patch_fallback_succeeds(client):
    """坏 patch → 自动 fallback 为全量重画 → ok=true, fallback=true。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    call = {"n": 0}

    def handler(messages):
        call["n"] += 1
        if call["n"] == 1:
            return json.dumps(_INIT_DSL, ensure_ascii=False)
        if call["n"] == 2:
            # 第二轮：返回坏 patch（删 A）
            return json.dumps(_BAD_PATCH, ensure_ascii=False)
        # 第三轮：fallback 时 LLM 返回全量重画的 DSL
        return json.dumps(_REDRAW_DSL, ensure_ascii=False)

    set_provider_override(MockProvider(handler=handler))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"})
        sid = r.json()["id"]

        # 第一轮：建初始图
        r = await client.post(f"/api/session/{sid}/chat",
                              json={"nl": "画等边三角形 边长 4"})
        assert r.status_code == 200
        assert r.json()["fallback"] is False

        # 第二轮：触发 fallback
        r = await client.post(f"/api/session/{sid}/chat",
                              json={"nl": "边长改成 6"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["fallback"] is True
        assert body["fallback_reason"] is not None
        assert body["dsl"]["constraints"][1]["value"] == 6

        # 验证 message 表里 fallback 列被持久化
        r = await client.get(f"/api/session/{sid}/messages")
        msgs = r.json()
        assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
        # 第二轮 assistant 消息应当 fallback=True
        assert assistant_msgs[-1]["fallback"] is True
        # 第一轮 assistant 消息没走 fallback
        assert assistant_msgs[0]["fallback"] in (None, False)
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_patch_fallback_also_fails(client):
    """坏 patch + fallback 也失败（LLM 返回 error）→ 返回 422，detail 含两次错误。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    call = {"n": 0}

    def handler(messages):
        call["n"] += 1
        if call["n"] == 1:
            return json.dumps(_INIT_DSL, ensure_ascii=False)
        if call["n"] == 2:
            return json.dumps(_BAD_PATCH, ensure_ascii=False)
        # fallback 第三次：LLM refuse
        return json.dumps({"error": "fallback 测试模拟失败"}, ensure_ascii=False)

    set_provider_override(MockProvider(handler=handler))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"})
        sid = r.json()["id"]

        await client.post(f"/api/session/{sid}/chat",
                          json={"nl": "画等边三角形"})

        r = await client.post(f"/api/session/{sid}/chat",
                              json={"nl": "试图删除一个被引用的点"})
        assert r.status_code == 422
        body = r.json()
        # FastAPI 会把 dict 包成 {"detail": {...}}
        detail = body["detail"]
        assert "[fallback]" in (detail.get("detail") or ""), (
            f"detail 应当包含 [fallback] 标记: {detail}"
        )
    finally:
        set_provider_override(None)
