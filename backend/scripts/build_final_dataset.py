"""从审核后的候选生成最终 chengdu_full.json 测试数据集。

策略：按审核结论——保留 AI 建议 keep 的、丢弃 AI 建议 drop 的（数轴 / 依赖题图 / 低置信）。
生成的 JSON 与 chengdu_selected.json 同结构，可直接用 eval_chengdu.py 跑。
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_ZK = PROJECT_ROOT / "test" / "chengdu" / "candidates_2021_zhongkao.json"
CANDIDATES_GK = PROJECT_ROOT / "test" / "chengdu" / "candidates_2025_gaokao.json"
OUT = PROJECT_ROOT / "test" / "chengdu" / "chengdu_full.json"


def load_drawing(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [x for x in data if x.get("is_drawing_task")]


def _should_drop(item) -> bool:
    """审核规则：drop 的条件（与 build_audit_worksheet.py 保持一致）。"""
    t = item.get("type", "")
    conf = item.get("confidence", "")
    notes = item.get("notes", "")
    if t == "数轴":
        return True
    if "无法重建" in notes or "依赖题图" in notes:
        return True
    if conf == "low":
        return True
    return False


def _make_id(prefix: str, seq: int) -> str:
    return f"{prefix}_{seq:03d}"


def main():
    zk = load_drawing(CANDIDATES_ZK)
    gk = load_drawing(CANDIDATES_GK)
    all_items = zk + gk

    kept = []
    dropped = []
    seq = 1

    for it in all_items:
        if _should_drop(it):
            dropped.append(it)
            continue
        prefix = "zk" if "中考" in it.get("tag", "") else "gk"
        entry = {
            "id": _make_id(prefix, seq),
            "source": it.get("tag", ""),
            "q_num": it.get("q_num", ""),
            "type": it.get("type", ""),
            "expected": it.get("expected", ""),
            "confidence": it.get("confidence", ""),
            "nl": it.get("nl", ""),
            "notes": it.get("notes", ""),
        }
        kept.append(entry)
        seq += 1

    # 稳定重编号：按 (source, q_num, type) 排序保证可复现
    kept.sort(key=lambda x: (x["source"], int(x.get("q_num") or "0"), x["type"]))
    # 重新分配连续 ID
    zk_seq = 1
    gk_seq = 1
    for e in kept:
        if e["source"].startswith("2021 中考"):
            e["id"] = _make_id("zk", zk_seq)
            zk_seq += 1
        else:
            e["id"] = _make_id("gk", gk_seq)
            gk_seq += 1

    OUT.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    print(f"输入候选：{len(all_items)} 题")
    print(f"保留：{len(kept)} 题")
    print(f"丢弃：{len(dropped)} 题")
    print("")
    print("保留分布：")
    from collections import Counter
    c_type = Counter(e["type"] for e in kept)
    c_expected = Counter(e["expected"] for e in kept)
    c_source = Counter(e["source"] for e in kept)
    for t, n in sorted(c_type.items(), key=lambda x: -x[1]):
        print(f"  {t:8}: {n}")
    print("")
    for e, n in sorted(c_expected.items(), key=lambda x: -x[1]):
        print(f"  {e:8}: {n}")
    print("")
    for s, n in sorted(c_source.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")
    print("")
    print(f"丢弃题目：")
    for d in dropped:
        print(f"  #{d.get('q_num')} [{d.get('type', '')}] {d.get('nl', '')[:50]}")

    print(f"\n写入: {OUT}")


if __name__ == "__main__":
    main()
