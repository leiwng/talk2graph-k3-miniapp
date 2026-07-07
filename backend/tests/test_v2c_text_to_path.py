"""V2-C 测试：文本 → SVG path outline 转换。

覆盖：
1. text_to_path 模块：字符 → path 提取、多字符拼接、anchor 对齐、缺字符跳过
2. render_svg：outline_text=False 走 <text>、outline_text=True 走 <path>
3. 端到端：等边三角形渲染两版对比
"""
from __future__ import annotations

import pytest

from app.render import text_to_path
from app.render.svg import render_svg


# ---------------------------------------------------------------------------
# 模块层：text_to_path
# ---------------------------------------------------------------------------

def test_font_available():
    assert text_to_path.is_available(), "Source Han Sans 子集字体未就位"


def test_single_char_path():
    out = text_to_path.text_to_svg_paths("A", x=100, y=50, font_size=14, anchor="middle")
    assert out.startswith("<path ")
    assert "d=" in out
    assert "fill=" in out
    assert "transform=" in out


def test_multi_char_paths():
    out = text_to_path.text_to_svg_paths("30°", x=0, y=0, font_size=11, anchor="start")
    # 3 个字符 = 3 个 path
    assert out.count("<path") == 3
    # 每个 path 应有独立的 transform（不同 advance 位置）
    assert out.count("transform=") == 3


def test_anchor_alignment():
    """不同 anchor 下，单字符的 transform 应反映水平偏移。"""
    s = "A"
    out_start = text_to_path.text_to_svg_paths(s, x=100, y=50, font_size=14, anchor="start")
    out_middle = text_to_path.text_to_svg_paths(s, x=100, y=50, font_size=14, anchor="middle")
    out_end = text_to_path.text_to_svg_paths(s, x=100, y=50, font_size=14, anchor="end")
    # 三者 transform 中的 translate(cx_font, 0) 不同
    assert out_start != out_middle
    assert out_middle != out_end
    assert out_start != out_end


def test_missing_char_skipped():
    """字体里没有的字符（如表情）应跳过，不报错。"""
    out = text_to_path.text_to_svg_paths("A★B", x=0, y=0, font_size=12)
    # A 和 B 有 path，★ 跳过
    assert out.count("<path") == 2


def test_cache_hit():
    """同一字符二次访问应命中缓存（返回相同结果）。"""
    a1 = text_to_path.text_to_svg_paths("X", x=0, y=0, font_size=12)
    a2 = text_to_path.text_to_svg_paths("X", x=0, y=0, font_size=12)
    assert a1 == a2


def test_chinese_char():
    """中文字符应能提取出 path（'原'/'点' 在子集字符集里）。"""
    out = text_to_path.text_to_svg_paths("原点", x=10, y=10, font_size=13)
    assert out.count("<path") == 2
    # 中文 path 应有较长的 d 字符串（笔画多）
    assert len(out) > 200


# ---------------------------------------------------------------------------
# render_svg 集成：outline_text 开关
# ---------------------------------------------------------------------------

def _build_simple_dsl():
    """简单等边三角形 DSL 用于渲染测试。"""
    from app.dsl.schema import (
        DSL,
        EqualLengthC,
        PointObj,
        PolygonObj,
        SegmentObj,
    )
    return DSL(
        version="0.1",
        objects=[
            PointObj(id="A", hint=(0.0, 0.0)),
            PointObj(id="B", hint=(1.0, 0.0)),
            PointObj(id="C", hint=(0.5, 0.866)),
            SegmentObj(id="AB", a="A", b="B"),
            SegmentObj(id="BC", a="B", b="C"),
            SegmentObj(id="CA", a="C", b="A"),
            PolygonObj(id="tri", vertices=["A", "B", "C"]),
        ],
            constraints=[EqualLengthC(type="equal_length", segments=["AB", "BC", "CA"])],
    )


def _solve(dsl):
    from app.solver.engine import solve
    return solve(dsl, seed=1, restarts=10)


def test_render_svg_default_uses_text_element():
    dsl = _build_simple_dsl()
    sol = _solve(dsl)
    svg = render_svg(dsl, sol)
    # 默认 outline_text=False：应有 <text> 元素
    assert "<text" in svg
    # 不应有 V2-C 的 outline <path>（注意区分几何 path 和 outline path：
    # 几何 path 有 class="t2g-obj" 或 d="M..."，但 outline path 的 d 来自字体）
    # 简单断言：默认渲染下 A/B/C 标签在 <text> 内
    assert ">A<" in svg or ">A</text>" in svg


def test_render_svg_outline_uses_path_only():
    dsl = _build_simple_dsl()
    sol = _solve(dsl)
    svg = render_svg(dsl, sol, outline_text=True)
    # outline 模式：不应有 <text 元素
    assert "<text" not in svg
    # 应有大量 <path（几何 + 文字 outline）
    assert svg.count("<path") >= 3  # 至少 3 个字母的 outline


def test_render_svg_outline_preserves_geometry():
    """outline 模式下几何元素（圆/线段）不变，仅文字替换。"""
    dsl = _build_simple_dsl()
    sol = _solve(dsl)
    svg_default = render_svg(dsl, sol)
    svg_outline = render_svg(dsl, sol, outline_text=True)
    # 几何元素数量相同：<circle>/<line>/<polygon>
    assert svg_default.count("<circle") == svg_outline.count("<circle")
    assert svg_default.count("<line") == svg_outline.count("<line")
    assert svg_default.count("<polygon") == svg_outline.count("<polygon")


def test_render_axis_outline():
    """含坐标系的 DSL：outline 模式下刻度数字也转为 path。"""
    from app.dsl.schema import AxisObj, DSL, PointObj, SegmentObj
    dsl = DSL(
        version="0.1",
        objects=[
            PointObj(id="O", hint=(0.0, 0.0)),
            AxisObj(id="axis", origin="O", x_range=[-3, 3], y_range=[-3, 3],
                    tick_step=1.0, show_grid=True, show_ticks=True),
        ],
        constraints=[],
    )
    from app.solver.engine import solve
    sol = solve(dsl, seed=1)
    svg_default = render_svg(dsl, sol)
    svg_outline = render_svg(dsl, sol, outline_text=True)
    # 默认有刻度数字 <text>（如 "1" "2" "-1" 等）
    assert "<text" in svg_default
    # outline 模式无 <text>，刻度数字也变 path
    assert "<text" not in svg_outline
    assert "<path" in svg_outline
