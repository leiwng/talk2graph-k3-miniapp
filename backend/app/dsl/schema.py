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
    # V2-G.3：网格作图模式，grid_size != None 时画明显的网格点（用于"5×7 网格中画图"场景）
    grid_size: float | None = None


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


class HomothetySpec(BaseModel):
    """位似变换 (V2-G.4)：以 center 为位似中心，按 ratio 缩放。
    ratio > 1 放大；0 < ratio < 1 缩小；ratio < 0 反向位似。
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["homothety"]
    center: str
    ratio: float


TransformSpec = Annotated[
    Union[RotationSpec, TranslationSpec, ReflectionSpec, CentralSymSpec, HomothetySpec],
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


class CurvePiece(BaseModel):
    """分段函数的一段 (V2-G.4)。"""
    model_config = ConfigDict(extra="forbid")
    expr: str
    domain: tuple[float, float]


class FunctionCurveObj(_Obj):
    """函数曲线 (V2-B)。y = f(x) 或 x = g(y)。

    必须在含 axis 的 DSL 中出现。求解器不处理此对象，渲染时采样绘制。
    V2-G.4：支持分段函数。若 pieces 字段非空，按 pieces 渲染；否则用 expr + domain 单段。
    """
    kind: Literal["curve"] = "curve"
    expr: str | None = None                       # 单段表达式（与 pieces 二选一）
    var: Literal["x", "y"] = "x"                  # 自变量
    domain: tuple[float, float] | None = None     # 采样域；None -> 用 axis 对应 range
    samples: int = 300
    color: str = "#0d6efd"                        # 曲线颜色（默认蓝，与几何黑色区分）
    dash: str | None = None                       # 可选虚线
    pieces: list[CurvePiece] | None = None        # V2-G.4 分段函数（与 expr 二选一）


class ArcObj(_Obj):
    """圆弧 (V2-G.1)。

    从 from_point 到 to_point 的弧，绕 center。
    - radius 缺省时由 solver 自动追加隐含约束 |center-from| == |center-to|（center 为圆心）。
    - ccw=True 表示逆时针（数学正方向，SVG 渲染时 y 翻转后需映射 sweep flag）。
    """
    kind: Literal["arc"] = "arc"
    center: str        # point id
    from_point: str    # point id
    to_point: str      # point id
    radius: float | None = None   # None -> 隐含 |center-from| == |center-to|
    ccw: bool = True


class SectorObj(_Obj):
    """扇形 (V2-G.1)。闭合区域：center + from_point + 弧 + to_point。
    半径由 |center-from| 推断（solver 自动追加隐含等距约束）。
    """
    kind: Literal["sector"] = "sector"
    center: str
    from_point: str
    to_point: str
    ccw: bool = True


class BowObj(_Obj):
    """弓形 (V2-G.4)。闭合区域：弧 + 弦（自动闭合 from_point 到 to_point）。
    与 sector 区别：不画到圆心的两条半径，只画弧 + 弦围成的区域。
    半径由 |center-from| 推断（solver 自动追加隐含等距约束）。
    """
    kind: Literal["bow"] = "bow"
    center: str
    from_point: str
    to_point: str
    ccw: bool = True


class AnnularSectorObj(_Obj):
    """圆环扇环 (V3.4 / P3)。两个同心弧 + 两条径向直线段围成的区域。

    外弧半径 = |center - from_point|（隐含等距约束 |center-from| == |center-to|）
    内弧半径 = r_inner（必须 > 0）
    渲染：外弧 + 内弧 + 两条径向直线段，闭合 path 填充。
    适用于「圆环扇形」「环形面积」等场景。
    """
    kind: Literal["annular_sector"] = "annular_sector"
    center: str
    from_point: str
    to_point: str
    r_inner: float       # 内圆半径（必须 > 0）
    ccw: bool = True


class RegionObj(_Obj):
    """阴影/填充区域 (V2-G.3)。
    通过 boundary 引用一组 SegmentObj/ArcObj id，按顺序组成闭合路径并填充。
    用于圆环/扇环/复合阴影等场景。不引入新自由变量。
    """
    kind: Literal["region"] = "region"
    boundary: list[str] = Field(min_length=2)   # segment/arc id 列表，按顺序首尾相连
    fill_color: str = "#0d6efd"
    fill_opacity: float = 0.15
    stroke: str | None = None   # None = 不画描边


class NumberLineObj(_Obj):
    """1D 数轴 (V2-G.3)。含负数刻度，小学+初中应用题（行程问题等）用。
    与 AxisObj 区别：只画一条水平数轴，不画 y 轴和网格。
    """
    kind: Literal["number_line"] = "number_line"
    origin: str                    # point id（数轴原点 0）
    range: tuple[float, float] = (-10.0, 10.0)
    tick_step: float = 1.0
    show_ticks: bool = True
    show_numbers: bool = True
    label: str = "x"


class AuxLineObj(_Obj):
    """辅助线 (V2-G.3)。虚线，不参与约束求解，用于几何证明辅助线标注。
    a/b 引用已有 PointObj，不引入新自由变量。
    """
    kind: Literal["aux_line"] = "aux_line"
    a: str   # point id
    b: str   # point id
    extended: bool = False   # True = 延长为无限直线（类似 LineObj），False = 有限线段
    dash: str | None = None   # None = 用 style.aux_dash


# ---------------------------------------------------------------------------
# V3.1 · 立体几何（等轴投影 SVG，不参与求解器约束）
# ---------------------------------------------------------------------------

class CubeObj(_Obj):
    """正方体 (V3.1)。vertex 是底面前左下顶点（用作 anchor），edge 是棱长。"""
    kind: Literal["cube"] = "cube"
    vertex: str            # point id（底面前左下顶点 anchor）
    edge: float            # 棱长


class CuboidObj(_Obj):
    """长方体 (V3.1)。vertex 是底面前左下顶点，length/width/height 对应 x/y/z 方向。"""
    kind: Literal["cuboid"] = "cuboid"
    vertex: str            # point id（底面前左下顶点 anchor）
    length: float          # x 方向（前-右）
    width: float           # z 方向（前-后，等轴投影水平偏移）
    height: float          # y 方向（向上）


class CylinderObj(_Obj):
    """圆柱 (V3.1)。center_bottom 是底面圆心（用作 anchor），radius + height。"""
    kind: Literal["cylinder"] = "cylinder"
    center_bottom: str     # point id（底面圆心 anchor）
    radius: float
    height: float


class ConeObj(_Obj):
    """圆锥 (V3.1)。center_bottom 是底面圆心，apex 是顶点（或用 radius+height 自动算）。"""
    kind: Literal["cone"] = "cone"
    center_bottom: str     # point id（底面圆心 anchor）
    radius: float
    height: float          # 圆锥高度


class SphereObj(_Obj):
    """球 (V3.1)。center 是球心 anchor，radius 是半径。"""
    kind: Literal["sphere"] = "sphere"
    center: str            # point id（球心 anchor）
    radius: float


# ---------------------------------------------------------------------------
# V3.2 · 统计图表（独立渲染，不走求解器）
# ---------------------------------------------------------------------------

class BarChartObj(_Obj):
    """条形统计图 (V3.2)。
    origin 是坐标系原点 anchor；data 是数值列表；labels 是对应标签。
    """
    kind: Literal["bar_chart"] = "bar_chart"
    origin: str                       # point id（左下角 anchor）
    data: list[float] = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    width: float = 8.0               # 图表总宽
    height: float = 6.0              # 图表总高
    bar_color: str = "#3b82f6"


class LineChartObj(_Obj):
    """折线统计图 (V3.2)。
    origin 是左下角 anchor；data 是 y 值列表（x 自动等距分布）。
    """
    kind: Literal["line_chart"] = "line_chart"
    origin: str
    data: list[float] = Field(min_length=2)
    labels: list[str] = Field(min_length=2)
    width: float = 8.0
    height: float = 6.0
    line_color: str = "#3b82f6"


class PieChartObj(_Obj):
    """扇形统计图 (V3.2)。
    center 是圆心 anchor；data 是各项数值（自动按比例分配角度）。
    """
    kind: Literal["pie_chart"] = "pie_chart"
    center: str
    data: list[float] = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    radius: float = 3.0
    colors: list[str] | None = None   # None = 用默认色板


GeometryObject = Annotated[
    Union[
        PointObj, SegmentObj, LineObj, PolygonObj, CircleObj, AxisObj,
        TransformedPointObj, TransformedPolygonObj,
        FunctionCurveObj,
        ArcObj, SectorObj, BowObj, AnnularSectorObj,
        RegionObj, NumberLineObj, AuxLineObj,
        CubeObj, CuboidObj, CylinderObj, ConeObj, SphereObj,
        BarChartObj, LineChartObj, PieChartObj,
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


class OnCurveC(_C):
    """点 point 在函数曲线 curve 上（V2-B 后处理 W12 增强）。

    - curve 必须是 kind=curve 的对象
    - 若 curve.var == "x"：约束 point.y == f(point.x)
    - 若 curve.var == "y"：约束 point.x == g(point.y)
    """
    type: Literal["on_curve"]
    point: str
    curve: str


class RegularPolygonC(_C):
    """正多边形 (V2-G.1)。隐含：N 条相邻边等长 + N 个内角 = (N-2)*180/N 度。

    sides 必须等于 polygon.vertices 数量（≥3）。
    """
    type: Literal["regular_polygon"]
    polygon: str
    sides: int   # 3=正三角形 / 4=正方形 / 5=正五边形 / 6=正六边形 ...


class TrapezoidC(_C):
    """梯形 (V2-G.1)。两底平行，两腰不平行靠自由求解自然产生。

    等腰梯形：额外加 equal_length{segments:[两腰]}；
    直角梯形：额外加 perpendicular{一腰, 一底}。
    bases 是 polygon 的两条对边（segment id），通常为 polygon.vertices 中相邻顶点构成的边。
    """
    type: Literal["trapezoid"]
    polygon: str
    bases: list[str] = Field(min_length=2, max_length=2)   # 两条对边的 segment id


class ArcAngleC(_C):
    """圆弧的圆心角约束 (V2-G.2)。

    约束 arc 所对圆心角为 value 度（0, 360）。
    残差用 cos/sin 分量表达，能区分 60° 和 300°（避免余弦约束歧义）。
    ccw 方向由 ArcObj.ccw 字段决定；这里 value 是按 arc.ccw 方向张的角度。
    """
    type: Literal["arc_angle"]
    arc: str        # ArcObj id
    value: float    # 度数 (0, 360)


class ArcLengthC(_C):
    """圆弧的弧长约束 (V2-G.2)。

    约束 arc 的弧长为 value（与单位坐标一致）。
    弧长 = 半径 × 圆心角（弧度）。
    """
    type: Literal["arc_length"]
    arc: str
    value: float    # > 0


class BowAreaC(_C):
    """弓形面积约束 (V2-G.2)。

    弓形 = 弧 + 弦围成的区域。
    面积公式：0.5 × r² × (θ - sin θ)，其中 θ 是圆心角（弧度）。
    value > 0。
    """
    type: Literal["bow_area"]
    arc: str
    value: float    # > 0


Constraint = Annotated[
    Union[
        LengthC, EqualLengthC, AngleC,
        ParallelC, PerpendicularC, CollinearC,
        TangentC, OnCircleC,
        IsocelesC, EquilateralC, RightTriangleC,
        RadiusC,
        MidpointC, FootOfPerpC, AngleBisectorC, ConcyclicC, ParallelogramC,
        SameSideC, OppositeSideC,
        OnCurveC,
        RegularPolygonC, TrapezoidC,
        ArcAngleC, ArcLengthC, BowAreaC,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Annotations & Style
# ---------------------------------------------------------------------------

class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str               # object id (segment / angle pseudo-id "angleABC" / circle…)
    kind: Literal["length", "angle", "label", "radius", "arc_length", "bow_area"]
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

    def arcs(self) -> list[ArcObj]:
        return [o for o in self.objects if isinstance(o, ArcObj)]

    def sectors(self) -> list[SectorObj]:
        return [o for o in self.objects if isinstance(o, SectorObj)]

    def bows(self) -> list[BowObj]:
        return [o for o in self.objects if isinstance(o, BowObj)]

    def annular_sectors(self) -> list[AnnularSectorObj]:
        return [o for o in self.objects if isinstance(o, AnnularSectorObj)]

    def regions(self) -> list[RegionObj]:
        return [o for o in self.objects if isinstance(o, RegionObj)]

    def number_lines(self) -> list[NumberLineObj]:
        return [o for o in self.objects if isinstance(o, NumberLineObj)]

    def aux_lines(self) -> list[AuxLineObj]:
        return [o for o in self.objects if isinstance(o, AuxLineObj)]

    # V3.1 立体几何 helpers
    def cubes(self) -> list[CubeObj]:
        return [o for o in self.objects if isinstance(o, CubeObj)]

    def cuboids(self) -> list[CuboidObj]:
        return [o for o in self.objects if isinstance(o, CuboidObj)]

    def cylinders(self) -> list[CylinderObj]:
        return [o for o in self.objects if isinstance(o, CylinderObj)]

    def cones(self) -> list[ConeObj]:
        return [o for o in self.objects if isinstance(o, ConeObj)]

    def spheres(self) -> list[SphereObj]:
        return [o for o in self.objects if isinstance(o, SphereObj)]

    # V3.2 统计图表 helpers
    def bar_charts(self) -> list[BarChartObj]:
        return [o for o in self.objects if isinstance(o, BarChartObj)]

    def line_charts(self) -> list[LineChartObj]:
        return [o for o in self.objects if isinstance(o, LineChartObj)]

    def pie_charts(self) -> list[PieChartObj]:
        return [o for o in self.objects if isinstance(o, PieChartObj)]

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
