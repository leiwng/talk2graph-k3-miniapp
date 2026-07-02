"""成都近5年真题精选测试 runner

跑 backend/test/chengdu/chengdu_selected.json，测试话图对**真实**试题的处理能力。

用法：
  .venv/bin/python scripts/eval_chengdu.py
  .venv/bin/python scripts/eval_chengdu.py --concurrency 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import settings  # noqa: F401 — 触发 dotenv 加载
from app.llm.extractor import extract_dsl
from app.llm.router import LLMRouter
from app.render import render_svg
from app.solver import SolveError, solve

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "test" / "chengdu" / "chengdu_selected.json"
RESULT_DIR = PROJECT_ROOT / "test" / "results_chengdu"


@dataclass
class Result:
    id: str
    source: str
    type: str
    expected: str
    nl: str
    status: str = ""
    provider: str = ""
    model: str = ""
    attempts: int = 0
    objects: int = 0
    constraints: int = 0
    residual: float = float("nan")
    latency_ms: int = 0
    svg_bytes: int = 0
    llm_reason: str = ""
    error: str = ""
    dsl_json: str = ""    # 新增：完整 DSL 便于人工检视


async def run_one(provider, item: dict, save_dir: Path) -> Result:
    r = Result(
        id=item["id"],
        source=item["source"],
        type=item["type"],
        expected=item["expected"],
        nl=item["nl"],
        provider=provider.name,
        model=getattr(provider, "model", ""),
    )
    t0 = time.perf_counter()
    try:
        ext = await extract_dsl(provider, item["nl"])
    except Exception as e:
        r.status = "llm_error"
        r.error = f"{type(e).__name__}: {e}"
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.attempts = ext.attempts

    if ext.error:
        r.status = "llm_refuse"
        r.llm_reason = ext.error
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    if ext.dsl is None:
        r.status = "no_dsl"
        r.error = ext.error or "no dsl returned"
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    dsl = ext.dsl
    r.objects = len(dsl.objects)
    r.constraints = len(dsl.constraints)
    r.dsl_json = json.dumps(dsl.to_json_dict(), ensure_ascii=False)

    try:
        sol = solve(dsl, seed=7, restarts=20)
    except SolveError as e:
        r.status = "solve_fail"
        r.error = str(e)
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.residual = sol.residual
    r.status = "ok"
    r.latency_ms = int((time.perf_counter() - t0) * 1000)
    try:
        svg = render_svg(dsl, sol)
        r.svg_bytes = len(svg)
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / f"{r.id}.svg").write_text(svg, encoding="utf-8")
    except Exception as e:
        r.status = "render_fail"
        r.error = f"{type(e).__name__}: {e}"
    return r


def _write_report(results: list[Result], provider, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = len(results)
    ok = sum(1 for r in results if r.status == "ok")
    refuse = sum(1 for r in results if r.status == "llm_refuse")
    solve_fail = sum(1 for r in results if r.status == "solve_fail")
    other = total - ok - refuse - solve_fail

    # 期望符合度
    hits = 0
    for r in results:
        if r.expected == "ok" and r.status == "ok":
            hits += 1
        elif r.expected == "refuse" and r.status == "llm_refuse":
            hits += 1
        elif r.expected == "partial":
            # partial 只要不崩溃（ok / refuse 都算部分符合）
            if r.status in ("ok", "llm_refuse"):
                hits += 1

    # 性能统计
    ok_results = [r for r in results if r.status == "ok"]
    latencies = sorted(r.latency_ms for r in results)
    residuals = [r.residual for r in ok_results if r.residual == r.residual]  # 排除 nan

    def _p(lst, pct):
        if not lst:
            return 0
        return lst[int(len(lst) * pct / 100)]

    p50 = _p(latencies, 50)
    p95 = _p(latencies, 95)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    avg_res = sum(residuals) / len(residuals) if residuals else 0

    lines = []
    lines.append("# 成都近 5 年真题测试报告 · v0.12.1")
    lines.append("")
    lines.append(f"- **Provider**：{provider.name} / {provider.model}")
    lines.append(f"- **题目总数**：{total}")
    lines.append(f"- **求解成功 (ok)**：{ok} / {total} ({ok * 100.0 / total:.1f}%)")
    lines.append(f"- **LLM 拒绝 (refuse)**：{refuse}")
    lines.append(f"- **求解失败 (solve_fail)**：{solve_fail}")
    lines.append(f"- **其它/异常**：{other}")
    lines.append(f"- **符合预期**：{hits} / {total} ({hits * 100.0 / total:.1f}%)")
    lines.append("")
    lines.append("## 性能指标")
    lines.append("")
    lines.append(f"- **平均延迟**：{avg_lat / 1000:.1f}s")
    lines.append(f"- **p50 延迟**：{p50 / 1000:.1f}s")
    lines.append(f"- **p95 延迟**：{p95 / 1000:.1f}s")
    lines.append(f"- **平均残差（ok 题）**：{avg_res:.2e}")
    lines.append("")

    # 表 1 · 按类型分组
    lines.append("## 按题型分组")
    lines.append("")
    lines.append("| 类型 | 总数 | ok | refuse | solve_fail | 符合预期 |")
    lines.append("|---|---|---|---|---|---|")
    types = sorted({r.type for r in results})
    for t in types:
        subset = [r for r in results if r.type == t]
        n_ok = sum(1 for r in subset if r.status == "ok")
        n_refuse = sum(1 for r in subset if r.status == "llm_refuse")
        n_fail = sum(1 for r in subset if r.status == "solve_fail")
        n_hits = 0
        for r in subset:
            if r.expected == "ok" and r.status == "ok":
                n_hits += 1
            elif r.expected == "refuse" and r.status == "llm_refuse":
                n_hits += 1
            elif r.expected == "partial" and r.status in ("ok", "llm_refuse"):
                n_hits += 1
        pct = n_hits * 100.0 / len(subset) if subset else 0
        lines.append(f"| {t} | {len(subset)} | {n_ok} | {n_refuse} | {n_fail} | {n_hits} ({pct:.0f}%) |")

    # 表 2 · 按来源分组
    lines.append("")
    lines.append("## 按来源分组")
    lines.append("")
    lines.append("| 来源 | 总数 | ok | refuse | solve_fail | 符合预期 |")
    lines.append("|---|---|---|---|---|---|")
    sources = sorted({r.source for r in results})
    for s in sources:
        subset = [r for r in results if r.source == s]
        n_ok = sum(1 for r in subset if r.status == "ok")
        n_refuse = sum(1 for r in subset if r.status == "llm_refuse")
        n_fail = sum(1 for r in subset if r.status == "solve_fail")
        n_hits = 0
        for r in subset:
            if r.expected == "ok" and r.status == "ok":
                n_hits += 1
            elif r.expected == "refuse" and r.status == "llm_refuse":
                n_hits += 1
            elif r.expected == "partial" and r.status in ("ok", "llm_refuse"):
                n_hits += 1
        pct = n_hits * 100.0 / len(subset) if subset else 0
        lines.append(f"| {s} | {len(subset)} | {n_ok} | {n_refuse} | {n_fail} | {n_hits} ({pct:.0f}%) |")

    # 表 3 · 失败题详情
    lines.append("")
    lines.append("## 失败题详情")
    lines.append("")

    solve_fails = [r for r in results if r.status == "solve_fail"]
    if solve_fails:
        lines.append(f"### solve_fail（{len(solve_fails)} 题）")
        lines.append("")
        for r in solve_fails:
            lines.append(f"- **{r.id}** [{r.type}] {r.nl[:80]}")
            lines.append(f"  - 期望：`{r.expected}` | obj={r.objects} con={r.constraints}")
            lines.append(f"  - 错误：{r.error[:150]}")
        lines.append("")

    # LLM 拒绝：区分"合理拒绝"（expected 就是 refuse）和"意外拒绝"（expected 是 ok 但被拒了）
    unexpected_refuse = [r for r in results
                        if r.status == "llm_refuse" and r.expected == "ok"]
    expected_refuse = [r for r in results
                      if r.status == "llm_refuse" and r.expected == "refuse"]
    partial_refuse = [r for r in results
                     if r.status == "llm_refuse" and r.expected == "partial"]

    if unexpected_refuse:
        lines.append(f"### 意外拒绝（{len(unexpected_refuse)} 题 - 期望 ok 但 LLM 拒绝了）")
        lines.append("")
        for r in unexpected_refuse:
            lines.append(f"- **{r.id}** [{r.type}] {r.nl[:80]}")
            lines.append(f"  - LLM 理由：{r.llm_reason[:120]}")
        lines.append("")

    if partial_refuse:
        lines.append(f"### partial 类拒绝（{len(partial_refuse)} 题 - 期望 partial，LLM 选择拒绝）")
        lines.append("")
        for r in partial_refuse:
            lines.append(f"- **{r.id}** [{r.type}] {r.nl[:80]}")
            lines.append(f"  - LLM 理由：{r.llm_reason[:120]}")
        lines.append("")

    if expected_refuse:
        lines.append(f"### 合理拒绝（{len(expected_refuse)} 题 - 期望和实际均为 refuse）")
        lines.append("")
        for r in expected_refuse:
            lines.append(f"- **{r.id}** [{r.type}] {r.nl[:60]}")
        lines.append("")

    # 表 4 · 逐题结果
    lines.append("## 逐题结果")
    lines.append("")
    lines.append("| ID | 来源 | 类型 | 期望 | 实际 | obj | con | 残差 | 延迟 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        mark = ""
        if r.expected == "ok" and r.status == "ok":
            mark = "✅"
        elif r.expected == "refuse" and r.status == "llm_refuse":
            mark = "✅"
        elif r.expected == "partial" and r.status in ("ok", "llm_refuse"):
            mark = "🟡"
        else:
            mark = "❌"
        residual = f"{r.residual:.0e}" if r.status == "ok" else "-"
        # source 太长会挤爆列，取简称
        src_short = r.source.replace("2021 中考·", "zk21").replace("2025 高考·新课标II", "gk25新II")
        lines.append(
            f"| {r.id} | {src_short} | {r.type} | {r.expected} | {mark} {r.status} | "
            f"{r.objects} | {r.constraints} | {residual} | {r.latency_ms}ms |"
        )

    # 详细
    lines.append("")
    lines.append("## 详情")
    for r in results:
        lines.append(f"\n### {r.id} — {r.type}")
        lines.append(f"**NL**：{r.nl}")
        lines.append(f"**期望**：`{r.expected}`  **实际**：`{r.status}`")
        if r.llm_reason:
            lines.append(f"**LLM 拒绝理由**：{r.llm_reason}")
        if r.error:
            lines.append(f"**错误**：{r.error}")
        if r.status == "ok":
            lines.append(f"**DSL**：{r.objects} 对象、{r.constraints} 约束、残差 {r.residual:.2e}")

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dataset", default=str(DATASET),
                    help="数据集 JSON 路径（默认 chengdu_selected.json）")
    ap.add_argument("--out", default=str(RESULT_DIR),
                    help="输出目录（默认 test/results_chengdu）")
    args = ap.parse_args()

    dataset_path = Path(args.dataset)
    out_dir = Path(args.out)

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]

    router = LLMRouter()
    provider = router.get()

    print(f"数据集：{dataset_path.name} ({len(data)} 题)")
    print(f"Provider：{provider.name} / {provider.model}")
    print(f"输出：{out_dir}")
    print("-" * 70)

    svg_dir = out_dir / "svgs"
    sem = asyncio.Semaphore(args.concurrency)

    async def _one(item):
        async with sem:
            r = await run_one(provider, item, svg_dir)
            mark = "✅" if r.status == "ok" else "⚠️ "
            print(f"  {mark} {r.id} [{r.type[:20]:20}] {r.status:12} {r.latency_ms}ms  {r.nl[:50]}")
            return r

    t0 = time.perf_counter()
    results = await asyncio.gather(*(_one(item) for item in data))
    elapsed = time.perf_counter() - t0

    print(f"\n完成 {len(results)} 题，耗时 {elapsed:.1f}s")

    _write_report(results, provider, out_dir)
    print(f"报告：{out_dir / 'report.md'}")


if __name__ == "__main__":
    asyncio.run(main())
