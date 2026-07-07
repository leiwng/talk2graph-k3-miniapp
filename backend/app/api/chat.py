"""Chat 路由：NL → DSL（首轮）或 DSL patch（后续）→ 求解 → 渲染。

W3 范围：JSON 响应（非流式）。SSE 流式留到 W4 前端接入时一并实现。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..dsl import DSL, DSLPatchError, apply_patch
from ..llm import LLMError, extract_dsl, get_router
from ..llm.base import LLMProvider
from ..render import render_svg
from ..session import repo as repo_mod
from ..solver import SolveError, solve
from .deps import db_dep, require_session
from .errors import classify, to_dict

router = APIRouter(prefix="/api", tags=["chat"])

# Provider 注入点（测试可覆盖）
_provider_override: LLMProvider | None = None


def set_provider_override(p: LLMProvider | None) -> None:
    global _provider_override
    _provider_override = p


def _pick_provider(name: str | None) -> LLMProvider:
    if _provider_override is not None:
        return _provider_override
    return get_router().get(name)


class ChatReq(BaseModel):
    nl: str
    provider: str | None = None


@router.post("/session/{sid}/chat")
async def chat(
    sid: str, req: ChatReq, db: AsyncSession = Depends(db_dep)
) -> dict[str, Any]:
    await require_session(db, sid)

    provider = _pick_provider(req.provider)

    # 1. 记录 user 消息
    await repo_mod.add_message(db, sid, role="user", content=req.nl)

    # 2. 取当前 DSL（用于 patch 模式）
    cur = await repo_mod.current_snapshot(db, sid)
    current_dsl = cur.dsl if cur else None

    # 3. 调 LLM
    try:
        result = await extract_dsl(provider, req.nl, current_dsl=current_dsl)
    except LLMError as e:
        fe = classify(e)
        await repo_mod.add_message(
            db, sid, role="assistant", content=fe.message,
            llm_provider=getattr(provider, "name", None),
            error_kind="network",
        )
        raise HTTPException(502, detail=to_dict(fe))

    if result.error:
        # LLM 主动拒绝（如「不支持抛物线」）— 友好化展示
        product_msg = _make_refuse_message(result.error)
        await repo_mod.add_message(
            db, sid, role="assistant", content=product_msg,
            llm_provider=result.provider,
            error_kind="refuse",
        )
        return {
            "ok": False,
            "error_kind": "refuse",
            "error": product_msg,
            "raw_reason": result.error,
            "provider": result.provider,
        }

    # 4. patch 或完整 DSL → 得到 new_dsl
    fallback_used = False
    fallback_reason: str | None = None
    if result.patch is not None:
        if current_dsl is None:
            raise HTTPException(400, detail="收到 patch 但当前没有 DSL")
        try:
            new_dsl = apply_patch(current_dsl, result.patch)
            patch_for_log = json.dumps(result.patch, ensure_ascii=False)
        except DSLPatchError as e:
            # W10：patch 不合法时自动 fallback —— 把 user nl 再发一次，不带 current_dsl
            patch_err = str(e)
            try:
                fb_result = await extract_dsl(provider, req.nl, current_dsl=None)
            except LLMError as e2:
                fe = classify(e2)
                await repo_mod.add_message(
                    db, sid, role="assistant", content=fe.message,
                    llm_provider=getattr(provider, "name", None),
                    error_kind="network",
                )
                raise HTTPException(502, detail=to_dict(fe))

            if fb_result.error or fb_result.dsl is None:
                # fallback 也失败：返回原 patch 错误 + fallback 错误
                fe = classify(e)
                fb_detail = fb_result.error if fb_result.error else "fallback 重画失败"
                if fe.detail:
                    fe.detail = f"{fe.detail}\n[fallback]: {fb_detail}"
                else:
                    fe.detail = f"[fallback]: {fb_detail}"
                await repo_mod.add_message(
                    db, sid, role="assistant", content=fe.message,
                    dsl_patch_json=json.dumps(result.patch, ensure_ascii=False),
                    llm_provider=result.provider,
                    error_kind="patch",
                )
                raise HTTPException(422, detail=to_dict(fe))

            new_dsl = fb_result.dsl
            fallback_used = True
            fallback_reason = patch_err
            patch_for_log = None  # fallback 后是全量 DSL，不再有 patch
    else:
        assert result.dsl is not None
        new_dsl = result.dsl
        patch_for_log = None

    # 5. 求解
    solve_repaired = False
    solve_repair_reason: str | None = None
    try:
        sol = solve(new_dsl, seed=0, restarts=20, restarts_extra=40)
    except SolveError as e:
        # W13-B：若残差 > 1e-2，说明约束真的病态；把诊断发给 LLM 让它修正 DSL
        original_err = e
        residual = getattr(e, "residual", float("nan"))
        diagnosis = getattr(e, "worst_constraint", "")

        should_repair = residual == residual and residual > 1e-2   # 排除 nan
        if should_repair:
            try:
                repair_dsl = await _repair_solve_with_llm(
                    provider, req.nl, residual, diagnosis
                )
            except Exception:
                repair_dsl = None

            if repair_dsl is not None:
                try:
                    sol = solve(repair_dsl, seed=0, restarts=20, restarts_extra=40)
                    new_dsl = repair_dsl
                    patch_for_log = None
                    solve_repaired = True
                    solve_repair_reason = f"原残差 {residual:.2e}，{diagnosis[:100]}"
                except SolveError:
                    # 修复也失败，用原错误
                    fe = classify(original_err)
                    if fe.detail:
                        fe.detail = f"{fe.detail}\n[solve_repair 也失败]"
                    else:
                        fe.detail = "[solve_repair 也失败]"
                    await repo_mod.add_message(
                        db, sid, role="assistant", content=fe.message,
                        dsl_patch_json=patch_for_log,
                        llm_provider=result.provider,
                        error_kind="solve",
                    )
                    raise HTTPException(422, detail=to_dict(fe))
            else:
                # LLM 修复调用失败
                fe = classify(original_err)
                await repo_mod.add_message(
                    db, sid, role="assistant", content=fe.message,
                    dsl_patch_json=patch_for_log,
                    llm_provider=result.provider,
                    error_kind="solve",
                )
                raise HTTPException(422, detail=to_dict(fe))
        else:
            fe = classify(original_err)
            await repo_mod.add_message(
                db, sid, role="assistant", content=fe.message,
                dsl_patch_json=patch_for_log,
                llm_provider=result.provider,
                error_kind="solve",
            )
            raise HTTPException(422, detail=to_dict(fe))

    # 6. 渲染 SVG
    svg = render_svg(new_dsl, sol)
    sol_dict = {
        "coordinates": {k: list(v) for k, v in sol.coordinates.items()},
        "circles": {
            k: {"center": list(v["center"]), "radius": v["radius"]}
            for k, v in sol.circles.items()
        },
        "residual": sol.residual,
        "method": sol.method,
    }

    # 7. 保存 snapshot + assistant 消息
    snap = await repo_mod.push_snapshot(db, sid, new_dsl, solution=sol_dict)
    await repo_mod.add_message(
        db, sid, role="assistant",
        content=json.dumps(new_dsl.to_json_dict(), ensure_ascii=False),
        dsl_patch_json=patch_for_log,
        llm_provider=result.provider,
        fallback=True if fallback_used else None,
    )

    return {
        "ok": True,
        "seq": snap.seq,
        "dsl": new_dsl.to_json_dict(),
        "solution": sol_dict,
        "svg": svg,
        "provider": result.provider,
        "attempts": result.attempts,
        "error_kind": None,
        "fallback": fallback_used,
        "fallback_reason": fallback_reason if fallback_used else None,
        "solve_repaired": solve_repaired,
        "solve_repair_reason": solve_repair_reason if solve_repaired else None,
    }


class PatchReq(BaseModel):
    """属性面板等直接传 DSL patch（不经 LLM）。"""

    ops: list[dict]
    rationale: str | None = None


@router.post("/session/{sid}/patch")
async def apply_dsl_patch(
    sid: str, req: PatchReq, db: AsyncSession = Depends(db_dep)
) -> dict[str, Any]:
    await require_session(db, sid)
    cur = await repo_mod.current_snapshot(db, sid)
    if cur is None:
        raise HTTPException(400, detail="当前没有 DSL")
    try:
        new_dsl = apply_patch(cur.dsl, {"ops": req.ops})
    except DSLPatchError as e:
        raise HTTPException(422, detail=to_dict(classify(e)))
    try:
        sol = solve(new_dsl, seed=0, restarts=20, restarts_extra=40)
    except SolveError as e:
        raise HTTPException(422, detail=to_dict(classify(e)))

    sol_dict = {
        "coordinates": {k: list(v) for k, v in sol.coordinates.items()},
        "circles": {
            k: {"center": list(v["center"]), "radius": v["radius"]}
            for k, v in sol.circles.items()
        },
        "residual": sol.residual,
        "method": sol.method,
    }
    svg = render_svg(new_dsl, sol)
    snap = await repo_mod.push_snapshot(db, sid, new_dsl, solution=sol_dict)
    return {
        "ok": True,
        "seq": snap.seq,
        "dsl": new_dsl.to_json_dict(),
        "solution": sol_dict,
        "svg": svg,
    }


# ---------------------------------------------------------------------------
# W13-B · Solve repair 回路：把 solver 诊断发给 LLM 让它修正 DSL
# ---------------------------------------------------------------------------

async def _repair_solve_with_llm(
    provider: LLMProvider, nl: str, residual: float, diagnosis: str
) -> DSL | None:
    """求解失败时让 LLM 基于诊断修正 DSL。返回修正后的 DSL 或 None。"""
    from pathlib import Path
    from ..dsl import DSLValidationError, validate
    from ..llm.base import ChatMessage, parse_json_response

    prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "repair_solve.txt"
    if not prompt_path.exists():
        return None

    template = prompt_path.read_text(encoding="utf-8")
    user_msg = template.format(residual=f"{residual:.3e}", diagnosis=diagnosis, nl=nl)

    # 加载 system + few-shots 作上下文（与 extract_dsl 一致）
    from ..llm.extractor import build_messages
    messages = build_messages(nl=user_msg, current_dsl=None)

    resp = await provider.chat(messages, json_mode=True, temperature=0.1)
    try:
        parsed = parse_json_response(resp.content)
    except ValueError:
        return None

    if not isinstance(parsed, dict) or "objects" not in parsed:
        return None

    try:
        dsl = DSL.model_validate(parsed)
        validate(dsl)
    except (DSLValidationError, ValueError, TypeError):
        return None
    return dsl


async def _repair_solve_with_llm_streaming(
    provider: LLMProvider, nl: str, residual: float, diagnosis: str
):
    """流式版 _repair_solve_with_llm。yield 事件 dict：

    - {"type": "token", "text": "..."}
    - {"type": "object_seen", "id": "X", "kind": "Y"}
    - {"type": "done", "dsl": DSL | None}  — 修正成功返回 DSL，失败 None

    复用同款 prompt（repair_solve.txt）；与 extract_dsl_streaming 共用
    partial JSON object 提取，让前端在 repair 期间也看到 token 流。
    """
    from pathlib import Path
    from ..dsl import DSLValidationError, validate
    from ..llm.base import parse_json_response
    from ..llm.extractor import _extract_seen_objects, build_messages

    prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "repair_solve.txt"
    if not prompt_path.exists():
        yield {"type": "done", "dsl": None}
        return

    template = prompt_path.read_text(encoding="utf-8")
    user_msg = template.format(residual=f"{residual:.3e}", diagnosis=diagnosis, nl=nl)
    messages = build_messages(nl=user_msg, current_dsl=None)

    buffer = ""
    seen: set[tuple[str, str]] = set()
    try:
        async for token in provider.chat_stream(
            messages, json_mode=True, temperature=0.1, timeout=120.0
        ):
            buffer += token
            yield {"type": "token", "text": token}
            new_objs = _extract_seen_objects(buffer)
            for obj_id, kind in new_objs - seen:
                seen.add((obj_id, kind))
                yield {"type": "object_seen", "id": obj_id, "kind": kind}
    except LLMError:
        yield {"type": "done", "dsl": None}
        return

    try:
        parsed = parse_json_response(buffer)
    except ValueError:
        yield {"type": "done", "dsl": None}
        return

    if not isinstance(parsed, dict) or "objects" not in parsed:
        yield {"type": "done", "dsl": None}
        return

    try:
        dsl = DSL.model_validate(parsed)
        validate(dsl)
    except (DSLValidationError, ValueError, TypeError):
        yield {"type": "done", "dsl": None}
        return

    yield {"type": "done", "dsl": dsl}


# ---------------------------------------------------------------------------
# Refuse message friendly formatter
# ---------------------------------------------------------------------------

def _make_refuse_message(raw: str) -> str:
    """把 LLM 主动拒绝的原始 reason 转成对老师更友好的产品话术。

    保留原 reason 作为副标题，由前端按需折叠显示。
    """
    s = (raw or "").strip()
    # 识别几类常见拒绝场景
    # V2-B 起：一次/二次/反比例/正弦余弦/抛物线（拆解形式）都已支持；
    # 仅保留椭圆/双曲线的一般式 x²/a²+y²/b²=1（隐式）作为不支持提示
    keywords_for_implicit_curve = ("椭圆", "双曲线", "圆锥曲线")
    keywords_for_3d = ("立体", "三视图", "四棱锥", "棱锥", "棱柱", "圆柱", "圆锥", "球", "正方体")
    keywords_for_chart = ("柱状图", "饼图", "折线图", "直方图", "统计图")
    keywords_for_coord_value = ("A(", "B(", "C(", "P(", "Q(", "坐标为", "坐标是")

    head = "话图当前版本主要支持平面几何作图（点、线段、圆、多边形、坐标系、几何变换、函数图像与常见约束）。"
    advice = "你可以尝试用几何语言重新描述这道题，或等待后续版本支持更多题型。"

    if any(k in s for k in keywords_for_implicit_curve):
        head = "话图当前版本暂不支持椭圆 / 双曲线的一般式（隐式方程 x²/a²±y²/b²=1）。"
        advice = "如果能拆成显式函数（如 y=±b·√(1 - x²/a²)），可以逐段画出；否则等 V3 版本符号求解上线。"
    elif any(k in s for k in keywords_for_3d):
        head = "话图当前版本只支持平面几何，立体几何（棱锥 / 棱柱 / 球 / 三视图）计划在 V3 中支持。"
        advice = "试试改成平面图形，例如「画一个矩形 / 圆 / 三角形」。"
    elif any(k in s for k in keywords_for_chart):
        head = "话图当前版本不支持统计图表（柱状图 / 饼图 / 折线图）。"
        advice = "如果你想画的是几何图形，请用「画三角形 ABC」「画圆 O」这类描述。"
    elif any(k in s for k in keywords_for_coord_value):
        head = "话图当前版本支持画坐标系，但暂不支持基于具体坐标值（如 A(2,3)）的描述。"
        advice = "请改用边长、角度等几何关系描述，例如「画三角形 ABC，AB=5，BC=6，CA=7」；或先「画一个坐标系」再独立描述图形。"

    return f"{head}\n\n💡 {advice}"
