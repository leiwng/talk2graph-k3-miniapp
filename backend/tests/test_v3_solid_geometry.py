"""V3.1 - 立体几何对象测试（cube/cuboid/cylinder/cone/sphere）。"""
from __future__ import annotations

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) Schema 解析
# ---------------------------------------------------------------------------

def test_cube_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "cube1", "kind": "cube", "vertex": "A", "edge": 3},
        ],
    })
    validate(dsl)
    assert dsl.cubes()[0].kind == "cube"
    assert dsl.cubes()[0].edge == 3


def test_cuboid_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "cub1", "kind": "cuboid", "vertex": "A", "length": 4, "width": 3, "height": 2},
        ],
    })
    validate(dsl)
    assert dsl.cuboids()[0].length == 4


def test_cylinder_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "cyl1", "kind": "cylinder", "center_bottom": "O", "radius": 2, "height": 5},
        ],
    })
    validate(dsl)
    assert dsl.cylinders()[0].radius == 2


def test_cone_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "cone1", "kind": "cone", "center_bottom": "O", "radius": 3, "height": 4},
        ],
    })
    validate(dsl)
    assert dsl.cones()[0].height == 4


def test_sphere_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "sph1", "kind": "sphere", "center": "O", "radius": 3},
        ],
    })
    validate(dsl)
    assert dsl.spheres()[0].radius == 3


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_cube_vertex_must_be_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "cube1", "kind": "cube", "vertex": "AB", "edge": 3},
        ],
    })
    with pytest.raises(DSLValidationError, match="cube.*vertex"):
        validate(bad)


def test_cube_edge_must_be_positive():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "cube1", "kind": "cube", "vertex": "A", "edge": -1},
        ],
    })
    with pytest.raises(DSLValidationError, match="cube.*edge"):
        validate(bad)


def test_sphere_radius_must_be_positive():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "sph1", "kind": "sphere", "center": "O", "radius": 0},
        ],
    })
    with pytest.raises(DSLValidationError, match="sphere.*radius"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Render
# ---------------------------------------------------------------------------

def test_render_cube_has_path():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point", "hint": [0, 0]},
            {"id": "cube1", "kind": "cube", "vertex": "A", "edge": 3},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="cube1"' in svg
    assert 'class="t2g-obj t2g-cube"' in svg
    assert '<path' in svg


def test_render_cuboid_has_three_faces():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point", "hint": [0, 0]},
            {"id": "cub1", "kind": "cuboid", "vertex": "A", "length": 4, "width": 3, "height": 2},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="cub1"' in svg
    # 应该有 3 个 path（顶面 + 右面 + 前面）+ 1 个隐藏边 path
    assert svg.count('<path') >= 3


def test_render_cylinder_has_ellipses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "cyl1", "kind": "cylinder", "center_bottom": "O", "radius": 2, "height": 5},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="cyl1"' in svg
    assert '<ellipse' in svg


def test_render_cone_has_apex():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "cone1", "kind": "cone", "center_bottom": "O", "radius": 3, "height": 4},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="cone1"' in svg
    assert '<ellipse' in svg


def test_render_sphere_has_circle_and_ellipse():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "sph1", "kind": "sphere", "center": "O", "radius": 3},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="sph1"' in svg
    assert '<circle' in svg
    assert '<ellipse' in svg  # 赤道椭圆
