"""V2-G.4 第二波 - 分段函数 / 位似 / 弓形 / 标注 测试。"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import apply_transform, solve


# ---------------------------------------------------------------------------
# 1) 分段函数 pieces
# ---------------------------------------------------------------------------

def test_curve_pieces_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "var": "x",
             "pieces": [
                 {"expr": "x", "domain": [-3, 0]},
                 {"expr": "-x", "domain": [0, 3]}
             ]},
        ],
    })
    validate(dsl)
    assert dsl.curves()[0].pieces is not None
    assert len(dsl.curves()[0].pieces) == 2


def test_curve_pieces_render_multiple_polylines():
    """分段函数渲染为多个 <polyline>。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-3, 3], "y_range": [-1, 4]},
            {"id": "c1", "kind": "curve", "var": "x",
             "pieces": [
                 {"expr": "x + 2", "domain": [-3, 0]},
                 {"expr": "2 - x", "domain": [0, 3]}
             ]},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    # 应该至少有 2 个 polyline（两段）
    assert svg.count('<polyline data-id="c1"') >= 2


def test_curve_pieces_or_expr_required():
    """pieces 和 expr 必须有其一。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "var": "x"},
        ],
    })
    with pytest.raises(DSLValidationError, match="expr or pieces"):
        validate(bad)


# ---------------------------------------------------------------------------
# 2) 位似变换 homothety
# ---------------------------------------------------------------------------

def test_homothety_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "A_h", "kind": "transformed_point", "source": "A",
             "transform": {"type": "homothety", "center": "O", "ratio": 2.0}},
        ],
    })
    validate(dsl)
    assert dsl.transformed_points()[0].transform.type == "homothety"


def test_homothety_math():
    """p' = center + ratio * (p - center)"""
    p = (3.0, 4.0)
    coords = {"O": (0.0, 0.0)}
    from app.dsl.schema import HomothetySpec
    result = apply_transform(
        HomothetySpec(type="homothety", center="O", ratio=2.0),
        p, coords=coords
    )
    assert abs(result[0] - 6.0) < 1e-9
    assert abs(result[1] - 8.0) < 1e-9


def test_homothety_with_non_origin_center():
    p = (5.0, 5.0)
    coords = {"C": (1.0, 1.0)}
    from app.dsl.schema import HomothetySpec
    result = apply_transform(
        HomothetySpec(type="homothety", center="C", ratio=0.5),
        p, coords=coords
    )
    # p' = (1, 1) + 0.5 * ((5,5) - (1,1)) = (1, 1) + (2, 2) = (3, 3)
    assert abs(result[0] - 3.0) < 1e-9
    assert abs(result[1] - 3.0) < 1e-9


# ---------------------------------------------------------------------------
# 3) 独立弓形对象 BowObj
# ---------------------------------------------------------------------------

def test_bow_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "bow1", "kind": "bow", "center": "O", "from_point": "A", "to_point": "B"},
        ],
    })
    validate(dsl)
    assert dsl.bows()[0].kind == "bow"


def test_bow_validator_center_must_be_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "bow1", "kind": "bow", "center": "AB", "from_point": "A", "to_point": "B"},
        ],
    })
    with pytest.raises(DSLValidationError, match="bow.*center"):
        validate(bad)


def test_bow_render_has_path():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [2, 0]},
            {"id": "B", "kind": "point", "hint": [0, 2]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "bow1", "kind": "bow", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert 'data-id="bow1"' in svg
    assert 'class="t2g-obj t2g-bow"' in svg
    assert 'fill-opacity="0.15"' in svg


def test_bow_area_constraint_accepts_bow_obj():
    """bow_area 约束现在可以指向 BowObj。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [2, 0]},
            {"id": "B", "kind": "point", "hint": [-2, 0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "bow1", "kind": "bow", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
            {"type": "bow_area", "arc": "bow1", "value": 2 * math.pi},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    O = sol.coordinates["O"]
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    v1 = (A[0]-O[0], A[1]-O[1])
    v2 = (B[0]-O[0], B[1]-O[1])
    r = math.hypot(*v1)
    cross = v1[0]*v2[1] - v1[1]*v2[0]
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    angle = math.atan2(cross, dot)
    if angle < 0:
        angle += 2 * math.pi
    area = 0.5 * r * r * (angle - math.sin(angle))
    assert abs(area - 2 * math.pi) < 1e-3


# ---------------------------------------------------------------------------
# 4) 标注 arc_length / bow_area
# ---------------------------------------------------------------------------

def test_annotation_arc_length_renders():
    """弧长标注渲染为数值。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [2, 0]},
            {"id": "B", "kind": "point", "hint": [0, 2]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
        ],
        "annotations": [
            {"target": "arc1", "kind": "arc_length", "show": True},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    # 应该有 <text> 元素包含弧长数值（约 π，半径 2 + 圆心角 90° = π）
    assert '<text' in svg


def test_annotation_bow_area_renders():
    """弓形面积标注渲染为数值。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "A", "kind": "point", "hint": [2, 0]},
            {"id": "B", "kind": "point", "hint": [-2, 0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "bow1", "kind": "bow", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
        ],
        "annotations": [
            {"target": "bow1", "kind": "bow_area", "show": True},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=10)
    svg = render_svg(dsl, sol)
    assert '<text' in svg
