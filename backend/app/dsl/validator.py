"""DSL 语义校验：确保 id 引用闭合、类型匹配等。"""
from __future__ import annotations

from .safe_expr import UnsafeExpressionError, compile_expr
from .schema import (
    AxisObj,
    ArcObj,
    AnnularSectorObj,
    AuxLineObj,
    BarChartObj,
    BowObj,
    CircleObj,
    CircleDefIncircle,
    CircleDefCircumcircle,
    CircleDefByCenterRadius,
    CircleDefByCenterPoint,
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
    ReflectionSpec,
    RegionObj,
    SectorObj,
    SegmentObj,
    SphereObj,
    TransformedPointObj,
    TransformedPolygonObj,
)


class DSLValidationError(ValueError):
    pass


def _validate_transform_refs(
    transform, obj_map: dict, where: str
) -> None:
    """校验 TransformSpec 内部的引用（center 是 PointObj、line 是 Segment/Line）。"""
    t = transform.type
    if t in ("rotation", "central_symmetry", "homothety"):
        if transform.center not in obj_map:
            raise DSLValidationError(f"{where}: transform.center unknown {transform.center!r}")
        if not isinstance(obj_map[transform.center], PointObj):
            raise DSLValidationError(
                f"{where}: transform.center must be a PointObj"
            )
    elif t == "reflection":
        if transform.line not in obj_map:
            raise DSLValidationError(f"{where}: transform.line unknown {transform.line!r}")
        if not isinstance(obj_map[transform.line], (SegmentObj, LineObj)):
            raise DSLValidationError(
                f"{where}: transform.line must be segment/line"
            )
    # translation 无引用需要校验


