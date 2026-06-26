"""把 v1 中 56 题的"原题描述"改写成"明确作图指令"，输出 v2_rewritten。

改写目标：
- 把"已知 / 求证 / 求 ..."这种考题语气，转成"画 ... "这种作图语气
- 去掉与作图无关的内容（"求面积"、"求最大值"、"求度数"等）
- 保留所有几何关键信息（顶点、边长、角度、特殊关系）
- 一句话或两句话搞定
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from app.config import settings
from app.llm.base import ChatMessage
from app.llm.router import LLMRouter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = PROJECT_ROOT / "test"

SRC_FILE = TEST_DIR / "cmm_test_v1_original.json"
OUT_FILE = TEST_DIR / "cmm_test_v2_rewritten.json"

SYSTEM_PROMPT = """你是数学题作图指令改写助手。

输入是一道中国 K12 / 高中数学考题（可能含 LaTeX 公式、求证/求解语言），
你的任务：把它改写为**一句明确的作图指令**，让作图工具可以直接画出题目中描述的图形。

# 改写准则
1. 用"画 ..."、"作 ..."开头
2. 保留所有几何要素：顶点字母、边长、角度、特殊位置（中点/垂足/切线等）
3. 去掉考题部分：「求...」「求证...」「问...」「比较...大小」「下列哪个正确」「填空」全部删掉
4. 把 LaTeX 数学符号改成中文/普通文字：
   - $\\triangle ABC$ → 三角形 ABC
   - $\\angle B$ → 角 B 或 ∠B
   - $\\sqrt{3}$ → √3
   - $30^{\\circ}$ → 30°
   - $\\frac{a}{b}$ → a/b
   - $\\overrightarrow{AB}$ → 向量 AB
5. 如果题目本身**没有可画图形**（纯计算 / 纯代数 / 纯三视图选择 / 单位换算），输出：
   `{"skip": "原因简述"}`
6. 输出 JSON 格式：`{"rewritten": "画...."}` 或 `{"skip": "..."}`，不要 Markdown 代码块。

# 示例
输入：已知 $\\triangle ABC$ 中, $AB=5, BC=6, AC=7$, 求面积
输出：{"rewritten": "画三角形 ABC，AB=5，BC=6，AC=7"}

输入：如图, $Rt \\triangle ABC$ 的两条直角边 $AC, BC$ 的长分别为 3,4, 以 $AC$ 为直径作圆与斜边 $AB$ 交于点 $D$, 则 $AD=$
输出：{"rewritten": "画直角三角形 ABC，C 为直角顶点，AC=3，BC=4；以 AC 为直径画圆，圆与斜边 AB 相交于点 D"}

输入：$\\sin^2 \\alpha + \\cos^2 \\alpha = ?$
输出：{"skip": "纯三角恒等式，无几何图形"}

输入：(本题8分) 求函数 $f(x)=|\\sin(2x-\\pi/6)|$ 的最小正周期
输出：{"skip": "求函数周期，与作图无关"}
"""


def _clean_latex(s: str) -> str:
    """轻度清理，让输入更可读。"""
    s = re.sub(r"\(本(小)?题[\d.]+分\)", "", s)
    s = s.replace(r"\$", "$").replace(r"\qquad", "____").replace(r"\quad", "  ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def rewrite_one(provider, item: dict) -> dict:
    """返回 dict：要么含 rewritten，要么含 skip。"""
    src = _clean_latex(item.get("description") or item.get("full_question") or "")
    msgs = [
        ChatMessage("system", SYSTEM_PROMPT),
        ChatMessage("user", src),
    ]
    try:
        resp = await provider.chat(msgs, json_mode=True, temperature=0.0, max_tokens=512, timeout=60)
    except Exception as e:
        return {"skip": f"LLM 调用失败: {e}", "_raw": ""}

    raw = resp.content.strip()
    # 解析 JSON
    text = raw
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
        if m:
            text = m.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # 尝试截取大括号
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            try:
                obj = json.loads(text[s : e + 1])
            except Exception:
                return {"skip": "LLM 输出无法解析为 JSON", "_raw": raw[:200]}
        else:
            return {"skip": "LLM 输出无法解析为 JSON", "_raw": raw[:200]}

    if "rewritten" in obj and obj["rewritten"]:
        return {"rewritten": obj["rewritten"], "_raw": raw}
    if "skip" in obj:
        return {"skip": obj["skip"], "_raw": raw}
    return {"skip": "LLM 输出无 rewritten/skip 字段", "_raw": raw[:200]}


async def main():
    src = json.loads(SRC_FILE.read_text(encoding="utf-8"))
    print(f"读入 {SRC_FILE.name}：{len(src)} 题")

    router = LLMRouter()
    provider = router.get()
    print(f"使用 Provider: {provider.name} / {provider.model}")
    print()

    sem = asyncio.Semaphore(6)
    out: list[dict | None] = [None] * len(src)

    async def _one(i: int, item: dict):
        async with sem:
            t0 = time.perf_counter()
            r = await rewrite_one(provider, item)
            ms = int((time.perf_counter() - t0) * 1000)
            tag = "OK" if "rewritten" in r else "SKIP"
            preview = (r.get("rewritten") or r.get("skip") or "")[:50]
            print(f"  #{i+1:3d}/{len(src)} [{tag:4}] [{item['subject']:6}] {ms:5d}ms  {preview}")

            new_item = {
                "id": item["id"],
                "subject": item["subject"],
                "difficulty": item["difficulty"],
                "original_description": item.get("description", ""),
                "full_question": item.get("full_question", ""),
                "rewritten": r.get("rewritten"),
                "skip_reason": r.get("skip"),
                "rewrite_status": "done" if "rewritten" in r else "skipped",
            }
            out[i] = new_item

    await asyncio.gather(*[_one(i, item) for i, item in enumerate(src)])

    # 统计
    done = sum(1 for x in out if x and x["rewrite_status"] == "done")
    skipped = sum(1 for x in out if x and x["rewrite_status"] == "skipped")
    print(f"\n✓ 改写完成：done={done}, skipped={skipped}, total={len(out)}")

    OUT_FILE.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ 已写入：{OUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
