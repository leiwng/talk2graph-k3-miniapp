"""W12 — on_curve 约束测试。

测试点：
1. schema：OnCurveC 解析
2. validator：point/curve 引用类型 + 未知 id 拒绝
3. solver：点在 y=x² 上、点在 y=1/x 上（hint 从任意位置拉回曲线）
4. solver：var=y 的 curve 也能用（x = g(y)）
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_on_curve_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "expr": "x**2"},
            {"id": "A", "kind": "point", "hint": [1, 1]},
        ],
        "constraints": [
            {"type": "on_curve", "point": "A", "curve": "c1"},
        ],
    })
    validate(dsl)
    assert dsl.constraints[0].type == "on_curve"
    assert dsl.constraints[0].point == "A"


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_validator_rejects_on_curve_unknown_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "c1", "kind": "curve", "expr": "x"},
        ],
        "constraints": [
            {"type": "on_curve", "point": "Z", "curve": "c1"},
        ],
    })
    with pytest.raises(DSLValidationError, match="on_curve.point"):
        validate(bad)


def test_validator_rejects_on_curve_wrong_curve_type():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O"},
            {"id": "A", "kind": "point"},
        ],
        "constraints": [
            # curve 指向 axis 不是 FunctionCurveObj
            {"type": "on_curve", "point": "A", "curve": "ax"},
        ],
    })
    with pytest.raises(DSLValidationError, match="FunctionCurveObj"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Solver — 硬约束把点拉到曲线上
# ---------------------------------------------------------------------------

def test_solver_on_curve_pulls_point_to_parabola():
    """点 A hint 在 (2, 1)（远离 y=x² 上的正确位置 (2, 4)）。
    on_curve 应把 A.y 拉到精确 4。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-3, 3], "y_range": [-1, 10]},
            {"id": "c1", "kind": "curve", "expr": "x**2", "var": "x", "domain": [-3, 3]},
            {"id": "A", "kind": "point", "hint": [2.0, 1.0]},   # 远离真解 (2, 4)
        ],
        "constraints": [
            {"type": "on_curve", "point": "A", "curve": "c1"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    ax, ay = sol.coordinates["A"]
    # A.y 应精确等于 A.x²
    assert abs(ay - ax * ax) < 1e-4, f"A=({ax}, {ay}), expected y ≈ x² = {ax*ax}"


def test_solver_on_curve_reciprocal():
    """y = 1/x：hint A=(3, 5) 应被拉到 (3, 1/3) 附近。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-5, 5], "y_range": [-5, 5]},
            {"id": "c1", "kind": "curve", "expr": "1/x", "var": "x", "domain": [-5, 5]},
            {"id": "A", "kind": "point", "hint": [3.0, 5.0]},
        ],
        "constraints": [
            {"type": "on_curve", "point": "A", "curve": "c1"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    ax, ay = sol.coordinates["A"]
    # 应满足 y = 1/x
    if abs(ax) > 1e-6:
        assert abs(ay - 1.0 / ax) < 1e-4


def test_solver_on_curve_var_y():
    """var='y' 时曲线为 x = g(y)，例如 x = y²。
    hint A=(0.5, 1)：应拉到 (1, 1)。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-1, 5], "y_range": [-3, 3]},
            {"id": "c1", "kind": "curve", "expr": "y**2", "var": "y", "domain": [-2, 2]},
            {"id": "A", "kind": "point", "hint": [0.5, 1.0]},
        ],
        "constraints": [
            {"type": "on_curve", "point": "A", "curve": "c1"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=12)
    ax, ay = sol.coordinates["A"]
    # 应满足 x = y²
    assert abs(ax - ay * ay) < 1e-4, f"A=({ax}, {ay}), expected x ≈ y² = {ay*ay}"


def test_solver_two_points_on_curve_collinear_with_origin():
    """反比例函数 y=6/x 上取 A、B 两点且过原点共线。
    正解：A、B 关于原点对称，如 (√6, √6) 和 (-√6, -√6)（如果 y = x 是过原点直线）。
    验证：|A·B| = 6 且 collinear 满足。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "ax", "kind": "axis", "origin": "O", "x_range": [-6, 6], "y_range": [-6, 6]},
            {"id": "c1", "kind": "curve", "expr": "6/x", "var": "x", "domain": [-6, 6]},
            {"id": "A", "kind": "point", "hint": [2, 3]},
            {"id": "B", "kind": "point", "hint": [-2, -3]},
            {"id": "AB", "kind": "line", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "on_curve", "point": "A", "curve": "c1"},
            {"type": "on_curve", "point": "B", "curve": "c1"},
            {"type": "collinear", "points": ["A", "O", "B"]},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=15)
    A = sol.coordinates["A"]
    B = sol.coordinates["B"]
    # A、B 在 y=6/x 上
    assert abs(A[0] * A[1] - 6) < 1e-3
    assert abs(B[0] * B[1] - 6) < 1e-3
    # A、O、B 共线（叉积为 0）
    cross = A[0] * B[1] - A[1] * B[0]
    assert abs(cross) < 1e-3
