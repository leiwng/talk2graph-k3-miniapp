"""数值求解器：把 DSL 转成最小二乘问题。

W1 范围：支持所有 DSL v0.1 约束。符号求解（SymPy）作为 V2 加速。
策略：
1. 自由变量 = 每个 point 的 (x, y) + 每个"派生中心"圆的 (cx, cy, r)
2. Gauge fixing：固定第一点在原点；若 ≥ 2 点，第二点在 +x 轴上
3. 约束 → 残差函数；scipy.optimize.least_squares 求解
4. 多初值随机重启，取残差最小者
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import least_squares

from ..dsl.safe_expr import compile_expr
from ..dsl.schema import (
    AxisObj,
    CentralSymSpec,
    CircleDefByCenterPoint,
    CircleDefByCenterRadius,
    CircleDefCircumcircle,
    CircleDefIncircle,
    CircleObj,
    DSL,
    FunctionCurveObj,
    LineObj,
    PointObj,
    PolygonObj,
    ReflectionSpec,
    RotationSpec,
    SegmentObj,
    TranslationSpec,
    TransformedPointObj,
    TransformedPolygonObj,
)


@dataclass
class Solution:
    coordinates: dict[str, tuple[float, float]]
    circles: dict[str, dict]  # circle id -> {center: (x,y), radius: r}
    residual: float
    method: str
    iterations: int


class SolveError(RuntimeError):
    pass


@dataclass
class _VarLayout:
    """变量布局：把所有自由变量打平成一维向量。"""
    point_idx: dict[str, int] = field(default_factory=dict)   # pid -> base offset (x at idx, y at idx+1)
    circle_idx: dict[str, int] = field(default_factory=dict)  # cid -> base offset (cx, cy, r)
    fixed: dict[str, tuple[float, float]] = field(default_factory=dict)  # pid -> fixed coords (gauge)
    n: int = 0

    def alloc_point(self, pid: str) -> None:
        self.point_idx[pid] = self.n
        self.n += 2

    def alloc_circle(self, cid: str) -> None:
        self.circle_idx[cid] = self.n
        self.n += 3

    def get_point(self, x: np.ndarray, pid: str) -> tuple[float, float]:
        if pid in self.fixed:
            return self.fixed[pid]
        i = self.point_idx[pid]
        return float(x[i]), float(x[i + 1])

    def get_circle(self, x: np.ndarray, cid: str) -> tuple[float, float, float]:
        i = self.circle_idx[cid]
        return float(x[i]), float(x[i + 1]), float(x[i + 2])


# ---------------------------------------------------------------------------
# Helpers (symbolic in numeric terms; operate on numpy floats/arrays)
# ---------------------------------------------------------------------------

def _vec(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
    return q[0] - p[0], q[1] - p[1]


def _norm(v: tuple[float, float]) -> float:
    return math.hypot(v[0], v[1])


def _dot(u: tuple[float, float], v: tuple[float, float]) -> float:
    return u[0] * v[0] + u[1] * v[1]


def _cross(u: tuple[float, float], v: tuple[float, float]) -> float:
    return u[0] * v[1] - u[1] * v[0]


def _line_direction(dsl: DSL, sid: str, x: np.ndarray, layout: _VarLayout) -> tuple[float, float]:
    obj = dsl.object_map()[sid]
    assert isinstance(obj, (SegmentObj, LineObj))
    pa = layout.get_point(x, obj.a)
    pb = layout.get_point(x, obj.b)
    return _vec(pa, pb)


def _point_line_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """点 p 到直线 ab 的有向距离的绝对值（数值稳定）。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L


