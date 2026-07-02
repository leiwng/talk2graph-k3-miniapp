"""W13-A · 求解器自适应重启测试。

覆盖：
1. 正常题不触发抢救（简单等边三角形）
2. 复杂约束题受益于抢救（多次重启后收敛）
3. 完全无解题不会无限循环
"""
from __future__ import annotations

import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import validate
from app.solver.engine import SolveError, solve


def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def test_simple_triangle_solves_without_extra_rescue():
    """简单等边三角形一步命中，不需要 stage-2。设 restarts_extra=0 确认仍能通过。"""
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
        ],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 4},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=6, restarts_extra=0)
    # 未使用 stage-2 也应通过
    assert sol.residual < 1e-6
    A, B, C = sol.coordinates["A"], sol.coordinates["B"], sol.coordinates["C"]
    assert abs(_dist(A, B) - 4) < 1e-4
    assert abs(_dist(B, C) - 4) < 1e-4
    assert abs(_dist(C, A) - 4) < 1e-4


def test_complex_dsl_benefits_from_rescue():
    """构造一个复杂约束系统：4 点 + 多角度关系，
    默认 restarts=6 可能不够，rescue 后能收敛。
    """
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
            {"id": "AC", "kind": "segment", "a": "A", "b": "C"},
            {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 5},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CD", "value": 5},
            {"type": "length", "segment": "DA", "value": 3},
            {"type": "length", "segment": "AC", "value": 4},
            {"type": "parallelogram", "polygon": "quad"},
        ],
    })
    validate(dsl)
    # 用少的初始 restarts + 充足 extra，逼迫 stage-2 生效
    sol = solve(dsl, restarts=3, restarts_extra=30)
    assert sol.residual < 1e-6
    # 平行四边形验证：AB == CD, DA == BC
    A, B, C, D = (sol.coordinates[k] for k in ["A", "B", "C", "D"])
    assert abs(_dist(A, B) - _dist(C, D)) < 1e-4
    assert abs(_dist(D, A) - _dist(B, C)) < 1e-4


def test_infeasible_dsl_terminates():
    """互斥约束 AB=3 且 AB=5 → 必然无解。
    应在 restarts + restarts_extra 用完后抛 SolveError，不会无限循环。
    """
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 3},
            {"type": "length", "segment": "AB", "value": 5},
        ],
    })
    validate(dsl)
    with pytest.raises(SolveError):
        solve(dsl, restarts=6, restarts_extra=10)


def test_disabled_extra_restarts():
    """restarts_extra=0 时 stage-2 完全不启动，行为回退到旧版本。"""
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 5},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=6, restarts_extra=0)
    assert sol.residual < 1e-9
