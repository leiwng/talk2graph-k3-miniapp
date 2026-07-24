"""V2-G.3 第一波 - 阴影区域 / 数轴 / 网格 / 辅助线 测试。

测试点：
1. schema：3 个新对象解析
2. validator：region boundary 类型 / number_line origin 类型 / aux_line a/b 类型
3. solver：number_line 作为 gauge anchor
4. render：region SVG path 含 fill-opacity；number_line 含 marker-end；aux_line 含 stroke-dasharray
"""
from __future__ import annotations

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_region_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "r1", "kind": "region", "boundary": ["AB", "BC"], "fill_color": "#ff0000", "fill_opacity": 0.3},
        ],
    })
    validate(dsl)
    r = dsl.regions()[0]
    assert r.kind == "region"
    assert r.boundary == ["AB", "BC"]
    assert r.fill_color == "#ff0000"


def test_number_line_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "nl", "kind": "number_line", "origin": "O", "range": [-5, 5], "tick_step": 1},
        ],
    })
    validate(dsl)
    nl = dsl.number_lines()[0]
    assert nl.kind == "number_line"
    assert nl.range == (-5.0, 5.0)


def test_aux_line_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "aux1", "kind": "aux_line", "a": "A", "b": "B", "extended": True},
        ],
    })
    validate(dsl)
    aux = dsl.aux_lines()[0]
    assert aux.kind == "aux_line"
    assert aux.extended is True


def test_axis_grid_size_field():
    """axis 加 grid_size 字段。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "grid_size": 1.0},
        ],
    })
    validate(dsl)
    assert dsl.axis().grid_size == 1.0


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_region_boundary_must_be_segment_or_arc():
    """region.boundary 元素必须是 SegmentObj 或 ArcObj。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "r1", "kind": "region", "boundary": ["A", "B"]},  # point 不是 boundary
        ],
    })
    with pytest.raises(DSLValidationError, match="boundary element"):
        validate(bad)


def test_number_line_origin_must_be_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "nl", "kind": "number_line", "origin": "AB"},
        ],
    })
    with pytest.raises(DSLValidationError, match="number_line.*origin"):
        validate(bad)


def test_number_line_range_invalid():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "nl", "kind": "number_line", "origin": "O", "range": [5, -5]},
        ],
    })
    with pytest.raises(DSLValidationError, match="range min"):
        validate(bad)


def test_aux_line_endpoints_must_be_points():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "aux1", "kind": "aux_line", "a": "A", "b": "AB"},  # b 不是 point
        ],
    })
    with pytest.raises(DSLValidationError, match="aux_line.*b"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver - number_line 作为 gauge anchor
# ---------------------------------------------------------------------------

def test_solver_number_line_as_gauge():
    """number_line.origin 固定为 (0,0)，类似 axis 行为。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point", "hint": [3, 0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "nl", "kind": "number_line", "origin": "O", "range": [-5, 5]},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 3.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    # O 应该固定在 (0, 0)
    O = sol.coordinates["O"]
    assert abs(O[0]) < 1e-6 and abs(O[1]) < 1e-6
    # A 应该在距 O 为 3 的位置
    A = sol.coordinates["A"]
    import math
    assert abs(math.hypot(A[0] - O[0], A[1] - O[1]) - 3.0) < 1e-3


# ---------------------------------------------------------------------------
# 4) Render
# ---------------------------------------------------------------------------

def test_render_region_has_fill_opacity():
    """region 渲染为 SVG path 含 fill-opacity。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [4, 0]},
            {"id": "B", "kind": "point", "hint": [0, 4]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "OB", "kind": "segment", "a": "O", "b": "B"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
            {"id": "r1", "kind": "region", "boundary": ["OA", "arc1", "OB"], "fill_color": "#ff0000", "fill_opacity": 0.25},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 4.0},
            {"type": "length", "segment": "OB", "value": 4.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="r1"' in svg
    assert 'class="t2g-obj t2g-region"' in svg
    assert 'fill="#ff0000"' in svg
    assert 'fill-opacity="0.25"' in svg


def test_render_number_line_has_marker():
    """number_line 渲染为 SVG line 含 marker-end（箭头）。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [3, 0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "nl", "kind": "number_line", "origin": "O", "range": [-5, 6]},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 3.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="nl"' in svg
    assert 'class="t2g-obj t2g-number-line"' in svg
    assert 'marker-end=' in svg


def test_render_aux_line_has_dash():
    """aux_line 渲染为虚线 SVG line。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "aux1", "kind": "aux_line", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 4.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="aux1"' in svg
    assert 'class="t2g-obj t2g-aux-line"' in svg
    assert 'stroke-dasharray=' in svg


def test_render_axis_with_grid_size():
    """axis 有 grid_size 时画网格点 circle。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-2, 2], "y_range": [-2, 2], "grid_size": 1.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    # 应该有多个网格点 circle（5x5 = 25 个）
    assert svg.count('<circle') >= 20
