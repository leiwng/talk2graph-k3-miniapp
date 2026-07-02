"""LLM 辅助真题抽取脚本（Phase 1）。

用法：
  .venv/bin/python scripts/build_dataset_from_pdf.py \
      --pdf "path/to/paper.pdf" \
      --tag "2021 中考·北京" \
      --out test/chengdu/candidates_xxx.json

流程：
  1. pdftotext -layout 提取 PDF 全文
  2. 按题号（如"5．" / "1．（2 分）"）粗切分为段
  3. 关键词粗筛"作图相关段"
  4. 每段调用 LLM（用 scripts/extract_prompt.txt）判断+抽取
  5. 输出候选 JSON 供人工审核
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import settings  # noqa: F401 触发 dotenv
from app.llm.base import ChatMessage
from app.llm.router import LLMRouter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "scripts" / "extract_prompt.txt"


# 作图相关关键词（粗筛）
DRAWING_KEYWORDS = [
    "如图", "画", "作", "连接", "延长", "过", "交", "垂足", "中点", "平分",
    "△", "⊙", "∠", "⊥", "∥",
    "三角形", "四边形", "五边形", "六边形", "矩形", "正方形", "菱形", "梯形",
    "平行四边形", "圆", "抛物线", "椭圆", "双曲线", "半径", "直径",
    "内切", "外接", "内接", "切线", "弦",
    "函数图象", "函数图像", "y=", "y =", "反比例",
    "旋转", "平移", "对称", "翻折", "翻转", "折叠",
    "四棱锥", "三棱锥", "棱柱", "圆柱", "圆锥", "球", "三视图", "展开图",
    "柱状图", "饼图", "折线图", "直方图", "扇形图",
    "坐标系", "象限", "数轴", "格点",
]


# 段边界：题号（如 "5．" / "5. " / "5、" / "5：" 或 " 5   xxx"）
# 中考卷常用："5．（3 分）..."
# 高考卷（如 2025 新课标II）："^ 5    xxx"（前置空格 + 数字 + 大段空白）
# 兼容两种格式
QUESTION_START = re.compile(
    r"(?:^|\n)"
    r"(?:"
    r"  \s*(?P<num1>\d{1,3})[．\.、]\s*(?:\(\d+\s*分\)|\（\d+\s*分\）)?"    # 中考格式：5．(3 分)
    r"|"
    r"  \s{1,4}(?P<num2>\d{1,3})\s{2,}"                                     # 高考格式：" 5    xxx"
    r")",
    re.VERBOSE,
)


@dataclass
class Candidate:
    tag: str
    q_num: str
    raw_text: str
    is_drawing_task: bool | None = None
    nl: str = ""
    type: str = ""
    expected: str = ""
    confidence: str = ""
    notes: str = ""
    reason: str = ""       # 非作图题的原因
    llm_error: str = ""


def pdftotext_extract(pdf_path: Path) -> str:
    """调用 pdftotext -layout 提取纯文本。"""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def split_questions(text: str) -> list[tuple[str, str]]:
    """按题号切分为 [(题号, 原文段), ...]。

    简单策略：找所有 "N．" 或 " N  " 的位置，两两之间作为一段。
    """
    matches = list(QUESTION_START.finditer(text))
    segments: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        num = m.group("num1") or m.group("num2")
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[start:end].strip()
        # 过滤太短或太长的段（噪声）
        if 20 < len(seg) < 3000:
            segments.append((num, seg))
    return segments


def looks_like_drawing(seg: str) -> bool:
    """粗筛：段内含至少 1 个作图关键词。"""
    return any(kw in seg for kw in DRAWING_KEYWORDS)


async def call_llm(provider, seg: str, prompt: str) -> dict | None:
    """把 seg 送 LLM，让它抽题。返回解析后的 dict 或 None。"""
    messages = [
        ChatMessage("system", prompt),
        ChatMessage("user", f"题目原文：\n{seg}\n\n请输出 JSON。"),
    ]
    resp = await provider.chat(messages, json_mode=True, temperature=0.1, max_tokens=800)
    content = resp.content.strip()
    # 尝试提取 JSON（LLM 有时会返回带 ```json 包裹的）
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?|\n?```$", "", content, flags=re.MULTILINE)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试找第一个 { 到最后一个 } 之间
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None


async def process_segment(
    provider, tag: str, num: str, seg: str, prompt: str
) -> Candidate:
    c = Candidate(tag=tag, q_num=num, raw_text=seg[:500])   # 只保留前 500 字符避免 JSON 过大
    try:
        data = await call_llm(provider, seg, prompt)
    except Exception as e:
        c.llm_error = f"{type(e).__name__}: {e}"
        return c

    if data is None:
        c.llm_error = "JSON 解析失败"
        return c

    c.is_drawing_task = bool(data.get("is_drawing_task"))
    if c.is_drawing_task:
        c.nl = str(data.get("nl", "")).strip()
        c.type = str(data.get("type", "")).strip()
        c.expected = str(data.get("expected", "")).strip()
        c.confidence = str(data.get("confidence", "")).strip()
        c.notes = str(data.get("notes", "")).strip()
    else:
        c.reason = str(data.get("reason", "")).strip()
    return c


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="PDF 文件路径")
    ap.add_argument("--tag", required=True, help="来源标签，如 '2021 中考·北京'")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None, help="限制处理段数（调试用）")
    ap.add_argument("--only-drawing", action="store_true",
                    help="只处理粗筛后的作图段（默认开启）")
    args = ap.parse_args()

    pdf = Path(args.pdf).expanduser()
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. 提取
    print(f"[1/4] pdftotext 提取：{pdf.name}")
    text = pdftotext_extract(pdf)
    print(f"      共 {len(text)} 字符")

    # 2. 切段
    print("[2/4] 按题号切分")
    segments = split_questions(text)
    print(f"      共 {len(segments)} 段候选")

    # 3. 粗筛
    drawing_segs = [(n, s) for n, s in segments if looks_like_drawing(s)]
    print(f"      粗筛后（含作图关键词）：{len(drawing_segs)} 段")

    if args.limit:
        drawing_segs = drawing_segs[: args.limit]
        print(f"      --limit 限制到前 {args.limit} 段")

    # 4. LLM 抽题
    print(f"[3/4] LLM 抽题（concurrency={args.concurrency}）")
    router = LLMRouter()
    provider = router.get()
    print(f"      Provider: {provider.name} / {provider.model}")

    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    sem = asyncio.Semaphore(args.concurrency)
    results: list[Candidate] = []

    async def _one(num, seg):
        async with sem:
            r = await process_segment(provider, args.tag, num, seg, prompt)
            if r.llm_error:
                mark = "⚠️ "
                info = r.llm_error
            elif r.is_drawing_task:
                mark = "✅" if r.expected == "ok" else "🟡" if r.expected == "partial" else "❌"
                info = f"[{r.type[:8]:8}] {r.expected:7} conf={r.confidence:4} : {r.nl[:60]}"
            else:
                mark = "  "
                info = f"skip: {r.reason[:60]}"
            print(f"  {mark} #{num:3}  {info}")
            return r

    t0 = time.perf_counter()
    tasks = [_one(n, s) for n, s in drawing_segs]
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    print(f"\n[4/4] 完成 {len(results)} 段，耗时 {elapsed:.1f}s")

    # 5. 写候选 JSON
    out_data = [asdict(r) for r in results]
    out.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. 汇总
    drawing_count = sum(1 for r in results if r.is_drawing_task)
    ok = sum(1 for r in results if r.expected == "ok")
    partial = sum(1 for r in results if r.expected == "partial")
    refuse = sum(1 for r in results if r.expected == "refuse")
    print(f"\n作图题: {drawing_count} / {len(results)}")
    print(f"  ok:      {ok}")
    print(f"  partial: {partial}")
    print(f"  refuse:  {refuse}")
    print(f"\n候选写入：{out}")


if __name__ == "__main__":
    asyncio.run(main())
