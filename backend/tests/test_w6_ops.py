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
    assert "open.bigmodel.cn" in fe.hint


def test_classify_llm_network_hint_per_provider():
    from app.api.errors import classify
    from app.llm.base import LLMError

    # 基础 provider
    assert "api.moonshot.cn" in classify(LLMError("kimi", None, "x")).hint
    assert "api.minimaxi.com" in classify(LLMError("minimax", None, "x")).hint
    assert "ark.cn-beijing.volces.com" in classify(LLMError("volcengine", None, "x")).hint
    # 多模型注册的带后缀 name（取前缀匹配厂商域名）
    assert "api.moonshot.cn" in classify(LLMError("kimi_k26", None, "x")).hint
    assert "api.moonshot.cn" in classify(LLMError("kimi_k27_code_hs", None, "x")).hint
    assert "ark.cn-beijing.volces.com" in classify(LLMError("volcengine_doubao_pro", None, "x")).hint
    assert "api.deepseek.com" in classify(LLMError("deepseek_v4_pro", None, "x")).hint


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
    """带 admin 用户的 test client。

    V2-F.1 后 /api/admin/* 要求 admin 角色，测试需带 Bearer token。
    通过 admin_token fixture 拿到 token 后注入 Authorization header。
    """
    from app.db.session import init_db, get_session
    from app.main import create_app
    from app.auth.password import hash_password
    from app.auth.repository import create_user

    app = create_app()
    await init_db()
    # 直接建 admin 用户
    async with get_session() as db:
        try:
            await create_user(
                db,
                email="w6admin@example.com",
                username="w6admin",
                hashed_password=hash_password("admin-pwd-123"),
                role="admin",
                status="active",
            )
        except Exception:
            pass  # 已存在则跳过
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_token(client):
    """登录拿 admin token，并返回 (token, auth_headers)。"""
    r = await client.post("/api/auth/login", json={
        "email": "w6admin@example.com", "password": "admin-pwd-123",
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client):
    """创建普通用户 + 登录拿 token。"""
    import uuid
    from app.auth.password import hash_password
    from app.auth.repository import create_user
    from app.db.session import get_session

    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    async with get_session() as db:
        await create_user(
            db,
            email=email,
            username="testuser",
            hashed_password=hash_password("password123"),
            role="user",
            status="active",
        )

    r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_stats_empty(client, admin_token):
    _, headers = admin_token
    r = await client.get("/api/admin/stats", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert "messages" in data
    assert "snapshots" in data
    assert "providers" in data


@pytest.mark.asyncio
async def test_admin_stats_with_activity(client, admin_token):
    """模拟一轮 chat → stats 应反映出来。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    _, headers = admin_token
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
        r = await client.post("/api/session", json={}, headers=headers)
        sid = r.json()["id"]
        await client.post(f"/api/session/{sid}/chat", json={"nl": "线段 AB 长 5"}, headers=headers)

        r = await client.get("/api/admin/stats", headers=headers)
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
async def test_chat_returns_friendly_error_on_solve_fail(client, auth_headers):
    """LLM 返回过约束的 DSL -> 求解失败 -> 友好错误。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    # AB 同时长度 3 和长度 5 - 矛盾
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
        r = await client.post("/api/session", json={}, headers=auth_headers)
        sid = r.json()["id"]
        r = await client.post(f"/api/session/{sid}/chat", json={"nl": "矛盾的指令"}, headers=auth_headers)
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["code"] == "solve_no_converge"
        assert "矛盾" in detail["message"]
    finally:
        set_provider_override(None)
