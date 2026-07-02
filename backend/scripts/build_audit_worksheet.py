"""生成审核工作表：把 candidates 分组、按类型排序、加上 AI 建议。

用法：
  .venv/bin/python scripts/build_audit_worksheet.py

输出：
  docs/audit-worksheet-v0.12.1.md（Markdown 表格 + 逐题建议）
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_ZK = PROJECT_ROOT / "test" / "chengdu" / "candidates_2021_zhongkao.json"
CANDIDATES_GK = PROJECT_ROOT / "test" / "chengdu" / "candidates_2025_gaokao.json"
OUT = PROJECT_ROOT.parent / "docs" / "audit-worksheet-v0.12.1.md"


def load_drawing(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [x for x in data if x.get("is_drawing_task")]


def _make_id(tag: str, q_num: str, seq: int) -> str:
    """生成 ID，如 zk_geo_001。"""
    prefix = "zk" if "中考" in tag else "gk"
    return f"{prefix}_{seq:03d}"


def _suggest(item) -> tuple[str, str]:
    """给出 AI 审核建议。返回 (决定, 理由)。

    决定：keep / drop / edit
    """
    t = item.get("type", "")
    e = item.get("expected", "")
    conf = item.get("confidence", "")
    nl = item.get("nl", "")
    notes = item.get("notes", "")

    # 硬删规则
    if t == "数轴":
        return "drop", "数轴题话图不专门支持，且当前 refuse 分类里数轴已有 1 题足够"
    if "无法重建" in notes or "依赖题图" in notes:
        return "drop", "依赖原题图片，无法可靠重建"
    if conf == "low":
        return "drop", "LLM 置信度低，建议手动补题或跳过"
    if "求最值" in nl or "求最小" in nl or "求最大" in nl:
        return "edit", "NL 含求值任务，需去除只留作图部分"
    # 检查含具体坐标点是否合理
    if "A(" in nl and "坐标" not in nl and t not in ("坐标系", "函数图像"):
        return "edit", "NL 引用具体坐标点，改用几何关系描述"
    # 长度过长可能太复杂
    if len(nl) > 120:
        return "edit", "NL 过长（>120字），可考虑简化"
    # 立体几何 / 统计图表 保留作 refuse 测试
    if t in ("立体几何", "统计图表") and e == "refuse":
        return "keep", "作 refuse 类边界测试"
    # 标准 ok 类
    if e == "ok" and conf == "high":
        return "keep", "高置信 ok 题，直接采纳"
    if e == "ok" and conf == "medium":
        return "keep", "中置信 ok 题，采纳（若测试发现问题再改）"
    if e == "partial":
        return "keep", "partial 类正好测试话图边界"
    if e == "refuse":
        return "keep", "refuse 类拒绝测试"
    return "keep", "默认保留"


def main():
    zk = load_drawing(CANDIDATES_ZK)
    gk = load_drawing(CANDIDATES_GK)

    all_items = zk + gk
    print(f"总候选: {len(all_items)} 题")

    # 分组：type × expected
    groups: dict[tuple[str, str], list] = {}
    for it in all_items:
        key = (it.get("type", "?"), it.get("expected", "?"))
        groups.setdefault(key, []).append(it)

    lines = []
    lines.append("# 候选题审核工作表 · v0.12.1 真题数据集")
    lines.append("")
    lines.append(f"- 候选总数：**{len(all_items)}** 题（2021 中考 {len(zk)} + 2025 高考 {len(gk)}）")
    lines.append(f"- 目标数：45-50 题")
    lines.append(f"- Provider：火山方舟 GLM-5.2")
    lines.append("")
    lines.append("## 审核使用方法")
    lines.append("")
    lines.append("- 「AI 建议」列的三种决定：")
    lines.append("  - ✅ **keep** — 直接采纳")
    lines.append("  - ❌ **drop** — 删除（含理由）")
    lines.append("  - ⚠️ **edit** — 需修改（含建议）")
    lines.append("- 「你的决定」列请填写：`✅` / `❌` / `修改后 nl`")
    lines.append("- 空白 = 采纳 AI 建议")
    lines.append("")

    # 汇总统计
    lines.append("## 分布汇总")
    lines.append("")
    lines.append("| 类型 | ok | partial | refuse | 合计 |")
    lines.append("|---|---|---|---|---|")
    types = sorted({t for (t, _) in groups.keys()})
    for t in types:
        ok = len(groups.get((t, "ok"), []))
        pt = len(groups.get((t, "partial"), []))
        rf = len(groups.get((t, "refuse"), []))
        total = ok + pt + rf
        lines.append(f"| {t} | {ok} | {pt} | {rf} | {total} |")

    # AI 建议汇总
    keep = drop = edit = 0
    for it in all_items:
        d, _ = _suggest(it)
        if d == "keep": keep += 1
        elif d == "drop": drop += 1
        else: edit += 1
    lines.append("")
    lines.append(f"**AI 建议汇总**：keep={keep}, drop={drop}, edit={edit}")
    lines.append("")

    # 分组表：按类型 × expected 排序
    priority_order = [
        ("平面几何", "ok"),
        ("平面几何", "partial"),
        ("坐标系", "ok"),
        ("函数图像", "ok"),
        ("函数图像", "partial"),
        ("几何变换", "ok"),
        ("几何变换", "partial"),
        ("立体几何", "refuse"),
        ("统计图表", "refuse"),
        ("数轴", "refuse"),
        ("平面几何", "refuse"),
        ("函数图像", "refuse"),
        ("几何变换", "refuse"),
    ]
    # 补齐未在优先级里的组
    all_keys = list(groups.keys())
    for k in all_keys:
        if k not in priority_order:
            priority_order.append(k)

    seq = 1
    for key in priority_order:
        if key not in groups:
            continue
        items = groups[key]
        t, e = key
        lines.append(f"## {t} · {e}（{len(items)} 题）")
        lines.append("")
        lines.append("| # | ID | 来源 | 题号 | 置信 | AI 建议 | 理由 | NL | 你的决定 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for it in items:
            cid = _make_id(it.get("tag", ""), it.get("q_num", ""), seq)
            source = it.get("tag", "").replace("2021 中考", "zk21").replace("2025 高考·新课标II", "gk25")
            q_num = it.get("q_num", "")
            conf = it.get("confidence", "")
            nl = it.get("nl", "").replace("|", "\\|").replace("\n", " ")
            decision, reason = _suggest(it)
            marker = {"keep": "✅", "drop": "❌", "edit": "⚠️"}[decision]
            reason_short = reason[:40].replace("|", "\\|")
            nl_short = nl[:100]
            lines.append(f"| {seq} | {cid} | {source} | {q_num} | {conf} | {marker} {decision} | {reason_short} | {nl_short} |  |")
            seq += 1
        lines.append("")

    # 全表结尾
    lines.append("---")
    lines.append("")
    lines.append("## 审核完成后请回复")
    lines.append("")
    lines.append("在对话中告诉我：")
    lines.append("- 哪些行的「你的决定」是 `❌` （删除）")
    lines.append("- 哪些行需要修改（给出修改后的 NL）")
    lines.append("- 未标注的默认按 AI 建议采纳")
    lines.append("")
    lines.append("我会据此生成最终的 `chengdu_full.json` 数据集。")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"审核工作表写入：{OUT}")


if __name__ == "__main__":
    main()
