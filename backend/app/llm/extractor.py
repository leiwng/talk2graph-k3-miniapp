"""NL → DSL 抽取器。

流程：
1. 拼装 messages：system + few-shots + (current_dsl?) + user
2. 调用 Provider.chat(json_mode=True)
3. 解析 JSON → Pydantic 校验 → 语义校验
4. 失败则用 repair prompt 重试（最多 N 次）
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from ..dsl import DSL, DSLValidationError, validate
from .base import ChatMessage, LLMProvider, parse_json_response

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class ExtractResult:
    dsl: DSL | None
    patch: dict | None
    raw: str
    provider: str
    attempts: int
    error: str | None = None


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")


def _load_repair_prompt() -> str:
    return (PROMPTS_DIR / "repair.txt").read_text(encoding="utf-8")


def _load_fewshots(limit: int = 20) -> list[dict]:
    path = PROMPTS_DIR / "fewshots.jsonl"
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if i >= limit:
            break
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def build_messages(
    nl: str,
    *,
    current_dsl: DSL | None = None,
    fewshot_limit: int = 20,
) -> list[ChatMessage]:
    msgs: list[ChatMessage] = [ChatMessage("system", _load_system_prompt())]
    for ex in _load_fewshots(fewshot_limit):
        msgs.append(ChatMessage("user", ex["nl"]))
        msgs.append(ChatMessage("assistant", json.dumps(ex["dsl"], ensure_ascii=False)))
    if current_dsl is not None:
        msgs.append(ChatMessage(
            "user",
            "当前图形 DSL（请基于它输出 patch）：\n"
            + json.dumps(current_dsl.to_json_dict(), ensure_ascii=False),
        ))
    msgs.append(ChatMessage("user", nl))
    return msgs


async def extract_dsl(
    provider: LLMProvider,
    nl: str,
    *,
    current_dsl: DSL | None = None,
    max_repair: int = 2,
) -> ExtractResult:
    """把自然语言转为 DSL 或 DSL patch。"""
    messages = build_messages(nl, current_dsl=current_dsl)
    last_raw = ""
    last_err: str | None = None

    for attempt in range(max_repair + 1):
        resp = await provider.chat(messages, json_mode=True, temperature=0.1)
        last_raw = resp.content
        try:
            parsed = parse_json_response(resp.content)
        except ValueError as e:
            last_err = str(e)
            messages = _append_repair(messages, resp.content, last_err)
            continue

        # 显式错误
        if isinstance(parsed, dict) and "error" in parsed and "objects" not in parsed and "ops" not in parsed:
            return ExtractResult(
                dsl=None, patch=None, raw=resp.content,
                provider=provider.name, attempts=attempt + 1,
                error=str(parsed["error"]),
            )

        # patch 模式
        if isinstance(parsed, dict) and "ops" in parsed:
            return ExtractResult(
                dsl=None, patch=parsed, raw=resp.content,
                provider=provider.name, attempts=attempt + 1,
            )

        # 完整 DSL 模式
        try:
            dsl = DSL.model_validate(parsed)
            validate(dsl)
        except (DSLValidationError, ValueError, TypeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            log.info("llm.dsl.validate_fail", attempt=attempt, err=last_err)
            messages = _append_repair(messages, resp.content, last_err)
            continue

        return ExtractResult(
            dsl=dsl, patch=None, raw=resp.content,
            provider=provider.name, attempts=attempt + 1,
        )

    return ExtractResult(
        dsl=None, patch=None, raw=last_raw,
        provider=provider.name, attempts=max_repair + 1,
        error=last_err or "extraction failed",
    )


def _append_repair(
    messages: list[ChatMessage], bad_output: str, errors: str
) -> list[ChatMessage]:
    repair = _load_repair_prompt().format(errors=errors)
    return messages + [
        ChatMessage("assistant", bad_output),
        ChatMessage("user", repair),
    ]