def validate(dsl: DSL) -> None:
    """对 DSL 做引用完整性 + 语义校验。失败抛出 DSLValidationError。"""
    obj_map = dsl.object_map()

    # 1. id 唯一
    if len(obj_map) != len(dsl.objects):
        raise DSLValidationError("duplicate object id")

    def _is(obj_id: str, type_) -> bool:
        return obj_id in obj_map and isinstance(obj_map[obj_id], type_)

    def _require(obj_id: str, type_, where: str) -> None:
        if obj_id not in obj_map:
            raise DSLValidationError(f"{where}: unknown id {obj_id!r}")
        if not isinstance(obj_map[obj_id], type_):
            raise DSLValidationError(
                f"{where}: expected {type_.__name__} for {obj_id!r}, "
                f"got {type(obj_map[obj_id]).__name__}"
            )

    def _require_point_like(obj_id: str, where: str) -> None:
        """W11：segment/polygon/line 的顶点可以是 PointObj 或 TransformedPointObj。"""
        if obj_id not in obj_map:
            raise DSLValidationError(f"{where}: unknown id {obj_id!r}")
        obj = obj_map[obj_id]
        if not isinstance(obj, (PointObj, TransformedPointObj)):
            raise DSLValidationError(
                f"{where}: expected point-like for {obj_id!r}, "
                f"got {type(obj).__name__}"
            )

    # 2. 对象内部引用
    for o in dsl.objects:
        if isinstance(o, (SegmentObj, LineObj)):
            _require_point_like(o.a, f"{o.kind} {o.id}.a")
            _require_point_like(o.b, f"{o.kind} {o.id}.b")
            if o.a == o.b:
                raise DSLValidationError(f"{o.kind} {o.id}: endpoints coincide")
        elif isinstance(o, PolygonObj):
            for v in o.vertices:
                _require_point_like(v, f"polygon {o.id}.vertices")
            if len(set(o.vertices)) != len(o.vertices):
                raise DSLValidationError(f"polygon {o.id}: duplicate vertices")
        elif isinstance(o, CircleObj):
            d = o.definition
            if isinstance(d, CircleDefByCenterRadius):
                _require(d.center, PointObj, f"circle {o.id}.center")
                if d.radius <= 0:
                    raise DSLValidationError(f"circle {o.id}: radius must be > 0")
            elif isinstance(d, CircleDefByCenterPoint):
                _require(d.center, PointObj, f"circle {o.id}.center")
                _require(d.through, PointObj, f"circle {o.id}.through")
            elif isinstance(d, (CircleDefIncircle, CircleDefCircumcircle)):
                _require(d.of, PolygonObj, f"circle {o.id}.of")
        elif isinstance(o, AxisObj):
            _require(o.origin, PointObj, f"axis {o.id}.origin")
            if o.x_range[0] >= o.x_range[1]:
                raise DSLValidationError(f"axis {o.id}: x_range min must < max")
            if o.y_range[0] >= o.y_range[1]:
                raise DSLValidationError(f"axis {o.id}: y_range min must < max")
            if o.tick_step <= 0:
                raise DSLValidationError(f"axis {o.id}: tick_step must be > 0")
        elif isinstance(o, TransformedPointObj):
            # source 必须是普通 PointObj（不允许派生对象嵌套派生）
            if o.source not in obj_map:
                raise DSLValidationError(f"transformed_point {o.id}: unknown source {o.source!r}")
            src = obj_map[o.source]
            if not isinstance(src, PointObj):
                raise DSLValidationError(
                    f"transformed_point {o.id}: source must be a PointObj, "
                    f"got {type(src).__name__} (nested transforms not supported)"
                )
            _validate_transform_refs(o.transform, obj_map, f"transformed_point {o.id}")
        elif isinstance(o, TransformedPolygonObj):
            if o.source not in obj_map:
                raise DSLValidationError(f"transformed_polygon {o.id}: unknown source {o.source!r}")
            src = obj_map[o.source]
            if not isinstance(src, PolygonObj):
                raise DSLValidationError(
                    f"transformed_polygon {o.id}: source must be a PolygonObj, "
                    f"got {type(src).__name__}"
                )
            if not o.vertex_suffix:
                raise DSLValidationError(f"transformed_polygon {o.id}: vertex_suffix must be non-empty")
            # 派生顶点 id 不能与已有对象冲突
            for v in src.vertices:
                derived_id = f"{v}_{o.vertex_suffix}"
                if derived_id in obj_map:
                    raise DSLValidationError(
                        f"transformed_polygon {o.id}: derived vertex id {derived_id!r} "
                        f"collides with existing object"
                    )
            _validate_transform_refs(o.transform, obj_map, f"transformed_polygon {o.id}")
        elif isinstance(o, FunctionCurveObj):
            # V2-B：函数曲线必须在含 axis 的 DSL 中；且 expr 必须过安全沙箱
            if not any(isinstance(x, AxisObj) for x in dsl.objects):
                raise DSLValidationError(
                    f"curve {o.id}: requires an axis (coordinate system) in the DSL"
                )
            if o.samples < 10:
                raise DSLValidationError(f"curve {o.id}: samples must be >= 10")
            if o.domain is not None and o.domain[0] >= o.domain[1]:
                raise DSLValidationError(f"curve {o.id}: domain min must < max")
            # V2-G.4：pieces 与 expr 二选一
            if o.pieces:
                for i, p in enumerate(o.pieces):
                    if p.domain[0] >= p.domain[1]:
                        raise DSLValidationError(
                            f"curve {o.id}: pieces[{i}].domain min must < max"
                        )
                    try:
                        compile_expr(p.expr, var=o.var)
                    except (UnsafeExpressionError, SyntaxError) as e:
                        raise DSLValidationError(
                            f"curve {o.id}: pieces[{i}] unsafe/invalid expr {p.expr!r}: {e}"
                        )
            else:
                if not o.expr:
                    raise DSLValidationError(
                        f"curve {o.id}: must have expr or pieces"
                    )
                try:
                    compile_expr(o.expr, var=o.var)
                except (UnsafeExpressionError, SyntaxError) as e:
                    raise DSLValidationError(
                        f"curve {o.id}: unsafe or invalid expression {o.expr!r}: {e}"
                    )
        elif isinstance(o, ArcObj):
            # V2-G.1：弧的 center/from_point/to_point 都必须是 PointObj
            _require(o.center, PointObj, f"arc {o.id}.center")
            _require(o.from_point, PointObj, f"arc {o.id}.from_point")
            _require(o.to_point, PointObj, f"arc {o.id}.to_point")
            if len({o.center, o.from_point, o.to_point}) != 3:
                raise DSLValidationError(
                    f"arc {o.id}: center, from_point, to_point must be distinct"
                )
            if o.radius is not None and o.radius <= 0:
                raise DSLValidationError(f"arc {o.id}: radius must be > 0")
        elif isinstance(o, SectorObj):
            # V2-G.1：扇形的 center/from_point/to_point 都必须是 PointObj
            _require(o.center, PointObj, f"sector {o.id}.center")
            _require(o.from_point, PointObj, f"sector {o.id}.from_point")
            _require(o.to_point, PointObj, f"sector {o.id}.to_point")
            if len({o.center, o.from_point, o.to_point}) != 3:
                raise DSLValidationError(
                    f"sector {o.id}: center, from_point, to_point must be distinct"
                )
        elif isinstance(o, BowObj):
            # V2-G.4：弓形的 center/from_point/to_point 都必须是 PointObj（同 sector）
            _require(o.center, PointObj, f"bow {o.id}.center")
            _require(o.from_point, PointObj, f"bow {o.id}.from_point")
            _require(o.to_point, PointObj, f"bow {o.id}.to_point")
            if len({o.center, o.from_point, o.to_point}) != 3:
                raise DSLValidationError(
                    f"bow {o.id}: center, from_point, to_point must be distinct"
                )
        elif isinstance(o, AnnularSectorObj):
            # P3 V3.4：圆环扇环。center/from_point/to_point 必须 PointObj；三点互异；r_inner > 0
            _require(o.center, PointObj, f"annular_sector {o.id}.center")
            _require(o.from_point, PointObj, f"annular_sector {o.id}.from_point")
            _require(o.to_point, PointObj, f"annular_sector {o.id}.to_point")
            if len({o.center, o.from_point, o.to_point}) != 3:
                raise DSLValidationError(
                    f"annular_sector {o.id}: center, from_point, to_point must be distinct"
                )
            if o.r_inner <= 0:
                raise DSLValidationError(
                    f"annular_sector {o.id}: r_inner must be > 0"
                )
        elif isinstance(o, RegionObj):
            # V2-G.3：阴影区域 boundary 必须是 segment/arc id 列表
            for bid in o.boundary:
                if not (_is(bid, SegmentObj) or _is(bid, ArcObj)):
                    raise DSLValidationError(
                        f"region {o.id}: boundary element {bid!r} must be segment or arc"
                    )
            if not (0 < o.fill_opacity <= 1):
                raise DSLValidationError(f"region {o.id}: fill_opacity must be in (0, 1]")
        elif isinstance(o, NumberLineObj):
            # V2-G.3：数轴 origin 必须是 PointObj
            _require(o.origin, PointObj, f"number_line {o.id}.origin")
            if o.range[0] >= o.range[1]:
                raise DSLValidationError(f"number_line {o.id}: range min must < max")
            if o.tick_step <= 0:
                raise DSLValidationError(f"number_line {o.id}: tick_step must be > 0")
        elif isinstance(o, AuxLineObj):
            # V2-G.3：辅助线 a/b 必须是 point-like（PointObj 或 TransformedPointObj）
            _require_point_like(o.a, f"aux_line {o.id}.a")
            _require_point_like(o.b, f"aux_line {o.id}.b")
            if o.a == o.b:
                raise DSLValidationError(f"aux_line {o.id}: endpoints coincide")
        elif isinstance(o, (CubeObj, CuboidObj, CylinderObj, ConeObj, SphereObj)):
            # V3.1：立体几何对象校验
            if isinstance(o, CubeObj):
                _require(o.vertex, PointObj, f"cube {o.id}.vertex")
                if o.edge <= 0:
                    raise DSLValidationError(f"cube {o.id}: edge must be > 0")
            elif isinstance(o, CuboidObj):
                _require(o.vertex, PointObj, f"cuboid {o.id}.vertex")
                if o.length <= 0 or o.width <= 0 or o.height <= 0:
                    raise DSLValidationError(f"cuboid {o.id}: length/width/height must be > 0")
            elif isinstance(o, (CylinderObj, ConeObj)):
                anchor_field = "center_bottom"
                _require(getattr(o, anchor_field), PointObj, f"{o.kind} {o.id}.{anchor_field}")
                if o.radius <= 0:
                    raise DSLValidationError(f"{o.kind} {o.id}: radius must be > 0")
                if o.height <= 0:
                    raise DSLValidationError(f"{o.kind} {o.id}: height must be > 0")
            elif isinstance(o, SphereObj):
                _require(o.center, PointObj, f"sphere {o.id}.center")
                if o.radius <= 0:
                    raise DSLValidationError(f"sphere {o.id}: radius must be > 0")
        elif isinstance(o, (BarChartObj, LineChartObj, PieChartObj)):
            # V3.2：统计图表校验
            if isinstance(o, (BarChartObj, LineChartObj)):
                anchor_field = "origin"
                _require(getattr(o, anchor_field), PointObj, f"{o.kind} {o.id}.{anchor_field}")
            else:  # PieChartObj
                _require(o.center, PointObj, f"pie_chart {o.id}.center")
                if o.radius <= 0:
                    raise DSLValidationError(f"pie_chart {o.id}: radius must be > 0")
            # data 和 labels 长度必须一致
            if len(o.data) != len(o.labels):
                raise DSLValidationError(
                    f"{o.kind} {o.id}: data and labels length mismatch "
                    f"({len(o.data)} vs {len(o.labels)})"
                )

    # 2.5 axis 唯一性
    axes = [o for o in dsl.objects if isinstance(o, AxisObj)]
    if len(axes) > 1:
        raise DSLValidationError("at most one axis allowed per DSL")

    # 3. 约束引用
    for c in dsl.constraints:
        t = c.type
        if t == "length":
            _require(c.segment, SegmentObj, "length.segment")
            if c.value <= 0:
                raise DSLValidationError("length.value must be > 0")
        elif t == "equal_length":
            for s in c.segments:
                _require(s, SegmentObj, "equal_length.segments")
        elif t == "angle":
            _require(c.a, PointObj, "angle.a")
            _require(c.b, PointObj, "angle.b")
            _require(c.c, PointObj, "angle.c")
            if not (0 < c.value < 180):
                raise DSLValidationError("angle.value must be in (0, 180)")
        elif t in ("parallel", "perpendicular"):
            for side in (c.a, c.b):
                if not (_is(side, SegmentObj) or _is(side, LineObj)):
                    raise DSLValidationError(f"{t}: expected segment/line {side!r}")
        elif t == "collinear":
            for p in c.points:
                _require(p, PointObj, "collinear.points")
        elif t == "tangent":
            if not (_is(c.line, SegmentObj) or _is(c.line, LineObj)):
                raise DSLValidationError("tangent.line must be segment/line")
            _require(c.circle, CircleObj, "tangent.circle")
        elif t == "on_circle":
            _require(c.point, PointObj, "on_circle.point")
            _require(c.circle, CircleObj, "on_circle.circle")
        elif t == "isoceles":
            _require(c.polygon, PolygonObj, "isoceles.polygon")
            _require(c.apex, PointObj, "isoceles.apex")
            if c.apex not in obj_map[c.polygon].vertices:
                raise DSLValidationError("isoceles.apex not a vertex of polygon")
        elif t == "equilateral":
            _require(c.polygon, PolygonObj, "equilateral.polygon")
            if len(obj_map[c.polygon].vertices) != 3:
                raise DSLValidationError("equilateral requires triangle")
        elif t == "right_triangle":
            _require(c.polygon, PolygonObj, "right_triangle.polygon")
            poly = obj_map[c.polygon]
            if len(poly.vertices) != 3:
                raise DSLValidationError("right_triangle requires triangle")
            if c.right_at not in poly.vertices:
                raise DSLValidationError("right_triangle.right_at not a vertex")
        elif t == "radius":
            _require(c.circle, CircleObj, "radius.circle")
            if c.value <= 0:
                raise DSLValidationError("radius.value must be > 0")
        elif t == "midpoint":
            _require(c.m, PointObj, "midpoint.m")
            _require(c.a, PointObj, "midpoint.a")
            _require(c.b, PointObj, "midpoint.b")
            if c.a == c.b:
                raise DSLValidationError("midpoint.a == midpoint.b")
        elif t == "foot_of_perp":
            for fld, name in [(c.f, "f"), (c.p, "p"), (c.a, "a"), (c.b, "b")]:
                _require(fld, PointObj, f"foot_of_perp.{name}")
            if c.a == c.b:
                raise DSLValidationError("foot_of_perp: a == b")
        elif t == "angle_bisector":
            for fld, name in [(c.a, "a"), (c.b, "b"), (c.c, "c"), (c.d, "d")]:
                _require(fld, PointObj, f"angle_bisector.{name}")
        elif t == "concyclic":
            for p in c.points:
                _require(p, PointObj, "concyclic.points")
            if len(set(c.points)) != len(c.points):
                raise DSLValidationError("concyclic: duplicate points")
        elif t == "parallelogram":
            _require(c.polygon, PolygonObj, "parallelogram.polygon")
            if len(obj_map[c.polygon].vertices) != 4:
                raise DSLValidationError("parallelogram requires quadrilateral")
        elif t in ("same_side", "opposite_side"):
            if not (_is(c.line, SegmentObj) or _is(c.line, LineObj)):
                raise DSLValidationError(f"{t}.line must be segment/line")
            _require(c.point, PointObj, f"{t}.point")
            _require(c.ref, PointObj, f"{t}.ref")
            if c.point == c.ref:
                raise DSLValidationError(f"{t}: point and ref are the same")
        elif t == "on_curve":
            _require(c.point, PointObj, "on_curve.point")
            _require(c.curve, FunctionCurveObj, "on_curve.curve")
        elif t == "regular_polygon":
            _require(c.polygon, PolygonObj, "regular_polygon.polygon")
            poly = obj_map[c.polygon]
            if c.sides != len(poly.vertices):
                raise DSLValidationError(
                    f"regular_polygon: sides ({c.sides}) must equal "
                    f"polygon.vertices count ({len(poly.vertices)})"
                )
            if c.sides < 3:
                raise DSLValidationError("regular_polygon: sides must be >= 3")
        elif t == "trapezoid":
            _require(c.polygon, PolygonObj, "trapezoid.polygon")
            poly = obj_map[c.polygon]
            if len(poly.vertices) != 4:
                raise DSLValidationError("trapezoid requires quadrilateral (4 vertices)")
            # bases 必须都是该 polygon 的边
            side_ids = _polygon_side_ids(dsl, poly)
            for b in c.bases:
                if not _is(b, SegmentObj):
                    raise DSLValidationError(f"trapezoid.bases: expected segment {b!r}")
                if b not in side_ids:
                    raise DSLValidationError(
                        f"trapezoid.bases: segment {b!r} is not a side of polygon {c.polygon!r}"
                    )
            if c.bases[0] == c.bases[1]:
                raise DSLValidationError("trapezoid.bases: two bases must be distinct")
            # bases 必须是对边（在四边形里相隔 2 个位置）
            i0 = side_ids.index(c.bases[0])
            i1 = side_ids.index(c.bases[1])
            if abs(i0 - i1) != 2:
                raise DSLValidationError(
                    "trapezoid.bases: two bases must be opposite sides of the quadrilateral"
                )
        elif t in ("arc_angle", "arc_length", "bow_area"):
            # V2-G.2：圆弧相关约束；V2-G.4：bow_area 也接受 BowObj
            if not _is(c.arc, ArcObj) and not _is(c.arc, BowObj):
                raise DSLValidationError(
                    f"{t}.arc: expected arc or bow object, got {c.arc!r}"
                )
            if t == "arc_angle":
                if not (0 < c.value < 360):
                    raise DSLValidationError("arc_angle.value must be in (0, 360) degrees")
            else:  # arc_length / bow_area
                if c.value <= 0:
                    raise DSLValidationError(f"{t}.value must be > 0")

    # 4. label key must point to existing object
    for k in dsl.labels:
        if k not in obj_map:
            raise DSLValidationError(f"label key {k!r} not an object id")


def _polygon_side_ids(dsl: DSL, poly: PolygonObj) -> list[str]:
    """返回 polygon 顶点顺序对应的边 segment id 列表（找不到对应 segment 的位置返回空 id ""）。"""
    out: list[str] = []
    v = poly.vertices
    n = len(v)
    for i in range(n):
        a, b = v[i], v[(i + 1) % n]
        found = ""
        for s in dsl.segments():
            if {s.a, s.b} == {a, b}:
                found = s.id
                break
        out.append(found)
    return out
