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
    if result.patch is not None:
        if current_dsl is None:
            raise HTTPException(400, detail="收到 patch 但当前没有 DSL")
        try:
            new_dsl = apply_patch(current_dsl, result.patch)
        except DSLPatchError as e:
            fe = classify(e)
            await repo_mod.add_message(
                db, sid, role="assistant", content=fe.message,
                dsl_patch_json=json.dumps(result.patch, ensure_ascii=False),
                llm_provider=result.provider,
                error_kind="patch",
            )
            raise HTTPException(422, detail=to_dict(fe))
        patch_for_log = json.dumps(result.patch, ensure_ascii=False)
    else:
        assert result.dsl is not None
        new_dsl = result.dsl
        patch_for_log = None

    # 5. 求解
    try:
        sol = solve(new_dsl, seed=0, restarts=20)
    except SolveError as e:
        fe = classify(e)
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
        sol = solve(new_dsl, seed=0, restarts=20)
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
# Refuse message friendly formatter
# ---------------------------------------------------------------------------

def _make_refuse_message(raw: str) -> str:
    """把 LLM 主动拒绝的原始 reason 转成对老师更友好的产品话术。

    保留原 reason 作为副标题，由前端按需折叠显示。
    """
    s = (raw or "").strip()
    # 识别几类常见拒绝场景
    keywords_for_function = ("函数图像", "函数图象", "y=", "y =", "正弦", "余弦", "三角函数", "抛物线", "椭圆", "双曲线", "圆锥曲线", "准线", "焦点")
    keywords_for_3d = ("立体", "三视图", "四棱锥", "棱锥", "棱柱", "圆柱", "圆锥", "球", "正方体")
    keywords_for_chart = ("柱状图", "饼图", "折线图", "直方图", "统计图")
    keywords_for_coord_value = ("A(", "B(", "C(", "P(", "Q(", "坐标为", "坐标是")
    keywords_for_transform = ("旋转", "平移", "翻折", "翻转", "对称", "镜像", "变换", "折叠")

    head = "话图当前版本主要支持平面几何作图（点、线段、圆、多边形、坐标系与常见约束）。"
    advice = "你可以尝试用几何语言重新描述这道题，或等待后续版本支持更多题型。"

    if any(k in s for k in keywords_for_function):
        head = "话图当前版本暂不支持函数图像和圆锥曲线（抛物线 / 椭圆 / 双曲线），这一类计划在 V2 中支持。"
        advice = "你可以试试改用平面几何描述，例如「画三角形 ABC，AB=...」。如只需画坐标系，可说「画一个平面直角坐标系」。"
    elif any(k in s for k in keywords_for_3d):
        head = "话图当前版本只支持平面几何，立体几何（棱锥 / 棱柱 / 球 / 三视图）计划在 V2 中支持。"
        advice = "试试改成平面图形，例如「画一个矩形 / 圆 / 三角形」。"
    elif any(k in s for k in keywords_for_chart):
        head = "话图当前版本不支持统计图表（柱状图 / 饼图 / 折线图）。"
        advice = "如果你想画的是几何图形，请用「画三角形 ABC」「画圆 O」这类描述。"
    elif any(k in s for k in keywords_for_transform):
        head = "话图当前版本暂不支持几何变换（旋转 / 平移 / 翻折 / 轴对称），这一类计划在 V2 中支持。"
        advice = (
            "可以试试把变换后的目标图形直接描述出来——\n"
            "  • 关于点 O 中心对称：用「O 是 AA' 的中点、O 是 BB' 的中点……」描述对称点\n"
            "  • 关于直线 l 轴对称：让 l 上的点为对称轴，用 `foot_of_perp` 约束描述\n"
            "  • 简单旋转：直接画出旋转后的三角形，约束对应边等长、对应角相等"
        )
    elif any(k in s for k in keywords_for_coord_value):
        head = "话图当前版本支持画坐标系，但暂不支持基于具体坐标值（如 A(2,3)）的描述。"
        advice = "请改用边长、角度等几何关系描述，例如「画三角形 ABC，AB=5，BC=6，CA=7」；或先「画一个坐标系」再独立描述图形。"

    return f"{head}\n\n💡 {advice}"
