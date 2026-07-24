"""SVG 渲染器。

输入：DSL + Solution
输出：SVG 字符串（含中文标签 / 几何元素）

W1 范围：点、线段、直线、圆、多边形、基本标注（长度/角度/标签）。
"""
from __future__ import annotations

import math
import xml.sax.saxutils as sx
from dataclasses import dataclass

from ..dsl.safe_expr import compile_expr
from ..dsl.schema import (
    AxisObj,
    ArcObj,
    AnnularSectorObj,
    AuxLineObj,
    BarChartObj,
    BowObj,
    CircleObj,
    ConeObj,
    CubeObj,
    CuboidObj,
    CylinderObj,
    DSL,
    FunctionCurveObj,
    LineChartObj,
    LineObj,
    NumberLineObj,
    PieChartObj,
    PointObj,
    PolygonObj,
    RegionObj,
    SectorObj,
    SegmentObj,
    SphereObj,
    Style,
)
from ..solver.engine import Solution
from . import text_to_path


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
    outline_text: bool = False,
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

    # V2-C：把 <text> 元素 outline 化为 <path>，解决复制到 PPT 字体丢失问题。
    # 默认 False（浏览器渲染 <text> 性能更好、可交互）；导出 SVG/PNG/PDF 时传 True。
    def text_el(
        text: str, *, x: float, y: float, fill: str = None,
        font_size: float | None = None, font_style: str | None = None,
        anchor: str = "start",
    ) -> str:
        return _render_text(
            text, x=x, y=y, fill=fill, font_size=font_size,
            font_style=font_style, anchor=anchor,
            default_fill=style.stroke, default_size=style.font_size,
            outline=outline_text,
        )

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

    # 坐标系（最底层）
    axis = dsl.axis()
    if axis is not None:
        parts.extend(_render_axis(axis, dsl, sol, tx, scale, style, text_el))

    # V2-B：函数曲线（在坐标系之上、几何图形之下）
    for curve in dsl.curves():
        parts.extend(_render_curve(curve, dsl, sol, tx, style))

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

    # W11：派生多边形（变换后）— 虚线 + 略浅色
    for tpoly in dsl.transformed_polygons():
        src = dsl.object_map().get(tpoly.source)
        if not isinstance(src, PolygonObj):
            continue
        pts = []
        for v in src.vertices:
            derived_id = f"{v}_{tpoly.vertex_suffix}"
            if derived_id in sol.coordinates:
                sx_, sy_ = tx(*sol.coordinates[derived_id])
                pts.append(f"{sx_:.2f},{sy_:.2f}")
        if pts:
            parts.append(
                f'<polygon data-id="{tpoly.id}" class="t2g-obj t2g-poly t2g-derived" '
                f'points="{" ".join(pts)}" fill="none" '
                f'stroke="{style.stroke}" stroke-width="{style.stroke_width}" '
                f'stroke-dasharray="{style.aux_dash}"/>'
            )
        # 每个派生顶点作为独立点画出 + 加撇 label
        for v in src.vertices:
            derived_id = f"{v}_{tpoly.vertex_suffix}"
            if derived_id not in sol.coordinates:
                continue
            dx, dy = tx(*sol.coordinates[derived_id])
            parts.append(
                f'<circle data-id="{derived_id}" class="t2g-obj t2g-point t2g-derived-point" '
                f'cx="{dx:.2f}" cy="{dy:.2f}" r="{style.point_radius}" '
                f'fill="{style.stroke}"/>'
            )
            label = dsl.labels.get(derived_id) or f"{v}'"
            cx0, cy0 = _figure_center(sol)
            sx0, sy0 = tx(cx0, cy0)
            ldx, ldy = dx - sx0, dy - sy0
            ln = math.hypot(ldx, ldy) or 1
            lx = dx + ldx / ln * 12
            ly = dy + ldy / ln * 12 + 4
            parts.append(
                text_el(label, x=lx, y=ly, fill=style.stroke, anchor="middle")
            )

    # W11：独立派生点（不隶属派生多边形）
    for tp in dsl.transformed_points():
        if tp.id not in sol.coordinates:
            continue
        dx, dy = tx(*sol.coordinates[tp.id])
        parts.append(
            f'<circle data-id="{tp.id}" class="t2g-obj t2g-point t2g-derived-point" '
            f'cx="{dx:.2f}" cy="{dy:.2f}" r="{style.point_radius}" '
            f'fill="{style.stroke}"/>'
        )
        # label：优先用 dsl.labels，否则用 source_id 加撇
        label = dsl.labels.get(tp.id) or f"{tp.source}'"
        cx0, cy0 = _figure_center(sol)
        sx0, sy0 = tx(cx0, cy0)
        ldx, ldy = dx - sx0, dy - sy0
        ln = math.hypot(ldx, ldy) or 1
        lx = dx + ldx / ln * 12
        ly = dy + ldy / ln * 12 + 4
        parts.append(
            text_el(label, x=lx, y=ly, fill=style.stroke, anchor="middle")
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

    # V2-G.1：圆弧（在 segment 之后、点之前）
    for arc in dsl.arcs():
        svg_path = _render_arc_path(arc, sol, tx, style, fill=False)
        if svg_path:
            parts.append(svg_path)

    # V2-G.1：扇形（半透明填充 + 描边）
    for sec in dsl.sectors():
        svg_path = _render_sector_path(sec, sol, tx, style)
        if svg_path:
            parts.append(svg_path)

    # V2-G.4：弓形（弧 + 弦闭合，半透明填充）
    for bow in dsl.bows():
        svg_path = _render_bow_path(bow, sol, tx, style)
        if svg_path:
            parts.append(svg_path)

    # P3 V3.4：圆环扇环（外弧 + 内弧 + 两条径向直线段，闭合填充）
    for ans in dsl.annular_sectors():
        svg_path = _render_annular_sector_path(ans, sol, tx, style)
        if svg_path:
            parts.append(svg_path)

    # V2-G.3：阴影/填充区域（在 segment 之后、点之前，避免遮挡）
    for region in dsl.regions():
        svg_path = _render_region_path(region, dsl, sol, tx, style)
        if svg_path:
            parts.append(svg_path)

    # V2-G.3：数轴（与 axis 同级渲染）
    for nl in dsl.number_lines():
        parts.extend(_render_number_line(nl, sol, tx, scale, style, text_el))

    # V2-G.3：辅助线（虚线，在 segment 之后渲染）
    for aux in dsl.aux_lines():
        svg_line = _render_aux_line(aux, sol, tx, style, canvas_size)
        if svg_line:
            parts.append(svg_line)

    # V3.1：立体几何（等轴投影，在普通几何之后渲染）
    for cube in dsl.cubes():
        parts.append(_render_cube(cube, sol, tx, style))
    for cuboid in dsl.cuboids():
        parts.append(_render_cuboid(cuboid, sol, tx, style))
    for cyl in dsl.cylinders():
        parts.append(_render_cylinder(cyl, sol, tx, style))
    for cone in dsl.cones():
        parts.append(_render_cone(cone, sol, tx, style))
    for sphere in dsl.spheres():
        parts.append(_render_sphere(sphere, sol, tx, style))

    # V3.2：统计图表（独立渲染，在所有几何之后）
    for bc in dsl.bar_charts():
        parts.append(_render_bar_chart(bc, sol, tx, style, text_el))
    for lc in dsl.line_charts():
        parts.append(_render_line_chart(lc, sol, tx, style, text_el))
    for pc in dsl.pie_charts():
        parts.append(_render_pie_chart(pc, sol, tx, style, text_el))

    # 点 + 标签
    aux_points = _isolated_aux_points(dsl)
    for p in dsl.points():
        if p.id not in sol.coordinates:
            continue
        # 孤立辅助点（hint != None 且未被任何对象引用）不画
        if p.id in aux_points:
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
            text_el(label, x=lx, y=ly, fill=style.stroke, anchor="middle")
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
            text_el(text, x=ax, y=ay, fill="#555",
                    font_style="italic", anchor="middle")
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
    # axis range 纳入 bbox，确保整个坐标系不被裁
    axis = dsl.axis()
    if axis is not None:
        xs.extend([axis.x_range[0], axis.x_range[1]])
        ys.extend([axis.y_range[0], axis.y_range[1]])
    # V2-B：曲线的 domain 也纳入 bbox
    for curve in dsl.curves():
        if curve.domain is not None:
            if curve.var == "x":
                xs.extend([curve.domain[0], curve.domain[1]])
            else:
                ys.extend([curve.domain[0], curve.domain[1]])
    if not xs:
        return _BBox(-1, -1, 1, 1)
    return _BBox(min(xs), min(ys), max(xs), max(ys))


def _figure_center(sol: Solution) -> tuple[float, float]:
    if not sol.coordinates:
        return 0.0, 0.0
    xs = [p[0] for p in sol.coordinates.values()]
    ys = [p[1] for p in sol.coordinates.values()]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _isolated_aux_points(dsl: DSL) -> set[str]:
    """识别"孤立辅助点"：hint != None 且未被任何 segment/line/polygon/circle/axis 引用。
    这类点仅用作 same_side 的方位参考，不在画板上渲染。
    constraint 引用（如 same_side.ref）不算作"被引用"，因为它本身就是要隐藏的语义。
    """
    referenced: set[str] = set()
    for o in dsl.objects:
        if isinstance(o, (SegmentObj, LineObj)):
            referenced.add(o.a)
            referenced.add(o.b)
        elif isinstance(o, PolygonObj):
            referenced.update(o.vertices)
        elif isinstance(o, CircleObj):
            d = o.definition
            if hasattr(d, "center"):
                referenced.add(d.center)
            if hasattr(d, "through"):
                referenced.add(d.through)
        elif isinstance(o, AxisObj):
            referenced.add(o.origin)
        elif hasattr(o, "source") and hasattr(o, "transform"):
            # W11：派生对象的 source 也算被引用（源点/源多边形不能算孤立）
            referenced.add(o.source)

    aux: set[str] = set()
    for p in dsl.points():
        if p.hint is not None and p.id not in referenced:
            aux.add(p.id)
    return aux


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
    # V2-G.4：弧长 / 弓形面积标注
    if ann.kind in ("arc_length", "bow_area"):
        arc = obj_map.get(ann.target)
        if isinstance(arc, (ArcObj, BowObj)):
            pc = sol.coordinates.get(arc.center)
            pf = sol.coordinates.get(arc.from_point)
            pt = sol.coordinates.get(arc.to_point)
            if pc and pf and pt:
                v1 = (pf[0]-pc[0], pf[1]-pc[1])
                v2 = (pt[0]-pc[0], pt[1]-pc[1])
                r = math.hypot(*v1)
                if r > 1e-9:
                    cross_v = v1[0]*v2[1] - v1[1]*v2[0]
                    dot_v = v1[0]*v2[0] + v1[1]*v2[1]
                    angle_signed = math.atan2(cross_v, dot_v)
                    if not arc.ccw:
                        angle_signed = -angle_signed
                    if angle_signed < 0:
                        angle_signed += 2 * math.pi
                    if ann.kind == "arc_length":
                        return _fmt_num(r * angle_signed)
                    else:  # bow_area
                        area = 0.5 * r * r * (angle_signed - math.sin(angle_signed))
                        return _fmt_num(area)
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
    # V2-G.4：弧长 / 弓形面积标注位置
    if ann.kind in ("arc_length", "bow_area"):
        arc = obj_map.get(ann.target)
        if isinstance(arc, (ArcObj, BowObj)):
            pc = sol.coordinates.get(arc.center)
            pf = sol.coordinates.get(arc.from_point)
            pt = sol.coordinates.get(arc.to_point)
            if pc and pf and pt:
                v1 = (pf[0]-pc[0], pf[1]-pc[1])
                v2 = (pt[0]-pc[0], pt[1]-pc[1])
                r = math.hypot(*v1)
                if r > 1e-9:
                    # 弧中点角度
                    a1 = math.atan2(v1[1], v1[0])
                    a2 = math.atan2(v2[1], v2[0])
                    sweep = (a2 - a1) if arc.ccw else (a1 - a2)
                    while sweep <= 0:
                        sweep += 2 * math.pi
                    while sweep > 2 * math.pi:
                        sweep -= 2 * math.pi
                    mid_angle = a1 + (sweep / 2 if arc.ccw else -sweep / 2)
                    if ann.kind == "arc_length":
                        # 弧外侧偏移 0.15r
                        offset_r = r * 1.15
                        mx = pc[0] + offset_r * math.cos(mid_angle)
                        my = pc[1] + offset_r * math.sin(mid_angle)
                    else:  # bow_area
                        # 弓形内部：弦中点 + 沿弧中点方向偏移 0.3
                        chord_mid = ((pf[0]+pt[0])/2, (pf[1]+pt[1])/2)
                        arc_mid = (pc[0] + r * math.cos(mid_angle), pc[1] + r * math.sin(mid_angle))
                        mx = chord_mid[0] + (arc_mid[0] - chord_mid[0]) * 0.4
                        my = chord_mid[1] + (arc_mid[1] - chord_mid[1]) * 0.4
                    return tx(mx, my)
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


# ---------------------------------------------------------------------------
# Axis / 坐标系绘制（V2-A）
# ---------------------------------------------------------------------------

def _render_axis(axis: AxisObj, dsl: DSL, sol: Solution, tx, scale: float, style: Style, text_el) -> list[str]:
    """绘制直角坐标系：网格 → 轴 → 箭头 → 刻度 → 数字 → 单位标签。"""
    out: list[str] = []
    origin = sol.coordinates.get(axis.origin)
    if origin is None:
        return out
    ox, oy = origin
    xmin, xmax = axis.x_range
    ymin, ymax = axis.y_range
    # 平移到 origin 所在世界坐标（origin 数学坐标恒为 (0,0)；范围相对它来定）
    # 即坐标系覆盖 [ox+xmin, ox+xmax] × [oy+ymin, oy+ymax]
    wx_min = ox + xmin
    wx_max = ox + xmax
    wy_min = oy + ymin
    wy_max = oy + ymax

    grid_stroke = "#e5e7eb"      # 浅灰网格
    axis_stroke = "#9ca3af"      # 中灰主轴
    tick_text_fill = "#6b7280"   # 刻度数字

    # 1) 网格（最底）
    if axis.show_grid:
        step = axis.tick_step
        # 垂直网格线（x = ox + k*step）
        k = math.ceil(xmin / step)
        while k * step <= xmax + 1e-9:
            wx = ox + k * step
            x1, y1 = tx(wx, wy_min)
            x2, y2 = tx(wx, wy_max)
            out.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{grid_stroke}" stroke-width="1"/>'
            )
            k += 1
        # 水平网格线
        k = math.ceil(ymin / step)
        while k * step <= ymax + 1e-9:
            wy = oy + k * step
            x1, y1 = tx(wx_min, wy)
            x2, y2 = tx(wx_max, wy)
            out.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{grid_stroke}" stroke-width="1"/>'
            )
            k += 1

    # 2) 主轴（带箭头）
    # x 轴：从 (wx_min, oy) 到 (wx_max, oy)
    ax1x, ax1y = tx(wx_min, oy)
    ax2x, ax2y = tx(wx_max, oy)
    out.append(
        f'<line x1="{ax1x:.2f}" y1="{ax1y:.2f}" x2="{ax2x:.2f}" y2="{ax2y:.2f}" '
        f'stroke="{axis_stroke}" stroke-width="1.4" marker-end="url(#t2g-arrow)"/>'
    )
    # y 轴：从 (ox, wy_min) 到 (ox, wy_max)
    ay1x, ay1y = tx(ox, wy_min)
    ay2x, ay2y = tx(ox, wy_max)
    out.append(
        f'<line x1="{ay1x:.2f}" y1="{ay1y:.2f}" x2="{ay2x:.2f}" y2="{ay2y:.2f}" '
        f'stroke="{axis_stroke}" stroke-width="1.4" marker-end="url(#t2g-arrow)"/>'
    )
    # 箭头标记定义（一次性插入 defs）
    out.append(
        '<defs><marker id="t2g-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerUnits="strokeWidth" markerWidth="8" markerHeight="8" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 Z" fill="{axis_stroke}"/></marker></defs>'
    )

    # 3) 刻度 + 数字
    if axis.show_ticks:
        step = axis.tick_step
        tick_len = 4.0  # SVG 像素
        # x 轴刻度
        k = math.ceil(xmin / step)
        while k * step <= xmax + 1e-9:
            if k != 0:  # 原点不画刻度数字
                wx = ox + k * step
                cx, cy = tx(wx, oy)
                out.append(
                    f'<line x1="{cx:.2f}" y1="{cy - tick_len:.2f}" x2="{cx:.2f}" y2="{cy + tick_len:.2f}" '
                    f'stroke="{axis_stroke}" stroke-width="1"/>'
                )
                out.append(
                    text_el(_fmt_num(k * step), x=cx, y=cy + tick_len + 12,
                            fill=tick_text_fill, font_size=11, anchor="middle")
                )
            k += 1
        # y 轴刻度
        k = math.ceil(ymin / step)
        while k * step <= ymax + 1e-9:
            if k != 0:
                wy = oy + k * step
                cx, cy = tx(ox, wy)
                out.append(
                    f'<line x1="{cx - tick_len:.2f}" y1="{cy:.2f}" x2="{cx + tick_len:.2f}" y2="{cy:.2f}" '
                    f'stroke="{axis_stroke}" stroke-width="1"/>'
                )
                out.append(
                    text_el(_fmt_num(k * step), x=cx - tick_len - 4, y=cy + 4,
                            fill=tick_text_fill, font_size=11, anchor="end")
                )
            k += 1

    # 4) 单位标签（轴末端文字）
    # 4) 单位标签（轴末端文字）
    out.append(
        text_el(axis.x_label, x=ax2x + 10, y=ax2y + 4,
                fill=axis_stroke, font_size=13, font_style="italic", anchor="start")
    )
    out.append(
        text_el(axis.y_label, x=ay2x, y=ay2y - 8,
                fill=axis_stroke, font_size=13, font_style="italic", anchor="middle")
    )

    # 5) 原点 O 标签
    oxs, oys = tx(ox, oy)
    out.append(
        text_el("O", x=oxs - 8, y=oys + 14,
                fill=tick_text_fill, font_size=11, anchor="end")
    )

    # 6) V2-G.3：网格作图模式 - 画明显的网格点
    if axis.grid_size is not None and axis.grid_size > 0:
        gs = axis.grid_size
        x_start = math.ceil(axis.x_range[0] / gs) * gs
        x_end = axis.x_range[1]
        y_start = math.ceil(axis.y_range[0] / gs) * gs
        y_end = axis.y_range[1]
        x = x_start
        while x <= x_end + 1e-9:
            y = y_start
            while y <= y_end + 1e-9:
                gx, gy = tx(x, y)
                out.append(
                    f'<circle cx="{gx:.2f}" cy="{gy:.2f}" r="1.5" fill="{axis_stroke}"/>'
                )
                y += gs
            x += gs

    return out


