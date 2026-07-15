"""V2-D 测试：SSE 流式 chat。

覆盖：
- 完整成功路径：stage 事件按顺序发出 + done 含 svg/dsl/solution
- LLM 拒绝路径：refuse 时直接 done(ok=false)
- LLM 网络错误：error 事件
- solve_fail 路径：error 事件含 solve 诊断
- patch 模式：stage=patch 出现
"""
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
    tmp = tempfile.mkdtemp(prefix="t2g_v2d_")
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
        # V2-F.2: 预建普通用户 + enterprise 订阅（无限配额，避免测试间 quota 超限）
        from app.auth.password import hash_password
        from app.auth.repository import create_user, get_user_by_email
        from app.db.session import get_session
        from app.db.models import UserSubscription
        import uuid

        async with get_session() as db:
            try:
                u = await create_user(
                    db,
                    email="v2dtest@example.com",
                    username="v2dtest",
                    hashed_password=hash_password("password123"),
                    role="user",
                    status="active",
                )
                # 给测试用户 enterprise 配额（无限），避免 9 个测试累计超 free 5/天
                db.add(UserSubscription(
                    id=uuid.uuid4().hex,
                    user_id=u.id,
                    plan_id="enterprise",
                    plan_code="enterprise",
                    status="active",
                    daily_graph_limit_override=0,  # 0 = 无限
                ))
                await db.commit()
            except Exception:
                pass
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """V2-F.2: 登录拿 token，返回 headers。"""
    r = await client.post("/api/auth/login", json={
        "email": "v2dtest@example.com", "password": "password123",
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """把 SSE 文本流解析成 (event, data) 列表。"""
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = ""
        data_str = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data_str = line[len("data: "):]
        if event and data_str:
            out.append((event, json.loads(data_str)))
    return out


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
async def test_stream_success_full_flow(client, auth_headers):
    """完整成功路径：每个 stage 事件按顺序发出，最终 done 含 svg。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(MockProvider(handler=lambda m: json.dumps(CANNED_DSL, ensure_ascii=False)))
    try:
        # 创建会话
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        # 调流式 chat
        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画一个等边三角形 边长 4"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)

        # stage 事件应按顺序：llm / patch / solve / render
        stage_events = [(e, d) for e, d in events if e == "stage"]
        stages = [d["stage"] for d in [data for _, data in stage_events]]
        assert stages == ["llm", "patch", "solve", "render"]

        # done 事件含 ok=true + svg
        done_events = [data for e, data in events if e == "done"]
        assert len(done_events) == 1
        done = done_events[0]
        assert done["ok"] is True
        assert "svg" in done and "<svg" in done["svg"]
        assert "dsl" in done
        assert "solution" in done
        assert done["seq"] >= 1
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_llm_refuse(client, auth_headers):
    """LLM 主动拒绝：直接 done(ok=false, error_kind=refuse)。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(MockProvider(handler=lambda m: json.dumps(
        {"error": "暂不支持立体几何"}
    )))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画一个正方体"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)
        # 应有 stage=llm + done
        stages = [data for e, data in events if e == "stage"]
        assert stages[0]["stage"] == "llm"

        done = [data for e, data in events if e == "done"]
        assert len(done) == 1
        assert done[0]["ok"] is False
        assert done[0]["error_kind"] == "refuse"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_llm_network_error(client, auth_headers):
    """LLM 网络错误：应发 error 事件。"""
    from app.api.chat import set_provider_override
    from app.llm.base import LLMError
    from app.llm.mock import MockProvider

    def fail_handler(messages):
        raise LLMError("mock", None, "Connection refused")

    set_provider_override(MockProvider(handler=fail_handler))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画一个三角形"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)
        err = [data for e, data in events if e == "error"]
        assert len(err) == 1
        assert err[0]["code"] == "llm_network"
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_solve_fail(client, auth_headers):
    """约束不一致导致 solve 失败：应发 error 事件含 solve_no_converge。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    # 故意给互斥约束：AB=3 且 AB=5（同一条边）
    bad_dsl = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 3.0},
            {"type": "length", "segment": "AB", "value": 5.0},
        ],
    }
    set_provider_override(MockProvider(handler=lambda m: json.dumps(bad_dsl, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画一条线段 AB=3 又 AB=5"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)
        err = [data for e, data in events if e == "error"]
        assert len(err) == 1
        # 互斥约束应该报 solve_no_converge 或 solve_error
        assert err[0]["code"] in ("solve_no_converge", "solve_error")
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_patch_mode(client, auth_headers):
    """patch 模式：第二轮 chat 应返回 patch 而非全量 DSL。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    canned_patch = {
        "ops": [{"op": "replace", "path": "/constraints/1/value", "value": 6}],
        "rationale": "把边长改成 6",
    }

    call = {"n": 0}

    def handler(messages):
        call["n"] += 1
        if call["n"] == 1:
            return json.dumps(CANNED_DSL, ensure_ascii=False)
        return json.dumps(canned_patch, ensure_ascii=False)

    set_provider_override(MockProvider(handler=handler))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        # 第一轮：完整 DSL
        r1 = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画等边三角形 边长 4"},
            headers=auth_headers,
        )
        events1 = _parse_sse(r1.text)
        done1 = [d for e, d in events1 if e == "done"][0]
        assert done1["ok"] is True

        # 第二轮：patch
        r2 = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "把边长改成 6"},
            headers=auth_headers,
        )
        events2 = _parse_sse(r2.text)
        done2 = [d for e, d in events2 if e == "done"][0]
        assert done2["ok"] is True
        # patch 后边长应是 6
        constraints = done2["dsl"]["constraints"]
        length_c = next(c for c in constraints if c["type"] == "length")
        assert length_c["value"] == 6
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_response_headers(client, auth_headers):
    """SSE 响应应有正确的 content-type 和缓存控制头。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(MockProvider(handler=lambda m: json.dumps(CANNED_DSL, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画一个三角形"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        assert "no-cache" in r.headers.get("cache-control", "")
    finally:
        set_provider_override(None)


# ---------------------------------------------------------------------------
# V2-D · token-level 流式新功能测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_token_events_yielded(client, auth_headers):
    """LLM 阶段应有 token 事件推送，每个 token 含 text 字段。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(MockProvider(handler=lambda m: json.dumps(CANNED_DSL, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画等边三角形 ABC"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)

        # 应有 token 事件
        token_events = [data for e, data in events if e == "token"]
        assert len(token_events) > 0, "应有 token 事件"
        # 每个 token 事件有 text 字段
        for tk in token_events:
            assert "text" in tk and isinstance(tk["text"], str)
        # token 拼起来应能恢复原始 LLM 输出
        rejoined = "".join(tk["text"] for tk in token_events)
        assert "version" in rejoined
        assert "objects" in rejoined
        assert "A" in rejoined  # 包含点 A
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_object_seen_events(client, auth_headers):
    """partial JSON 解析应识别已生成对象，推送 object_seen 事件。"""
    from app.api.chat import set_provider_override
    from app.llm.mock import MockProvider

    set_provider_override(MockProvider(handler=lambda m: json.dumps(CANNED_DSL, ensure_ascii=False)))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画等边三角形 ABC"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)

        # 应有 object_seen 事件
        obj_events = [data for e, data in events if e == "object_seen"]
        assert len(obj_events) > 0, "应有 object_seen 事件"

        # CANNED_DSL 含 7 个对象：A/B/C 点 + AB/BC/CA 线段 + tri 多边形
        ids = {(o["id"], o["kind"]) for o in obj_events}
        assert ("A", "point") in ids
        assert ("B", "point") in ids
        assert ("C", "point") in ids
        assert ("AB", "segment") in ids
        assert ("BC", "segment") in ids
        assert ("CA", "segment") in ids
        assert ("tri", "polygon") in ids

        # 每个对象只推送一次（去重）
        assert len(obj_events) == 7
    finally:
        set_provider_override(None)


@pytest.mark.asyncio
async def test_stream_llm_error_during_stream(client, auth_headers):
    """LLM 流式过程中网络断开：应发 error 事件。"""
    from app.api.chat import set_provider_override
    from app.llm.base import LLMError
    from app.llm.mock import MockProvider

    # MockProvider.chat_stream 抛错模拟 LLM 流中断
    class StreamFailProvider(MockProvider):
        async def chat_stream(self, *args, **kwargs):
            raise LLMError("mock", None, "stream broken mid-flight")
            yield  # pragma: no cover  让它是 async generator

    set_provider_override(StreamFailProvider(handler=lambda m: "ignored"))
    try:
        r = await client.post("/api/session", json={"llm_provider": "mock"}, headers=auth_headers)
        sid = r.json()["id"]

        r = await client.post(
            f"/api/session/{sid}/chat/stream",
            json={"nl": "画三角形"},
            headers=auth_headers,
        )
        events = _parse_sse(r.text)
        err = [data for e, data in events if e == "error"]
        assert len(err) == 1
        assert err[0]["code"] == "llm_network"
        assert "stream broken" in err[0]["message"] or "stream broken" in err[0].get("detail", "")
    finally:
        set_provider_override(None)


def test_extract_seen_objects_unit():
    """单元测试 _extract_seen_objects：从 LLM 部分输出中识别 (id, kind) 对。"""
    from app.llm.extractor import _extract_seen_objects

    # 空 buffer
    assert _extract_seen_objects("") == set()

    # 只有 id 还没 kind
    assert _extract_seen_objects('{"id":"A","kind":') == set()

    # id + kind 完整 → 识别成功
    s1 = '{"id":"A","kind":"point"}'
    assert _extract_seen_objects(s1) == {("A", "point")}

    # 多个对象（典型 DSL 输出片段）
    s2 = '{"version":"0.1","objects":[{"id":"A","kind":"point"},{"id":"B","kind":"point"},{"id":"AB","kind":"segment"}]}'
    assert _extract_seen_objects(s2) == {("A", "point"), ("B", "point"), ("AB", "segment")}

    # kind 在 id 之前（顺序颠倒）也能识别
    s3 = '{"kind":"point","id":"A"}'
    assert _extract_seen_objects(s3) == {("A", "point")}

    # 嵌套对象：transformed_polygon 的 source 是字符串引用，不构成干扰
    s4 = '{"id":"AB_p","kind":"transformed_polygon","source":"tri","transform":{"type":"rotation","center":"A","angle":90}}'
    assert _extract_seen_objects(s4) == {("AB_p", "transformed_polygon")}

    # 部分输出：JSON 不完整但 id+kind 已输出 → 应识别
    s5 = '{"id":"A","kind":"point","hint":null},{"id":"B","kind":"poin'
    assert _extract_seen_objects(s5) == {("A", "point")}  # B 还没写完，不识别

    # 跨对象不配对：A 的 id 和 B 的 kind 之间隔了 } 或 {，不应误配对
    s6 = '{"id":"A","kind":"point"}{"id":"B","kind":"segment"}'
    # 这里 A 配 point，B 配 segment，[^{}] 保证不跨对象
    assert _extract_seen_objects(s6) == {("A", "point"), ("B", "segment")}


def test_extract_seen_objects_no_false_match_for_constraints():
    """约束对象没有 id 字段，不应误识别。"""
    from app.llm.extractor import _extract_seen_objects

    # 约束对象：只有 type，没有 id+kind，不应匹配
    s = '{"constraints":[{"type":"length","segment":"AB","value":3}]}'
    assert _extract_seen_objects(s) == set()
