"""V2-G.1 - 弧 arc + 扇形 sector 测试。

测试点：
1. schema：ArcObj / SectorObj 解析
2. validator：center/from/to 类型错 / radius<=0 / 三点重合
3. solver：arc 隐含等距约束把 from/to 拉到以 center 为圆心的同一圆上
4. render：SVG 含 <path d="M ... A ..."/>；扇形含 fill-opacity
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

def test_arc_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [],
    })
    validate(dsl)
    arc = dsl.arcs()[0]
    assert arc.kind == "arc"
    assert arc.center == "O"
    assert arc.from_point == "A"
    assert arc.to_point == "B"
    assert arc.radius is None
    assert arc.ccw is True


def test_sector_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "sec1", "kind": "sector", "center": "O", "from_point": "A", "to_point": "B", "ccw": False},
        ],
        "constraints": [],
    })
    validate(dsl)
    sec = dsl.sectors()[0]
    assert sec.kind == "sector"
    assert sec.center == "O"
    assert sec.ccw is False


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_arc_validator_center_must_be_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "arc1", "kind": "arc", "center": "AB", "from_point": "A", "to_point": "B"},
        ],
    })
    with pytest.raises(DSLValidationError, match="arc.*center"):
        validate(bad)


def test_arc_validator_radius_must_be_positive():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B", "radius": -1},
        ],
    })
    with pytest.raises(DSLValidationError, match="radius"):
        validate(bad)


def test_arc_validator_distinct_points():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "A"},
        ],
    })
    with pytest.raises(DSLValidationError, match="distinct"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver - arc 隐含等距约束
# ---------------------------------------------------------------------------

def test_solver_arc_implicit_equal_distance():
    """arc 隐含 |O-A| == |O-B|：
    hint O=(0,0), A=(2,0), B=(0,2)。
    求解后 |O-A| 与 |O-B| 必须相等（被 arc 约束拉到同圆）。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 2.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    O = sol.coordinates["O"]
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    d_oa = math.hypot(A[0] - O[0], A[1] - O[1])
    d_ob = math.hypot(B[0] - O[0], B[1] - O[1])
    # hint 软约束（权重 0.05）会与硬约束轻微拉扯，1e-3 精度足够证明等距约束生效
    assert abs(d_oa - d_ob) < 1e-3, f"|O-A|={d_oa}, |O-B|={d_ob}, should be equal"
    assert abs(d_oa - 2.0) < 1e-3


def test_solver_sector_implicit_equal_distance():
    """sector 也隐含 |O-A| == |O-B|。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [3.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 3.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "sec1", "kind": "sector", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 3.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    O = sol.coordinates["O"]
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    d_oa = math.hypot(A[0] - O[0], A[1] - O[1])
    d_ob = math.hypot(B[0] - O[0], B[1] - O[1])
    assert abs(d_oa - d_ob) < 1e-3


# ---------------------------------------------------------------------------
# 4) Render
# ---------------------------------------------------------------------------

def test_render_arc_has_svg_path():
    """弧渲染为 SVG <path d="M ... A ..."/>。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 2.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="arc1"' in svg
    assert 'class="t2g-obj t2g-arc"' in svg
    assert 'd="M ' in svg
    assert 'A ' in svg  # SVG arc command
    assert 'fill="none"' in svg


def test_render_sector_has_fill():
    """扇形渲染为闭合 path 且含 fill-opacity。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [3.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 3.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "sec1", "kind": "sector", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 3.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="sec1"' in svg
    assert 'class="t2g-obj t2g-sector"' in svg
    assert 'fill-opacity="0.15"' in svg
    assert 'd="M ' in svg
    assert ' Z"' in svg  # 闭合 path
