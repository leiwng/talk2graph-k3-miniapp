"""W2: NL → DSL 抽取测试（使用 MockProvider，离线）。

覆盖三类场景：
1. 正确输出：MockProvider 直接返回合法 DSL JSON
2. 修复循环：第一次返回缺字段，repair 提示后给出正确版本
3. 错误模式：模糊指令 → {"error": ...}
4. patch 模式：基于 current_dsl 返回 ops
5. 完整 NL 集（10 题）通过校验
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.dsl import DSL
from app.llm.extractor import build_messages, extract_dsl
from app.llm.mock import MockProvider
from app.solver.engine import solve

FEWSHOTS_PATH = (
    Path(__file__).parent.parent / "app" / "llm" / "prompts" / "fewshots.jsonl"
)


# ---------------------------------------------------------------------------

def _last_user_text(messages) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


# ---------------------------------------------------------------------------

async def test_build_messages_contains_system_and_fewshots():
    msgs = build_messages("画一个等边三角形", fewshot_limit=3)
    assert msgs[0].role == "system"
    assert "话图" in msgs[0].content
    # few-shots: pairs of user/assistant
    fewshot_count = sum(1 for m in msgs[1:-1] if m.role == "user")
    assert fewshot_count >= 3
    # last is user nl
    assert msgs[-1].role == "user"
    assert "等边" in msgs[-1].content


# ---------------------------------------------------------------------------

async def test_extract_simple_equilateral():
    canned = {
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
        "annotations": [],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }

    def handler(messages):
        return json.dumps(canned, ensure_ascii=False)

    provider = MockProvider(handler=handler)
    result = await extract_dsl(provider, "画一个等边三角形 ABC 边长为 4")
    assert result.error is None
    assert result.dsl is not None
    assert result.attempts == 1
    # 求解能跑通
    sol = solve(result.dsl, seed=42)
    assert sol.residual < 1e-4


# ---------------------------------------------------------------------------

async def test_extract_with_markdown_fence():
    """LLM 用 ```json ... ``` 包了一层，仍能解析。"""
    canned = {
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "circ", "kind": "circle",
             "definition": {"type": "center_radius", "center": "O", "radius": 5}},
        ],
        "constraints": [
            {"type": "on_circle", "point": "A", "circle": "circ"},
        ],
        "labels": {"O": "O", "A": "A"},
    }
    raw = "```json\n" + json.dumps(canned, ensure_ascii=False) + "\n```"

    provider = MockProvider(handler=lambda m: raw)
    result = await extract_dsl(provider, "圆 O 半径 5，A 在圆上")
    assert result.dsl is not None
    assert result.attempts == 1


# ---------------------------------------------------------------------------

async def test_extract_repair_loop():
    """第一次输出无效 JSON，第二次给出合法版本。"""
    call_count = {"n": 0}
    good = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 7}],
        "labels": {"A": "A", "B": "B"},
    }

    def handler(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "这不是合法 JSON"
        # 第二次时，messages 应包含 repair 提示
        last_user = _last_user_text(messages)
        assert "请仔细修正" in last_user
        return json.dumps(good, ensure_ascii=False)

    provider = MockProvider(handler=handler)
    result = await extract_dsl(provider, "画线段 AB，长 7")
    assert result.dsl is not None
    assert result.attempts == 2


# ---------------------------------------------------------------------------

async def test_extract_repair_dsl_validation_fail_then_recover():
    """第一次 isoceles apex 不在顶点列表里 → repair → 修正。"""
    call_count = {"n": 0}
    bad = {
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "isoceles", "polygon": "tri", "apex": "Z"},  # Z 不存在
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }
    good = {**bad}
    good = json.loads(json.dumps(good))  # deep copy
    good["constraints"][0]["apex"] = "A"
    good["constraints"].append(
        {"type": "angle", "a": "A", "b": "B", "c": "C", "value": 70}
    )

    def handler(messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps(bad, ensure_ascii=False)
        return json.dumps(good, ensure_ascii=False)

    provider = MockProvider(handler=handler)
    result = await extract_dsl(provider, "画等腰三角形 ABC", max_repair=2)
    assert result.dsl is not None
    assert result.attempts == 2


# ---------------------------------------------------------------------------

async def test_extract_error_mode():
    provider = MockProvider(handler=lambda m: '{"error":"你的描述自相矛盾"}')
    result = await extract_dsl(provider, "画一个有 4 条边的三角形")
    assert result.dsl is None
    assert result.patch is None
    assert "自相矛盾" in (result.error or "")


# ---------------------------------------------------------------------------

async def test_extract_patch_mode():
    """已有 DSL，返回 patch。"""
    current = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 5}],
        "labels": {"A": "A", "B": "B"},
    })
    patch = {
        "ops": [
            {"op": "replace", "path": "/constraints/0/value", "value": 8},
        ],
        "rationale": "把 AB 改成 8",
    }
    provider = MockProvider(handler=lambda m: json.dumps(patch, ensure_ascii=False))
    result = await extract_dsl(provider, "把 AB 改成 8", current_dsl=current)
    assert result.patch is not None
    assert result.dsl is None
    assert result.patch["ops"][0]["value"] == 8


# ---------------------------------------------------------------------------

async def test_all_fewshots_are_valid_dsl_and_solvable():
    """所有 few-shot 示例必须自身合法 + 可求解。这是 prompt 质量的硬约束。"""
    lines = FEWSHOTS_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 10, "few-shots 至少 10 条"
    for line in lines:
        if not line.strip():
            continue
        ex = json.loads(line)
        nl = ex["nl"]
        dsl = DSL.model_validate(ex["dsl"])
        # 通过 LLM 抽取闭环（mock 返回 ex["dsl"]）
        provider = MockProvider(handler=lambda m, d=ex["dsl"]: json.dumps(d, ensure_ascii=False))
        result = await extract_dsl(provider, nl)
        assert result.dsl is not None, f"few-shot 解析失败: {nl}"
        sol = solve(result.dsl, seed=7, restarts=10)
        assert sol.residual < 1e-3, f"few-shot 求解失败 (res={sol.residual:.3e}): {nl}"


# ---------------------------------------------------------------------------

async def test_router_lists_providers():
    from app.llm.router import LLMRouter

    r = LLMRouter()
    items = r.list_available()
    names = {i["name"] for i in items}
    assert names == {"zhipu", "volcengine", "deepseek", "minimax"}
    # 默认 = env DEFAULT_PROVIDER（缺省 zhipu）
    defaults = [i for i in items if i["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] in names