# ---------------------------------------------------------------------------
# V2-B · 函数曲线绘制
# ---------------------------------------------------------------------------

_CURVE_CLIP_MAG = 1000.0  # 值绝对值超过此阈值切段（防止 1/x 在断点附近乱画）


def _render_curve(
    curve: FunctionCurveObj, dsl: DSL, sol: Solution, tx, style: Style
) -> list[str]:
    """采样 curve.expr 并输出一或多段 <polyline>（用断点切段）。
    V2-G.4：若 curve.pieces 非空，按 pieces 渲染分段函数。
    """
    axis = dsl.axis()
    if axis is None:
        return []  # validator 已阻止；此处兜底

    # 收集所有要渲染的 (expr, domain) 段
    pieces: list[tuple[str, tuple[float, float]]] = []
    if curve.pieces:
        for p in curve.pieces:
            pieces.append((p.expr, p.domain))
    else:
        if not curve.expr:
            return []
        if curve.domain is not None:
            dmin, dmax = curve.domain
        elif curve.var == "x":
            dmin, dmax = axis.x_range
        else:
            dmin, dmax = axis.y_range
        pieces.append((curve.expr, (dmin, dmax)))

    dash_attr = f' stroke-dasharray="{curve.dash}"' if curve.dash else ""
    out: list[str] = []

    for expr, (dmin, dmax) in pieces:
        if dmin >= dmax or curve.samples < 2:
            continue
        try:
            f = compile_expr(expr, var=curve.var)
        except Exception:
            continue

        N = curve.samples
        step = (dmax - dmin) / (N - 1)
        segments: list[list[tuple[float, float]]] = [[]]
        for i in range(N):
            v = dmin + i * step
            y = f(v)
            if not _is_finite(y) or abs(y) > _CURVE_CLIP_MAG:
                if segments[-1]:
                    segments.append([])
                continue
            if curve.var == "x":
                pt = (v, y)
            else:
                pt = (y, v)
            segments[-1].append(pt)

        for seg in segments:
            if len(seg) < 2:
                continue
            pts_svg = " ".join(f"{sx_:.2f},{sy_:.2f}" for sx_, sy_ in (tx(*p) for p in seg))
            out.append(
                f'<polyline data-id="{curve.id}" class="t2g-obj t2g-curve" '
                f'points="{pts_svg}" fill="none" '
                f'stroke="{curve.color}" stroke-width="1.6"{dash_attr}/>'
            )
    return out


