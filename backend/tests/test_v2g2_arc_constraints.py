"""V2-G.2 - 圆弧角度 / 弧长 / 弓形面积约束测试。

测试点：
1. schema：ArcAngleC / ArcLengthC / BowAreaC 解析
2. validator：arc 类型错 / value 越界
3. solver：arc_angle 60° / arc_length 2π / bow_area 2π
4. solver：大角度 270°（验证 cos/sin 分量避免歧义）
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.solver.engine import solve


def _arc_angle_of(sol, O, A, B, ccw=True):
    """计算 sol 中弧 (O,A,B) 的实际圆心角（度）。"""
    O = sol.coordinates[O]
    A = sol.coordinates[A]
    B = sol.coordinates[B]
    v1 = (A[0] - O[0], A[1] - O[1])
    v2 = (B[0] - O[0], B[1] - O[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    angle = math.atan2(cross, dot)  # 数学坐标系：逆时针为正
    if not ccw:
        angle = -angle
    if angle < 0:
        angle += 2 * math.pi
    return math.degrees(angle)


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_arc_angle_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "arc_angle", "arc": "arc1", "value": 60.0},
        ],
    })
    validate(dsl)
    c = dsl.constraints[0]
    assert c.type == "arc_angle"
    assert c.value == 60.0


def test_arc_length_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "arc_length", "arc": "arc1", "value": 6.28},
        ],
    })
    validate(dsl)
    assert dsl.constraints[0].type == "arc_length"


def test_bow_area_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "bow_area", "arc": "arc1", "value": 3.14},
        ],
    })
    validate(dsl)
    assert dsl.constraints[0].type == "bow_area"


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_validator_arc_angle_arc_must_be_arc_obj():
    """arc_angle.arc 必须是 ArcObj。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
        ],
        "constraints": [
            {"type": "arc_angle", "arc": "OA", "value": 60.0},
        ],
    })
    with pytest.raises(DSLValidationError, match="arc_angle.arc"):
        validate(bad)


def test_validator_arc_angle_value_range():
    """arc_angle.value 必须在 (0, 360)。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "arc_angle", "arc": "arc1", "value": 0.0},
        ],
    })
    with pytest.raises(DSLValidationError, match="arc_angle.value"):
        validate(bad)


def test_validator_arc_length_value_positive():
    """arc_length.value 必须 > 0。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "arc_length", "arc": "arc1", "value": -1.0},
        ],
    })
    with pytest.raises(DSLValidationError, match="arc_length.value"):
        validate(bad)


def test_validator_bow_area_value_positive():
    """bow_area.value 必须 > 0。"""
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "bow_area", "arc": "arc1", "value": 0.0},
        ],
    })
    with pytest.raises(DSLValidationError, match="bow_area.value"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver
# ---------------------------------------------------------------------------

def test_solver_arc_angle_60_degrees():
    """弧 arc1 圆心角为 60°，半径 2。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [1.0, 1.732]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
            {"type": "arc_angle", "arc": "arc1", "value": 60.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    angle = _arc_angle_of(sol, "O", "A", "B", ccw=True)
    assert abs(angle - 60.0) < 1e-3, f"actual={angle}, target=60"


def test_solver_arc_angle_270_degrees():
    """大角度 270°（验证 cos/sin 分量避免 90° 歧义）。
    半径 2，圆心角 270°。
    hint 用 270° 弧的端点：A=(2,0), B=(0,-2)。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [0.0, -2.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B", "ccw": True},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
            {"type": "arc_angle", "arc": "arc1", "value": 270.0},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=30, restarts_extra=40)
    angle = _arc_angle_of(sol, "O", "A", "B", ccw=True)
    assert abs(angle - 270.0) < 1e-3, f"actual={angle}, target=270"


def test_solver_arc_length_2pi():
    """弧长 = 2π：半径 2 + 圆心角 180°。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [-2.0, 0.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
            {"type": "arc_length", "arc": "arc1", "value": 2 * math.pi},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    angle = _arc_angle_of(sol, "O", "A", "B", ccw=True)
    # 弧长 = r * angle_rad
    O = sol.coordinates["O"]; A = sol.coordinates["A"]
    r = math.hypot(A[0] - O[0], A[1] - O[1])
    arc_len = r * math.radians(angle)
    assert abs(arc_len - 2 * math.pi) < 1e-3, f"arc_len={arc_len}, target={2*math.pi}"


def test_solver_bow_area_half_circle():
    """弓形面积 = 2π：半径 2 + 圆心角 180°（半圆弓形）。
    面积公式：0.5 * r² * (θ - sin θ) = 0.5 * 4 * (π - 0) = 2π
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0.0, 0.0]},
            {"id": "A", "kind": "point", "hint": [2.0, 0.0]},
            {"id": "B", "kind": "point", "hint": [-2.0, 0.0]},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "arc1", "kind": "arc", "center": "O", "from_point": "A", "to_point": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "OA", "value": 2.0},
            {"type": "bow_area", "arc": "arc1", "value": 2 * math.pi},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=20)
    angle = _arc_angle_of(sol, "O", "A", "B", ccw=True)
    O = sol.coordinates["O"]; A = sol.coordinates["A"]
    r = math.hypot(A[0] - O[0], A[1] - O[1])
    area = 0.5 * r * r * (math.radians(angle) - math.sin(math.radians(angle)))
    assert abs(area - 2 * math.pi) < 1e-3, f"area={area}, target={2*math.pi}"
