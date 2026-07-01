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

    lines = []
    lines.append("# 成都近 5 年真题精选测试报告")
    lines.append("")
    lines.append(f"- **Provider**：{provider.name} / {provider.model}")
    lines.append(f"- **题目总数**：{total}")
    lines.append(f"- **求解成功 (ok)**：{ok} / {total} ({ok * 100.0 / total:.1f}%)")
    lines.append(f"- **LLM 拒绝 (refuse)**：{refuse}")
    lines.append(f"- **求解失败 (solve_fail)**：{solve_fail}")
    lines.append(f"- **其它/异常**：{other}")
    lines.append(f"- **符合预期**：{hits} / {total} ({hits * 100.0 / total:.1f}%)")
    lines.append("")
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
        lines.append(
            f"| {r.id} | {r.source} | {r.type} | {r.expected} | {mark} {r.status} | "
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
    args = ap.parse_args()

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]

    router = LLMRouter()
    provider = router.get()

    print(f"数据集：{DATASET.name} ({len(data)} 题)")
    print(f"Provider：{provider.name} / {provider.model}")
    print(f"输出：{RESULT_DIR}")
    print("-" * 70)

    svg_dir = RESULT_DIR / "svgs"
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

    _write_report(results, provider, RESULT_DIR)
    print(f"报告：{RESULT_DIR / 'report.md'}")


if __name__ == "__main__":
    asyncio.run(main())
