"""多 Provider 自动对比评测。

按 chengdu_full.json 跑每个 enabled Provider，输出对比报告。

用法：
  .venv/bin/python scripts/eval_multi_providers.py
  .venv/bin/python scripts/eval_multi_providers.py --providers volcengine,kimi_k26
  .venv/bin/python scripts/eval_multi_providers.py --limit 10  # 只跑前 10 题（快速预览）
  .venv/bin/python scripts/eval_multi_providers.py --concurrency 3  # 单 provider 并发数

输出：
  test/results_chengdu_multi/
    comparison.md          — 对比报告（5 张表）
    <provider>/results.json — 每家详细结果
    svgs/<id>_<provider>.svg — 每家每题渲染图
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import AsyncIterator

from app.config import settings  # noqa: F401 — 触发 dotenv 加载
from app.llm.base import LLMProvider
from app.llm.extractor import extract_dsl
from app.llm.router import LLMRouter
from app.render import render_svg
from app.solver import SolveError, solve

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "test" / "chengdu" / "chengdu_full.json"
DEFAULT_OUT = PROJECT_ROOT / "test" / "results_chengdu_multi"

# 各家定价（元 / 百万 tokens）
# 来源：各家官网公开公告（2026-07 估算），仅作成本对比参考，实际以官网为准
PRICING_CNY_PER_MTOK = {
    # 火山方舟 CodingPlan
    "volcengine":             {"in": 0.5,  "out": 1.5,  "label": "glm-5.2 (火山 CodingPlan)"},
    "volcengine_doubao_pro":  {"in": 0.8,  "out": 2.0,  "label": "Doubao-Seed-2.0-pro"},
    # DeepSeek
    "deepseek":               {"in": 0.5,  "out": 1.5,  "label": "deepseek-chat (V4)"},
    "deepseek_v4_pro":        {"in": 2.0,  "out": 8.0,  "label": "deepseek-v4-pro (推理模型)"},
    # MiniMax
    "minimax":                {"in": 0.5,  "out": 1.5,  "label": "MiniMax-M3"},
    # Moonshot / Kimi
    "kimi_k26":               {"in": 1.0,  "out": 4.0,  "label": "kimi-k2.6"},
    "kimi_k27_code":          {"in": 1.0,  "out": 4.0,  "label": "kimi-k2.7-code"},
    "kimi_k27_code_hs":       {"in": 0.5,  "out": 1.5,  "label": "kimi-k2.7-code-highspeed"},
    # 智谱 BigModel
    "zhipu":                  {"in": 0.5,  "out": 1.5,  "label": "glm-5.2 (BigModel)"},
}


class UsageTracker:
    """包装 Provider，记录每次 chat 的 token usage 累计。

    用 duck typing 实现 LLMProvider Protocol（extract_dsl 只用 chat 方法），
    不需要修改 extractor.py 即可累计 token 用量。
    """

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.inner, "enabled", False))

    @property
    def base_url(self) -> str:
        return getattr(self.inner, "base_url", "")

    async def chat(self, messages, *, json_mode=False, temperature=0.2,
                   max_tokens=4096, timeout=60.0):
        # 即使抛 LLMError 也算一次 API 调用（用于真实请求次数统计）
        try:
            resp = await self.inner.chat(
                messages,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception:
            self.calls += 1
            raise
        self.calls += 1
        self.prompt_tokens += resp.usage.prompt_tokens
        self.completion_tokens += resp.usage.completion_tokens
        return resp

    async def chat_stream(self, messages, **kwargs) -> AsyncIterator[str]:
        async for tok in self.inner.chat_stream(messages, **kwargs):
            yield tok


@dataclass
class CaseResult:
    id: str
    source: str
    type: str
    expected: str
    nl: str
    status: str = ""
    attempts: int = 0
    objects: int = 0
    constraints: int = 0
    residual: float = float("nan")
    latency_ms: int = 0
    error: str = ""


async def run_one(tracker: UsageTracker, item: dict,
                  svg_dir: Path, save_svg: bool = True) -> CaseResult:
    r = CaseResult(
        id=item["id"],
        source=item["source"],
        type=item["type"],
        expected=item["expected"],
        nl=item["nl"],
    )
    t0 = time.perf_counter()
    try:
        ext = await extract_dsl(tracker, item["nl"])
    except Exception as e:
        r.status = "llm_error"
        r.error = f"{type(e).__name__}: {e}"
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.attempts = ext.attempts

    if ext.error:
        r.status = "llm_refuse"
        r.error = ext.error
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

    try:
        sol = solve(dsl, seed=7, restarts=20)
    except SolveError as e:
        r.status = "solve_fail"
        r.error = str(e)[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r
    except Exception as e:
        # 防御性：solver 内部 bug（如 KeyError 逃逸）也不应让整个评测崩溃
        r.status = "solve_fail"
        r.error = f"{type(e).__name__}: {e}"[:200]
        r.latency_ms = int((time.perf_counter() - t0) * 1000)
        return r

    r.residual = float(sol.residual)
    r.status = "ok"
    r.latency_ms = int((time.perf_counter() - t0) * 1000)

    if save_svg:
        try:
            svg = render_svg(dsl, sol)
            svg_dir.mkdir(parents=True, exist_ok=True)
            (svg_dir / f"{r.id}_{tracker.name}.svg").write_text(svg, encoding="utf-8")
        except Exception:
            pass  # 渲染失败不影响评测

    return r


def _percentile(lst: list[float], pct: float) -> float:
    if not lst:
        return 0.0
    k = int(len(lst) * pct / 100)
    return lst[min(k, len(lst) - 1)]


def _expected_match(r: CaseResult) -> bool:
    """是否符合预期：根据 expected 与实际 status 判断。"""
    if r.expected == "ok" and r.status == "ok":
        return True
    if r.expected == "refuse" and r.status == "llm_refuse":
        return True
    if r.expected == "partial" and r.status in ("ok", "llm_refuse"):
        return True
    return False


def _estimate_cost(tracker: UsageTracker) -> float:
    p = PRICING_CNY_PER_MTOK.get(tracker.name, {"in": 0, "out": 0})
    return (tracker.prompt_tokens * p["in"]
            + tracker.completion_tokens * p["out"]) / 1_000_000


def _write_comparison_report(
    all_results: dict[str, list[CaseResult]],
    trackers: dict[str, UsageTracker],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    provider_names = list(all_results.keys())
    first_results = all_results[provider_names[0]] if provider_names else []
    total = len(first_results)

    lines.append("# 多 Provider 对比评测报告")
    lines.append("")
    lines.append(f"- **数据集**：chengdu_full.json")
    lines.append(f"- **题数**：{total}")
    lines.append(f"- **Provider 数**：{len(provider_names)}")
    lines.append(f"- **生成时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 表 1 · 总览对比
    lines.append("## 表 1 · 总览对比")
    lines.append("")
    lines.append(
        "| Provider | Model | OK | 符合预期 | 通过率 | 平均残差 | "
        "p50 延迟 | p95 延迟 | 调用次数 | 输入 tokens | 输出 tokens | 估算成本(元) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

    for name in provider_names:
        results = all_results[name]
        tracker = trackers[name]
        n_ok = sum(1 for r in results if r.status == "ok")
        n_hit = sum(1 for r in results if _expected_match(r))
        oks = [r for r in results if r.status == "ok"]
        avg_res = (
            sum(r.residual for r in oks if r.residual == r.residual) / len(oks)
            if oks else 0.0
        )
        lats = sorted(r.latency_ms for r in results)
        p50 = _percentile(lats, 50)
        p95 = _percentile(lats, 95)
        cost = _estimate_cost(tracker)
        lines.append(
            f"| `{name}` | {tracker.model} | {n_ok} | {n_hit} | "
            f"{n_ok*100/len(results):.1f}% | {avg_res:.1e} | "
            f"{p50/1000:.1f}s | {p95/1000:.1f}s | "
            f"{tracker.calls} | {tracker.prompt_tokens:,} | {tracker.completion_tokens:,} | {cost:.3f} |"
        )
    lines.append("")

    # 表 2 · 逐题状态对比
    lines.append("## 表 2 · 逐题状态对比")
    lines.append("")
    header = "| ID | 类型 | 期望 | " + " | ".join(f"`{n}`" for n in provider_names) + " |"
    sep = "|---|---|---|" + "---|" * len(provider_names)
    lines.append(header)
    lines.append(sep)

    by_id: dict[str, dict[str, CaseResult]] = {}
    for name, results in all_results.items():
        for r in results:
            by_id.setdefault(r.id, {})[name] = r

    status_icon = {
        "ok": "✅",
        "llm_refuse": "🟡",
        "solve_fail": "🔴",
        "llm_error": "⚠️",
        "no_dsl": "🔴",
    }

    for r in first_results:
        cells = []
        for name in provider_names:
            cr = by_id.get(r.id, {}).get(name)
            cells.append(status_icon.get(cr.status, "?") if cr else "—")
        lines.append(
            f"| {r.id} | {r.type} | {r.expected} | " + " | ".join(cells) + " |"
        )
    lines.append("")

    # 表 3 · 失败题详情
    lines.append("## 表 3 · 失败题详情")
    lines.append("")
    lines.append("（仅展示至少一家 provider 失败的题）")
    lines.append("")
    lines.append(
        "| ID | NL（前 60 字） | 类型 | 期望 | "
        + " | ".join(f"`{n}`" for n in provider_names) + " |"
    )
    lines.append("|---|---|---|---|" + "---|" * len(provider_names))

    for r in first_results:
        statuses = []
        any_fail = False
        for name in provider_names:
            cr = by_id.get(r.id, {}).get(name)
            if cr is None:
                statuses.append("—")
                continue
            statuses.append(cr.status)
            if cr.status != "ok":
                any_fail = True
        if not any_fail:
            continue
        row = [r.id, r.nl[:60], r.type, r.expected] + statuses
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # 表 4 · 定价参考
    lines.append("## 表 4 · 定价参考")
    lines.append("")
    lines.append("> 价格为参考估算（元 / 百万 tokens），以各家官网为准。")
    lines.append("")
    lines.append("| Provider | Model 标签 | 输入 (元/M tokens) | 输出 (元/M tokens) |")
    lines.append("|---|---|---|---|")
    for name in provider_names:
        p = PRICING_CNY_PER_MTOK.get(name, {"in": "?", "out": "?", "label": ""})
        lines.append(f"| `{name}` | {p['label']} | {p['in']} | {p['out']} |")
    lines.append("")

    # 表 5 · 综合小结
    lines.append("## 表 5 · 综合小结")
    lines.append("")

    if provider_names:
        best_ok = max(
            provider_names,
            key=lambda n: sum(1 for r in all_results[n] if r.status == "ok"),
        )
        best_hit = max(
            provider_names,
            key=lambda n: sum(1 for r in all_results[n] if _expected_match(r)),
        )
        fastest = min(
            provider_names,
            key=lambda n: _percentile(sorted(r.latency_ms for r in all_results[n]), 50),
        )
        cheapest = min(provider_names, key=lambda n: _estimate_cost(trackers[n]))

        ok_count = sum(1 for r in all_results[best_ok] if r.status == "ok")
        hit_count = sum(1 for r in all_results[best_hit] if _expected_match(r))
        p50 = _percentile(sorted(r.latency_ms for r in all_results[fastest]), 50)
        cost = _estimate_cost(trackers[cheapest])

        lines.append(f"- **通过率最高**：`{best_ok}` — {ok_count}/{total} ok")
        lines.append(f"- **符合预期最高**：`{best_hit}` — {hit_count}/{total}")
        lines.append(f"- **p50 延迟最低**：`{fastest}` — p50={p50/1000:.1f}s")
        lines.append(f"- **总成本最低**：`{cheapest}` — ¥{cost:.3f}")
    lines.append("")

    (out_dir / "comparison.md").write_text("\n".join(lines), encoding="utf-8")

    # 每家详细 results.json
    for name, results in all_results.items():
        sub = out_dir / name
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "results.json").write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


async def run_provider(provider, dataset: list[dict], concurrency: int,
                       svg_dir: Path) -> tuple[list[CaseResult], UsageTracker]:
    tracker = UsageTracker(inner=provider)
    sem = asyncio.Semaphore(concurrency)

    async def _one(item):
        async with sem:
            r = await run_one(tracker, item, svg_dir)
            mark = "✅" if r.status == "ok" else "⚠️ "
            print(
                f"    [{provider.name:>25}] {mark} {r.id} "
                f"[{r.type[:18]:18}] {r.status:12} {r.latency_ms:>5}ms  {r.nl[:40]}"
            )
            return r

    results = await asyncio.gather(*(_one(item) for item in dataset))
    return list(results), tracker


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--providers", default="",
        help="逗号分隔的 provider name 列表，留空 = 全部 enabled",
    )
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=None,
                    help="只跑前 N 题（快速预览）")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="单 provider 内并发数")
    ap.add_argument("--no-svg", action="store_true",
                    help="不保存 SVG（节省磁盘）")
    args = ap.parse_args()

    dataset_path = Path(args.dataset)
    out_dir = Path(args.out)

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if args.limit:
        data = data[:args.limit]

    router = LLMRouter()

    if args.providers:
        names = [n.strip() for n in args.providers.split(",") if n.strip()]
    else:
        names = [p["name"] for p in router.list_available() if p["enabled"]]

    providers = []
    for n in names:
        try:
            p = router.get(n)
        except KeyError:
            print(f"⚠️  跳过未知 provider: {n}")
            continue
        if not getattr(p, "enabled", False):
            print(f"⚠️  跳过未配置 Key 的 provider: {n}")
            continue
        providers.append(p)

    if not providers:
        print("❌ 没有可用的 provider")
        return

    print(f"数据集：{dataset_path.name} ({len(data)} 题)")
    print(f"Provider 数：{len(providers)}")
    for p in providers:
        print(f"  - {p.name} / {p.model}")
    print(f"输出：{out_dir}")
    print("-" * 70)

    all_results: dict[str, list[CaseResult]] = {}
    trackers: dict[str, UsageTracker] = {}
    svg_dir = out_dir / "svgs"

    t0 = time.perf_counter()
    for p in providers:
        print(f"\n▶ 跑 {p.name} / {p.model}")
        results, tracker = await run_provider(p, data, args.concurrency, svg_dir)
        all_results[p.name] = results
        trackers[p.name] = tracker
        n_ok = sum(1 for r in results if r.status == "ok")
        n_hit = sum(1 for r in results if _expected_match(r))
        cost = _estimate_cost(tracker)
        print(
            f"  ✓ {p.name}: ok {n_ok}/{len(results)}  符合预期 {n_hit}/{len(results)}  "
            f"tokens in={tracker.prompt_tokens:,} out={tracker.completion_tokens:,}  成本 ¥{cost:.3f}"
        )

    elapsed = time.perf_counter() - t0
    print(f"\n全部完成，耗时 {elapsed:.1f}s")

    _write_comparison_report(all_results, trackers, out_dir)
    print(f"对比报告：{out_dir / 'comparison.md'}")


if __name__ == "__main__":
    asyncio.run(main())
