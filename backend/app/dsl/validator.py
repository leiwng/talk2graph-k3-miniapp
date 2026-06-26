"""DSL 语义校验：确保 id 引用闭合、类型匹配等。"""
from __future__ import annotations

from .schema import (
    CircleObj,
    CircleDefIncircle,
    CircleDefCircumcircle,
    CircleDefByCenterRadius,
    CircleDefByCenterPoint,
    DSL,
    LineObj,
    PointObj,
    PolygonObj,
    SegmentObj,
)


class DSLValidationError(ValueError):
    pass


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

    # 2. 对象内部引用
    for o in dsl.objects:
        if isinstance(o, (SegmentObj, LineObj)):
            _require(o.a, PointObj, f"{o.kind} {o.id}.a")
            _require(o.b, PointObj, f"{o.kind} {o.id}.b")
            if o.a == o.b:
                raise DSLValidationError(f"{o.kind} {o.id}: endpoints coincide")
        elif isinstance(o, PolygonObj):
            for v in o.vertices:
                _require(v, PointObj, f"polygon {o.id}.vertices")
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

    # 4. label key must point to existing object
    for k in dsl.labels:
        if k not in obj_map:
            raise DSLValidationError(f"label key {k!r} not an object id")
