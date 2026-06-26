"""SVG 渲染器。

输入：DSL + Solution
输出：SVG 字符串（含中文标签 / 几何元素）

W1 范围：点、线段、直线、圆、多边形、基本标注（长度/角度/标签）。
"""
from __future__ import annotations

import math
import xml.sax.saxutils as sx
from dataclasses import dataclass

from ..dsl.schema import (
    CircleObj,
    DSL,
    LineObj,
    PointObj,
    PolygonObj,
    SegmentObj,
    Style,
)
from ..solver.engine import Solution


@dataclass
class _BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    @property
    def width(self) -> float:
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        return self.maxy - self.miny

    def expand(self, pad: float) -> "_BBox":
        return _BBox(self.minx - pad, self.miny - pad, self.maxx + pad, self.maxy + pad)


def render_svg(
    dsl: DSL,
    sol: Solution,
    *,
    canvas_size: int = 480,
    margin: float = 40.0,
) -> str:
    style = dsl.style
    bbox = _compute_bbox(dsl, sol)
    if bbox.width < 1e-9 and bbox.height < 1e-9:
        bbox = _BBox(bbox.minx - 1, bbox.miny - 1, bbox.maxx + 1, bbox.maxy + 1)
    bbox = bbox.expand(max(bbox.width, bbox.height) * 0.12 + 0.1)

    scale = (canvas_size - 2 * margin) / max(bbox.width, bbox.height, 1e-6)
    # 居中
    offset_x = margin + (canvas_size - 2 * margin - bbox.width * scale) / 2
    offset_y = margin + (canvas_size - 2 * margin - bbox.height * scale) / 2

    def tx(x: float, y: float) -> tuple[float, float]:
        # 数学坐标系 → SVG（y 翻转）
        sx_ = offset_x + (x - bbox.minx) * scale
        sy_ = canvas_size - (offset_y + (y - bbox.miny) * scale)
        return sx_, sy_

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_size} {canvas_size}" '
        f'width="{canvas_size}" height="{canvas_size}" '
        f'data-t2g-scale="{scale}" '
        f'data-t2g-offset-x="{offset_x}" '
        f'data-t2g-offset-y="{offset_y}" '
        f'data-t2g-bbox-minx="{bbox.minx}" '
        f'data-t2g-bbox-miny="{bbox.miny}" '
        f'data-t2g-canvas-size="{canvas_size}" '
        f'font-family="{sx.escape(style.font_family)}" '
        f'font-size="{style.font_size}">'
    )
    parts.append(
        f'<rect width="100%" height="100%" fill="white"/>'
    )

    # 圆
    for c in dsl.circles():
        info = sol.circles.get(c.id)
        if not info:
            continue
        cx, cy = info["center"]
        r = info["radius"]
        scx, scy = tx(cx, cy)
        parts.append(
            f'<circle data-id="{c.id}" class="t2g-obj t2g-circle" '
            f'cx="{scx:.2f}" cy="{scy:.2f}" r="{r * scale:.2f}" '
            f'fill="none" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        )

    # 多边形（用其顶点描边，不填充）
    for poly in dsl.polygons():
        pts = []
        for v in poly.vertices:
            if v in sol.coordinates:
                sx_, sy_ = tx(*sol.coordinates[v])
                pts.append(f"{sx_:.2f},{sy_:.2f}")
        if pts:
            parts.append(
                f'<polygon data-id="{poly.id}" class="t2g-obj t2g-poly" '
                f'points="{" ".join(pts)}" fill="none" '
                f'stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
            )

    # 线段
    for seg in dsl.segments():
        if seg.a not in sol.coordinates or seg.b not in sol.coordinates:
            continue
        x1, y1 = tx(*sol.coordinates[seg.a])
        x2, y2 = tx(*sol.coordinates[seg.b])
        parts.append(
            f'<line data-id="{seg.id}" class="t2g-obj t2g-seg" '
            f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        )

    # 直线（延长到画布边缘）
    for line in [o for o in dsl.objects if isinstance(o, LineObj)]:
        if line.a not in sol.coordinates or line.b not in sol.coordinates:
            continue
        x1, y1 = tx(*sol.coordinates[line.a])
        x2, y2 = tx(*sol.coordinates[line.b])
        # 简单延长
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        ext = canvas_size * 2
        ex1, ey1 = x1 - dx / L * ext, y1 - dy / L * ext
        ex2, ey2 = x2 + dx / L * ext, y2 + dy / L * ext
        parts.append(
            f'<line x1="{ex1:.2f}" y1="{ey1:.2f}" x2="{ex2:.2f}" y2="{ey2:.2f}" '
            f'stroke="{style.stroke}" stroke-width="{style.stroke_width}" '
            f'stroke-dasharray="{style.aux_dash}"/>'
        )

    # 点 + 标签
    for p in dsl.points():
        if p.id not in sol.coordinates:
            continue
        x, y = tx(*sol.coordinates[p.id])
        parts.append(
            f'<circle data-id="{p.id}" class="t2g-obj t2g-point" '
            f'cx="{x:.2f}" cy="{y:.2f}" r="{style.point_radius}" '
            f'fill="{style.stroke}"/>'
        )
        label = dsl.labels.get(p.id, p.id)
        # 标签偏移：背离图形中心
        cx0, cy0 = _figure_center(sol)
        sx0, sy0 = tx(cx0, cy0)
        ldx, ldy = x - sx0, y - sy0
        ln = math.hypot(ldx, ldy) or 1
        lx = x + ldx / ln * 12
        ly = y + ldy / ln * 12 + 4  # baseline 调整
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="middle" '
            f'fill="{style.stroke}">{sx.escape(label)}</text>'
        )

    # ----- 几何标记（基于约束自动绘制） -----
    parts.extend(_render_decorations(dsl, sol, tx, scale, style))

    # 注解：长度 / 角度 / 半径
    for ann in dsl.annotations:
        text = _annotation_text(ann, dsl, sol)
        if text is None:
            continue
        pos = _annotation_position(ann, dsl, sol, tx, style)
        if pos is None:
            continue
        ax, ay = pos
        parts.append(
            f'<text x="{ax:.2f}" y="{ay:.2f}" text-anchor="middle" '
            f'fill="#555" font-style="italic">{sx.escape(text)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_bbox(dsl: DSL, sol: Solution) -> _BBox:
    xs, ys = [], []
    for x, y in sol.coordinates.values():
        xs.append(x); ys.append(y)
    for cinfo in sol.circles.values():
        cx, cy = cinfo["center"]
        r = cinfo["radius"]
        xs.extend([cx - r, cx + r])
        ys.extend([cy - r, cy + r])
    if not xs:
        return _BBox(-1, -1, 1, 1)
    return _BBox(min(xs), min(ys), max(xs), max(ys))


def _figure_center(sol: Solution) -> tuple[float, float]:
    if not sol.coordinates:
        return 0.0, 0.0
    xs = [p[0] for p in sol.coordinates.values()]
    ys = [p[1] for p in sol.coordinates.values()]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _annotation_text(ann, dsl: DSL, sol: Solution) -> str | None:
    if ann.text:
        return ann.text
    obj_map = dsl.object_map()
    if ann.kind == "label":
        return dsl.labels.get(ann.target, ann.target)
    if ann.kind == "length":
        seg = obj_map.get(ann.target)
        if isinstance(seg, SegmentObj):
            pa = sol.coordinates.get(seg.a); pb = sol.coordinates.get(seg.b)
            if pa and pb:
                return _fmt_num(math.hypot(pa[0] - pb[0], pa[1] - pb[1]))
    if ann.kind == "radius":
        info = sol.circles.get(ann.target)
        if info:
            return _fmt_num(info["radius"])
    if ann.kind == "angle":
        # target 形如 "angleABC"，按字符切分
        s = ann.target
        if s.startswith("angle") and len(s) >= 8:
            a, b, c = s[5], s[6], s[7]
            pa = sol.coordinates.get(a); pb = sol.coordinates.get(b); pc = sol.coordinates.get(c)
            if pa and pb and pc:
                v1 = (pa[0] - pb[0], pa[1] - pb[1])
                v2 = (pc[0] - pb[0], pc[1] - pb[1])
                n1 = math.hypot(*v1); n2 = math.hypot(*v2)
                if n1 > 1e-9 and n2 > 1e-9:
                    cosv = max(-1, min(1, (v1[0]*v2[0]+v1[1]*v2[1])/(n1*n2)))
                    deg = math.degrees(math.acos(cosv))
                    return f"{_fmt_num(deg)}°"
    return None


def _annotation_position(ann, dsl: DSL, sol: Solution, tx, style: Style) -> tuple[float, float] | None:
    obj_map = dsl.object_map()
    if ann.kind in ("length",):
        seg = obj_map.get(ann.target)
        if isinstance(seg, SegmentObj):
            pa = sol.coordinates.get(seg.a); pb = sol.coordinates.get(seg.b)
            if pa and pb:
                mx, my = (pa[0]+pb[0])/2, (pa[1]+pb[1])/2
                # 垂直偏移
                dx, dy = pb[0]-pa[0], pb[1]-pa[1]
                L = math.hypot(dx, dy) or 1
                nx, ny = -dy/L, dx/L
                off = 0.18 * L
                sxv, syv = tx(mx + nx*off, my + ny*off)
                return sxv, syv
    if ann.kind == "radius":
        info = sol.circles.get(ann.target)
        if info:
            cx, cy = info["center"]; r = info["radius"]
            sxv, syv = tx(cx + r*0.5, cy + r*0.3)
            return sxv, syv
    if ann.kind == "angle":
        s = ann.target
        if s.startswith("angle") and len(s) >= 8:
            b = s[6]
            pb = sol.coordinates.get(b)
            if pb:
                sxv, syv = tx(pb[0] + 0.3, pb[1] + 0.3)
                return sxv, syv
    if ann.kind == "label":
        p = sol.coordinates.get(ann.target)
        if p:
            return tx(p[0], p[1])
    return None


def _fmt_num(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# 几何装饰：直角小方块 / 等长刻度 / 角度弧
# ---------------------------------------------------------------------------

def _render_decorations(dsl: DSL, sol: Solution, tx, scale: float, style: Style) -> list[str]:
    """根据约束自动添加教学常见标记。"""
    out: list[str] = []
    obj_map = dsl.object_map()
    seg_endpoints = {s.id: (s.a, s.b) for s in dsl.segments()}

    # 1) 直角标记：right_triangle / perpendicular
    right_corners: list[tuple[str, str, str]] = []   # (vertex, ray_a, ray_b)
    for c in dsl.constraints:
        if c.type == "right_triangle":
            poly = obj_map.get(c.polygon)
            if isinstance(poly, PolygonObj) and len(poly.vertices) == 3:
                others = [v for v in poly.vertices if v != c.right_at]
                if len(others) == 2:
                    right_corners.append((c.right_at, others[0], others[1]))
        elif c.type == "perpendicular":
            sa = seg_endpoints.get(c.a)
            sb = seg_endpoints.get(c.b)
            if sa and sb:
                common = set(sa) & set(sb)
                if len(common) == 1:
                    v = next(iter(common))
                    ra = sa[0] if sa[1] == v else sa[1]
                    rb = sb[0] if sb[1] == v else sb[1]
                    right_corners.append((v, ra, rb))

    for v, a, b in right_corners:
        if v not in sol.coordinates or a not in sol.coordinates or b not in sol.coordinates:
            continue
        out.append(_right_angle_marker(sol.coordinates[v], sol.coordinates[a],
                                       sol.coordinates[b], tx, style))

    # 2) 等长刻度：equal_length / equilateral / isoceles
    tick_groups: list[list[str]] = []   # 每组 segment id
    for c in dsl.constraints:
        if c.type == "equal_length":
            tick_groups.append(list(c.segments))
        elif c.type == "equilateral":
            poly = obj_map.get(c.polygon)
            if isinstance(poly, PolygonObj):
                segs = _polygon_sides(dsl, poly)
                if len(segs) == 3:
                    tick_groups.append(segs)
        elif c.type == "isoceles":
            poly = obj_map.get(c.polygon)
            if isinstance(poly, PolygonObj) and len(poly.vertices) == 3:
                others = [v for v in poly.vertices if v != c.apex]
                if len(others) == 2:
                    s1 = _find_segment(dsl, c.apex, others[0])
                    s2 = _find_segment(dsl, c.apex, others[1])
                    if s1 and s2:
                        tick_groups.append([s1, s2])

    for gi, group in enumerate(tick_groups):
        n_ticks = (gi % 3) + 1   # 第 1/2/3 组分别 1/2/3 道刻度
        for seg_id in group:
            ep = seg_endpoints.get(seg_id)
            if not ep:
                continue
            a, b = ep
            if a not in sol.coordinates or b not in sol.coordinates:
                continue
            out.append(_equal_length_ticks(
                sol.coordinates[a], sol.coordinates[b], n_ticks, tx, style
            ))

    # 3) 角度弧：仅对 angle 约束绘制一个小弧
    for c in dsl.constraints:
        if c.type == "angle":
            if all(p in sol.coordinates for p in (c.a, c.b, c.c)):
                out.append(_angle_arc(
                    sol.coordinates[c.a], sol.coordinates[c.b],
                    sol.coordinates[c.c], tx, style, value=c.value,
                ))
    return out


def _polygon_sides(dsl: DSL, poly: PolygonObj) -> list[str]:
    """返回 polygon 顶点顺序对应的边 id（必须在 DSL 中已声明）。"""
    out: list[str] = []
    v = poly.vertices
    n = len(v)
    for i in range(n):
        s = _find_segment(dsl, v[i], v[(i + 1) % n])
        if s is None:
            return []
        out.append(s)
    return out


def _find_segment(dsl: DSL, a: str, b: str) -> str | None:
    for s in dsl.segments():
        if {s.a, s.b} == {a, b}:
            return s.id
    return None


def _right_angle_marker(v, a, b, tx, style: Style) -> str:
    """在顶点 v 处绘制直角小方块（数学坐标输入，画到 SVG 上）。"""
    import math as _m
    vx, vy = v
    ax, ay = a
    bx, by = b
    la = _m.hypot(ax - vx, ay - vy) or 1
    lb = _m.hypot(bx - vx, by - vy) or 1
    # 在 SVG 像素里画固定大小 12px
    # 转换 v、v + unit*size 到 SVG
    size_math_a = 0.0  # 不直接用，使用 SVG 像素后处理
    # 我们改为：先把 v、a、b 转到 SVG 像素，再做单位向量
    svx, svy = tx(vx, vy)
    sax, say = tx(ax, ay)
    sbx, sby = tx(bx, by)
    dax = sax - svx; day = say - svy
    dbx = sbx - svx; dby = sby - svy
    nla = _m.hypot(dax, day) or 1
    nlb = _m.hypot(dbx, dby) or 1
    s = 10.0
    p1x = svx + dax / nla * s
    p1y = svy + day / nla * s
    p2x = svx + dbx / nlb * s
    p2y = svy + dby / nlb * s
    p3x = p1x + dbx / nlb * s
    p3y = p1y + dby / nlb * s
    return (
        f'<polyline points="{p1x:.2f},{p1y:.2f} {p3x:.2f},{p3y:.2f} '
        f'{p2x:.2f},{p2y:.2f}" fill="none" '
        f'stroke="{style.stroke}" stroke-width="1.2"/>'
    )


def _equal_length_ticks(a, b, n: int, tx, style: Style) -> str:
    """在线段中点附近画 n 个短刻度。"""
    import math as _m
    ax, ay = a; bx, by = b
    sax, say = tx(ax, ay)
    sbx, sby = tx(bx, by)
    dx = sbx - sax; dy = sby - say
    L = _m.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L      # 单位方向
    nx, ny = -uy, ux             # 垂直方向
    mid_x = (sax + sbx) / 2
    mid_y = (say + sby) / 2
    tick_len = 6.0
    gap = 4.0
    pieces: list[str] = []
    for k in range(n):
        offset = (k - (n - 1) / 2) * gap
        cx = mid_x + ux * offset
        cy = mid_y + uy * offset
        x1 = cx - nx * tick_len / 2
        y1 = cy - ny * tick_len / 2
        x2 = cx + nx * tick_len / 2
        y2 = cy + ny * tick_len / 2
        pieces.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{style.stroke}" stroke-width="1.2"/>'
        )
    return "".join(pieces)


def _angle_arc(a, b, c, tx, style: Style, *, value: float | None = None) -> str:
    """在 ∠abc 处画一段小圆弧。"""
    import math as _m
    sax, say = tx(*a)
    sbx, sby = tx(*b)
    scx, scy = tx(*c)
    v1x, v1y = sax - sbx, say - sby
    v2x, v2y = scx - sbx, scy - sby
    l1 = _m.hypot(v1x, v1y) or 1
    l2 = _m.hypot(v2x, v2y) or 1
    # 90° 已经有直角小方块，弧就不画了（避免重复）
    if value is not None and abs(value - 90) < 0.5:
        return ""
    r = min(l1, l2) * 0.25
    r = max(min(r, 24.0), 12.0)
    # 起止角（SVG y 向下）
    ang1 = _m.atan2(v1y / l1, v1x / l1)
    ang2 = _m.atan2(v2y / l2, v2x / l2)
    # 选短弧方向
    diff = ang2 - ang1
    while diff > _m.pi:
        diff -= 2 * _m.pi
    while diff < -_m.pi:
        diff += 2 * _m.pi
    large_arc = 0
    sweep = 1 if diff > 0 else 0
    x1 = sbx + _m.cos(ang1) * r
    y1 = sby + _m.sin(ang1) * r
    x2 = sbx + _m.cos(ang2) * r
    y2 = sby + _m.sin(ang2) * r
    return (
        f'<path d="M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 '
        f'{large_arc} {sweep} {x2:.2f} {y2:.2f}" '
        f'fill="none" stroke="#888" stroke-width="1"/>'
    )