def _signed_point_line_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return 0.0
    return ((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve(
    dsl: DSL,
    *,
    seed: int = 0,
    restarts: int = 6,
    restarts_extra: int = 20,
    tol: float = 1e-9,
) -> Solution:
    """求解 DSL 的所有约束。

    参数说明：
    - restarts：主循环重启次数（默认 6，API 层通常传 20）
    - restarts_extra：W13-A 自适应抢救阶段的额外重启次数（默认 20）
        当阶段 1 完成后，若最佳 cost ∈ (tol, 1e-2)，说明接近可行解但初值不佳，
        启动阶段 2 用多样化初值策略再抢救 restarts_extra 次。
    """
    points = dsl.points()
    if not points:
        return Solution({}, {}, 0.0, "trivial", 0)

    layout = _VarLayout()

    axis = dsl.axis()

    # Gauge 选择：
    # - 无 axis：第一点固定 (0,0)；第二点 y=0（消除平移 + 旋转的 3 个自由度，
    #   仅保留缩放/全局形状的合法变化），这是 W1 默认行为。
    # - 有 axis：origin 点固定 (0,0)，坐标系朝向由 axis 本身定义（+x 向右、+y 向上），
    #   不再加 second-y=0 约束；其余点全自由。
    if axis is not None:
        if axis.origin not in {p.id for p in points}:
            raise SolveError(f"axis origin {axis.origin!r} 不是已声明的点")
        layout.fixed[axis.origin] = (0.0, 0.0)
        second_pid: str | None = None
        for p in points:
            if p.id == axis.origin:
                continue
            layout.alloc_point(p.id)
    else:
        first = points[0].id
        layout.fixed[first] = (0.0, 0.0)
        second_pid = points[1].id if len(points) >= 2 else None
        for p in points:
            if p.id == first:
                continue
            layout.alloc_point(p.id)

    # 派生圆变量：center_radius / center_through 不需要新变量；incircle / circumcircle 需要 (cx,cy,r)
    for c in dsl.circles():
        d = c.definition
        if isinstance(d, (CircleDefIncircle, CircleDefCircumcircle)):
            layout.alloc_circle(c.id)

    # 构造残差函数
    residual_fns: list[Callable[[np.ndarray], list[float]]] = []

    # gauge：固定 second 点 y=0
    if second_pid is not None:
        i = layout.point_idx[second_pid]
        def _gauge_second(x: np.ndarray, _i: int = i) -> list[float]:
            return [x[_i + 1]]  # y = 0
        residual_fns.append(_gauge_second)

    obj_map = dsl.object_map()

    # ---- 约束 ----
    for c in dsl.constraints:
        residual_fns.append(_build_constraint_residual(c, dsl, layout))

    # ---- 圆定义对应的"绑定残差" ----
    for circle in dsl.circles():
        d = circle.definition
        if isinstance(d, CircleDefIncircle):
            residual_fns.append(_build_incircle_residual(circle, d.of, layout, dsl))
        elif isinstance(d, CircleDefCircumcircle):
            residual_fns.append(_build_circumcircle_residual(circle, d.of, layout, dsl))

    # ---- hint 软约束（用户拖动产生的目标位置，低权重） ----
    # W12: 独立记录 hint 残差数量，用于分离 "硬约束是否收敛" 与 "软 hint 偏差"
    HINT_WEIGHT = 0.05
    hint_residual_count = 0
    for p in points:
        if p.hint is None or p.id not in layout.point_idx:
            continue
        idx = layout.point_idx[p.id]
        hx, hy = p.hint
        def _hint(x: np.ndarray, _i: int = idx, _hx: float = hx, _hy: float = hy) -> list[float]:
            return [HINT_WEIGHT * (x[_i] - _hx), HINT_WEIGHT * (x[_i + 1] - _hy)]
        residual_fns.append(_hint)
        hint_residual_count += 2

    def residual_vec(x: np.ndarray) -> np.ndarray:
        out: list[float] = []
        for fn in residual_fns:
            out.extend(fn(x))
        return np.array(out, dtype=float)

    if layout.n == 0:
        # 全部点被 gauge 固定
        return _build_solution(np.zeros(0), dsl, layout)

    rng = random.Random(seed)
    best: tuple[float, np.ndarray, int] | None = None  # (cost, x, nit)

    def _initial_guess(strategy: str = "default") -> np.ndarray:
        """初值生成。strategy：
        - "default"：所有点 (-5, 5) 均匀，hint 覆盖
        - "narrow"：所有点 (-2, 2) 小范围
        - "wide"：所有点 (-15, 15) 大范围
        - "perturb_hint"：hint 附近扰动 ±2
        """
        x0 = np.zeros(layout.n)
        if strategy == "narrow":
            lo, hi = -2.0, 2.0
        elif strategy == "wide":
            lo, hi = -15.0, 15.0
        else:
            lo, hi = -5.0, 5.0
        for pid, idx in layout.point_idx.items():
            x0[idx] = rng.uniform(lo, hi)
            x0[idx + 1] = rng.uniform(lo, hi)
            obj = obj_map[pid]
            if isinstance(obj, PointObj) and obj.hint is not None:
                if strategy == "perturb_hint":
                    x0[idx] = obj.hint[0] + rng.uniform(-2, 2)
                    x0[idx + 1] = obj.hint[1] + rng.uniform(-2, 2)
                else:
                    x0[idx] = obj.hint[0]
                    x0[idx + 1] = obj.hint[1]
        for cid, idx in layout.circle_idx.items():
            x0[idx] = rng.uniform(-1, 1)
            x0[idx + 1] = rng.uniform(-1, 1)
            x0[idx + 2] = abs(rng.uniform(0.5, 3)) + 0.5
        return x0

    def _try_solve(x0):
        """跑一次 least_squares 并计算硬约束 cost。返回 (cost, x, nfev)。"""
        try:
            result = least_squares(
                residual_vec, x0, method="lm", xtol=1e-12, ftol=1e-12, max_nfev=2000
            )
        except ValueError:
            result = least_squares(
                residual_vec, x0, method="trf", xtol=1e-12, ftol=1e-12, max_nfev=2000
            )
        full_res = residual_vec(result.x)
        if hint_residual_count > 0 and len(full_res) >= hint_residual_count:
            hard_res = full_res[: len(full_res) - hint_residual_count]
        else:
            hard_res = full_res
        cost = float((hard_res ** 2).sum())
        return cost, result.x, int(result.nfev)

    # ---------- 阶段 1：主 restarts 循环 ----------
    for attempt in range(restarts):
        x0 = _initial_guess("default")
        cost, x_sol, nfev = _try_solve(x0)
        if best is None or cost < best[0]:
            best = (cost, x_sol, nfev)
        if cost < tol:
            break

    # ---------- W13-A 阶段 2：自适应抢救 ----------
    # 若最佳 cost 在 (tol, 1e-2) 之间，说明接近可行解但初值不佳，
    # 用多样化策略再跑 restarts_extra 次
    STRATEGIES = ["narrow", "perturb_hint", "wide", "default"]
    assert best is not None
    if best[0] > tol and best[0] < 1e-2 and restarts_extra > 0:
        for extra_attempt in range(restarts_extra):
            strategy = STRATEGIES[extra_attempt % len(STRATEGIES)]
            x0 = _initial_guess(strategy)
            cost, x_sol, nfev = _try_solve(x0)
            if cost < best[0]:
                best = (cost, x_sol, nfev)
            if cost < tol:
                break

    assert best is not None
    cost, x_sol, nit = best
    if cost > 1e-4:
        raise SolveError(
            f"solver failed to converge (residual={cost:.3e}); "
            "约束可能不一致或欠定。"
        )
    return _build_solution(x_sol, dsl, layout, residual=cost, iterations=nit)


# ---------------------------------------------------------------------------
# Constraint residual builders
# ---------------------------------------------------------------------------

def _build_constraint_residual(c, dsl: DSL, L: _VarLayout) -> Callable:
    obj_map = dsl.object_map()
    t = c.type

    if t == "length":
        seg = obj_map[c.segment]
        assert isinstance(seg, SegmentObj)
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, seg.a)
            pb = L.get_point(x, seg.b)
            return [_norm(_vec(pa, pb)) - c.value]
        return f

    if t == "equal_length":
        segs = [obj_map[s] for s in c.segments]
        def f(x: np.ndarray) -> list[float]:
            lens = []
            for s in segs:
                pa = L.get_point(x, s.a); pb = L.get_point(x, s.b)
                lens.append(_norm(_vec(pa, pb)))
            return [lens[i] - lens[0] for i in range(1, len(lens))]
        return f

    if t == "angle":
        target_rad = math.radians(c.value)
        cos_target = math.cos(target_rad)
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, c.a)
            pb = L.get_point(x, c.b)
            pc = L.get_point(x, c.c)
            ba = _vec(pb, pa); bc = _vec(pb, pc)
            la = _norm(ba); lc = _norm(bc)
            if la < 1e-9 or lc < 1e-9:
                return [1e3]
            cos_v = _dot(ba, bc) / (la * lc)
            return [cos_v - cos_target]
        return f

    if t == "parallel":
        def f(x: np.ndarray) -> list[float]:
            u = _line_direction(dsl, c.a, x, L)
            v = _line_direction(dsl, c.b, x, L)
            # 归一化叉积 — 避免长度量纲影响
            lu = _norm(u); lv = _norm(v)
            if lu < 1e-9 or lv < 1e-9:
                return [0.0]
            return [_cross(u, v) / (lu * lv)]
        return f

    if t == "perpendicular":
        def f(x: np.ndarray) -> list[float]:
            u = _line_direction(dsl, c.a, x, L)
            v = _line_direction(dsl, c.b, x, L)
            lu = _norm(u); lv = _norm(v)
            if lu < 1e-9 or lv < 1e-9:
                return [0.0]
            return [_dot(u, v) / (lu * lv)]
        return f

    if t == "collinear":
        pids = c.points
        def f(x: np.ndarray) -> list[float]:
            p0 = L.get_point(x, pids[0])
            p1 = L.get_point(x, pids[1])
            out = []
            for k in range(2, len(pids)):
                pk = L.get_point(x, pids[k])
                out.append(_cross(_vec(p0, p1), _vec(p0, pk)))
            return out
        return f

    if t == "tangent":
        line_obj = obj_map[c.line]
        circle = obj_map[c.circle]
        assert isinstance(circle, CircleObj)
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, line_obj.a)
            pb = L.get_point(x, line_obj.b)
            cx, cy, r = _circle_geometry(circle, x, L, dsl)
            d = _point_line_distance((cx, cy), pa, pb)
            return [d - r]
        return f

    if t == "on_circle":
        circle = obj_map[c.circle]
        assert isinstance(circle, CircleObj)
        def f(x: np.ndarray) -> list[float]:
            p = L.get_point(x, c.point)
            cx, cy, r = _circle_geometry(circle, x, L, dsl)
            return [math.hypot(p[0] - cx, p[1] - cy) - r]
        return f

    if t == "isoceles":
        poly = obj_map[c.polygon]
        assert isinstance(poly, PolygonObj)
        # 顶角顶点到两腰另一端等距
        apex = c.apex
        others = [v for v in poly.vertices if v != apex]
        if len(others) < 2:
            return lambda x: []
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, apex)
            d = [_norm(_vec(pa, L.get_point(x, v))) for v in others]
            return [d[i] - d[0] for i in range(1, len(d))]
        return f

    if t == "equilateral":
        poly = obj_map[c.polygon]
        assert isinstance(poly, PolygonObj)
        v = poly.vertices
        def f(x: np.ndarray) -> list[float]:
            p = [L.get_point(x, vid) for vid in v]
            d01 = _norm(_vec(p[0], p[1]))
            d12 = _norm(_vec(p[1], p[2]))
            d20 = _norm(_vec(p[2], p[0]))
            return [d01 - d12, d12 - d20]
        return f

    if t == "right_triangle":
        ra = c.right_at
        poly = obj_map[c.polygon]
        assert isinstance(poly, PolygonObj)
        others = [v for v in poly.vertices if v != ra]
        def f(x: np.ndarray) -> list[float]:
            pr = L.get_point(x, ra)
            u = _vec(pr, L.get_point(x, others[0]))
            v = _vec(pr, L.get_point(x, others[1]))
            lu = _norm(u); lv = _norm(v)
            if lu < 1e-9 or lv < 1e-9:
                return [0.0]
            return [_dot(u, v) / (lu * lv)]
        return f

    if t == "radius":
        circle = obj_map[c.circle]
        assert isinstance(circle, CircleObj)
        def f(x: np.ndarray) -> list[float]:
            cx, cy, r = _circle_geometry(circle, x, L, dsl)
            return [r - c.value]
        return f

    if t == "midpoint":
        def f(x: np.ndarray) -> list[float]:
            pm = L.get_point(x, c.m)
            pa = L.get_point(x, c.a)
            pb = L.get_point(x, c.b)
            return [
                pm[0] - (pa[0] + pb[0]) / 2.0,
                pm[1] - (pa[1] + pb[1]) / 2.0,
            ]
        return f

    if t == "foot_of_perp":
        def f(x: np.ndarray) -> list[float]:
            pf = L.get_point(x, c.f)
            pp = L.get_point(x, c.p)
            pa = L.get_point(x, c.a)
            pb = L.get_point(x, c.b)
            ab = _vec(pa, pb)
            ap = _vec(pa, pp)
            l2 = _dot(ab, ab)
            if l2 < 1e-12:
                return [pf[0] - pa[0], pf[1] - pa[1]]
            t_param = _dot(ap, ab) / l2
            fx = pa[0] + t_param * ab[0]
            fy = pa[1] + t_param * ab[1]
            return [pf[0] - fx, pf[1] - fy]
        return f

    if t == "angle_bisector":
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, c.a)
            pb = L.get_point(x, c.b)
            pc = L.get_point(x, c.c)
            pd = L.get_point(x, c.d)
            ba = _vec(pb, pa); bc = _vec(pb, pc); bd = _vec(pb, pd)
            la = _norm(ba); lc = _norm(bc); ld = _norm(bd)
            if la < 1e-9 or lc < 1e-9 or ld < 1e-9:
                return [0.0]
            cos_ad = (ba[0]*bd[0] + ba[1]*bd[1]) / (la * ld)
            cos_cd = (bc[0]*bd[0] + bc[1]*bd[1]) / (lc * ld)
            return [cos_ad - cos_cd]
        return f

    if t == "concyclic":
        pts = c.points
        # 共圆 = 任三点确定的外接圆经过所有其他点
        # 残差：每对 (p_i, p_0) 到 (p1, p_0) 的圆心距相等。
        # 实际更稳：直接用四点行列式 = 0
        def f(x: np.ndarray) -> list[float]:
            coords = [L.get_point(x, p) for p in pts]
            out = []
            # 取前三点定圆，其他点检查在圆上
            (x1, y1), (x2, y2), (x3, y3) = coords[0], coords[1], coords[2]
            # 圆心：解 |P-C|^2 相等
            # 方程：2(x2-x1)cx + 2(y2-y1)cy = (x2^2+y2^2 - x1^2 - y1^2)
            #       2(x3-x1)cx + 2(y3-y1)cy = (x3^2+y3^2 - x1^2 - y1^2)
            a1 = 2 * (x2 - x1); b1 = 2 * (y2 - y1)
            c1 = x2 * x2 + y2 * y2 - x1 * x1 - y1 * y1
            a2 = 2 * (x3 - x1); b2 = 2 * (y3 - y1)
            c2 = x3 * x3 + y3 * y3 - x1 * x1 - y1 * y1
            det = a1 * b2 - a2 * b1
            if abs(det) < 1e-9:
                return [1e3] * (len(pts) - 3)
            cx = (c1 * b2 - c2 * b1) / det
            cy = (a1 * c2 - a2 * c1) / det
            r2 = (x1 - cx) ** 2 + (y1 - cy) ** 2
            for k in range(3, len(pts)):
                xk, yk = coords[k]
                out.append((xk - cx) ** 2 + (yk - cy) ** 2 - r2)
            return out
        return f

    if t == "parallelogram":
        poly = obj_map[c.polygon]
        assert isinstance(poly, PolygonObj)
        v = poly.vertices  # [A, B, C, D]
        # AB 与 DC 同向且等长 → 等价于 A + C == B + D
        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, v[0])
            pb = L.get_point(x, v[1])
            pc = L.get_point(x, v[2])
            pd = L.get_point(x, v[3])
            return [
                pa[0] + pc[0] - pb[0] - pd[0],
                pa[1] + pc[1] - pb[1] - pd[1],
            ]
        return f

    if t in ("same_side", "opposite_side"):
        # 不等式软约束：要求 point 与 ref 在 line 的同侧（或异侧）
        # 残差：max(0, margin - sign * sd_p * sd_r) * weight
        # sign = +1 (same_side) / -1 (opposite_side)
        line_obj = obj_map[c.line]
        assert isinstance(line_obj, (SegmentObj, LineObj))
        sign = 1.0 if t == "same_side" else -1.0
        margin = 0.1
        weight = 5.0

        def f(x: np.ndarray) -> list[float]:
            pa = L.get_point(x, line_obj.a)
            pb = L.get_point(x, line_obj.b)
            pp = L.get_point(x, c.point)
            pr = L.get_point(x, c.ref)
            sd_p = _signed_point_line_distance(pp, pa, pb)
            sd_r = _signed_point_line_distance(pr, pa, pb)
            product = sign * sd_p * sd_r
            # 若违反（product < margin），输出非零残差；否则 0
            violation = margin - product
            return [max(0.0, violation) * weight]
        return f

    if t == "on_curve":
        # 点在函数曲线上：curve.var == "x" 时约束 y - f(x) = 0；var == "y" 时约束 x - g(y) = 0
        # W12：权重放大 10x，压制 hint 软约束的 0.05 拉扯，让点精确落到曲线上
        curve = obj_map[c.curve]
        assert isinstance(curve, FunctionCurveObj)
        var = curve.var
        try:
            fn = compile_expr(curve.expr, var=var)
        except Exception:
            # validator 已保证合法；此处兜底返回无残差
            return lambda x: []
        weight = 10.0

        def f(x: np.ndarray) -> list[float]:
            px, py = L.get_point(x, c.point)
            if var == "x":
                y_pred = fn(px)
                if y_pred != y_pred or y_pred == float("inf") or y_pred == float("-inf"):
                    # 表达式无定义（如 log(-1) 或 1/0）→ 大残差把点推离
                    return [1e3]
                return [(py - y_pred) * weight]
            else:
                x_pred = fn(py)
                if x_pred != x_pred or x_pred == float("inf") or x_pred == float("-inf"):
                    return [1e3]
                return [(px - x_pred) * weight]
        return f

    raise NotImplementedError(f"constraint type {t}")