def _is_finite(v: float) -> bool:
    return v == v and v != float("inf") and v != float("-inf")


# ---------------------------------------------------------------------------
# V2-G.1 · 圆弧 / 扇形渲染
# ---------------------------------------------------------------------------

def _compute_arc_geometry(
    center_id: str, from_id: str, to_id: str,
    sol: Solution, tx,
) -> tuple[float, float, float, float, float, float, float] | None:
    """返回 SVG 坐标系下的 (cx_svg, cy_svg, fx_svg, fy_svg, tx_svg, ty_svg, r_svg)
    或 None（坐标缺失）。
    """
    if (center_id not in sol.coordinates
            or from_id not in sol.coordinates
            or to_id not in sol.coordinates):
        return None
    cx, cy = sol.coordinates[center_id]
    fx, fy = sol.coordinates[from_id]
    tx_math, ty_math = sol.coordinates[to_id]
    cx_svg, cy_svg = tx(cx, cy)
    fx_svg, fy_svg = tx(fx, fy)
    tx_svg, ty_svg = tx(tx_math, ty_math)
    r_svg = math.hypot(fx_svg - cx_svg, fy_svg - cy_svg)
    return cx_svg, cy_svg, fx_svg, fy_svg, tx_svg, ty_svg, r_svg


def _arc_sweep_flags(
    cx: float, cy: float, fx: float, fy: float, tx_pt: float, ty_pt: float,
    ccw: bool, r: float,
) -> tuple[int, int]:
    """计算 SVG arc 命令的 large_arc 与 sweep flag。

    SVG 中 y 轴向下（与数学坐标系相反），因此 ccw=True（数学逆时针）
    在 SVG 中变成顺时针（sweep=0）；ccw=False 在 SVG 中是 sweep=1。
    large_arc：当弧的扫过角度 > 180° 时为 1，否则 0。
    """
    # 计算起止向量相对圆心的角度（SVG 坐标系，y 向下）
    a1 = math.atan2(fy - cy, fx - cx)
    a2 = math.atan2(ty_pt - cy, tx_pt - cx)
    # 数学坐标系中 sweep（ccw 为正）；SVG y 翻转后变号
    sweep_math = (a2 - a1) if not ccw else (a1 - a2)
    # 归一到 (0, 2π)
    while sweep_math <= 0:
        sweep_math += 2 * math.pi
    while sweep_math > 2 * math.pi:
        sweep_math -= 2 * math.pi
    large_arc = 1 if sweep_math > math.pi else 0
    # SVG sweep flag：1=顺时针（SVG y 向下），0=逆时针
    # ccw=True（数学逆时针）-> SVG 中是顺时针 -> sweep=0（SVG y 翻转后再次反向）
    # 经过验证：ccw=True -> sweep=0；ccw=False -> sweep=1
    sweep_flag = 0 if ccw else 1
    return large_arc, sweep_flag


