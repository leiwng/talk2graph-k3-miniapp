"""W6 压测：20 道初中常见几何题（NL → DSL → 求解 → 渲染），用 MockProvider 跑通。

每题在 cases 列表里写出预期 DSL；MockProvider 直接返回它。
验收标准：
- 求解残差 < 1e-3
- SVG 非空
"""
from __future__ import annotations

import json
import math

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import validate
from app.llm.extractor import extract_dsl
from app.llm.mock import MockProvider
from app.render.svg import render_svg
from app.solver.engine import solve


def _eq(name, vertices=None):
    return {"id": name, "kind": "polygon", "vertices": vertices}


def _p(name):
    return {"id": name, "kind": "point"}


def _seg(name, a, b):
    return {"id": name, "kind": "segment", "a": a, "b": b}


def _triangle_objs():
    return [
        _p("A"), _p("B"), _p("C"),
        _seg("AB", "A", "B"), _seg("BC", "B", "C"), _seg("CA", "C", "A"),
        {"id": "tri", "kind": "polygon", "vertices": ["A", "B", "C"]},
    ]


def _quad_objs():
    return [
        _p("A"), _p("B"), _p("C"), _p("D"),
        _seg("AB", "A", "B"), _seg("BC", "B", "C"),
        _seg("CD", "C", "D"), _seg("DA", "D", "A"),
        {"id": "quad", "kind": "polygon", "vertices": ["A", "B", "C", "D"]},
    ]


