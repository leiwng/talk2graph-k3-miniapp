"""DSL 语义校验：确保 id 引用闭合、类型匹配等。"""
from __future__ import annotations

from .safe_expr import UnsafeExpressionError, compile_expr
from .schema import (
    AxisObj,
    CircleObj,
    CircleDefIncircle,
    CircleDefCircumcircle,
    CircleDefByCenterRadius,
    CircleDefByCenterPoint,
    DSL,
    FunctionCurveObj,
    LineObj,
    PointObj,
    PolygonObj,
    ReflectionSpec,
    SegmentObj,
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
    if t in ("rotation", "central_symmetry"):
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
            try:
                compile_expr(o.expr, var=o.var)
            except (UnsafeExpressionError, SyntaxError) as e:
                raise DSLValidationError(
                    f"curve {o.id}: unsafe or invalid expression {o.expr!r}: {e}"
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

    # 4. label key must point to existing object
    for k in dsl.labels:
        if k not in obj_map:
            raise DSLValidationError(f"label key {k!r} not an object id")
