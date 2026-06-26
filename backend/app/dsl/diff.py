"""DSL diff 应用器。

只支持 JSON Patch (RFC 6902) 的子集：
- add    : path 以 "/-" 结尾时 append；否则 insert
- remove : 删除
- replace: 替换

路径形如：
  /constraints/2/value
  /objects/-
  /constraints/0

应用流程：
  1. 把 DSL 序列化为 dict
  2. 顺序执行 ops（任一失败即回滚，整体抛错）
  3. 重新 model_validate + validate
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from .schema import DSL
from .validator import DSLValidationError, validate


class DSLPatchError(ValueError):
    pass


@dataclass
class PatchOp:
    op: str        # "add" | "remove" | "replace"
    path: str
    value: Any = None


_VALID_OPS = {"add", "remove", "replace"}


def parse_ops(raw: dict | list) -> list[PatchOp]:
    if isinstance(raw, dict):
        ops_raw = raw.get("ops", [])
    else:
        ops_raw = raw
    out: list[PatchOp] = []
    for i, o in enumerate(ops_raw):
        if not isinstance(o, dict):
            raise DSLPatchError(f"op[{i}]: not an object")
        op = o.get("op")
        path = o.get("path")
        if op not in _VALID_OPS:
            raise DSLPatchError(f"op[{i}]: unknown op {op!r}")
        if not isinstance(path, str) or not path.startswith("/"):
            raise DSLPatchError(f"op[{i}]: invalid path {path!r}")
        out.append(PatchOp(op=op, path=path, value=o.get("value")))
    return out


def apply_patch(dsl: DSL, ops_or_raw: list[PatchOp] | dict | list) -> DSL:
    """对 DSL 应用 patch，返回新 DSL（不修改原对象）。"""
    if isinstance(ops_or_raw, (dict, list)):
        ops = parse_ops(ops_or_raw)
    else:
        ops = ops_or_raw

    data = copy.deepcopy(dsl.model_dump(mode="json"))
    for i, op in enumerate(ops):
        try:
            data = _apply_one(data, op)
        except DSLPatchError:
            raise
        except Exception as e:
            raise DSLPatchError(f"op[{i}] ({op.op} {op.path}): {e}") from e

    try:
        new_dsl = DSL.model_validate(data)
        validate(new_dsl)
    except (DSLValidationError, ValueError, TypeError) as e:
        raise DSLPatchError(f"resulting DSL invalid: {e}") from e
    return new_dsl


# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"~1|~0|[^/]+")


def _split_path(path: str) -> list[str]:
    if path == "/":
        return []
    if not path.startswith("/"):
        raise DSLPatchError(f"invalid path: {path!r}")
    # JSON Pointer 转义：~1 -> /，~0 -> ~
    parts = path[1:].split("/")
    out = []
    for p in parts:
        p = p.replace("~1", "/").replace("~0", "~")
        out.append(p)
    return out


def _apply_one(root: Any, op: PatchOp) -> Any:
    tokens = _split_path(op.path)
    if not tokens:
        raise DSLPatchError("cannot operate on root")

    parent_tokens, last = tokens[:-1], tokens[-1]
    parent = _resolve(root, parent_tokens)

    if op.op == "add":
        if isinstance(parent, list):
            if last == "-":
                parent.append(op.value)
            else:
                idx = _to_int(last, op.path)
                if idx < 0 or idx > len(parent):
                    raise DSLPatchError(f"index out of range: {op.path}")
                parent.insert(idx, op.value)
        elif isinstance(parent, dict):
            parent[last] = op.value
        else:
            raise DSLPatchError(f"cannot add into {type(parent).__name__}")
    elif op.op == "remove":
        if isinstance(parent, list):
            idx = _to_int(last, op.path)
            if idx < 0 or idx >= len(parent):
                raise DSLPatchError(f"index out of range: {op.path}")
            parent.pop(idx)
        elif isinstance(parent, dict):
            if last not in parent:
                raise DSLPatchError(f"key not found: {op.path}")
            parent.pop(last)
        else:
            raise DSLPatchError(f"cannot remove from {type(parent).__name__}")
    elif op.op == "replace":
        if isinstance(parent, list):
            idx = _to_int(last, op.path)
            if idx < 0 or idx >= len(parent):
                raise DSLPatchError(f"index out of range: {op.path}")
            parent[idx] = op.value
        elif isinstance(parent, dict):
            if last not in parent:
                raise DSLPatchError(f"key not found: {op.path}")
            parent[last] = op.value
        else:
            raise DSLPatchError(f"cannot replace in {type(parent).__name__}")
    return root


def _resolve(root: Any, tokens: list[str]) -> Any:
    cur = root
    for t in tokens:
        if isinstance(cur, list):
            i = _to_int(t, "/".join(tokens))
            if i < 0 or i >= len(cur):
                raise DSLPatchError(f"index out of range: {t}")
            cur = cur[i]
        elif isinstance(cur, dict):
            if t not in cur:
                raise DSLPatchError(f"key not found: {t}")
            cur = cur[t]
        else:
            raise DSLPatchError(f"cannot traverse into {type(cur).__name__}")
    return cur


def _to_int(s: str, path: str) -> int:
    try:
        return int(s)
    except ValueError:
        raise DSLPatchError(f"expected integer index in {path}, got {s!r}")
