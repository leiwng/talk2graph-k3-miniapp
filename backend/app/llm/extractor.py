"""NL → DSL 抽取器。

流程：
1. 拼装 messages：system + few-shots + (current_dsl?) + user
2. 调用 Provider.chat(json_mode=True)
3. 解析 JSON → Pydantic 校验 → 语义校验
4. 失败则用 repair prompt 重试（最多 N 次）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import structlog

from ..dsl import DSL, DSLValidationError, validate
from .base import ChatMessage, LLMError, LLMProvider, parse_json_response

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Partial JSON 对象识别：匹配同一对象内的 "id": "X" 与 "kind": "Y"。
# `[^{}]*?` 确保不跨过 { }（即 id 和 kind 在同一对象层级，避免跨对象误配对）。
# 支持两种字段顺序：id 在前 / kind 在前（Pydantic 序列化默认 id 在前，
# 但 LLM 输出可能颠倒，特别是无 json_mode 时）。
_OBJ_PATTERN = re.compile(
    r'(?:'
    r'"id"\s*:\s*"(?P<id1>[^"]+)"[^{}]*?"kind"\s*:\s*"(?P<kind1>[^"]+)"'
    r'|'
    r'"kind"\s*:\s*"(?P<kind2>[^"]+)"[^{}]*?"id"\s*:\s*"(?P<id2>[^"]+)"'
    r')'
)


def _extract_seen_objects(buffer: str) -> set[tuple[str, str]]:
    """从 LLM 流式输出 buffer 中识别已出现的 (id, kind) 对。

    即便 JSON 还不完整（缺末尾的 } 或字段），只要 "id" 和 "kind" 两段都
    已输出，regex 就能匹配。用于 streaming 期间向用户预告已生成对象。

    支持两种字段顺序（id 在前 / kind 在前）。
    """
    result: set[tuple[str, str]] = set()
    for m in _OBJ_PATTERN.finditer(buffer):
        if m.group("id1") is not None:
            result.add((m.group("id1"), m.group("kind1")))
        else:
            result.add((m.group("id2"), m.group("kind2")))
    return result


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


def _load_fewshots(limit: int = 21) -> list[dict]:
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
    fewshot_limit: int = 21,
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
        # W13-B 修复：复杂题（如多 curve + on_curve + 多点）LLM 输出可达 4096 tokens 上限且耗时 >60s
        # 第一次用默认 60s timeout + 4096 max_tokens；
        # 若第一次超时（LLMError status=None），第二次用 120s + 8192 重试
        try:
            if attempt == 0:
                resp = await provider.chat(messages, json_mode=True, temperature=0.1)
            else:
                resp = await provider.chat(
                    messages, json_mode=True, temperature=0.1,
                    max_tokens=8192, timeout=120.0,
                )
        except LLMError as e:
            if e.status is None and attempt == 0:
                # 超时/网络错误，用更宽松参数重试一次
                log.info("llm.chat.timeout_retry", provider=provider.name)
                resp = await provider.chat(
                    messages, json_mode=True, temperature=0.1,
                    max_tokens=8192, timeout=120.0,
                )
            else:
                raise
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


# ---------------------------------------------------------------------------
# V2-D · 流式版 extract_dsl：边收 LLM token 边推给前端
# ---------------------------------------------------------------------------


async def extract_dsl_streaming(
    provider: LLMProvider,
    nl: str,
    *,
    current_dsl: DSL | None = None,
    max_repair: int = 2,
) -> AsyncIterator[dict]:
    """流式版 extract_dsl：yield 事件 dict 给上层（chat_stream 路由）。

    事件类型：
    - {"type": "token", "text": "..."}  — 每个 LLM token（delta.content）
    - {"type": "object_seen", "id": "A", "kind": "point"}  — 已识别的新对象
    - {"type": "done", "result": ExtractResult}  — LLM 完整返回 + parse 完成
    - {"type": "error", "error": LLMError}  — LLM 网络错误（不可恢复）

    与 extract_dsl 行为等价：复用 build_messages / parse_json_response /
    DSL 校验 / repair 循环。区别是中间过程推 token / object_seen 给前端。

    repair 阶段也流式（用户在第二次 LLM 调用期间也能看到 token）。
    """
    messages = build_messages(nl, current_dsl=current_dsl)
    last_raw = ""
    last_err: str | None = None

    for attempt in range(max_repair + 1):
        # W13-B 修复：复杂题（多 curve + on_curve + 多点）LLM 输出可达 4096 tokens
        # 上限且耗时 >60s。第一次用默认 timeout，第二次用 120s 重试。
        # 流式版：流式本身能缓解 timeout（边收边返回），但仍保留重试机制以应对网络断开。
        try:
            buffer = ""
            seen: set[tuple[str, str]] = set()
            timeout = 60.0 if attempt == 0 else 120.0
            max_tokens = 4096 if attempt == 0 else 8192
            async for token in provider.chat_stream(
                messages,
                json_mode=True,
                temperature=0.1,
                max_tokens=max_tokens,
                timeout=timeout,
            ):
                buffer += token
                yield {"type": "token", "text": token}
                # partial JSON 对象识别
                new_objs = _extract_seen_objects(buffer)
                for obj_id, kind in new_objs - seen:
                    seen.add((obj_id, kind))
                    yield {"type": "object_seen", "id": obj_id, "kind": kind}
        except LLMError as e:
            if e.status is None and attempt == 0:
                # 超时/网络错误，用更宽松参数重试一次（不 yield error，对前端透明）
                log.info("llm.chat_stream.timeout_retry", provider=provider.name)
                continue
            yield {"type": "error", "error": e}
            return

        last_raw = buffer
        try:
            parsed = parse_json_response(buffer)
        except ValueError as e:
            last_err = str(e)
            messages = _append_repair(messages, buffer, last_err)
            continue

        # 显式错误（LLM 主动拒绝）
        if (
            isinstance(parsed, dict)
            and "error" in parsed
            and "objects" not in parsed
            and "ops" not in parsed
        ):
            yield {
                "type": "done",
                "result": ExtractResult(
                    dsl=None,
                    patch=None,
                    raw=buffer,
                    provider=provider.name,
                    attempts=attempt + 1,
                    error=str(parsed["error"]),
                ),
            }
            return

        # patch 模式
        if isinstance(parsed, dict) and "ops" in parsed:
            yield {
                "type": "done",
                "result": ExtractResult(
                    dsl=None,
                    patch=parsed,
                    raw=buffer,
                    provider=provider.name,
                    attempts=attempt + 1,
                ),
            }
            return

        # 完整 DSL 模式
        try:
            dsl = DSL.model_validate(parsed)
            validate(dsl)
        except (DSLValidationError, ValueError, TypeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            log.info("llm.dsl.validate_fail", attempt=attempt, err=last_err)
            messages = _append_repair(messages, buffer, last_err)
            continue

        yield {
            "type": "done",
            "result": ExtractResult(
                dsl=dsl,
                patch=None,
                raw=buffer,
                provider=provider.name,
                attempts=attempt + 1,
            ),
        }
        return

    # 所有 repair 都失败
    yield {
        "type": "done",
        "result": ExtractResult(
            dsl=None,
            patch=None,
            raw=last_raw,
            provider=provider.name,
            attempts=max_repair + 1,
            error=last_err or "extraction failed",
        ),
    }
