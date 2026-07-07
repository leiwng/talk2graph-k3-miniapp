"""文本 → SVG path outline 转换（V2-C）。

用内置 Source Han Sans SC 子集字体把字符渲染成矢量 path，替代 <text> 元素，
解决 SVG/PNG/PDF 复制到 PPT 后中文字体丢失的问题。

字符 → path 提取仅在首次访问时执行，结果缓存，后续渲染零成本。
"""
from __future__ import annotations

import threading
import xml.sax.saxutils as sx
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

_FONT_PATH = (
    Path(__file__).parent.parent.parent / "assets" / "fonts" / "SourceHanSansSC-Subset.otf"
)

_font: TTFont | None = None
_glyf = None
_cmap: dict[int, str] = {}
_upem: int = 1000
_advance: dict[str, float] = {}
_path_cache: dict[str, str] = {}
_lock = threading.Lock()


def _ensure_loaded() -> None:
    """惰性加载字体（首次调用时）。线程安全。"""
    global _font, _glyf, _cmap, _upem, _advance
    if _font is not None:
        return
    with _lock:
        if _font is not None:
            return
        if not _FONT_PATH.exists():
            raise FileNotFoundError(
                f"V2-C outline 字体未找到：{_FONT_PATH}（请确认子集化字体已就位）"
            )
        _font = TTFont(_FONT_PATH)
        _glyf = _font.getGlyphSet()
        _cmap = _font.getBestCmap()
        _upem = _font["head"].unitsPerEm
        hmtx = _font["hmtx"]
        for cp, glyph_name in _cmap.items():
            _advance[glyph_name] = float(hmtx[glyph_name][0])


def _char_path(ch: str) -> str:
    """单字符的 SVG path d 字符串（字体内部坐标，y 向上，em 单位）。"""
    cached = _path_cache.get(ch)
    if cached is not None:
        return cached
    _ensure_loaded()
    cp = ord(ch)
    glyph_name = _cmap.get(cp)
    if glyph_name is None:
        _path_cache[ch] = ""
        return ""
    pen = SVGPathPen(_glyf)
    _glyf[glyph_name].draw(pen)
    d = pen.getCommands()
    _path_cache[ch] = d
    return d


def _char_advance(ch: str) -> float:
    """字符 advance width（字体 em 单位）。"""
    _ensure_loaded()
    glyph_name = _cmap.get(ord(ch))
    if glyph_name is None:
        return _upem * 0.5
    return _advance.get(glyph_name, _upem * 0.5)


def text_to_svg_paths(
    text: str,
    *,
    x: float,
    y: float,
    font_size: float,
    fill: str = "#000",
    anchor: str = "start",
    font_style: str | None = None,
) -> str:
    """把文本转为 SVG <path> 元素字符串。

    Args:
        text: 文本内容（含空格也合法）
        x, y: 文本基线锚点（SVG 像素坐标，y 已是 SVG 向下）
        font_size: 字号（SVG 像素，等价于 <text font-size>)
        fill: 填充色
        anchor: "start" | "middle" | "end"，对齐方式
        font_style: 兼容参数（如 "italic"），outline 化后无效果，仅占位

    Returns:
        多个 <path> 元素拼接的字符串；缺字符自动跳过

    坐标变换：fonttools 字形 path 用字体坐标系（1em = upem 字体单位，y 向上）。
    要让它显示在 SVG（y 向下），用 transform：
        translate(x, y) scale(s, -s) translate(cx_font, 0)
    其中 s = font_size / upem。应用顺序：先 translate(cx_font, 0) 把字符移到正确位置，
    再 scale(s, -s) 把字体单位缩放到像素并翻转 y，最后 translate(x, y) 移到 SVG 锚点。
    """
    _ensure_loaded()
    scale = font_size / _upem

    # 计算每个字符的 advance（字体坐标）
    font_widths = [_char_advance(c) for c in text]
    font_total = sum(font_widths)
    if anchor == "middle":
        start_font_x = -font_total / 2
    elif anchor == "end":
        start_font_x = -font_total
    else:
        start_font_x = 0.0

    parts: list[str] = []
    cx_font = start_font_x
    for ch, fw in zip(text, font_widths):
        d = _char_path(ch)
        if d:
            transform = (
                f"translate({x:.2f} {y:.2f}) "
                f"scale({scale:.4f} {-scale:.4f}) "
                f"translate({cx_font:.2f} 0)"
            )
            parts.append(
                f'<path d="{sx.escape(d)}" fill="{fill}" transform="{transform}"/>'
            )
        cx_font += fw

    return "".join(parts)


def is_available() -> bool:
    """字体文件是否就位（用于测试前置条件）。"""
    return _FONT_PATH.exists()