def _circle_geometry(
    circle: CircleObj, x: np.ndarray, L: _VarLayout, dsl: DSL
) -> tuple[float, float, float]:
    d = circle.definition
    if isinstance(d, CircleDefByCenterRadius):
        cx, cy = L.get_point(x, d.center)
        return cx, cy, d.radius
    if isinstance(d, CircleDefByCenterPoint):
        cx, cy = L.get_point(x, d.center)
        px, py = L.get_point(x, d.through)
        return cx, cy, math.hypot(px - cx, py - cy)
    # incircle / circumcircle 用派生变量
    return L.get_circle(x, circle.id)


def _build_incircle_residual(circle: CircleObj, poly_id: str, L: _VarLayout, dsl: DSL) -> Callable:
    poly = dsl.object_map()[poly_id]
    assert isinstance(poly, PolygonObj)
    verts = poly.vertices
    n = len(verts)

    def f(x: np.ndarray) -> list[float]:
        cx, cy, r = L.get_circle(x, circle.id)
        out = []
        # 圆心到各边距离 = r，且圆心在多边形内部（用有向距离同号）
        pts = [L.get_point(x, v) for v in verts]
        signs = []
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            sd = _signed_point_line_distance((cx, cy), a, b)
            signs.append(sd)
            out.append(abs(sd) - r)
        # 鼓励所有 signs 同号（差异作为软残差）
        s0 = signs[0]
        for k in range(1, n):
            # 若异号，乘以一个小权重把它拉回来
            if s0 * signs[k] < 0:
                out.append(0.1 * (signs[k] - s0))
        return out

    return f


