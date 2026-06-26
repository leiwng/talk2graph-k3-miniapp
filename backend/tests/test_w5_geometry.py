"""W5 测试：新约束（中点 / 垂足 / 角平分线 / 共圆 / 平行四边形）+ 渲染装饰。"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import validate
from app.render.svg import render_svg
from app.solver.engine import solve

GOLDEN = Path(__file__).parent / "golden"


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _save(name: str, svg: str) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / name).write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------------------

def test_midpoint_on_segment():
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "M", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 10},
            {"type": "midpoint", "m": "M", "a": "A", "b": "B"},
        ],
        "labels": {"A": "A", "B": "B", "M": "M"},
    })
    validate(dsl)
    sol = solve(dsl, seed=10)
    assert sol.residual < 1e-6
    pa = sol.coordinates["A"]
    pb = sol.coordinates["B"]
    pm = sol.coordinates["M"]
    assert abs(_dist(pa, pm) - 5) < 1e-3
    assert abs(_dist(pb, pm) - 5) < 1e-3
    _save("w5_01_midpoint.svg", render_svg(dsl, sol))


def test_foot_of_perpendicular_in_right_triangle():
    """直角三角形 ABC（C 直角），H 是 C 到 AB 的垂足。"""
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "H", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "CH", "kind": "segment", "a": "C", "b": "H"},
            {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
            {"type": "foot_of_perp", "f": "H", "p": "C", "a": "A", "b": "B"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "H": "H"},
    })
    validate(dsl)
    sol = solve(dsl, seed=11, restarts=10)
    assert sol.residual < 1e-4

    pa = sol.coordinates["A"]
    pb = sol.coordinates["B"]
    pc = sol.coordinates["C"]
    ph = sol.coordinates["H"]
    # CH ⊥ AB
    ab = (pb[0] - pa[0], pb[1] - pa[1])
    ch = (ph[0] - pc[0], ph[1] - pc[1])
    dot = ab[0] * ch[0] + ab[1] * ch[1]
    assert abs(dot) < 1e-3
    # CH 长度 = 2.4 （3-4-5 直角三角形）
    assert abs(_dist(pc, ph) - 2.4) < 1e-2
    _save("w5_02_foot_of_perp.svg", render_svg(dsl, sol))


def test_parallelogram():
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
            {"id": "p", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "parallelogram", "polygon": "p"},
            {"type": "length", "segment": "AB", "value": 6},
            {"type": "length", "segment": "BC", "value": 4},
            {"type": "angle", "a": "D", "b": "A", "c": "B", "value": 70},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    })
    validate(dsl)
    sol = solve(dsl, seed=12, restarts=10)
    assert sol.residual < 1e-4

    pa = sol.coordinates["A"]; pb = sol.coordinates["B"]
    pc = sol.coordinates["C"]; pd = sol.coordinates["D"]
    # 对边等长
    assert abs(_dist(pa, pb) - _dist(pd, pc)) < 1e-3
    assert abs(_dist(pb, pc) - _dist(pa, pd)) < 1e-3
    # 对角线互相平分
    mid_ac = ((pa[0] + pc[0]) / 2, (pa[1] + pc[1]) / 2)
    mid_bd = ((pb[0] + pd[0]) / 2, (pb[1] + pd[1]) / 2)
    assert abs(mid_ac[0] - mid_bd[0]) < 1e-3
    assert abs(mid_ac[1] - mid_bd[1]) < 1e-3
    _save("w5_03_parallelogram.svg", render_svg(dsl, sol))


def test_concyclic_four_points():
    """A、B、C、D 共圆，给若干长度。"""
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
            {"id": "q", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
        ],
        "constraints": [
            {"type": "concyclic", "points": ["A", "B", "C", "D"]},
            {"type": "length", "segment": "AB", "value": 3},
            {"type": "length", "segment": "BC", "value": 4},
            {"type": "length", "segment": "CD", "value": 3},
            {"type": "length", "segment": "DA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    })
    validate(dsl)
    sol = solve(dsl, seed=13, restarts=15)
    assert sol.residual < 1e-3

    # 验证四点共圆：取前三点定圆，检查 D
    pa = sol.coordinates["A"]
    pb = sol.coordinates["B"]
    pc = sol.coordinates["C"]
    pd = sol.coordinates["D"]
    cx, cy, r = _circumscribed(pa, pb, pc)
    assert abs(_dist(pd, (cx, cy)) - r) < 1e-2
    _save("w5_04_concyclic.svg", render_svg(dsl, sol))


def test_angle_bisector_in_triangle():
    """在三角形 ABC 中，AD 平分 ∠BAC，D 在 BC 上。"""
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "C", "kind": "point"},
            {"id": "D", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
            {"id": "BC", "kind": "segment", "a": "B", "b": "C"},
            {"id": "CA", "kind": "segment", "a": "C", "b": "A"},
            {"id": "AD", "kind": "segment", "a": "A", "b": "D"},
        ],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 4},
            {"type": "length", "segment": "CA", "value": 6},
            {"type": "length", "segment": "BC", "value": 5},
            {"type": "collinear", "points": ["B", "D", "C"]},
            {"type": "angle_bisector", "a": "B", "b": "A", "c": "C", "d": "D"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    })
    validate(dsl)
    sol = solve(dsl, seed=14, restarts=15)
    assert sol.residual < 1e-3

    # 角平分线定理：BD/DC = AB/AC = 4/6 = 2/3
    pa = sol.coordinates["A"]
    pb = sol.coordinates["B"]
    pc = sol.coordinates["C"]
    pd = sol.coordinates["D"]
    bd = _dist(pb, pd)
    dc = _dist(pd, pc)
    ratio = bd / dc
    assert abs(ratio - 4 / 6) < 1e-2
    _save("w5_05_angle_bisector.svg", render_svg(dsl, sol))


# ---------------------------------------------------------------------------
# 渲染装饰
# ---------------------------------------------------------------------------

def test_renderer_has_data_id_attrs():
    dsl = DSL.model_validate({
        "objects": [
            {"id": "A", "kind": "point"},
            {"id": "B", "kind": "point"},
            {"id": "AB", "kind": "segment", "a": "A", "b": "B"},
        ],
        "constraints": [{"type": "length", "segment": "AB", "value": 4}],
        "labels": {"A": "A", "B": "B"},
    })
    sol = solve(dsl)
    svg = render_svg(dsl, sol)
    assert 'data-id="A"' in svg
    assert 'data-id="B"' in svg
    assert 'data-id="AB"' in svg
    assert 't2g-obj' in svg
    assert 't2g-point' in svg
    assert 't2g-seg' in svg


def test_renderer_draws_right_angle_marker():
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
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    })
    sol = solve(dsl, seed=20, restarts=10)
    svg = render_svg(dsl, sol)
    # 直角标记是一个 polyline
    assert '<polyline points="' in svg


def test_renderer_draws_equal_length_ticks_for_equilateral():
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
            {"type": "length", "segment": "AB", "value": 5},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    })
    sol = solve(dsl, seed=21)
    svg = render_svg(dsl, sol)
    # equilateral 触发等长刻度 → 至少 3 个短刻度 line（每边 1 道）
    assert svg.count("stroke-width=\"1.2\"") >= 3


def test_renderer_draws_angle_arc():
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
            {"type": "length", "segment": "AB", "value": 4},
            {"type": "length", "segment": "BC", "value": 5},
            {"type": "angle", "a": "A", "b": "B", "c": "C", "value": 60},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    })
    sol = solve(dsl, seed=22)
    svg = render_svg(dsl, sol)
    # 非 90° 角应该有弧 path
    assert '<path d="M ' in svg


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _circumscribed(p1, p2, p3):
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    a1 = 2 * (x2 - x1); b1 = 2 * (y2 - y1)
    c1 = x2 * x2 + y2 * y2 - x1 * x1 - y1 * y1
    a2 = 2 * (x3 - x1); b2 = 2 * (y3 - y1)
    c2 = x3 * x3 + y3 * y3 - x1 * x1 - y1 * y1
    det = a1 * b2 - a2 * b1
    cx = (c1 * b2 - c2 * b1) / det
    cy = (a1 * c2 - a2 * c1) / det
    r = math.hypot(x1 - cx, y1 - cy)
    return cx, cy, r
