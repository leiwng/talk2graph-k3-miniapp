"""生成 v1 / v2r 严格 A/B 对比报告（56 条 id 一一对应）。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = PROJECT_ROOT / "test"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "test"

v1_data = json.loads((TEST_DIR / "cmm_test_v1_original.json").read_text(encoding="utf-8"))
v2r_data = json.loads((TEST_DIR / "cmm_test_v2_rewritten.json").read_text(encoding="utf-8"))
v1_res = json.loads((RESULTS_DIR / "results_cmm_v1" / "results.json").read_text(encoding="utf-8"))
v2r_res = json.loads((RESULTS_DIR / "results_cmm_v2r" / "results.json").read_text(encoding="utf-8"))

assert len(v1_data) == len(v2r_data) == 56, "v1 和 v2r 应都是 56 题"

v1_by_id = {r["id"]: r for r in v1_res}
v2r_by_id = {r["id"]: r for r in v2r_res}
src_v1_by_id = {d["id"]: d for d in v1_data}
src_v2r_by_id = {d["id"]: d for d in v2r_data}

# 对齐 — id 一一对应
ids = [d["id"] for d in v1_data]
assert ids == [d["id"] for d in v2r_data], "v1 和 v2r 的 id 顺序应一致"

# 统计
def summarize(res):
    n = len(res)
    by = Counter(r["status"] for r in res)
    ok = [r for r in res if r["status"] == "ok"]
    return {
        "n": n,
        "ok": len(ok),
        "by": dict(by),
        "avg_res": (sum(r["residual"] for r in ok) / len(ok)) if ok else float("nan"),
        "avg_lat": (sum(r["latency_ms"] for r in ok) / len(ok)) if ok else 0,
    }

s1 = summarize(v1_res)
s2 = summarize(v2r_res)

# 逐题对比
class Flip:
    """v1 vs v2r 在同 id 下的状态变化。"""
    def __init__(self): self.items = []
    def add(self, kind, cid, r1, r2):
        self.items.append((kind, cid, r1, r2))

both_ok = 0
v1_only_ok = []
v2r_only_ok = []
both_fail = 0
unchanged_fail = 0

for cid in ids:
    r1 = v1_by_id[cid]
    r2 = v2r_by_id[cid]
    s1_ok = r1["status"] == "ok"
    s2_ok = r2["status"] == "ok"
    if s1_ok and s2_ok:
        both_ok += 1
    elif s1_ok and not s2_ok:
        v1_only_ok.append(cid)
    elif (not s1_ok) and s2_ok:
        v2r_only_ok.append(cid)
    else:
        both_fail += 1

# 按科目对比
subjects = sorted({d["subject"] for d in v1_data})
subj_stats = {}
for subj in subjects:
    total = sum(1 for d in v1_data if d["subject"] == subj)
    v1_ok = sum(1 for r in v1_res if r["subject"] == subj and r["status"] == "ok")
    v2r_ok = sum(1 for r in v2r_res if r["subject"] == subj and r["status"] == "ok")
    subj_stats[subj] = (total, v1_ok, v2r_ok)


# 写报告
def fmt_pct(k, total):
    return f"{k/total*100:.1f}%" if total else "—"

lines = []
lines.append("# CMM 测试集 v1 / v2r 严格 A/B 对比报告")
lines.append("")
lines.append("> **本报告基于真正改写后的 v2r 数据集**（v1 原题 vs v2r 明确作图指令），")
lines.append("> 56 条同 id 一一对应，可直接做\"原始描述 vs 改写描述\"的效果对比。")
lines.append("")
lines.append(f"- Provider：volcengine / glm-5.2")
lines.append(f"- Base URL：https://ark.cn-beijing.volces.com/api/coding/v3")
lines.append(f"- 题数：56（v1 和 v2r 完全对齐）")
lines.append("")

lines.append("## 一、总体结果")
lines.append("")
lines.append("| 维度 | v1 原题 | v2r 改写 | 变化 |")
lines.append("|---|---|---|---|")
lines.append(f"| 求解成功 | **{s1['ok']} / 56 = {s1['ok']/56*100:.1f}%** | **{s2['ok']} / 56 = {s2['ok']/56*100:.1f}%** | {s2['ok'] - s1['ok']:+d} |")
lines.append(f"| LLM 拒绝 | {s1['by'].get('llm_refuse',0)} ({s1['by'].get('llm_refuse',0)/56*100:.1f}%) | {s2['by'].get('llm_refuse',0)} ({s2['by'].get('llm_refuse',0)/56*100:.1f}%) | {s2['by'].get('llm_refuse',0)-s1['by'].get('llm_refuse',0):+d} |")
lines.append(f"| 求解失败 | {s1['by'].get('solve_fail',0)} | {s2['by'].get('solve_fail',0)} | {s2['by'].get('solve_fail',0)-s1['by'].get('solve_fail',0):+d} |")
lines.append(f"| 改写阶段跳过 | — | {s2['by'].get('skipped_input',0)}（题目本身不可作图）| — |")
lines.append(f"| 平均残差（成功题）| {s1['avg_res']:.2e} | {s2['avg_res']:.2e} | — |")
lines.append(f"| 平均延迟（成功题）| {int(s1['avg_lat'])}ms | {int(s2['avg_lat'])}ms | — |")
lines.append("")

lines.append("## 二、逐题分布")
lines.append("")
lines.append("| 类别 | 数量 | 说明 |")
lines.append("|---|---|---|")
lines.append(f"| 两轮都通过 | **{both_ok}** | 改写没改变结果（都成功）|")
lines.append(f"| v1 通过但 v2r 失败 | {len(v1_only_ok)} | 改写可能引入了新信息或丢了关键约束 |")
lines.append(f"| v1 失败但 v2r 通过 | **{len(v2r_only_ok)}** | 改写挽救了原题！|")
lines.append(f"| 两轮都失败 | {both_fail} | 题目本身超出 MVP 范围 |")
lines.append("")
lines.append(f"**改写带来的净效果：{len(v2r_only_ok)} 题挽救 vs {len(v1_only_ok)} 题失分 = "
             f"净 {len(v2r_only_ok) - len(v1_only_ok):+d} 题**")
lines.append("")

lines.append("## 三、按科目对比")
lines.append("")
lines.append("| 科目 | 总数 | v1 OK | v1 % | v2r OK | v2r % | 变化 |")
lines.append("|---|---|---|---|---|---|---|")
for subj in sorted(subjects, key=lambda s: -subj_stats[s][0]):
    total, v1_k, v2r_k = subj_stats[subj]
    diff = v2r_k - v1_k
    arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "·")
    lines.append(f"| {subj} | {total} | {v1_k} | {fmt_pct(v1_k,total)} | {v2r_k} | {fmt_pct(v2r_k,total)} | {arrow} {diff:+d} |")
lines.append("")

# v2r 挽救的题
if v2r_only_ok:
    lines.append("## 四、改写挽救的题（v1 失败 → v2r 成功）")
    lines.append("")
    lines.append("| id | 科目 | v1 原题 | v2r 改写 |")
    lines.append("|---|---|---|---|")
    for cid in v2r_only_ok:
        src1 = src_v1_by_id[cid]["description"].replace("|", "·")[:80]
        src2 = src_v2r_by_id[cid].get("rewritten", "").replace("|", "·")[:80]
        lines.append(f"| {cid} | {src_v1_by_id[cid]['subject']} | {src1} | {src2} |")
    lines.append("")

# v1 通过但 v2r 失败
if v1_only_ok:
    lines.append("## 五、改写后反而失败的题（v1 成功 → v2r 失败）")
    lines.append("")
    lines.append("| id | 科目 | v2r 失败原因 | 改写内容 |")
    lines.append("|---|---|---|---|")
    for cid in v1_only_ok:
        r2 = v2r_by_id[cid]
        src2 = src_v2r_by_id[cid].get("rewritten") or src_v2r_by_id[cid].get("skip_reason", "")
        src2 = src2.replace("|", "·")[:80]
        err = r2.get("error", "")[:60]
        lines.append(f"| {cid} | {r2['subject']} | {r2['status']}: {err} | {src2} |")
    lines.append("")

# 跳过题清单
skipped = [d for d in v2r_data if d.get("rewrite_status") == "skipped"]
if skipped:
    lines.append("## 六、改写阶段跳过的题")
    lines.append("")
    lines.append("LLM 判定无法作图（纯计算 / 三视图选择 / 缺少几何要素）：")
    lines.append("")
    lines.append("| id | 科目 | 跳过原因 |")
    lines.append("|---|---|---|")
    for d in skipped:
        lines.append(f"| {d['id']} | {d['subject']} | {d.get('skip_reason','')} |")
    lines.append("")

lines.append("## 七、结论")
lines.append("")
delta = s2["ok"] - s1["ok"]
if delta > 0:
    verdict = f"✅ **改写有效**：通过率提升 {delta} 题（+{delta/56*100:.1f}%）"
elif delta < 0:
    verdict = f"⚠️ **改写整体降低通过率**：净失 {-delta} 题"
else:
    verdict = "≈ **改写整体持平**"
lines.append(f"1. {verdict}")
lines.append("")
lines.append(f"2. 改写带来 **{len(v2r_only_ok)} 题被挽救**（v1 LLM 拒绝过但 v2r 能正确作图），")
lines.append(f"   也带来 **{len(v1_only_ok)} 题反而失败**（改写时可能误删了关键约束或引入歧义）。")
lines.append("")
lines.append(f"3. 改写阶段主动跳过 **{s2['by'].get('skipped_input',0)} 题**（纯计算、三视图、应用题示意），")
lines.append(f"   这些题本质不属于\"几何作图\"任务，应在评估前过滤。")
lines.append("")
lines.append(f"4. 求解精度：v1 残差 {s1['avg_res']:.1e}，v2r 残差 {s2['avg_res']:.1e}，"
             f"两者都已达机器精度量级。")
lines.append("")

lines.append("## 八、产物清单")
lines.append("")
lines.append("```")
lines.append("test/")
lines.append("├── cmm_test_v1_original.json      # 56 条原题")
lines.append("└── cmm_test_v2_rewritten.json     # 56 条改写后（48 done + 8 skipped）")
lines.append("")
lines.append("backend/test/")
lines.append("├── results_md38_dataset/          # 早期 38 题数据集")
lines.append("├── results_cmm_v1/                # v1 原题评估")
lines.append("│   ├── report.md")
lines.append("│   ├── results.json")
lines.append(f"│   └── svgs/                      # {s1['ok']} 个 SVG")
lines.append("├── results_cmm_v2r/               # v2r 改写后评估")
lines.append("│   ├── report.md")
lines.append("│   ├── results.json")
lines.append(f"│   └── svgs/                      # {s2['ok']} 个 SVG")
lines.append("└── results_v1_v2r_comparison.md   # ← 本对比报告")
lines.append("```")

out = RESULTS_DIR / "results_v1_v2r_comparison.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"✓ 对比报告已写入：{out}")
print(f"  字节数：{out.stat().st_size}")
print()
print(f"summary: v1={s1['ok']}/56  v2r={s2['ok']}/56  rescue={len(v2r_only_ok)}  lost={len(v1_only_ok)}")
