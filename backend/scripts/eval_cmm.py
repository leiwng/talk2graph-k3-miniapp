"""通用 CMM 测试集 runner —— 跑 v1（原始）和 v2（待改写）数据集。

用法：
  .venv/bin/python3 scripts/eval_cmm.py v1
  .venv/bin/python3 scripts/eval_cmm.py v2
  .venv/bin/python3 scripts/eval_cmm.py both   # 跑两个
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path

from app.config import settings
from app.llm.extractor import extract_dsl
from app.llm.router import LLMRouter
from app.render import render_svg
from app.solver import SolveError, solve

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent   # backend/scripts/.. = repo
TEST_DIR = PROJECT_ROOT / "test"


@dataclass
class Result:
    no: int
    id: str
    subject: str
    difficulty: str
    description_preview: str
    status: str
    provider: str = ""
    model: str = ""
    attempts: int = 0
    objects: int = 0
    constraints: int = 0
    residual: float = float("nan")
    latency_ms: int = 0
    svg_bytes: int = 0
    error: str = ""


def _clean_latex(text: str) -> str:
    """简单清理 LaTeX 命令，仅用于发给 LLM 的输入。"""
    s = text
    # \mathrm{XXX} -> XXX
    s = re.sub(r"\\mathrm\{([^}]+)\}", r"\1", s)
    s = re.sub(r"\\text\{([^}]+)\}", r"\1", s)
    # $...$ 保留内容
    s = re.sub(r"\$([^$]+)\$", r"\1", s)
    # 常见数学命令
    s = s.replace(r"\circ", "°").replace(r"\angle", "∠")
    s = s.replace(r"\qquad", "____").replace(r"\quad", "  ")
    s = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", s)
    s = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", s)
    # 删除剩余反斜杠命令（保守起见，只删孤立的）
    s = re.sub(r"\\[a-zA-Z]+\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def run_single(provider, item: dict, idx: int, save_dir: Path) -> Result:
    # 支持两种数据格式：
    #   v1 / v2_to_rewrite: 用 description 字段
    #   v2_rewritten:        用 rewritten 字段（若 status=skipped 则该题不发 LLM）
    if "rewrite_status" in item:
        if item["rewrite_status"] == "skipped":
            r = Result(
                no=idx,
                id=str(item.get("id", "")),
                subject=item.get("subject", ""),
                difficulty=item.get("difficulty", ""),
                description_preview=(item.get("rewritten") or item.get("original_description", ""))[:80],
                status="skipped_input",
                error=item.get("skip_reason", "")[:200],
                model=getattr(provider, "model", ""),
            )
            return r
        nl = item.get("rewritten") or item.get("original_description", "")
        nl = _clean_latex(nl)
    else:
        nl_raw = item.get("description", "")
        nl = _clean_latex(nl_raw)

    r = Result(
        no=idx,
        id=str(item.get("id", "")),
        subject=item.get("subject", ""),
        difficulty=item.get("difficulty", ""),
        description_preview=nl[:80],
        status="",
        model=getattr(provider, "model", ""),
    )

    t0 = time.perf_counter()
    try:
        ext = await extract_dsl(provider, nl)
    except Exception as e:
        r.status = "extract_fail"; r.error = str(e)[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.provider = ext.provider
    r.attempts = ext.attempts

    if ext.error:
        r.status = "llm_refuse"
        r.error = ext.error[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    if ext.dsl is None:
        r.status = "no_dsl"
        r.error = "no dsl extracted"
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
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
        (save_dir / f"case_{idx:03d}_{r.id}.svg").write_text(svg, encoding="utf-8")
    except Exception as e:
        r.status = "render_fail"; r.error = str(e)[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.status = "ok"
    r.latency_ms = int((time.perf_counter() - t0) * 1000)
    return r


def _write_report(results: list[Result], provider, out_dir: Path, dataset_name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # raw JSON
    (out_dir / "results.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    n = len(results)
    by_status = Counter(r.status for r in results)
    by_subj_total = Counter(r.subject for r in results)
    by_subj_ok = Counter(r.subject for r in results if r.status == "ok")
    by_diff_total = Counter(r.difficulty for r in results)
    by_diff_ok = Counter(r.difficulty for r in results if r.status == "ok")

    ok = [r for r in results if r.status == "ok"]
    n_ok = len(ok)
    avg_res = sum(r.residual for r in ok) / n_ok if ok else float("nan")
    avg_lat_ok = sum(r.latency_ms for r in ok) / n_ok if ok else 0
    avg_lat_all = sum(r.latency_ms for r in results) / n

    lines = []
    lines.append(f"# CMM 测试集评估报告 — {dataset_name}")
    lines.append("")
    lines.append(f"- **数据集**：{dataset_name}（{n} 题）")
    lines.append(f"- **Provider**：{provider.name} / {provider.model}")
    lines.append(f"- **Base URL**：{provider.base_url}")
    lines.append(f"- **求解成功**：{n_ok} / {n}（{n_ok/n*100:.1f}%）")
    lines.append(f"- **平均残差（成功题）**：{avg_res:.2e}")
    lines.append(f"- **平均延迟（成功 / 全部）**：{int(avg_lat_ok)}ms / {int(avg_lat_all)}ms")
    lines.append("")

    lines.append("## 状态分布")
    lines.append("")
    lines.append("| 状态 | 数量 | 占比 |")
    lines.append("|---|---|---|")
    for st, cnt in by_status.most_common():
        lines.append(f"| {st} | {cnt} | {cnt/n*100:.1f}% |")
    lines.append("")

    lines.append("## 按科目")
    lines.append("")
    lines.append("| 科目 | 总数 | OK | 通过率 |")
    lines.append("|---|---|---|---|")
    for subj, total in by_subj_total.most_common():
        k = by_subj_ok.get(subj, 0)
        lines.append(f"| {subj} | {total} | {k} | {k/total*100:.1f}% |")
    lines.append("")

    lines.append("## 按难度")
    lines.append("")
    lines.append("| 难度 | 总数 | OK | 通过率 |")
    lines.append("|---|---|---|---|")
    for diff, total in by_diff_total.most_common():
        k = by_diff_ok.get(diff, 0)
        lines.append(f"| {diff} | {total} | {k} | {k/total*100:.1f}% |")
    lines.append("")

    lines.append("## 详细结果（前 50 + 全部成功）")
    lines.append("")
    lines.append("| # | id | 科目 | 难度 | 状态 | obj | con | 残差 | 延迟 | 描述 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    # 先列所有 ok，再列前 50 个非 ok
    shown: list[Result] = list(ok)
    others = [r for r in results if r.status != "ok"][:50]
    shown.extend(others)
    for r in shown:
        icon = "✅" if r.status == "ok" else "⚠️"
        res = f"{r.residual:.1e}" if r.status == "ok" else "—"
        desc = r.description_preview.replace("|", "·")[:60]
        lines.append(
            f"| {r.no} | {r.id} | {r.subject} | {r.difficulty} | {icon} {r.status} "
            f"| {r.objects or '—'} | {r.constraints or '—'} | {res} | {r.latency_ms}ms | {desc} |"
        )
    lines.append("")
    lines.append(f"> 完整结果见 `results.json`；成功 SVG 见 `svgs/`")

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def run_dataset(
    dataset_file: Path,
    output_dir: Path,
    dataset_name: str,
    *,
    limit: int | None = None,
    concurrency: int = 4,
) -> None:
    data = json.loads(dataset_file.read_text(encoding="utf-8"))
    if limit:
        data = data[:limit]
    router = LLMRouter()
    provider = router.get()

    print(f"\n{'='*70}")
    print(f"数据集：{dataset_name}  ({len(data)} 题)")
    print(f"Provider：{provider.name} / {provider.model}")
    print(f"输出：{output_dir}")
    print('='*70)

    svg_dir = output_dir / "svgs"
    sem = asyncio.Semaphore(concurrency)
    results: list[Result] = []
    t_start = time.perf_counter()

    async def _one(idx: int, item: dict) -> Result:
        async with sem:
            r = await run_single(provider, item, idx, svg_dir)
            mark = "✅" if r.status == "ok" else "⚠️ "
            extra = (
                f"obj={r.objects} con={r.constraints} res={r.residual:.0e} {r.latency_ms}ms"
                if r.status == "ok"
                else r.status
            )
            print(f"  {mark} #{idx:3d} [{r.subject:6}] [{r.difficulty:4}] {extra}  {r.description_preview[:50]}")
            return r

    tasks = [_one(i, item) for i, item in enumerate(data, start=1)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda r: r.no)

    elapsed = time.perf_counter() - t_start
    print(f"\n✓ 完成 {len(results)} 题，耗时 {elapsed:.1f}s")

    _write_report(results, provider, output_dir, dataset_name)
    print(f"✓ 报告写入：{output_dir / 'report.md'}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["v1", "v2r", "both"],
                    help="跑哪个数据集（v1 原题 / v2r 改写后 / both 两者都跑）")
    ap.add_argument("--limit", type=int, default=None, help="限制题目数（调试用）")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    name_map = {
        "v1":  ("cmm_test_v1_original.json",   "v1_original (原题)",       "results_cmm_v1"),
        "v2r": ("cmm_test_v2_rewritten.json",  "v2_rewritten (已改写)",    "results_cmm_v2r"),
    }
    targets = {
        "v1":   ["v1"],
        "v2r":  ["v2r"],
        "both": ["v1", "v2r"],
    }[args.which]

    for t in targets:
        fname, dataset_name, out_subdir = name_map[t]
        file = TEST_DIR / fname
        if not file.exists():
            print(f"⚠ 找不到 {file}，跳过 {t}")
            continue
        out = TEST_DIR.parent / "backend" / "test" / out_subdir
        await run_dataset(file, out, dataset_name, limit=args.limit, concurrency=args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