def _build_circumcircle_residual(circle: CircleObj, poly_id: str, L: _VarLayout, dsl: DSL) -> Callable:
    poly = dsl.object_map()[poly_id]
    assert isinstance(poly, PolygonObj)
    verts = poly.vertices

    def f(x: np.ndarray) -> list[float]:
        cx, cy, r = L.get_circle(x, circle.id)
        out = []
        for v in verts:
            px, py = L.get_point(x, v)
            out.append(math.hypot(px - cx, py - cy) - r)
        return out

    return f


def _build_solution(
    x: np.ndarray, dsl: DSL, L: _VarLayout, *, residual: float = 0.0, iterations: int = 0
) -> Solution:
    coords: dict[str, tuple[float, float]] = {}
    for p in dsl.points():
        coords[p.id] = L.get_point(x, p.id)

    circles: dict[str, dict] = {}
    for c in dsl.circles():
        cx, cy, r = _circle_geometry(c, x, L, dsl)
        circles[c.id] = {"center": (cx, cy), "radius": r}

    # W11：派生对象坐标 = 源坐标经变换（后处理，不参与求解）
    _apply_derived_objects(dsl, coords)
    return Solution(coords, circles, residual, "numeric", iterations)


# ---------------------------------------------------------------------------
# W11 · 几何变换：数学函数 + 派生对象后处理
# ---------------------------------------------------------------------------

