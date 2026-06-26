"""按测试数据集跑一轮评估。

注意：
- 话图 T2G MVP 只支持初中平面几何
- 函数图像 / 坐标系 / 统计图表属于 V2 范围，预期会失败（用以下标记区分）
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.config import settings
from app.dsl import DSL, apply_patch
from app.llm.extractor import extract_dsl
from app.llm.router import LLMRouter
from app.render import render_svg
from app.solver import SolveError, solve

# ---- 全部 38 题 ----
Category = Literal["geometry", "function", "coord", "chart", "multi-round"]


@dataclass
class Case:
    no: int
    nl: str
    difficulty: str             # ⭐ / ⭐⭐ / ⭐⭐⭐
    category: Category
    expected: Literal["pass", "best-effort", "unsupported"]
    # 多轮：第二轮指令
    nl_round2: str | None = None


CASES: list[Case] = [
    # ----- 一、几何图形 -----
    Case(1,  "画一个直角三角形，两条直角边分别是 3 和 4",                 "⭐",   "geometry", "pass"),
    Case(2,  "画一个等边三角形，边长 5cm",                                "⭐",   "geometry", "pass"),
    Case(3,  "画一个正方形，边长 4cm",                                    "⭐",   "geometry", "pass"),
    Case(4,  "画一个圆，半径 3cm，标注圆心",                              "⭐",   "geometry", "pass"),
    Case(5,  "画一个等腰三角形，底边长 6cm，腰长 5cm",                    "⭐",   "geometry", "pass"),
    Case(6,  "画直角三角形，直角边 3 和 4，标出三条边的边长和直角标记",   "⭐⭐", "geometry", "pass"),
    Case(7,  "画一个底角为 30° 的等腰三角形，腰长 5cm，标出顶角和底角",   "⭐⭐", "geometry", "pass"),
    Case(8,  "画一个圆，内接一个正六边形，标注圆心",                      "⭐⭐", "geometry", "best-effort"),
    Case(9,  "画一个平行四边形，相邻两边分别为 4cm 和 3cm，夹角 60°",     "⭐⭐", "geometry", "pass"),
    Case(10, "画直角梯形，上底 3cm，下底 5cm，高 4cm",                    "⭐⭐", "geometry", "pass"),
    Case(11, "画一个三角形，已知 AB=5，BC=6，AC=7，标出各边长度",         "⭐⭐⭐","geometry", "pass"),
    Case(12, "画直角三角形的内切圆，直角边分别为 3 和 4，标出内切圆圆心和半径", "⭐⭐⭐","geometry", "pass"),
    Case(13, "画两个相交的圆，半径分别为 3cm 和 4cm，圆心距 5cm，标注两个交点和圆心", "⭐⭐⭐","geometry", "best-effort"),
    Case(14, "画一个正五边形，边长 3cm，标出所有顶点",                    "⭐⭐⭐","geometry", "best-effort"),
    Case(15, "画一个三角形 ABC，在 AB 边上取中点 D，连接 CD，标注 D 和中线","⭐⭐⭐","geometry", "pass"),

    # ----- 二、函数图像（V2 范围） -----
    Case(16, "画 y = 2x + 1 的图像，在 -5 到 5 范围内",                   "⭐",   "function", "unsupported"),
    Case(17, "画 y = x² 的图像，在 -3 到 3 范围内",                       "⭐",   "function", "unsupported"),
    Case(18, "画 y = sin(x) 的图像，在 -2π 到 2π 范围内",                 "⭐",   "function", "unsupported"),
    Case(19, "在同一个坐标系中画 y = x² 和 y = 2x + 1，-3 到 3 范围，用不同颜色区分", "⭐⭐", "function", "unsupported"),
    Case(20, "画 y = sin(x) 和 y = cos(x)，-2π 到 2π，用蓝色和红色区分",  "⭐⭐", "function", "unsupported"),
    Case(21, "画 y = log₂(x) 的图像，1/4 到 8 范围，标注关键点 (1,0) (2,1) (4,2)", "⭐⭐", "function", "unsupported"),
    Case(22, "画 y = x³ - 3x，-3 到 3，标注极值点和零点",                 "⭐⭐⭐","function", "unsupported"),
    Case(23, "画分段函数：x<0 时 y=x²，x≥0 时 y=2x，用不同颜色标注两段", "⭐⭐⭐","function", "unsupported"),
    Case(24, "画参数方程绘制的椭圆：x=3cos(t), y=2sin(t)，t 从 0 到 2π", "⭐⭐⭐","function", "unsupported"),

    # ----- 三、坐标系与几何综合 -----
    Case(25, "在坐标系中画点 A(2,3), B(5,1), C(1,1)，连接成三角形",      "⭐",   "coord", "best-effort"),
    Case(26, "画点 A(1,2), B(5,6)，连接 AB，标出线段中点坐标",            "⭐⭐", "coord", "best-effort"),
    Case(27, "在坐标系中画以原点为圆心、半径为 5 的圆，标出与坐标轴的四个交点", "⭐⭐", "coord", "best-effort"),
    Case(28, "画 △ABC，A(0,0), B(4,0), C(2,3)，给出三边中垂线，标出外心","⭐⭐⭐","coord", "best-effort"),
    Case(29, "画抛物线 y=x² 和圆 x²+y²=4，标出交点区域",                  "⭐⭐⭐","coord", "unsupported"),
    Case(30, "画点 A(2,3) 关于直线 y=x 的对称点 A'，标出对称轴和两个点", "⭐⭐⭐","coord", "best-effort"),

    # ----- 四、统计图表（V2 范围） -----
    Case(31, "画一个柱状图：一班 85 分，二班 78 分，三班 92 分，四班 80 分", "⭐", "chart", "unsupported"),
    Case(32, "画一个饼图：优秀 30%，良好 45%，及格 20%，不及格 5%",      "⭐", "chart", "unsupported"),
    Case(33, "画频率分布直方图：区间 [0,10):5, [10,20):12, [20,30):20, [30,40):10, [40,50):3", "⭐⭐", "chart", "unsupported"),

    # ----- 五、多轮修改 -----
    Case(34, "画一个直角三角形，直角边 3 和 4", "⭐⭐⭐", "multi-round", "pass",
         nl_round2="去掉边长的标注，加一条斜边上的高"),
    Case(35, "画 y=x² 和 y=2x+1 在同一个坐标系", "⭐⭐⭐", "multi-round", "unsupported",
         nl_round2="把 x² 改成红色，2x+1 改成虚线蓝色"),
    Case(36, "画等腰三角形，底 6cm，腰 5cm", "⭐⭐⭐", "multi-round", "pass",
         nl_round2="不标边长，改标三个角的度数"),
    Case(37, "画一个圆，内接正六边形", "⭐⭐⭐", "multi-round", "best-effort",
         nl_round2="把六边形改成正八边形，其他不变"),
    Case(38, "画 y=sin(x)，-2π 到 2π", "⭐⭐⭐", "multi-round", "unsupported",
         nl_round2="只保留第一象限的部分（0 到 π/2），其他不要"),
]


@dataclass
class Result:
    no: int
    nl: str
    difficulty: str
    category: str
    expected: str
    status: str  # ok / extract_fail / patch_fail / solve_fail / unsupported_detected
    provider: str = ""
    attempts: int = 0
    objects: int = 0
    constraints: int = 0
    residual: float = float("nan")
    latency_ms: int = 0
    svg_bytes: int = 0
    error: str = ""
    # 多轮
    round2_status: str = ""
    round2_objects: int = 0
    round2_constraints: int = 0


async def run_single(provider, case: Case, save_dir: Path) -> Result:
    r = Result(case.no, case.nl, case.difficulty, case.category, case.expected, "")
    t0 = time.perf_counter()
    try:
        ext = await extract_dsl(provider, case.nl)
    except Exception as e:
        r.status = "extract_fail"; r.error = str(e)[:200]
        return r

    r.provider = ext.provider
    r.attempts = ext.attempts

    if ext.error:
        r.status = "llm_error"
        r.error = ext.error
        return r

    if ext.dsl is None:
        r.status = "no_dsl"
        r.error = (ext.error or "no dsl extracted")[:200]
        return r

    dsl = ext.dsl
    r.objects = len(dsl.objects)
    r.constraints = len(dsl.constraints)

    try:
        sol = solve(dsl, seed=1, restarts=20)
    except SolveError as e:
        r.status = "solve_fail"; r.error = str(e)[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.residual = float(sol.residual)
    try:
        svg = render_svg(dsl, sol)
        r.svg_bytes = len(svg)
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / f"case_{case.no:02d}.svg").write_text(svg, encoding="utf-8")
    except Exception as e:
        r.status = "render_fail"; r.error = str(e)[:200]
        return r

    # 多轮第二轮
    if case.nl_round2:
        try:
            ext2 = await extract_dsl(provider, case.nl_round2, current_dsl=dsl)
        except Exception as e:
            r.round2_status = f"extract_fail: {e}"[:120]
        else:
            if ext2.error:
                r.round2_status = f"llm_error: {ext2.error[:80]}"
            elif ext2.patch:
                try:
                    dsl2 = apply_patch(dsl, ext2.patch)
                    sol2 = solve(dsl2, seed=2, restarts=20)
                    svg2 = render_svg(dsl2, sol2)
                    (save_dir / f"case_{case.no:02d}_r2.svg").write_text(svg2, encoding="utf-8")
                    r.round2_objects = len(dsl2.objects)
                    r.round2_constraints = len(dsl2.constraints)
                    r.round2_status = (
                        f"ok patch ({len(ext2.patch.get('ops', []))} ops, res={sol2.residual:.1e})"
                    )
                except Exception as e:
                    r.round2_status = f"patch/solve fail: {str(e)[:80]}"
            elif ext2.dsl:
                try:
                    sol2 = solve(ext2.dsl, seed=2, restarts=20)
                    svg2 = render_svg(ext2.dsl, sol2)
                    (save_dir / f"case_{case.no:02d}_r2.svg").write_text(svg2, encoding="utf-8")
                    r.round2_objects = len(ext2.dsl.objects)
                    r.round2_constraints = len(ext2.dsl.constraints)
                    r.round2_status = f"ok full-dsl (res={sol2.residual:.1e})"
                except Exception as e:
                    r.round2_status = f"solve fail: {str(e)[:80]}"

    r.latency_ms = int((time.perf_counter() - t0) * 1000)
    r.status = "ok"
    return r


async def main():
    router = LLMRouter()
    provider = router.get()  # 用默认 provider
    print(f"# 评估开始：default provider = {provider.name}, model = {provider.model}")
    print(f"# 共 {len(CASES)} 题\n")

    save_dir = Path("test/results/svgs")
    results: list[Result] = []
    sem = asyncio.Semaphore(3)   # 并发 3

    async def _run(c):
        async with sem:
            r = await run_single(provider, c, save_dir)
            mark = {
                "ok": "✅",
                "solve_fail": "🔴",
                "no_dsl": "🔴",
                "extract_fail": "🔴",
                "render_fail": "🔴",
                "llm_error": "⚠️ ",
            }.get(r.status, "⚠️ ")
            r2 = f" | r2={r.round2_status}" if r.nl else ""
            r2 = f" | r2={r.round2_status}" if (CASES[c.no - 1].nl_round2) else ""
            extra = (
                f"obj={r.objects} con={r.constraints} res={r.residual:.1e} "
                f"svg={r.svg_bytes}B {r.latency_ms}ms"
                if r.status == "ok" else r.error[:80]
            )
            print(f"  {mark} #{c.no:2d} [{c.difficulty:>4}] [{c.category:11}] "
                  f"[exp={c.expected:11}] {r.status:14s}  {extra}{r2}")
            return r

    tasks = [_run(c) for c in CASES]
    results = await asyncio.gather(*tasks)

    # 报告
    Path("test/results").mkdir(parents=True, exist_ok=True)
    _write_report(results, provider)


def _write_report(results: list[Result], provider) -> None:
    by_cat: dict[str, list[Result]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    lines = []
    lines.append(f"# 话图 T2G 评估报告")
    lines.append("")
    lines.append(f"- **Provider**：{provider.name} / {provider.model}")
    lines.append(f"- **Base URL**：{provider.base_url}")
    lines.append(f"- **测试用例数**：{len(results)}")
    n_ok = sum(1 for r in results if r.status == "ok")
    lines.append(f"- **求解成功**：{n_ok} / {len(results)}（{n_ok/len(results)*100:.1f}%）")
    lines.append("")

    # 分类统计
    lines.append("## 分类通过率")
    lines.append("")
    lines.append("| 类别 | 总数 | OK | 通过率 | 平均残差 | 平均延迟 |")
    lines.append("|---|---|---|---|---|---|")
    cat_zh = {
        "geometry": "几何图形（MVP 范围）",
        "function": "函数图像（V2）",
        "coord": "坐标系几何",
        "chart": "统计图表（V2）",
        "multi-round": "多轮修改",
    }
    for cat in ["geometry", "coord", "multi-round", "function", "chart"]:
        items = by_cat.get(cat, [])
        if not items:
            continue
        oks = [r for r in items if r.status == "ok"]
        avg_res = sum(r.residual for r in oks) / len(oks) if oks else float("nan")
        avg_lat = sum(r.latency_ms for r in oks) / len(oks) if oks else 0
        lines.append(
            f"| {cat_zh.get(cat, cat)} | {len(items)} | {len(oks)} | "
            f"{len(oks)/len(items)*100:.0f}% | "
            f"{avg_res:.1e} | {int(avg_lat)}ms |"
        )
    lines.append("")

    # 详细
    lines.append("## 详细结果")
    lines.append("")
    lines.append("| # | 难度 | 类别 | 期望 | 状态 | 求解 | 对象 | 约束 | 残差 | 延迟 | 多轮 | 错误 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: x.no):
        status_icon = "✅" if r.status == "ok" else "🔴" if "fail" in r.status else "⚠️"
        res_str = f"{r.residual:.1e}" if r.status == "ok" else "—"
        lat_str = f"{r.latency_ms}ms" if r.status == "ok" else "—"
        r2 = r.round2_status[:50] if r.round2_status else "—"
        err = r.error[:60] if r.error else "—"
        lines.append(
            f"| {r.no} | {r.difficulty} | {r.category} | {r.expected} | "
            f"{status_icon} {r.status} | "
            f"{'通过' if r.status=='ok' else '—'} | "
            f"{r.objects or '—'} | {r.constraints or '—'} | "
            f"{res_str} | {lat_str} | {r2} | {err} |"
        )
    lines.append("")

    # SVG 文件清单
    lines.append("## 渲染产物")
    lines.append("")
    lines.append("成功用例的 SVG 文件保存在 `test/results/svgs/`：")
    for r in sorted(results, key=lambda x: x.no):
        if r.status == "ok":
            note = " + 第二轮" if r.round2_status.startswith("ok") else ""
            lines.append(f"- `case_{r.no:02d}.svg`{note} — {r.nl[:40]}")

    out = Path("test/results/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已写入 {out}")


if __name__ == "__main__":
    asyncio.run(main())
