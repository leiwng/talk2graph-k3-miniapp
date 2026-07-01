"""W11 — 几何变换（rotation / translation / reflection / central_symmetry）测试。

覆盖：
1. Schema：Pydantic 解析 TransformedPointObj / TransformedPolygonObj
2. Validator：source 引用、类型、id 冲突、嵌套派生禁止
3. Math：apply_transform 4 种变换的纯数学正确性
4. Solver：整合到 _build_solution 的后处理生效
5. Render：派生多边形使用 stroke-dasharray；派生点标签自动加撇
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import (
    DSL,
    CentralSymSpec,
    ReflectionSpec,
    RotationSpec,
    TranslationSpec,
)
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import apply_transform, solve


def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_transformed_point_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AC", "kind": "segment", "a": "A", "b": "C"},
            {"id": "D", "kind": "transformed_point", "source": "C",
             "transform": {"type": "rotation", "center": "A", "angle": 90}},
        ],
    })
    tp = [o for o in dsl.objects if o.kind == "transformed_point"][0]
    assert tp.source == "C"
    assert tp.transform.type == "rotation"
    assert tp.transform.center == "A"
    assert tp.transform.angle == 90


def test_transformed_polygon_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "tri2", "kind": "transformed_polygon", "source": "tri",
             "transform": {"type": "central_symmetry", "center": "A"}},
        ],
    })
    tp = [o for o in dsl.objects if o.kind == "transformed_polygon"][0]
    assert tp.source == "tri"
    assert tp.transform.type == "central_symmetry"
    assert tp.vertex_suffix == "p"


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_validator_rejects_unknown_source():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "D", "kind": "transformed_point", "source": "Z",
             "transform": {"type": "translation", "dx": 1, "dy": 0}},
        ],
    })
    with pytest.raises(DSLValidationError, match="unknown source"):
        validate(bad)


def test_validator_rejects_wrong_source_type():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            # transformed_point 的 source 必须是 point，不能是 segment
            {"id": "X", "kind": "transformed_point", "source": "AB",
             "transform": {"type": "translation", "dx": 1, "dy": 0}},
        ],
    })
    with pytest.raises(DSLValidationError, match="source must be a PointObj"):
        validate(bad)


def test_validator_rejects_derived_id_collision():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "A_p", "kind": "point"},  # 与派生顶点 id 冲突
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "tri2", "kind": "transformed_polygon", "source": "tri",
             "transform": {"type": "central_symmetry", "center": "A"},
             "vertex_suffix": "p"},
        ],
    })
    with pytest.raises(DSLValidationError, match="collides with existing"):
        validate(bad)


def test_validator_rejects_reflection_with_bad_line():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "transformed_point", "source": "C",
             "transform": {"type": "reflection", "line": "A"}},  # A 是点不是 line
        ],
    })
    with pytest.raises(DSLValidationError, match="transform.line must be segment/line"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Math — apply_transform 纯数学
# ---------------------------------------------------------------------------

def test_apply_transform_rotation_90():
    coords = {"O": (0.0, 0.0)}
    t = RotationSpec(type="rotation", center="O", angle=90)
    p = apply_transform(t, (1.0, 0.0), coords=coords)
    assert abs(p[0] - 0.0) < 1e-9
    assert abs(p[1] - 1.0) < 1e-9


def test_apply_transform_rotation_around_nonorigin():
    coords = {"O": (2.0, 3.0)}
    t = RotationSpec(type="rotation", center="O", angle=180)
    p = apply_transform(t, (5.0, 3.0), coords=coords)
    # 关于 (2,3) 旋 180° → (-1, 3)
    assert abs(p[0] - (-1.0)) < 1e-9
    assert abs(p[1] - 3.0) < 1e-9


def test_apply_transform_translation():
    t = TranslationSpec(type="translation", dx=3.0, dy=4.0)
    p = apply_transform(t, (1.0, 2.0))
    assert p == (4.0, 6.0)


def test_apply_transform_central_symmetry():
    coords = {"O": (0.0, 0.0)}
    t = CentralSymSpec(type="central_symmetry", center="O")
    p = apply_transform(t, (1.0, 1.0), coords=coords)
    assert p == (-1.0, -1.0)


def test_apply_transform_reflection_about_x_axis():
    t = ReflectionSpec(type="reflection", line="AB")
    # 直线 AB 沿 x 轴（(0,0) -> (1,0)）
    p = apply_transform(t, (2.0, 3.0),
                        line_endpoints=((0.0, 0.0), (1.0, 0.0)))
    assert abs(p[0] - 2.0) < 1e-9
    assert abs(p[1] - (-3.0)) < 1e-9


# ---------------------------------------------------------------------------
# 4) Solver — 整合后处理
# ---------------------------------------------------------------------------

def test_solver_transformed_polygon_produces_derived_coords():
    """等边三角形 ABC 关于 A 中心对称 → 派生顶点 A_p / B_p / C_p 出现在坐标里。
    派生三角形三边应与源等长。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "tri2", "kind": "transformed_polygon", "source": "tri",
             "transform": {"type": "central_symmetry", "center": "A"},
             "vertex_suffix": "p"},
        ],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 4},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    # 派生顶点存在
    assert "A_p" in sol.coordinates
    assert "B_p" in sol.coordinates
    assert "C_p" in sol.coordinates
    # 中心对称：A_p 应当 == A（对称中心自身）
    assert _dist(sol.coordinates["A_p"], sol.coordinates["A"]) < 1e-9
    # 派生三角形三边等长 = 4
    assert abs(_dist(sol.coordinates["A_p"], sol.coordinates["B_p"]) - 4) < 1e-4
    assert abs(_dist(sol.coordinates["B_p"], sol.coordinates["C_p"]) - 4) < 1e-4


def test_solver_transformed_point_single():
    """直角三角形 ABC，AB=3、BC=4；把 C 绕 A 旋转 90° 得到 D。
    验证 |AD| = |AC| = 5，∠CAD = 90°。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "D", "kind": "transformed_point", "source": "C",
             "transform": {"type": "rotation", "center": "A", "angle": 90}},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "B"},
            {"type": "length", "segment": "AB", "value": 3},
            {"type": "length", "segment": "BC", "value": 4},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    A = sol.coordinates["A"]
    C = sol.coordinates["C"]
    D = sol.coordinates["D"]
    # |AD| == |AC|
    assert abs(_dist(A, D) - _dist(A, C)) < 1e-6
    # ∠CAD = 90°
    ac = (C[0] - A[0], C[1] - A[1])
    ad = (D[0] - A[0], D[1] - A[1])
    dot = ac[0] * ad[0] + ac[1] * ad[1]
    assert abs(dot) < 1e-6


# ---------------------------------------------------------------------------
# 5) Render
# ---------------------------------------------------------------------------

def test_render_derived_polygon_dashed():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "tri2", "kind": "transformed_polygon", "source": "tri",
             "transform": {"type": "translation", "dx": 5, "dy": 0}},
        ],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 3},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    svg = render_svg(dsl, sol)
    # 派生多边形应含 stroke-dasharray
    assert 'data-id="tri2"' in svg
    assert 't2g-derived' in svg
    # 派生顶点应存在 SVG
    assert 'data-id="A_p"' in svg
    # 派生点 label 自动加撇（无 dsl.labels 覆盖时用 A'）
    assert "A&#39;" in svg or "A'" in svg