def apply_transform(
    transform,
    p: tuple[float, float],
    *,
    coords: dict[str, tuple[float, float]] | None = None,
    line_endpoints: tuple[tuple[float, float], tuple[float, float]] | None = None,
) -> tuple[float, float]:
    """把点 p 经 transform 变换后的坐标返回。

    - rotation / central_symmetry：需要 coords 里能查到 transform.center
    - reflection：需要显式传入 line_endpoints=((ax, ay), (bx, by))
    - translation：无需外部依赖
    """
    if isinstance(transform, RotationSpec):
        if coords is None or transform.center not in coords:
            raise ValueError(f"rotation: center {transform.center!r} not in coords")
        cx, cy = coords[transform.center]
        theta = math.radians(transform.angle)
        cos_t = math.cos(theta); sin_t = math.sin(theta)
        dx, dy = p[0] - cx, p[1] - cy
        return (cx + cos_t * dx - sin_t * dy, cy + sin_t * dx + cos_t * dy)
    if isinstance(transform, TranslationSpec):
        return (p[0] + transform.dx, p[1] + transform.dy)
    if isinstance(transform, CentralSymSpec):
        if coords is None or transform.center not in coords:
            raise ValueError(f"central_symmetry: center {transform.center!r} not in coords")
        cx, cy = coords[transform.center]
        return (2 * cx - p[0], 2 * cy - p[1])
    if isinstance(transform, ReflectionSpec):
        if line_endpoints is None:
            raise ValueError("reflection: line_endpoints must be provided")
        (ax, ay), (bx, by) = line_endpoints
        dx, dy = bx - ax, by - ay
        Ld = math.hypot(dx, dy)
        if Ld < 1e-12:
            return p
        ux, uy = dx / Ld, dy / Ld
        nx, ny = -uy, ux
        d = (p[0] - ax) * nx + (p[1] - ay) * ny
        return (p[0] - 2 * d * nx, p[1] - 2 * d * ny)
    raise NotImplementedError(f"unknown transform: {type(transform).__name__}")


