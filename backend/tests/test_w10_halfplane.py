"""W10 — 半平面约束（same_side / opposite_side）端到端测试。

覆盖：
1. Schema：Pydantic 解析新约束类型
2. Validator：line 类型、point/ref 引用合法性、point != ref
3. Solver：含 hint 辅助点 P0 时，same_side 强制 C 与 P0 同侧；opposite_side 强制异侧
4. Render：孤立辅助点（hint != None 且未被任何对象引用）不画
5. Render：被引用的辅助点（hint != None 但出现在 segment.a 等）仍画
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg, _isolated_aux_points
from app.solver.engine import solve


def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_same_side_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "same_side", "line": "AB", "point": "C", "ref": "P0"},
        ],
    })
    validate(dsl)
    assert dsl.constraints[0].type == "same_side"
    assert dsl.constraints[0].line == "AB"


def test_opposite_side_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "opposite_side", "line": "AB", "point": "C", "ref": "P0"},
        ],
    })
    validate(dsl)
    assert dsl.constraints[0].type == "opposite_side"


# ---------------------------------------------------------------------------
# 2) Validator 边界
# ---------------------------------------------------------------------------

def test_validator_rejects_non_segment_line():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
        ],
        "constraints": [
            {"type": "same_side", "line": "A", "point": "C", "ref": "P0"},
        ],
    })
    with pytest.raises(DSLValidationError, match="line must be segment/line"):
        validate(bad)


def test_validator_rejects_same_point_and_ref():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "same_side", "line": "AB", "point": "C", "ref": "C"},
        ],
    })
    with pytest.raises(DSLValidationError, match="point and ref are the same"):
        validate(bad)


def test_validator_rejects_unknown_ref():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "same_side", "line": "AB", "point": "C", "ref": "Z"},
        ],
    })
    with pytest.raises(DSLValidationError, match="unknown id"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver
# ---------------------------------------------------------------------------

def test_solver_same_side_forces_above():
    """直角三角形 BC=3 CA=4 + C 与 P0(0,5) 在 AB 同侧 → C.y 应当 > 0。

    无 axis、gauge 为 A=(0,0)、B.y=0；故 AB 在 x 轴上；same_side 把 C 拉到上方。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
            {"type": "same_side", "line": "AB", "point": "C", "ref": "P0"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    C = sol.coordinates["C"]
    P0 = sol.coordinates["P0"]
    # 几何不变量
    assert abs(_dist(B, C) - 3) < 1e-3
    assert abs(_dist(C, A) - 4) < 1e-3
    # ∠C ≈ 90°
    cb = (B[0] - C[0], B[1] - C[1])
    ca = (A[0] - C[0], A[1] - C[1])
    dot = cb[0]*ca[0] + cb[1]*ca[1]
    assert abs(dot) < 1e-3
    # C 在 AB 上方（与 P0 同侧）
    assert C[1] > 0, f"C.y={C[1]} should be > 0 (above AB which is on x-axis)"
    assert P0[1] > 0


def test_solver_opposite_side_forces_below():
    """同样的直角三角形 + C 与 P0(0,5) 在 AB 两侧 → C.y < 0。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
            {"type": "opposite_side", "line": "AB", "point": "C", "ref": "P0"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    C = sol.coordinates["C"]
    P0 = sol.coordinates["P0"]
    # P0 在 AB 上方，opposite_side 把 C 推到下方
    assert P0[1] > 0
    assert C[1] < 0, f"C.y={C[1]} should be < 0 (opposite side of P0)"


# ---------------------------------------------------------------------------
# 4) Render — 隐藏孤立辅助点
# ---------------------------------------------------------------------------

def test_isolated_aux_points_detection():
    """P0 有 hint 且未被任何对象引用 → 算孤立辅助点。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
    })
    aux = _isolated_aux_points(dsl)
    assert aux == {"P0"}


def test_render_hides_isolated_aux_point():
    """SVG 输出中不含 data-id="P0" 的 circle。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "P0", "kind": "point", "hint": [0, 5]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
            {"type": "same_side", "line": "AB", "point": "C", "ref": "P0"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "P0": "P0"},
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    svg = render_svg(dsl, sol)
    assert 'data-id="P0"' not in svg, "P0 should be hidden as isolated aux point"
    # A/B/C 仍画
    assert 'data-id="A"' in svg
    assert 'data-id="B"' in svg
    assert 'data-id="C"' in svg


def test_render_keeps_aux_point_when_referenced():
    """若一个 hint 点被任何 segment / polygon / circle 引用，仍画出。

    hint 设为等边三角形的真解坐标，避免与求解结果冲突触发软残差未收敛。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            # C 的 hint 设为正等边三角形的解 (2, 2*sqrt(3))，避免软残差扰动
            {"id": "C", "kind": "point", "hint": [2.0, 3.4641]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 4},
        ],
    })
    validate(dsl)
    # 这里我们关心的是 _isolated_aux_points 的判定 + render 输出，不依赖求解残差
    aux = _isolated_aux_points(dsl)
    assert "C" not in aux, "C 被 segment BC/CA 和 polygon tri 引用，不该算孤立点"

    sol = solve(dsl, restarts=30)
    svg = render_svg(dsl, sol)
    assert 'data-id="C"' in svg

