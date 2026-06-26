"""W6 测试：错误分类 + admin stats endpoint。"""
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
    tmp = tempfile.mkdtemp(prefix="t2g_w6_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def test_classify_llm_auth_error():
    from app.api.errors import classify
    from app.llm.base import LLMError

    fe = classify(LLMError("zhipu", 401, "Unauthorized"))
    assert fe.code == "llm_auth"
    assert "鉴权" in fe.message


def test_classify_llm_rate_limit():
    from app.api.errors import classify
    from app.llm.base import LLMError

    fe = classify(LLMError("deepseek", 429, "Too Many Requests"))
    assert fe.code == "llm_rate_limit"
    assert "频繁" in fe.message


def test_classify_llm_network_error():
    from app.api.errors import classify
    from app.llm.base import LLMError

    fe = classify(LLMError("zhipu", None, "Connection refused"))
    assert fe.code == "llm_network"


def test_classify_solve_no_converge():
    from app.api.errors import classify
    from app.solver.engine import SolveError

    fe = classify(SolveError("solver failed to converge (residual=1.2e-1)"))
    assert fe.code == "solve_no_converge"
    assert "矛盾" in fe.message


def test_classify_patch_index():
    from app.api.errors import classify
    from app.dsl.diff import DSLPatchError

    fe = classify(DSLPatchError("op[0] (replace /constraints/99): index out of range"))
    assert fe.code == "patch_index"


def test_classify_dsl_invalid():
    from app.api.errors import classify
    from app.dsl.validator import DSLValidationError

    fe = classify(DSLValidationError("isoceles.apex not a vertex of polygon"))
    assert fe.code == "dsl_invalid"


def test_classify_unknown():
    from app.api.errors import classify

    fe = classify(RuntimeError("some weird error"))
    assert fe.code == "unknown"


# ---------------------------------------------------------------------------
# Admin stats endpoint
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
async def test_admin_stats_empty(client):
    r = await client.get("/api/admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert "messages" in data
    assert "snapshots" in data
    assert "providers" in data


@pytest.mark.asyncio
async def test_admin_stats_with_activity(client):
    """模拟一轮 chat → stats 应反映出来。"""
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
        await client.post(f"/api/session/{sid}/chat", json={"nl": "线段 AB 长 5"})

        r = await client.get("/api/admin/stats")
        data = r.json()
        assert data["sessions"] >= 1
        assert data["messages"] >= 2  # 1 user + 1 assistant
        assert data["snapshots"] >= 1
    finally:
        set_provider_override(None)


# ---------------------------------------------------------------------------
# Friendly error surfaced via API (整合测试)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_returns_friendly_error_on_solve_fail(client):
    """LLM 返回过约束的 DSL → 求解失败 → 友好错误。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    # AB 同时长度 3 和长度 5 — 矛盾
    bad = {
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
    set_provider_override(MockProvider(handler=lambda m: json.dumps(bad, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={})
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "矛盾的指令"})
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["code"] == "solve_no_converge"
        assert "矛盾" in detail["message"]
    finally:
        set_provider_override(None)
