"""V3.2 - 统计图表测试（bar_chart / line_chart / pie_chart）。"""
from __future__ import annotations

import pytest

from app.dsl.schema import DSL
from app.dsl.validator import DSLValidationError, validate
from app.render.svg import render_svg
from app.solver.engine import solve


# ---------------------------------------------------------------------------
# 1) Schema
# ---------------------------------------------------------------------------

def test_bar_chart_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "bc1", "kind": "bar_chart", "origin": "O",
             "data": [3, 5, 7, 4], "labels": ["A", "B", "C", "D"]},
        ],
    })
    validate(dsl)
    assert dsl.bar_charts()[0].kind == "bar_chart"
    assert len(dsl.bar_charts()[0].data) == 4


def test_line_chart_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "lc1", "kind": "line_chart", "origin": "O",
             "data": [1, 3, 2, 5, 4], "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"]},
        ],
    })
    validate(dsl)
    assert dsl.line_charts()[0].data == [1, 3, 2, 5, 4]


def test_pie_chart_schema_parses():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "pc1", "kind": "pie_chart", "center": "O",
             "data": [30, 40, 30], "labels": ["A", "B", "C"], "radius": 3},
        ],
    })
    validate(dsl)
    assert dsl.pie_charts()[0].radius == 3


# ---------------------------------------------------------------------------
# 2) Validator
# ---------------------------------------------------------------------------

def test_bar_chart_origin_must_be_point():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "A", "kind": "point"},
            {"id": "OA", "kind": "segment", "a": "O", "b": "A"},
            {"id": "bc1", "kind": "bar_chart", "origin": "OA",
             "data": [1, 2], "labels": ["A", "B"]},
        ],
    })
    with pytest.raises(DSLValidationError, match="bar_chart.*origin"):
        validate(bad)


def test_chart_data_labels_length_mismatch():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "bc1", "kind": "bar_chart", "origin": "O",
             "data": [1, 2, 3], "labels": ["A", "B"]},
        ],
    })
    with pytest.raises(DSLValidationError, match="data and labels length mismatch"):
        validate(bad)


def test_pie_chart_radius_positive():
    bad = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point"},
            {"id": "pc1", "kind": "pie_chart", "center": "O",
             "data": [1, 2], "labels": ["A", "B"], "radius": -1},
        ],
    })
    with pytest.raises(DSLValidationError, match="pie_chart.*radius"):
        validate(bad)


# ---------------------------------------------------------------------------
# 3) Render
# ---------------------------------------------------------------------------

def test_render_bar_chart_has_rects():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "bc1", "kind": "bar_chart", "origin": "O",
             "data": [3, 5, 7, 4], "labels": ["A", "B", "C", "D"]},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="bc1"' in svg
    assert 'class="t2g-obj t2g-bar-chart"' in svg
    assert '<rect' in svg
    assert '<line' in svg  # 坐标轴


def test_render_line_chart_has_polyline():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "lc1", "kind": "line_chart", "origin": "O",
             "data": [1, 3, 2, 5, 4], "labels": ["M", "T", "W", "T", "F"]},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="lc1"' in svg
    assert 'class="t2g-obj t2g-line-chart"' in svg
    assert '<polyline' in svg
    assert '<circle' in svg  # 数据点


def test_render_pie_chart_has_paths():
    dsl = DSL.model_validate({
        "version": "0.1",
        "objects": [
            {"id": "O", "kind": "point", "hint": [0, 0]},
            {"id": "pc1", "kind": "pie_chart", "center": "O",
             "data": [30, 40, 30], "labels": ["A", "B", "C"], "radius": 3},
        ],
    })
    validate(dsl)
    sol = solve(dsl, restarts=5)
    svg = render_svg(dsl, sol)
    assert 'data-id="pc1"' in svg
    assert 'class="t2g-obj t2g-pie-chart"' in svg
    # 应该有 3 个扇形 path
    assert svg.count('<path') >= 3
    # 应该有百分比标签
    assert '%' in svg
