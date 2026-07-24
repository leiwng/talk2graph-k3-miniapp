"""P3 V3.4 圆环扇环测试（5 个）。

覆盖：
- schema 解析
- validator：center 类型错 / r_inner <= 0 / 三点重合
- solver：外弧隐含等距约束
- render：SVG 含 annular-sector path
"""
from __future__ import annotations

import math
import re

from app.dsl.schema import DSL
from app.dsl.validator import validate, DSLValidationError
from app.solver.engine import solve


def _arc_angle_of(sol, O, A, B, ccw=True) -> float:
    """计算圆心角（弧度）。"""
    ox, oy = sol.coordinates[O]
    ax, ay = sol.coordinates[A]
    bx, by = sol.coordinates[B]
    cross = (ax - ox) * (by - oy) - (bx - ox) * (ay - oy)
    dot = (ax - ox) * (bx - ox) + (ay - oy) * (by - oy)
    angle = math.atan2(cross, dot)
    if not ccw:
        angle = -angle
    if angle < 0:
        angle += 2 * math.pi
    return angle


def test_annular_sector_schema_parses():
    """annular_sector 对象能被 Pydantic 解析。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "ans1", "kind": "annular_sector",
             "center": "O", "from_point": "A", "to_point": "B", "r_inner": 1.0},
        ],
        "constraints": [],
    })
    validate(dsl)
    assert len(dsl.annular_sectors()) == 1
    assert dsl.annular_sectors()[0].r_inner == 1.0


def test_validator_annular_sector_center_must_be_point():
    """center 必须是 PointObj。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "ans1", "kind": "annular_sector",
             "center": "AB", "from_point": "A", "to_point": "B", "r_inner": 1.0},
        ],
        "constraints": [],
    })
    try:
        validate(dsl)
        raise AssertionError("expected DSLValidationError")
    except DSLValidationError as e:
        assert "annular_sector" in str(e)


def test_validator_annular_sector_r_inner_must_be_positive():
    """r_inner 必须 > 0。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "ans1", "kind": "annular_sector",
             "center": "O", "from_point": "A", "to_point": "B", "r_inner": 0.0},
        ],
        "constraints": [],
    })
    try:
        validate(dsl)
        raise AssertionError("expected DSLValidationError")
    except DSLValidationError as e:
        assert "r_inner" in str(e)


def test_solver_annular_sector_implicit_constraint():
    """annular_sector 隐含 |center-from| == |center-to|。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [3.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 3.0]},
            {"id": "ans1", "kind": "annular_sector",
             "center": "O", "from_point": "A", "to_point": "B", "r_inner": 1.0},
        ],
        "constraints": [],
    })
    validate(dsl)
    sol = solve(dsl, seed=0)
    # |OA| == |OB|
    O = sol.coordinates["O"]
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    dA = math.hypot(A[0] - O[0], A[1] - O[1])
    dB = math.hypot(B[0] - O[0], B[1] - O[1])
    assert abs(dA - dB) < 1e-6


def test_render_annular_sector_has_path():
    """SVG 渲染应含 annular_sector path。"""
    from app.render.svg import render_svg

    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [3.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, 3.0]},
            {"id": "ans1", "kind": "annular_sector",
             "center": "O", "from_point": "A", "to_point": "B", "r_inner": 1.0},
        ],
        "constraints": [],
    })
    validate(dsl)
    sol = solve(dsl, seed=0)
    svg = render_svg(dsl, sol)
    # 应包含 annular-sector class
    assert "t2g-annular-sector" in svg
    # path 应包含两条 A 命令（外弧 + 内弧）
    a_count = svg.count("A ")
    assert a_count >= 2