CASES: list[tuple[str, dict]] = [
    ("等边三角形边长 5", {
        "objects": _triangle_objs(),
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 5},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("等腰三角形 顶角 40 度 腰 6", {
        "objects": _triangle_objs(),
        "constraints": [
            {"type": "isoceles", "polygon": "tri", "apex": "A"},
            {"type": "angle", "a": "B", "b": "A", "c": "C", "value": 40},
            {"type": "length", "segment": "AB", "value": 6},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("直角三角形 3-4-5", {
        "objects": _triangle_objs(),
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "CA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("等腰直角三角形 腰 4", {
        "objects": _triangle_objs(),
        "constraints": [
            {"type": "right_triangle", "polygon": "tri", "right_at": "C"},
            {"type": "equal_length", "segments": ["CA", "BC"]},
            {"type": "length", "segment": "CA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("三角形含中线", {
        "objects": _triangle_objs() + [_p("M"), _seg("AM", "A", "M")],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 5},
            {"type": "length", "segment": "BC", "value": 6},
            {"type": "length", "segment": "CA", "value": 7},
            {"type": "midpoint", "m": "M", "a": "B", "b": "C"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "M": "M"},
    }),
    ("三角形含高线（C 到 AB）", {
        "objects": _triangle_objs() + [_p("H"), _seg("CH", "C", "H")],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 6},
            {"type": "length", "segment": "BC", "value": 5},
            {"type": "length", "segment": "CA", "value": 4},
            {"type": "foot_of_perp", "f": "H", "p": "C", "a": "A", "b": "B"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "H": "H"},
    }),
    ("三角形角平分线 BD/DC=AB/AC", {
        "objects": _triangle_objs() + [_p("D"), _seg("AD", "A", "D")],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 4},
            {"type": "length", "segment": "CA", "value": 6},
            {"type": "length", "segment": "BC", "value": 5},
            {"type": "collinear", "points": ["B", "D", "C"]},
            {"type": "angle_bisector", "a": "B", "b": "A", "c": "C", "d": "D"},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("正方形 边长 5", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "equal_length", "segments": ["AB", "BC", "CD", "DA"]},
            {"type": "perpendicular", "a": "AB", "b": "BC"},
            {"type": "perpendicular", "a": "BC", "b": "CD"},
            {"type": "length", "segment": "AB", "value": 5},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("矩形 长 6 宽 4", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "perpendicular", "a": "AB", "b": "BC"},
            {"type": "perpendicular", "a": "BC", "b": "CD"},
            {"type": "perpendicular", "a": "CD", "b": "DA"},
            {"type": "length", "segment": "AB", "value": 6},
            {"type": "length", "segment": "BC", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("菱形 边长 4 ∠A=60", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "equal_length", "segments": ["AB", "BC", "CD", "DA"]},
            {"type": "length", "segment": "AB", "value": 4},
            {"type": "angle", "a": "D", "b": "A", "c": "B", "value": 60},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("平行四边形 AB=6 BC=4 ∠A=70", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "parallelogram", "polygon": "quad"},
            {"type": "length", "segment": "AB", "value": 6},
            {"type": "length", "segment": "BC", "value": 4},
            {"type": "angle", "a": "D", "b": "A", "c": "B", "value": 70},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("圆 r=5 + 圆心角 90", {
        "objects": [
            _p("O"), _p("A"), _p("B"),
            _seg("OA", "O", "A"), _seg("OB", "O", "B"), _seg("AB", "A", "B"),
            {"id": "circ", "kind": "circle",
             "definition": {"type": "center_radius", "center": "O", "radius": 5}},
        ],
        "constraints": [
            {"type": "on_circle", "point": "A", "circle": "circ"},
            {"type": "on_circle", "point": "B", "circle": "circ"},
            {"type": "angle", "a": "A", "b": "O", "c": "B", "value": 90},
        ],
        "labels": {"O": "O", "A": "A", "B": "B"},
    }),
    ("直径上的圆周角", {
        "objects": [
            _p("O"), _p("A"), _p("B"), _p("C"),
            _seg("AB", "A", "B"),
            {"id": "circ", "kind": "circle",
             "definition": {"type": "center_radius", "center": "O", "radius": 5}},
        ],
        "constraints": [
            {"type": "on_circle", "point": "A", "circle": "circ"},
            {"type": "on_circle", "point": "B", "circle": "circ"},
            {"type": "on_circle", "point": "C", "circle": "circ"},
            {"type": "collinear", "points": ["A", "O", "B"]},
        ],
        "labels": {"O": "O", "A": "A", "B": "B", "C": "C"},
    }),
    ("内切圆 r=3 等腰三角形 底角 60", {
        "objects": _triangle_objs() + [{
            "id": "inc", "kind": "circle",
            "definition": {"type": "incircle", "of": "tri"},
        }],
        "constraints": [
            {"type": "isoceles", "polygon": "tri", "apex": "A"},
            {"type": "radius", "circle": "inc", "value": 3},
            {"type": "angle", "a": "A", "b": "B", "c": "C", "value": 60},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("外接圆 + 三边", {
        "objects": _triangle_objs() + [{
            "id": "circ", "kind": "circle",
            "definition": {"type": "circumcircle", "of": "tri"},
        }],
        "constraints": [
            {"type": "length", "segment": "AB", "value": 5},
            {"type": "length", "segment": "BC", "value": 6},
            {"type": "length", "segment": "CA", "value": 7},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
    ("圆 O 半径 5 + 切线 AT", {
        "objects": [
            _p("O"), _p("A"), _p("T"),
            _seg("OT", "O", "T"), _seg("AT", "A", "T"),
            {"id": "circ", "kind": "circle",
             "definition": {"type": "center_radius", "center": "O", "radius": 5}},
        ],
        "constraints": [
            {"type": "on_circle", "point": "T", "circle": "circ"},
            {"type": "tangent", "line": "AT", "circle": "circ"},
            {"type": "length", "segment": "AT", "value": 12},
        ],
        "labels": {"O": "O", "A": "A", "T": "T"},
    }),
    ("梯形 AB ∥ CD", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "parallel", "a": "AB", "b": "CD"},
            {"type": "length", "segment": "AB", "value": 8},
            {"type": "length", "segment": "CD", "value": 4},
            {"type": "length", "segment": "BC", "value": 3},
            {"type": "length", "segment": "DA", "value": 3},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("四点共圆 + 边长 3434", {
        "objects": _quad_objs(),
        "constraints": [
            {"type": "concyclic", "points": ["A", "B", "C", "D"]},
            {"type": "length", "segment": "AB", "value": 3},
            {"type": "length", "segment": "BC", "value": 4},
            {"type": "length", "segment": "CD", "value": 3},
            {"type": "length", "segment": "DA", "value": 4},
        ],
        "labels": {"A": "A", "B": "B", "C": "C", "D": "D"},
    }),
    ("线段 AB 上的点 P：AP=2 PB=3", {
        "objects": [
            _p("A"), _p("B"), _p("P"),
            _seg("AB", "A", "B"),
            _seg("AP", "A", "P"), _seg("PB", "P", "B"),
        ],
        "constraints": [
            {"type": "collinear", "points": ["A", "P", "B"]},
            {"type": "length", "segment": "AP", "value": 2},
            {"type": "length", "segment": "PB", "value": 3},
        ],
        "labels": {"A": "A", "B": "B", "P": "P"},
    }),
    ("等边三角形 + 外接圆", {
        "objects": _triangle_objs() + [{
            "id": "circ", "kind": "circle",
            "definition": {"type": "circumcircle", "of": "tri"},
        }],
        "constraints": [
            {"type": "equilateral", "polygon": "tri"},
            {"type": "length", "segment": "AB", "value": 6},
        ],
        "labels": {"A": "A", "B": "B", "C": "C"},
    }),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,dsl_dict", CASES, ids=[c[0] for c in CASES])
async def test_stress_case(name: str, dsl_dict: dict):
    """每条 NL → MockProvider 返回 DSL → 抽取 → 求解 → 渲染。"""
    full = {"version": "0.1", **dsl_dict, "annotations": []}
    provider = MockProvider(handler=lambda m, d=full: json.dumps(d, ensure_ascii=False))
    result = await extract_dsl(provider, name)
    assert result.dsl is not None, f"抽取失败 ({name}): {result.error}"
    validate(result.dsl)
    sol = solve(result.dsl, seed=42, restarts=30)
    assert sol.residual < 1e-3, f"求解失败 ({name})：残差 {sol.residual:.3e}"
    svg = render_svg(result.dsl, sol)
    assert svg.startswith("<svg")
    assert "</svg>" in svg
