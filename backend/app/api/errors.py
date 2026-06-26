"""错误归类 → 中文可读消息。

用于把后端各种异常（LLM / 求解器 / DSL patch）翻成老师能看懂的提示。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..dsl.diff import DSLPatchError
from ..dsl.validator import DSLValidationError
from ..llm.base import LLMError
from ..solver.engine import SolveError


@dataclass
class FriendlyError:
    code: str             # 机器可读
    message: str          # 中文，给老师看
    hint: str | None = None
    detail: str | None = None  # 原始错误（折叠展示）


def classify(exc: Exception) -> FriendlyError:
    s = str(exc)

    if isinstance(exc, LLMError):
        if exc.status in (401, 403):
            return FriendlyError(
                "llm_auth",
                "LLM 服务鉴权失败，请检查 API Key 是否正确。",
                hint="到 .env 中重置 ZHIPU_API_KEY / DEEPSEEK_API_KEY / VOLCENGINE_API_KEY",
                detail=s,
            )
        if exc.status == 429:
            return FriendlyError(
                "llm_rate_limit",
                "LLM 调用过于频繁，请稍候再试，或切换到其他 Provider。",
                detail=s,
            )
        if exc.status is None:
            return FriendlyError(
                "llm_network",
                "无法连接 LLM 服务（网络异常或超时）。",
                hint="检查后端机器到 open.bigmodel.cn / ark.cn-beijing / api.deepseek.com 的网络",
                detail=s,
            )
        if exc.status and exc.status >= 500:
            return FriendlyError(
                "llm_server",
                "LLM 服务端出错，请重试或切换 Provider。",
                detail=s,
            )
        return FriendlyError("llm_error", "LLM 调用失败。", detail=s)

    if isinstance(exc, SolveError):
        if "fail to converge" in s.lower() or "residual" in s.lower():
            return FriendlyError(
                "solve_no_converge",
                "无法满足全部几何条件，请检查约束是否过紧或自相矛盾。",
                hint="试着减少 1 条约束（如去掉一条边长或角度）",
                detail=s,
            )
        return FriendlyError("solve_error", "几何无解。", detail=s)

    if isinstance(exc, DSLPatchError):
        if "index out of range" in s.lower():
            return FriendlyError(
                "patch_index",
                "修改失败：要操作的对象/约束不存在。",
                hint="可能是 AI 输出了过期的索引，请重试或换个说法",
                detail=s,
            )
        if "key not found" in s.lower():
            return FriendlyError(
                "patch_key",
                "修改失败：找不到要替换的字段。",
                detail=s,
            )
        if "resulting dsl invalid" in s.lower():
            return FriendlyError(
                "patch_invalid_dsl",
                "修改后图形不合法（可能删除了被引用的对象）。",
                hint="先删掉用到该对象的约束/线段，再删点",
                detail=s,
            )
        return FriendlyError("patch_error", "修改失败。", detail=s)

    if isinstance(exc, DSLValidationError):
        return FriendlyError(
            "dsl_invalid",
            "AI 输出的图形描述不合法（已自动重试 2 次）。",
            hint="请尝试换个说法，或切换 Provider",
            detail=s,
        )

    # 未知异常
    return FriendlyError("unknown", "发生未知错误。", detail=s[:200])


def to_dict(fe: FriendlyError) -> dict:
    return {
        "code": fe.code,
        "message": fe.message,
        "hint": fe.hint,
        "detail": fe.detail,
    }


# 求解失败时再深入定位"哪条约束最难"
def diagnose_solve_failure(residual_per_constraint: list[tuple[str, float]]) -> str | None:
    """求解残差按约束分解后，给出最违反的那条的可读描述。"""
    if not residual_per_constraint:
        return None
    worst = max(residual_per_constraint, key=lambda x: abs(x[1]))
    name, r = worst
    if abs(r) < 1e-3:
        return None
    return f"最难满足的约束：{name}（残差 {r:.3f}）"
