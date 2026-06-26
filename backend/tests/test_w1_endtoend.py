"""W1 端到端测试：5 个手写 DSL → 求解 → 渲染 SVG。

每个 case 校验：
- 求解残差 < 1e-6
- 几何不变量（边长、半径、角度等）满足约束
- SVG 文本含关键 tag
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import validate
from app.render.svg import render_svg
from app.solver.engine import solve

GOLDEN_DIR = Path(__file__).parent / "golden"


def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------------------

def test_case_01_isoceles_with_incircle_radius_3():
    """等腰三角形 ABC（顶角 A，底角 30°），内切圆半径 3。"""
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "inc", "kind": "circle",
             "definition": {"type": "incircle", "of": "tri"}},
        ],
        "constraints": [
            {"type": "isoceles", "polygon": "tri", "apex": "A"},
            {"type": "radius", "circle": "inc", "value": 3},
            {"type": "angle", "a": "A", "b": "B", "c": "C", "value": 70},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
        "annotations": [
            {"target": "inc", "kind": "radius"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, seed=1, restarts=10)
    assert sol.residual < 1e-4

    # 几何校验
    r = sol.circles["inc"]["radius"]
    assert abs(r - 3) < 1e-3

    # 等腰：AB = AC
    pa, pb, pc = sol.coordinates["A"], sol.coordinates["B"], sol.coordinates["C"]
    assert abs(_dist(pa, pb) - _dist(pa, pc)) < 1e-3

    svg = render_svg(dsl, sol)
    assert svg.startswith("<svg")
    assert "circle" in svg
    _write_golden("01_isoceles_incircle_r3.svg", svg)


def test_case_02_equilateral_triangle_side_4():
    dsl = DSL.model_validate({
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
        "labels": {"A": "A", "B": "B", "C": "C"},
        "annotations": [
            {"target": "AB", "kind": "length"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, seed=2)
    assert sol.residual < 1e-6

    pa, pb, pc = sol.coordinates["A"], sol.coordinates["B"], sol.coordinates["C"]
    assert abs(_dist(pa, pb) - 4) < 1e-3
    assert abs(_dist(pb, pc) - 4) < 1e-3
    assert abs(_dist(pc, pa) - 4) < 1e-3

    svg = render_svg(dsl, sol)
    _write_golden("02_equilateral_4.svg", svg)


def test_case_03_right_triangle_with_circumcircle():
    """直角三角形，直角在 C；外接圆半径应为斜边/2。"""
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "circ", "kind": "circle",
             "definition": {"type": "circumcircle", "of": "tri"}},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    })
    validate(dsl)
    sol = solve(dsl, seed=3)
    assert sol.residual < 1e-6

    pa, pb, pc = sol.coordinates["A"], sol.coordinates["B"], sol.coordinates["C"]
    assert abs(_dist(pa, pb) - 5) < 1e-3  # 3-4-5
    r = sol.circles["circ"]["radius"]
    assert abs(r - 2.5) < 1e-3  # 外接圆半径 = 斜边/2

    svg = render_svg(dsl, sol)
    _write_golden("03_right_3_4_5.svg", svg)


def test_case_04_square_side_5():
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CD", "kind": "segment", "a": "C", "b": "D"},
            {"id": "DA", "kind": "segment", "a": "D", "b": "A"},
            {"id": "sq", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "equal_length", "segments": ["AB", "BC", "CD", "DA"]},
            {"type": "perpendicular", "a": "AB", "b": "BC"},
            {"type": "perpendicular", "a": "BC", "b": "CD"},
            {"type": "length", "segment": "AB", "value": 5},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    })
    validate(dsl)
    sol = solve(dsl, seed=4, restarts=10)
    assert sol.residual < 1e-4

    pa, pb, pc, pd = (
        sol.coordinates[k] for k in ("A", "B", "C", "D")
    )
    for side in [(pa, pb), (pb, pc), (pc, pd), (pd, pa)]:
        assert abs(_dist(*side) - 5) < 1e-3
    # 对角线相等
    assert abs(_dist(pa, pc) - _dist(pb, pd)) < 1e-3

    svg = render_svg(dsl, sol)
    _write_golden("04_square_5.svg", svg)


def test_case_05_circle_with_inscribed_angle():
    """圆 O 半径 5，A、B 在圆上，∠AOB = 90° → 弦 AB = 5√2"""
    dsl = DSL.model_validate({
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "OB", "kind": "segment", "a": "O", "b": "B"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "circ", "kind": "circle",
             "definition": {"type": "center_radius", "center": "O", "radius": 5}},
        ],
        "constraints": [
            {"type": "on_circle", "point": "A", "circle": "circ"},
            {"type": "on_circle", "point": "B", "circle": "circ"},
            {"type": "angle", "a": "A", "b": "O", "c": "B", "value": 90},
        ],
        "labels": {"O": "O", "A": "A", "B": "B"},
        "annotations": [
            {"target": "AB", "kind": "length"},
        ],
    })
    validate(dsl)
    sol = solve(dsl, seed=5, restarts=10)
    assert sol.residual < 1e-4

    po, pa, pb = sol.coordinates["O"], sol.coordinates["A"], sol.coordinates["B"]
    assert abs(_dist(po, pa) - 5) < 1e-3
    assert abs(_dist(po, pb) - 5) < 1e-3
    expected = 5 * math.sqrt(2)
    assert abs(_dist(pa, pb) - expected) < 1e-2

    svg = render_svg(dsl, sol)
    _write_golden("05_circle_chord.svg", svg)


# ---------------------------------------------------------------------------

def _write_golden(name: str, svg: str) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    (GOLDEN_DIR / name).write_text(svg, encoding="utf-8")
