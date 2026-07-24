"""V2-G.1 - 正多边形 regular_polygon + 梯形 trapezoid 测试。

测试点：
1. schema：RegularPolygonC / TrapezoidC 解析
2. validator：sides 不匹配 / 非 4 边 / bases 不是 polygon 边 / bases 不是对边
3. solver：正六边形所有边等长 + 内角 120°；梯形两底平行
4. render：正多边形闭合
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_regular_polygon_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "regular_polygon", "polygon": "tri", "sides": 3},
        ],
    })
    validate(dsl)
    c = dsl.constraints[0]
    assert c.type == "regular_polygon"
    assert c.sides == 3


def test_trapezoid_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CD", "kind": "segment", "a": "C", "b": "D"},
            {"id": "DA", "kind": "segment", "a": "D", "b": "A"},
            {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "trapezoid", "polygon": "quad", "bases": ["AB", "CD"]},
        ],
    })
    validate(dsl)
    c = dsl.constraints[0]
    assert c.type == "trapezoid"
    assert c.bases == ["AB", "CD"]


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_regular_polygon_sides_mismatch():
    """sides != len(vertices) 应被拒绝。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "regular_polygon", "polygon": "tri", "sides": 4},
        ],
    })
    with pytest.raises(DSLValidationError, match="sides"):
        validate(bad)


def test_trapezoid_requires_quadrilateral():
    """梯形必须是四边形。"""
    bad = DSL.model_validate({
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
            {"type": "trapezoid", "polygon": "tri", "bases": ["AB", "BC"]},
        ],
    })
    with pytest.raises(DSLValidationError, match="quadrilateral"):
        validate(bad)


def test_trapezoid_bases_must_be_polygon_edges():
    """bases 必须是 polygon 的边。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CD", "kind": "segment", "a": "C", "b": "D"},
            {"id": "DA", "kind": "segment", "a": "D", "b": "A"},
            {"id": "AC", "kind": "segment", "a": "A", "b": "C"},  # 对角线，不是边
            {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "trapezoid", "polygon": "quad", "bases": ["AC", "BD"] if False else ["AC", "CD"]},
        ],
    })
    with pytest.raises(DSLValidationError, match="not a side"):
        validate(bad)


def test_trapezoid_bases_must_be_opposite():
    """bases 必须是对边（在四边形中相隔 2 个位置）。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CD", "kind": "segment", "a": "C", "b": "D"},
            {"id": "DA", "kind": "segment", "a": "D", "b": "A"},
            {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            # AB 和 BC 是邻边不是对边
            {"type": "trapezoid", "polygon": "quad", "bases": ["AB", "BC"]},
        ],
    })
    with pytest.raises(DSLValidationError, match="opposite"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver
# ---------------------------------------------------------------------------

def test_solver_regular_hexagon():
    """正六边形：所有相邻边等长 + 所有内角 120°。
    去掉 hint（hint 软约束权重 0.05 会与正六边形对称约束轻微拉扯，
    导致残差卡在 ~3e-4 无法收敛到 1e-4 阈值；让求解器自由搜索更稳定）。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "P0", "kind": "point"},
            {"id": "P1", "kind": "point"},
            {"id": "P2", "kind": "point"},
            {"id": "P3", "kind": "point"},
            {"id": "P4", "kind": "point"},
            {"id": "P5", "kind": "point"},
            {"id": "hex", "kind": "polygon", "vertices": ["P0", "P1", "P2", "P3", "P4", "P5"]},
        ],
        "constraints": [
            {"type": "regular_polygon", "polygon": "hex", "sides": 6},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=30, restarts_extra=40)
    pts = [sol.coordinates[f"P{i}"] for i in range(6)]
    # 所有相邻边等长
    lens = [math.hypot(pts[(i+1) % 6][0] - pts[i][0], pts[(i+1) % 6][1] - pts[i][1]) for i in range(6)]
    for d in lens:
        assert abs(d - lens[0]) < 1e-3, f"边长不等: {lens}"
    # 所有内角 ≈ 120°
    for i in range(6):
        pa = pts[(i - 1) % 6]
        pb = pts[i]
        pc = pts[(i + 1) % 6]
        ba = (pa[0] - pb[0], pa[1] - pb[1])
        bc = (pc[0] - pb[0], pc[1] - pb[1])
        la = math.hypot(*ba); lc = math.hypot(*bc)
        cos_v = (ba[0]*bc[0] + ba[1]*bc[1]) / (la * lc)
        assert abs(cos_v - math.cos(math.radians(120))) < 1e-3, f"内角 != 120°"


def test_solver_trapezoid_bases_parallel():
    """梯形 ABCD，AB ∥ CD（两底平行）。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point", "hint": [-3, 0]},
            {"id": "B", "kind": "point", "hint": [3, 0]},
            {"id": "C", "kind": "point", "hint": [2, 2]},
            {"id": "D", "kind": "point", "hint": [-2, 2]},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CD", "kind": "segment", "a": "C", "b": "D"},
            {"id": "DA", "kind": "segment", "a": "D", "b": "A"},
            {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "trapezoid", "polygon": "quad", "bases": ["AB", "CD"]},
            {"type": "length", "segment": "AB", "value": 6.0},
            {"type": "length", "segment": "CD", "value": 4.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=15)
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    C = sol.coordinates["C"]
    D = sol.coordinates["D"]
    # AB 方向与 CD 方向叉积 ≈ 0
    ab = (B[0] - A[0], B[1] - A[1])
    cd = (D[0] - C[0], D[1] - C[1])
    cross = ab[0] * cd[1] - ab[1] * cd[0]
    assert abs(cross) < 1e-3, f"两底不平行: cross={cross}"


# ---------------------------------------------------------------------------
# 4) Render
# ---------------------------------------------------------------------------

def test_render_regular_polygon_closed():
    """正六边形渲染为闭合 polygon。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "P0", "kind": "point"},
            {"id": "P1", "kind": "point"},
            {"id": "P2", "kind": "point"},
            {"id": "P3", "kind": "point"},
            {"id": "P4", "kind": "point"},
            {"id": "P5", "kind": "point"},
            {"id": "hex", "kind": "polygon", "vertices": ["P0", "P1", "P2", "P3", "P4", "P5"]},
        ],
        "constraints": [
            {"type": "regular_polygon", "polygon": "hex", "sides": 6},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=30, restarts_extra=40)
    svg = render_svg(dsl, sol)
    assert 'data-id="hex"' in svg
    assert 'class="t2g-obj t2g-poly"' in svg
    assert '<polygon' in svg