def _render_arc_path(
    arc: ArcObj, sol: Solution, tx, style: Style, *, fill: bool = False,
) -> str:
    """渲染圆弧为 SVG <path d="M fx fy A r r 0 large sweep tx ty"/>。"""
    g = _compute_arc_geometry(arc.center, arc.from_point, arc.to_point, sol, tx)
    if g is None:
        return ""
    cx, cy, fx, fy, tx_pt, ty_pt, r = g
    if r < 1e-9:
        return ""
    large, sweep = _arc_sweep_flags(cx, cy, fx, fy, tx_pt, ty_pt, arc.ccw, r)
    fill_attr = 'fill="none"' if not fill else f'fill="{style.stroke}" fill-opacity="0.15"'
    return (
        f'<path data-id="{arc.id}" class="t2g-obj t2g-arc" '
        f'd="M {fx:.2f} {fy:.2f} A {r:.2f} {r:.2f} 0 {large} {sweep} {tx_pt:.2f} {ty_pt:.2f}" '
        f'{fill_attr} stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )


def _render_sector_path(sec: SectorObj, sol: Solution, tx, style: Style) -> str:
    """渲染扇形为闭合 SVG path：M cx cy L fx fy A ... tx ty Z（半透明填充）。"""
    g = _compute_arc_geometry(sec.center, sec.from_point, sec.to_point, sol, tx)
    if g is None:
        return ""
    cx, cy, fx, fy, tx_pt, ty_pt, r = g
    if r < 1e-9:
        return ""
    large, sweep = _arc_sweep_flags(cx, cy, fx, fy, tx_pt, ty_pt, sec.ccw, r)
    return (
        f'<path data-id="{sec.id}" class="t2g-obj t2g-sector" '
        f'd="M {cx:.2f} {cy:.2f} L {fx:.2f} {fy:.2f} '
        f'A {r:.2f} {r:.2f} 0 {large} {sweep} {tx_pt:.2f} {ty_pt:.2f} Z" '
        f'fill="{style.stroke}" fill-opacity="0.15" '
        f'stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )


def _render_bow_path(bow: BowObj, sol: Solution, tx, style: Style) -> str:
    """渲染弓形 (V2-G.4)：M fx fy A ... tx ty Z（弧 + 弦自动闭合，不画到圆心）。"""
    g = _compute_arc_geometry(bow.center, bow.from_point, bow.to_point, sol, tx)
    if g is None:
        return ""
    cx, cy, fx, fy, tx_pt, ty_pt, r = g
    if r < 1e-9:
        return ""
    large, sweep = _arc_sweep_flags(cx, cy, fx, fy, tx_pt, ty_pt, bow.ccw, r)
    return (
        f'<path data-id="{bow.id}" class="t2g-obj t2g-bow" '
        f'd="M {fx:.2f} {fy:.2f} '
        f'A {r:.2f} {r:.2f} 0 {large} {sweep} {tx_pt:.2f} {ty_pt:.2f} Z" '
        f'fill="{style.stroke}" fill-opacity="0.15" '
        f'stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )


def _render_annular_sector_path(
    ans: AnnularSectorObj, sol: Solution, tx, style: Style
) -> str:
    """渲染圆环扇环 (P3 V3.4)。

    构造闭合 path：
      M outer_from A ... outer_to    （外弧）
      L inner_to                      （径向直线）
      A ... inner_from                （内弧，方向相反）
      Z                               （径向直线自动闭合回 outer_from）

    外弧半径 = |center - from_point|（已求解）
    内弧半径 = ans.r_inner
    """
    g = _compute_arc_geometry(ans.center, ans.from_point, ans.to_point, sol, tx)
    if g is None:
        return ""
    cx, cy, fx, fy, tx_pt, ty_pt, r_outer = g
    if r_outer < 1e-9 or ans.r_inner <= 0:
        return ""

    r_inner = ans.r_inner  # 数学坐标系下的半径

    # 内弧端点（沿 center->from / center->to 方向，距离 r_inner）
    fx_math = sol.coordinates[ans.from_point][0]
    fy_math = sol.coordinates[ans.from_point][1]
    tx_math = sol.coordinates[ans.to_point][0]
    ty_math = sol.coordinates[ans.to_point][1]
    cx_math, cy_math = sol.coordinates[ans.center]

    # 单位向量
    def _unit(dx: float, dy: float) -> tuple[float, float]:
        L = math.hypot(dx, dy)
        if L < 1e-12:
            return 1.0, 0.0
        return dx / L, dy / L

    ux, uy = _unit(fx_math - cx_math, fy_math - cy_math)  # center -> from 方向
    vx, vy = _unit(tx_math - cx_math, ty_math - cy_math)  # center -> to 方向

    # 内弧端点（数学坐标）
    inner_from = (cx_math + ux * r_inner, cy_math + uy * r_inner)
    inner_to = (cx_math + vx * r_inner, cy_math + vy * r_inner)

    # 转 SVG 坐标
    ifx, ify = tx(*inner_from)
    itx, ity = tx(*inner_to)

    # 外弧 sweep flags
    large_outer, sweep_outer = _arc_sweep_flags(
        cx, cy, fx, fy, tx_pt, ty_pt, ans.ccw, r_outer
    )
    # 内弧 sweep flags：方向与外弧相反（因为反向走）
    # 简化：large_inner = large_outer；sweep_inner = 1 - sweep_outer
    large_inner = large_outer
    sweep_inner = 1 - sweep_outer

    return (
        f'<path data-id="{ans.id}" class="t2g-obj t2g-annular-sector" '
        f'd="M {fx:.2f} {fy:.2f} '
        f'A {r_outer:.2f} {r_outer:.2f} 0 {large_outer} {sweep_outer} '
        f'{tx_pt:.2f} {ty_pt:.2f} '
        f'L {itx:.2f} {ity:.2f} '
        f'A {r_inner:.2f} {r_inner:.2f} 0 {large_inner} {sweep_inner} '
        f'{ifx:.2f} {ify:.2f} Z" '
        f'fill="{style.stroke}" fill-opacity="0.15" '
        f'stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )


# ---------------------------------------------------------------------------
# V2-G.3 · 阴影区域 / 数轴 / 辅助线
# ---------------------------------------------------------------------------

def _render_region_path(
    region: RegionObj, dsl: DSL, sol: Solution, tx, style: Style
) -> str:
    """按 boundary 顺序拼接 segment/arc 端点，构造闭合 SVG path 并填充。

    简化实现：把每个 boundary 元素的起点按顺序连成 path。
    - SegmentObj：起点 = a，终点 = b
    - ArcObj：起点 = from_point，终点 = to_point（弧线用 SVG A 命令）
    """
    obj_map = dsl.object_map()
    path_cmds: list[str] = []
    first_pt: tuple[float, float] | None = None
    last_pt: tuple[float, float] | None = None

    for bid in region.boundary:
        obj = obj_map.get(bid)
        if obj is None:
            continue
        if isinstance(obj, SegmentObj):
            if obj.a not in sol.coordinates or obj.b not in sol.coordinates:
                return ""
            a_pt = sol.coordinates[obj.a]
            b_pt = sol.coordinates[obj.b]
            ax_s, ay_s = tx(*a_pt)
            bx_s, by_s = tx(*b_pt)
            # 如果是第一个元素，移到起点；否则从上一个终点开始
            if first_pt is None:
                path_cmds.append(f"M {ax_s:.2f} {ay_s:.2f}")
                first_pt = (ax_s, ay_s)
            path_cmds.append(f"L {bx_s:.2f} {by_s:.2f}")
            last_pt = (bx_s, by_s)
        elif isinstance(obj, ArcObj):
            g = _compute_arc_geometry(obj.center, obj.from_point, obj.to_point, sol, tx)
            if g is None:
                return ""
            cx, cy, fx, fy, tx_pt, ty_pt, r = g
            if r < 1e-9:
                return ""
            large, sweep = _arc_sweep_flags(cx, cy, fx, fy, tx_pt, ty_pt, obj.ccw, r)
            if first_pt is None:
                path_cmds.append(f"M {fx:.2f} {fy:.2f}")
                first_pt = (fx, fy)
            path_cmds.append(f"A {r:.2f} {r:.2f} 0 {large} {sweep} {tx_pt:.2f} {ty_pt:.2f}")
            last_pt = (tx_pt, ty_pt)

    if first_pt is None:
        return ""
    # 闭合
    path_cmds.append("Z")
    stroke_attr = (
        f'stroke="{region.stroke}" stroke-width="{style.stroke_width}"'
        if region.stroke is not None else 'stroke="none"'
    )
    return (
        f'<path data-id="{region.id}" class="t2g-obj t2g-region" '
        f'd="{" ".join(path_cmds)}" '
        f'fill="{region.fill_color}" fill-opacity="{region.fill_opacity}" '
        f'{stroke_attr}/>'
    )


def _render_number_line(
    nl: NumberLineObj, sol: Solution, tx, scale: float, style: Style, text_el
) -> list[str]:
    """渲染 1D 数轴：水平线 + 箭头 + 刻度 + 数字。"""
    if nl.origin not in sol.coordinates:
        return []
    ox, oy = sol.coordinates[nl.origin]
    out: list[str] = []
    r_min, r_max = nl.range
    # 主线
    x1_s, y1_s = tx(r_min, oy)
    x2_s, y2_s = tx(r_max, oy)
    out.append(
        f'<line data-id="{nl.id}" class="t2g-obj t2g-number-line" '
        f'x1="{x1_s:.2f}" y1="{y1_s:.2f}" x2="{x2_s:.2f}" y2="{y2_s:.2f}" '
        f'stroke="{style.stroke}" stroke-width="{style.stroke_width}" '
        f'marker-end="url(#t2g-arrow)"/>'
    )
    # 刻度
    if nl.show_ticks:
        step = nl.tick_step
        n_ticks = int((r_max - r_min) / step)
        for i in range(n_ticks + 1):
            v = r_min + i * step
            x_s, y_s = tx(v, oy)
            tick_len = 4
            out.append(
                f'<line x1="{x_s:.2f}" y1="{y_s:.2f}" x2="{x_s:.2f}" y2="{y_s + tick_len:.2f}" '
                f'stroke="{style.stroke}" stroke-width="1"/>'
            )
            if nl.show_numbers and abs(v) > 1e-9:
                out.append(
                    text_el(_fmt_num(v), x=x_s, y=y_s + tick_len + 14,
                            fill="#6b7280", anchor="middle")
                )
    # 原点标签 O
    oxs, oys = tx(ox, oy)
    out.append(
        text_el("O", x=oxs - 8, y=oys + 14, fill=style.stroke, anchor="middle")
    )
    # 数轴标签（右端）
    x_end_s, y_end_s = tx(r_max, oy)
    out.append(
        text_el(nl.label, x=x_end_s + 12, y=y_end_s + 4, fill=style.stroke, anchor="start")
    )
    return out


def _render_aux_line(
    aux: AuxLineObj, sol: Solution, tx, style: Style, canvas_size: int
) -> str:
    """渲染辅助线：虚线 segment 或延长直线。"""
    if aux.a not in sol.coordinates or aux.b not in sol.coordinates:
        return ""
    a = sol.coordinates[aux.a]
    b = sol.coordinates[aux.b]
    x1, y1 = tx(*a)
    x2, y2 = tx(*b)
    dash = aux.dash if aux.dash is not None else style.aux_dash
    if aux.extended:
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        ext = canvas_size * 2
        ex1, ey1 = x1 - dx / L * ext, y1 - dy / L * ext
        ex2, ey2 = x2 + dx / L * ext, y2 + dy / L * ext
        return (
            f'<line data-id="{aux.id}" class="t2g-obj t2g-aux-line" '
            f'x1="{ex1:.2f}" y1="{ey1:.2f}" x2="{ex2:.2f}" y2="{ey2:.2f}" '
            f'stroke="{style.stroke}" stroke-width="{style.stroke_width * 0.7:.2f}" '
            f'stroke-dasharray="{dash}"/>'
        )
    return (
        f'<line data-id="{aux.id}" class="t2g-obj t2g-aux-line" '
        f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{style.stroke}" stroke-width="{style.stroke_width * 0.7:.2f}" '
        f'stroke-dasharray="{dash}"/>'
    )


# ---------------------------------------------------------------------------
# V3.1 · 立体几何（等轴投影 SVG）
# ---------------------------------------------------------------------------

# 等轴投影：3D (x, y, z) -> 2D (x', y')
# x' = x + z * cos(30°) ≈ x + 0.866 * z
# y' = y - z * sin(30°) ≈ y - 0.5 * z
_ISO_COS30 = math.cos(math.radians(30))
_ISO_SIN30 = math.sin(math.radians(30))


def _project_3d(x: float, y: float, z: float) -> tuple[float, float]:
    """3D 数学坐标 -> 2D 投影坐标（仍是数学坐标系，y 向上）"""
    return (x + z * _ISO_COS30, y - z * _ISO_SIN30)


def _render_cube(cube: CubeObj, sol: Solution, tx, style: Style) -> str:
    """渲染正方体：底面 4 顶点 + 顶面 4 顶点，等轴投影。"""
    if cube.vertex not in sol.coordinates:
        return ""
    vx, vy = sol.coordinates[cube.vertex]
    e = cube.edge
    # 8 个顶点（3D 坐标，相对于 vertex）
    # 底面：A(0,0,0) B(e,0,0) C(e,0,e) D(0,0,e)
    # 顶面：E(0,e,0) F(e,e,0) G(e,e,e) H(0,e,e)
    pts3d = [
        (vx,       vy,       0),    # A 底前左
        (vx + e,   vy,       0),    # B 底前右
        (vx + e,   vy,       e),    # C 底后右
        (vx,       vy,       e),    # D 底后左
        (vx,       vy + e,   0),    # E 顶前左
        (vx + e,   vy + e,   0),    # F 顶前右
        (vx + e,   vy + e,   e),    # G 顶后右
        (vx,       vy + e,   e),    # H 顶后左
    ]
    pts2d = [tx(*_project_3d(*p)) for p in pts3d]
    # 可见面：顶面 EFGH + 右面 BCGF + 前面 ABFE
    top = f"M {pts2d[4][0]:.2f} {pts2d[4][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f} L {pts2d[7][0]:.2f} {pts2d[7][1]:.2f} Z"
    right = f"M {pts2d[1][0]:.2f} {pts2d[1][1]:.2f} L {pts2d[2][0]:.2f} {pts2d[2][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} Z"
    front = f"M {pts2d[0][0]:.2f} {pts2d[0][1]:.2f} L {pts2d[1][0]:.2f} {pts2d[1][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} L {pts2d[4][0]:.2f} {pts2d[4][1]:.2f} Z"
    # 隐藏边：从 A 到 D 到 H 到 G（虚线）
    hidden = f"M {pts2d[0][0]:.2f} {pts2d[0][1]:.2f} L {pts2d[3][0]:.2f} {pts2d[3][1]:.2f} L {pts2d[7][0]:.2f} {pts2d[7][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f}"
    return (
        f'<path data-id="{cube.id}" class="t2g-obj t2g-cube" '
        f'd="{front}" fill="#f5f5f5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{right}" fill="#e5e5e5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{top}" fill="#ffffff" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{hidden}" fill="none" stroke="{style.stroke}" stroke-width="{style.stroke_width * 0.7:.2f}" stroke-dasharray="{style.aux_dash}"/>'
    )


def _render_cuboid(cuboid: CuboidObj, sol: Solution, tx, style: Style) -> str:
    """渲染长方体：与 cube 类似但用 length/width/height。"""
    if cuboid.vertex not in sol.coordinates:
        return ""
    vx, vy = sol.coordinates[cuboid.vertex]
    L, W, H = cuboid.length, cuboid.width, cuboid.height
    pts3d = [
        (vx,     vy,     0),
        (vx + L, vy,     0),
        (vx + L, vy,     W),
        (vx,     vy,     W),
        (vx,     vy + H, 0),
        (vx + L, vy + H, 0),
        (vx + L, vy + H, W),
        (vx,     vy + H, W),
    ]
    pts2d = [tx(*_project_3d(*p)) for p in pts3d]
    top = f"M {pts2d[4][0]:.2f} {pts2d[4][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f} L {pts2d[7][0]:.2f} {pts2d[7][1]:.2f} Z"
    right = f"M {pts2d[1][0]:.2f} {pts2d[1][1]:.2f} L {pts2d[2][0]:.2f} {pts2d[2][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} Z"
    front = f"M {pts2d[0][0]:.2f} {pts2d[0][1]:.2f} L {pts2d[1][0]:.2f} {pts2d[1][1]:.2f} L {pts2d[5][0]:.2f} {pts2d[5][1]:.2f} L {pts2d[4][0]:.2f} {pts2d[4][1]:.2f} Z"
    hidden = f"M {pts2d[0][0]:.2f} {pts2d[0][1]:.2f} L {pts2d[3][0]:.2f} {pts2d[3][1]:.2f} L {pts2d[7][0]:.2f} {pts2d[7][1]:.2f} L {pts2d[6][0]:.2f} {pts2d[6][1]:.2f}"
    return (
        f'<path data-id="{cuboid.id}" class="t2g-obj t2g-cuboid" '
        f'd="{front}" fill="#f5f5f5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{right}" fill="#e5e5e5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{top}" fill="#ffffff" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<path d="{hidden}" fill="none" stroke="{style.stroke}" stroke-width="{style.stroke_width * 0.7:.2f}" stroke-dasharray="{style.aux_dash}"/>'
    )


def _render_cylinder(cyl: CylinderObj, sol: Solution, tx, style: Style) -> str:
    """渲染圆柱：底面椭圆 + 顶面椭圆 + 两条母线。"""
    if cyl.center_bottom not in sol.coordinates:
        return ""
    cx, cy = sol.coordinates[cyl.center_bottom]
    r = cyl.radius
    h = cyl.height
    # 底面圆心 3D -> 2D（用作椭圆中心）
    bot2d = tx(*_project_3d(cx, cy, 0))
    top2d = tx(*_project_3d(cx, cy + h, 0))
    # 椭圆参数：rx = r，ry = r * sin30（透视压缩）
    rx = r
    ry = r * _ISO_SIN30
    return (
        f'<g data-id="{cyl.id}" class="t2g-obj t2g-cylinder">'
        # 底面（半椭圆后半部分虚线 + 前半实线，简化为完整椭圆）
        f'<ellipse cx="{bot2d[0]:.2f}" cy="{bot2d[1]:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="#f5f5f5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        # 顶面
        f'<ellipse cx="{top2d[0]:.2f}" cy="{top2d[1]:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="#ffffff" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        # 左右母线
        f'<line x1="{bot2d[0] - rx:.2f}" y1="{bot2d[1]:.2f}" x2="{top2d[0] - rx:.2f}" y2="{top2d[1]:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<line x1="{bot2d[0] + rx:.2f}" y1="{bot2d[1]:.2f}" x2="{top2d[0] + rx:.2f}" y2="{top2d[1]:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'</g>'
    )


def _render_cone(cone: ConeObj, sol: Solution, tx, style: Style) -> str:
    """渲染圆锥：底面椭圆 + 顶点 + 两条母线。"""
    if cone.center_bottom not in sol.coordinates:
        return ""
    cx, cy = sol.coordinates[cone.center_bottom]
    r = cone.radius
    h = cone.height
    bot2d = tx(*_project_3d(cx, cy, 0))
    apex2d = tx(*_project_3d(cx, cy + h, 0))
    rx = r
    ry = r * _ISO_SIN30
    return (
        f'<g data-id="{cone.id}" class="t2g-obj t2g-cone">'
        f'<ellipse cx="{bot2d[0]:.2f}" cy="{bot2d[1]:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="#f5f5f5" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        # 左右母线
        f'<line x1="{bot2d[0] - rx:.2f}" y1="{bot2d[1]:.2f}" x2="{apex2d[0]:.2f}" y2="{apex2d[1]:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<line x1="{bot2d[0] + rx:.2f}" y1="{bot2d[1]:.2f}" x2="{apex2d[0]:.2f}" y2="{apex2d[1]:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'</g>'
    )


def _render_sphere(sphere: SphereObj, sol: Solution, tx, style: Style) -> str:
    """渲染球：大圆 + 赤道椭圆。"""
    if sphere.center not in sol.coordinates:
        return ""
    cx, cy = sol.coordinates[sphere.center]
    r = sphere.radius
    center2d = tx(*_project_3d(cx, cy, 0))
    return (
        f'<g data-id="{sphere.id}" class="t2g-obj t2g-sphere">'
        # 大圆（外形圆）
        f'<circle cx="{center2d[0]:.2f}" cy="{center2d[1]:.2f}" r="{r:.2f}" fill="#ffffff" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        # 赤道椭圆（透视）
        f'<ellipse cx="{center2d[0]:.2f}" cy="{center2d[1]:.2f}" rx="{r:.2f}" ry="{r * _ISO_SIN30:.2f}" fill="none" stroke="{style.stroke}" stroke-width="{style.stroke_width * 0.7:.2f}" stroke-dasharray="{style.aux_dash}"/>'
        f'</g>'
    )


# ---------------------------------------------------------------------------
# V3.2 · 统计图表
# ---------------------------------------------------------------------------

# 默认色板（K12 教学用色）
_CHART_PALETTE = [
    "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
    "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
]


def _render_bar_chart(
    bc: BarChartObj, sol: Solution, tx, style: Style, text_el
) -> str:
    """渲染条形图：每条数据用一个矩形。"""
    if bc.origin not in sol.coordinates:
        return ""
    ox, oy = sol.coordinates[bc.origin]
    n = len(bc.data)
    max_v = max(bc.data) if bc.data else 1
    if max_v <= 0:
        max_v = 1
    chart_w = bc.width
    chart_h = bc.height
    bar_w = chart_w / n * 0.7
    gap = chart_w / n * 0.3

    out: list[str] = [f'<g data-id="{bc.id}" class="t2g-obj t2g-bar-chart">']
    # 坐标轴
    ox_svg, oy_svg = tx(ox, oy)
    x_end_svg, _ = tx(ox + chart_w, oy)
    _, y_end_svg = tx(ox, oy + chart_h)
    out.append(
        f'<line x1="{ox_svg:.2f}" y1="{oy_svg:.2f}" x2="{x_end_svg:.2f}" y2="{oy_svg:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<line x1="{ox_svg:.2f}" y1="{oy_svg:.2f}" x2="{ox_svg:.2f}" y2="{y_end_svg:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )
    # 条形
    for i, v in enumerate(bc.data):
        bx = ox + i * (bar_w + gap) + gap / 2
        bh = chart_h * (v / max_v)
        bx1, by1 = tx(bx, oy)
        bx2, by2 = tx(bx + bar_w, oy + bh)
        # SVG y 向下翻转
        ry = min(by1, by2)
        rh = abs(by2 - by1)
        out.append(
            f'<rect x="{min(bx1, bx2):.2f}" y="{ry:.2f}" width="{abs(bx2 - bx1):.2f}" height="{rh:.2f}" fill="{bc.bar_color}" stroke="{style.stroke}" stroke-width="1"/>'
        )
        # 数值标签
        out.append(text_el(_fmt_num(v), x=(bx1 + bx2) / 2, y=ry - 4,
                           fill="#374151", anchor="middle"))
        # x 轴标签
        if i < len(bc.labels):
            out.append(text_el(bc.labels[i], x=(bx1 + bx2) / 2, y=oy_svg + 16,
                               fill="#6b7280", anchor="middle"))
    out.append('</g>')
    return "".join(out)


def _render_line_chart(
    lc: LineChartObj, sol: Solution, tx, style: Style, text_el
) -> str:
    """渲染折线图：连接数据点。"""
    if lc.origin not in sol.coordinates:
        return ""
    ox, oy = sol.coordinates[lc.origin]
    n = len(lc.data)
    max_v = max(lc.data) if lc.data else 1
    min_v = min(lc.data) if lc.data else 0
    if max_v == min_v:
        max_v = min_v + 1
    chart_w = lc.width
    chart_h = lc.height

    out: list[str] = [f'<g data-id="{lc.id}" class="t2g-obj t2g-line-chart">']
    # 坐标轴
    ox_svg, oy_svg = tx(ox, oy)
    x_end_svg, _ = tx(ox + chart_w, oy)
    _, y_end_svg = tx(ox, oy + chart_h)
    out.append(
        f'<line x1="{ox_svg:.2f}" y1="{oy_svg:.2f}" x2="{x_end_svg:.2f}" y2="{oy_svg:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
        f'<line x1="{ox_svg:.2f}" y1="{oy_svg:.2f}" x2="{ox_svg:.2f}" y2="{y_end_svg:.2f}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
    )
    # 数据点
    pts: list[tuple[float, float]] = []
    for i, v in enumerate(lc.data):
        if n == 1:
            px = ox + chart_w / 2
        else:
            px = ox + chart_w * i / (n - 1)
        py = oy + chart_h * (v - min_v) / (max_v - min_v)
        pts.append((px, py))
    # 折线
    pts_svg = " ".join(f"{tx(*p)[0]:.2f},{tx(*p)[1]:.2f}" for p in pts)
    out.append(
        f'<polyline points="{pts_svg}" fill="none" stroke="{lc.line_color}" stroke-width="2"/>'
    )
    # 数据点 + 标签
    for i, (p, v) in enumerate(zip(pts, lc.data)):
        sx, sy = tx(*p)
        out.append(f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="3" fill="{lc.line_color}"/>')
        out.append(text_el(_fmt_num(v), x=sx, y=sy - 8,
                           fill="#374151", anchor="middle"))
        if i < len(lc.labels):
            x_axis_svg, _ = tx(p[0], oy)
            out.append(text_el(lc.labels[i], x=x_axis_svg, y=oy_svg + 16,
                               fill="#6b7280", anchor="middle"))
    out.append('</g>')
    return "".join(out)


def _render_pie_chart(
    pc: PieChartObj, sol: Solution, tx, style: Style, text_el
) -> str:
    """渲染扇形图：按比例分配角度。"""
    if pc.center not in sol.coordinates:
        return ""
    cx, cy = sol.coordinates[pc.center]
    total = sum(pc.data) if pc.data else 1
    if total <= 0:
        total = 1
    r = pc.radius
    colors = pc.colors or _CHART_PALETTE
    cx_svg, cy_svg = tx(cx, cy)

    out: list[str] = [f'<g data-id="{pc.id}" class="t2g-obj t2g-pie-chart">']
    angle_start = -math.pi / 2   # 从 12 点方向开始
    for i, v in enumerate(pc.data):
        sweep = 2 * math.pi * v / total
        angle_end = angle_start + sweep
        # 计算弧端点
        x1 = cx_svg + r * math.cos(angle_start)
        y1 = cy_svg + r * math.sin(angle_start)
        x2 = cx_svg + r * math.cos(angle_end)
        y2 = cy_svg + r * math.sin(angle_end)
        large_arc = 1 if sweep > math.pi else 0
        color = colors[i % len(colors)]
        # 闭合 path：M center L start A ... end Z
        out.append(
            f'<path d="M {cx_svg:.2f} {cy_svg:.2f} L {x1:.2f} {y1:.2f} '
            f'A {r:.2f} {r:.2f} 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z" '
            f'fill="{color}" fill-opacity="0.7" stroke="{style.stroke}" stroke-width="1"/>'
        )
        # 标签（百分比）
        mid_angle = (angle_start + angle_end) / 2
        label_r = r * 1.15
        lx = cx_svg + label_r * math.cos(mid_angle)
        ly = cy_svg + label_r * math.sin(mid_angle)
        pct = v / total * 100
        out.append(text_el(f"{pct:.1f}%", x=lx, y=ly + 4,
                           fill="#374151", anchor="middle"))
        if i < len(pc.labels):
            out.append(text_el(pc.labels[i], x=lx, y=ly + 18,
                               fill="#6b7280", anchor="middle"))
        angle_start = angle_end
    out.append('</g>')
    return "".join(out)


# ---------------------------------------------------------------------------
# V2-C · 文本渲染：默认 <text>，outline 模式下转 <path>（解决 PPT 字体丢失）
# ---------------------------------------------------------------------------

def _render_text(
    text: str,
    *,
    x: float,
    y: float,
    fill: str | None = None,
    font_size: float | None = None,
    font_style: str | None = None,
    anchor: str = "start",
    default_fill: str = "#000",
    default_size: float = 14.0,
    outline: bool = False,
) -> str:
    """渲染一段文本：默认走 <text>；outline=True 时走矢量 <path>。"""
    if outline:
        fs = font_size or default_size
        return text_to_path.text_to_svg_paths(
            text, x=x, y=y, font_size=fs,
            fill=fill or default_fill, anchor=anchor, font_style=font_style,
        )
    fill_attr = f' fill="{fill}"' if fill else ""
    size_attr = f' font-size="{font_size}"' if font_size else ""
    style_attr = f' font-style="{font_style}"' if font_style else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}"'
        f'{fill_attr}{size_attr}{style_attr}>'
        f'{sx.escape(text)}</text>'
    )