def _apply_derived_objects(dsl: DSL, coords: dict[str, tuple[float, float]]) -> None:
    """把 TransformedPointObj / TransformedPolygonObj 的坐标算出并注入 coords。"""

    def line_endpoints(line_id: str):
        obj = dsl.object_map().get(line_id)
        if isinstance(obj, (SegmentObj, LineObj)):
            if obj.a in coords and obj.b in coords:
                return coords[obj.a], coords[obj.b]
        return None

    def _apply(transform, p):
        ep = None
        if isinstance(transform, ReflectionSpec):
            ep = line_endpoints(transform.line)
            if ep is None:
                return p  # 静默降级：line 未就绪
        return apply_transform(transform, p, coords=coords, line_endpoints=ep)

    obj_map = dsl.object_map()
    for o in dsl.transformed_points():
        src = obj_map.get(o.source)
        if isinstance(src, PointObj) and src.id in coords:
            coords[o.id] = _apply(o.transform, coords[src.id])

    for o in dsl.transformed_polygons():
        src = obj_map.get(o.source)
        if not isinstance(src, PolygonObj):
            continue
        for v in src.vertices:
            if v in coords:
                derived_id = f"{v}_{o.vertex_suffix}"
                coords[derived_id] = _apply(o.transform, coords[v])
