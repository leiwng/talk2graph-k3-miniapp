"""话图 (T2G) 几何 DSL — v0.1

约定：
- 所有几何对象通过 `id` 引用；id 仅由字母/数字/下划线组成。
- 求解器输出每个 point 的坐标；其他对象的几何属性（圆心、半径等）由 point + constraints 派生。
- LLM 只输出本 schema 的结构 或 DSL diff（见 diff.py），永不直接输出坐标。
"""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

class _Obj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"invalid id: {v!r}")
        return v


class PointObj(_Obj):
    kind: Literal["point"] = "point"
    # 可选：求解时的提示坐标（仅用于多解时挑选 / 初值，不当作硬约束）
    hint: tuple[float, float] | None = None


class SegmentObj(_Obj):
    kind: Literal["segment"] = "segment"
    a: str  # point id
    b: str  # point id


class LineObj(_Obj):
    """无限直线，由两点决定。"""
    kind: Literal["line"] = "line"
    a: str
    b: str


class PolygonObj(_Obj):
    kind: Literal["polygon"] = "polygon"
    vertices: list[str] = Field(min_length=3)


class CircleDefByCenterRadius(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["center_radius"]
    center: str   # point id
    radius: float


class CircleDefByCenterPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["center_through"]
    center: str
    through: str


class CircleDefIncircle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["incircle"]
    of: str  # polygon id


class CircleDefCircumcircle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["circumcircle"]
    of: str  # polygon id


CircleDefinition = Annotated[
    Union[
        CircleDefByCenterRadius,
        CircleDefByCenterPoint,
        CircleDefIncircle,
        CircleDefCircumcircle,
    ],
    Field(discriminator="type"),
]


class CircleObj(_Obj):
    kind: Literal["circle"] = "circle"
    definition: CircleDefinition


class AxisObj(_Obj):
    """直角坐标系（V2-A）。

    约定：
    - 一个 DSL 最多含 **1 个** axis。
    - 存在 axis 时，求解器以 axis.origin 为原点、x 轴方向锁定单位长度；其他点全自由。
    - 不存在 axis 时，保持 W1 行为（第一点固定原点 + 第二点 y=0）。
    - origin 必须引用一个 PointObj id；省略时由验证器要求添加 'O'。
    """
    kind: Literal["axis"] = "axis"
    origin: str  # point id
    x_range: tuple[float, float] = (-5.0, 5.0)
    y_range: tuple[float, float] = (-5.0, 5.0)
    tick_step: float = 1.0
    show_grid: bool = True
    show_ticks: bool = True
    x_label: str = "x"
    y_label: str = "y"


# ---------------------------------------------------------------------------
# Transforms (W11 · 几何变换)
# ---------------------------------------------------------------------------

class RotationSpec(BaseModel):
    """绕 center 逆时针旋转 angle 度。"""
    model_config = ConfigDict(extra="forbid")
    type: Literal["rotation"]
    center: str
    angle: float


class TranslationSpec(BaseModel):
    """平移向量 (dx, dy)。"""
    model_config = ConfigDict(extra="forbid")
    type: Literal["translation"]
    dx: float
    dy: float


class ReflectionSpec(BaseModel):
    """关于直线（segment / line id）对称。"""
    model_config = ConfigDict(extra="forbid")
    type: Literal["reflection"]
    line: str


class CentralSymSpec(BaseModel):
    """关于 center 点中心对称（等价于 rotation angle=180）。"""
    model_config = ConfigDict(extra="forbid")
    type: Literal["central_symmetry"]
    center: str


TransformSpec = Annotated[
    Union[RotationSpec, TranslationSpec, ReflectionSpec, CentralSymSpec],
    Field(discriminator="type"),
]


class TransformedPointObj(_Obj):
    """派生点：源点经变换后的位置。不引入新自由变量，坐标由求解器后处理算出。"""
    kind: Literal["transformed_point"] = "transformed_point"
    source: str        # source point id
    transform: TransformSpec


class TransformedPolygonObj(_Obj):
    """派生多边形：源 polygon 所有顶点经变换后组成的新 polygon。
    自动为每个源顶点生成派生点，id 规则：`<vertex>_<suffix>`（如 A_p / B_p / C_p）。
    """
    kind: Literal["transformed_polygon"] = "transformed_polygon"
    source: str        # source polygon id
    transform: TransformSpec
    vertex_suffix: str = "p"


class FunctionCurveObj(_Obj):
    """函数曲线 (V2-B)。y = f(x) 或 x = g(y)。

    必须在含 axis 的 DSL 中出现。求解器不处理此对象，渲染时采样绘制。
    """
    kind: Literal["curve"] = "curve"
    expr: str                                    # 表达式，如 "x**2" / "sin(x)"
    var: Literal["x", "y"] = "x"                 # 自变量
    domain: tuple[float, float] | None = None    # 采样域；None → 用 axis 对应 range
    samples: int = 300
    color: str = "#0d6efd"                       # 曲线颜色（默认蓝，与几何黑色区分）
    dash: str | None = None                      # 可选虚线


GeometryObject = Annotated[
    Union[
        PointObj, SegmentObj, LineObj, PolygonObj, CircleObj, AxisObj,
        TransformedPointObj, TransformedPolygonObj,
        FunctionCurveObj,
    ],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

class _C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LengthC(_C):
    type: Literal["length"]
    segment: str
    value: float


class EqualLengthC(_C):
    type: Literal["equal_length"]
    segments: list[str] = Field(min_length=2)


class AngleC(_C):
    """角度约束：以 b 为顶点的 ∠abc，单位：度。"""
    type: Literal["angle"]
    a: str
    b: str
    c: str
    value: float


class ParallelC(_C):
    type: Literal["parallel"]
    a: str  # segment/line id
    b: str


class PerpendicularC(_C):
    type: Literal["perpendicular"]
    a: str
    b: str


class CollinearC(_C):
    type: Literal["collinear"]
    points: list[str] = Field(min_length=3)


class TangentC(_C):
    """直线/线段与圆相切。"""
    type: Literal["tangent"]
    line: str    # segment or line id
    circle: str


class OnCircleC(_C):
    type: Literal["on_circle"]
    point: str
    circle: str


class IsocelesC(_C):
    type: Literal["isoceles"]
    polygon: str
    apex: str  # 顶角所在顶点


class EquilateralC(_C):
    type: Literal["equilateral"]
    polygon: str


class RightTriangleC(_C):
    type: Literal["right_triangle"]
    polygon: str
    right_at: str  # 直角顶点


class RadiusC(_C):
    type: Literal["radius"]
    circle: str
    value: float


class MidpointC(_C):
    """约束 m 为 a、b 的中点。"""
    type: Literal["midpoint"]
    m: str  # point id
    a: str
    b: str


class FootOfPerpC(_C):
    """f 为 p 在直线 ab 上的垂足。"""
    type: Literal["foot_of_perp"]
    f: str
    p: str
    a: str
    b: str


class AngleBisectorC(_C):
    """点 d 在 ∠abc 的角平分线上。"""
    type: Literal["angle_bisector"]
    a: str
    b: str   # 角顶点
    c: str
    d: str   # 角平分线上的点（通常是对边上的交点）


class ConcyclicC(_C):
    """四点（或更多）共圆。"""
    type: Literal["concyclic"]
    points: list[str] = Field(min_length=4)


class ParallelogramC(_C):
    """polygon 是平行四边形（按顶点顺序）。"""
    type: Literal["parallelogram"]
    polygon: str


class SameSideC(_C):
    """点 point 与参考点 ref 在直线 line 的同一侧。
    用于表达"C 在 AB 上方"等方位语义：把"上方"建模为一个 hint 朝目标方向放置的辅助点
    P0，再用 same_side 强制 C 与 P0 同侧。
    """
    type: Literal["same_side"]
    line: str    # segment 或 line id
    point: str   # point id
    ref: str     # point id


class OppositeSideC(_C):
    """点 point 与参考点 ref 在直线 line 的两侧。"""
    type: Literal["opposite_side"]
    line: str
    point: str
    ref: str


Constraint = Annotated[
    Union[
        LengthC, EqualLengthC, AngleC,
        ParallelC, PerpendicularC, CollinearC,
        TangentC, OnCircleC,
        IsocelesC, EquilateralC, RightTriangleC,
        RadiusC,
        MidpointC, FootOfPerpC, AngleBisectorC, ConcyclicC, ParallelogramC,
        SameSideC, OppositeSideC,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Annotations & Style
# ---------------------------------------------------------------------------

class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str               # object id (segment / angle pseudo-id "angleABC" / circle…)
    kind: Literal["length", "angle", "label", "radius"]
    show: bool = True
    text: str | None = None   # 显式覆盖文字（如 "a"、"√3"）


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["classroom"] = "classroom"
    stroke: str = "#222"
    stroke_width: float = 1.6
    point_radius: float = 3.0
    aux_dash: str = "5 4"
    font_size: float = 14.0
    font_family: str = "PingFang SC, Source Han Sans SC, Noto Sans CJK SC, sans-serif"


# ---------------------------------------------------------------------------
# DSL document
# ---------------------------------------------------------------------------

class DSL(BaseModel):
    """完整 DSL 文档。"""
    model_config = ConfigDict(extra="forbid")

    version: Literal["0.1"] = "0.1"
    objects: list[GeometryObject] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    style: Style = Field(default_factory=Style)

    # ---- helpers ----
    def object_map(self) -> dict[str, GeometryObject]:
        return {o.id: o for o in self.objects}

    def points(self) -> list[PointObj]:
        return [o for o in self.objects if isinstance(o, PointObj)]

    def segments(self) -> list[SegmentObj]:
        return [o for o in self.objects if isinstance(o, SegmentObj)]

    def circles(self) -> list[CircleObj]:
        return [o for o in self.objects if isinstance(o, CircleObj)]

    def polygons(self) -> list[PolygonObj]:
        return [o for o in self.objects if isinstance(o, PolygonObj)]

    def axis(self) -> AxisObj | None:
        for o in self.objects:
            if isinstance(o, AxisObj):
                return o
        return None

    def transformed_polygons(self) -> list[TransformedPolygonObj]:
        return [o for o in self.objects if isinstance(o, TransformedPolygonObj)]

    def transformed_points(self) -> list[TransformedPointObj]:
        return [o for o in self.objects if isinstance(o, TransformedPointObj)]

    def curves(self) -> list[FunctionCurveObj]:
        return [o for o in self.objects if isinstance(o, FunctionCurveObj)]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
