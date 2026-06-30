"""W9 — 坐标系（V2-A）端到端测试。

覆盖：
1. AxisObj schema + validator（必填项、唯一性、range/tick_step 边界）
2. 含 axis 的 DSL 求解 gauge 行为：origin 固定 (0,0)，其他点全自由
3. axis + 三角形混合：三角形几何不变量仍成立
4. render_svg 输出含坐标系核心元素（marker/text 单位标签/网格线）
5. refuse 文案在显式"画坐标系"场景已不再拦截（_make_refuse_message 仅对 A(2,3) 拒绝）
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------------------
# 1) Schema + Validator
# ---------------------------------------------------------------------------

def test_axis_schema_minimal():
    """最小可用 axis：仅原点 + axis 对象。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
        ],
        "labels": {"O": "O"},
    })
    validate(dsl)
    ax = dsl.axis()
    assert ax is not None
    assert ax.origin == "O"
    assert ax.x_range == (-5.0, 5.0)
    assert ax.y_range == (-5.0, 5.0)
    assert ax.tick_step == 1.0
    assert ax.show_grid is True


def test_axis_validator_rejects_bad_range():
    """range min >= max 应被拒。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [3, 3]},
        ],
    })
    with pytest.raises(DSLValidationError, match="x_range"):
        validate(bad)


def test_axis_validator_rejects_duplicate_axis():
    """最多 1 个 axis。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O1", "kind": "point"},
            {"id": "O2", "kind": "point"},
            {"id": "ax1", "kind": "axis", "origin": "O1"},
            {"id": "ax2", "kind": "axis", "origin": "O2"},
        ],
    })
    with pytest.raises(DSLValidationError, match="at most one axis"):
        validate(bad)


def test_axis_validator_rejects_missing_origin():
    """origin 必须引用已声明的 point。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "ax", "kind": "axis", "origin": "O"},
        ],
    })
    with pytest.raises(DSLValidationError, match="unknown id"):
        validate(bad)


def test_axis_validator_rejects_bad_tick_step():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "tick_step": 0},
        ],
    })
    with pytest.raises(DSLValidationError, match="tick_step"):
        validate(bad)


# ---------------------------------------------------------------------------
# 2) Solver gauge：有 axis 时不再强加 second-y=0
# ---------------------------------------------------------------------------

def test_solver_axis_only():
    """只有坐标系 + 原点：origin 固定 (0,0)，残差应为 0。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
        ],
    })
    validate(dsl)
    sol = solve(dsl)
    assert sol.coordinates["O"] == (0.0, 0.0)
    assert sol.residual < 1e-9


def test_solver_axis_with_equilateral_triangle():
    """坐标系 + 一个边长 4 的等边三角形。
    origin O 固定原点；三角形顶点全自由（不强加 y=0 gauge），
    边长仍精确为 4。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "ax", "kind": "axis", "origin": "O"},
        ],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 4},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    assert sol.residual < 1e-6
    assert sol.coordinates["O"] == (0.0, 0.0)
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    C = sol.coordinates["C"]
    assert abs(_dist(A, B) - 4) < 1e-4
    assert abs(_dist(B, C) - 4) < 1e-4
    assert abs(_dist(C, A) - 4) < 1e-4


def test_solver_rejects_axis_origin_not_a_point():
    """origin 在 schema 层通过，但 solver 期望它在 points()。
    若 axis 引用了某个不存在于 points 的 id（schema 已经会拒，但留一道防线）。
    本测试用一个 origin 指向 segment 的极端 case → validator 会先拒。
    """
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "ax", "kind": "axis", "origin": "AB"},
        ],
    })
    with pytest.raises(DSLValidationError):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Render：含 marker/text/网格线
# ---------------------------------------------------------------------------

def test_render_axis_has_arrows_and_ticks():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O",
             "x_range": [-3, 3], "y_range": [-2, 2], "tick_step": 1,
             "show_grid": True, "show_ticks": True},
        ],
        "labels": {"O": "O"},
    })
    validate(dsl)
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    # 箭头 marker
    assert "t2g-arrow" in svg
    # x / y 轴标签
    assert ">x</text>" in svg
    assert ">y</text>" in svg
    # 刻度数字：x = -3,-2,-1,1,2,3（0 不画）
    assert ">3</text>" in svg
    assert ">-3</text>" in svg
    assert ">2</text>" in svg
    # 网格线（浅灰）
    assert "#e5e7eb" in svg


def test_render_axis_no_grid_no_ticks_when_disabled():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O",
             "show_grid": False, "show_ticks": False},
        ],
    })
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    # 关闭后不应有网格色
    assert "#e5e7eb" not in svg
    # 但箭头仍存在
    assert "t2g-arrow" in svg


# ---------------------------------------------------------------------------
# 4) Refuse 文案：显式"画坐标系"已不再拦截（这一项验证在 prompt 层）
# ---------------------------------------------------------------------------

def test_refuse_message_no_longer_blocks_axis_keyword():
    """老的 '坐标 / 象限 / x 轴' 关键词不再触发 refuse 头部。
    现在仅 A(2,3) 这类显式坐标值才会被拒。
    """
    from app.api.chat import _make_refuse_message
    # 显式"画坐标系"理应根本不被 LLM refuse，但若 LLM 误判抛出 refuse，文案不再硬说"不支持坐标"
    s = _make_refuse_message("用户要求画坐标系")
    assert "暂不支持基于坐标" not in s

    # 显式坐标值 A(2,3) 仍保留拒绝路径
    s2 = _make_refuse_message("暂不支持 A(2,3) 的描述")
    assert "坐标" in s2
