"""Chat SSE 流式路由：把 chat 主流程的每阶段进度推给前端。

事件协议：
    event: stage
    data: {"stage":"llm","status":"start"}

    event: token
    data: {"text":"{"}                  ← V2-D：LLM token-level 流式

    event: object_seen
    data: {"id":"A","kind":"point"}     ← V2-D：partial JSON 解析后已识别的对象

    event: stage
    data: {"stage":"fallback","status":"start","provider":"deepseek"}  ← V2-E：自动切换备选模型

    event: stage
    data: {"stage":"solve","status":"start"}

    event: done
    data: {"ok":true,"seq":3,"dsl":{...},"solution":{...},"svg":"..."}

    event: error
    data: {"code":"solve_no_converge","message":"...","hint":"..."}

stage 取值：llm / fallback / patch / solve / repair / render

复用 chat.py 内部逻辑（_make_refuse_message / _repair_solve_with_llm_streaming），
保持与同步 chat 端点行为一致。

V2-E 升级：
- LLM 阶段加自动 fallback chain：网络/5xx/4xx/空响应等错误时自动切到下一个 provider 重试。
- 切换时推 event:stage fallback 让前端显示"已切换到备选模型"。
- 默认 chain 由 LLMRouter 配置（最多 3 个）。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import actions, repository as audit_repo
from ..auth.deps import CurrentUser, get_current_user
from ..dsl import DSL, DSLPatchError, apply_patch
from ..llm import LLMError, get_router, is_retryable
from ..llm.base import LLMProvider
from ..llm.extractor import ExtractResult, extract_dsl, extract_dsl_streaming
from ..payment.entitlement import QuotaExceededError, ensure_user_can_send_chat
from ..render import render_svg
from ..session import repo as repo_mod
from ..solver import SolveError, solve
from . import chat as chat_module
from .chat import ChatReq, _make_refuse_message, _repair_solve_with_llm_streaming
from .deps import db_dep, require_session
from .errors import classify, to_dict

router = APIRouter(prefix="/api", tags=["chat-stream"])


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _sol_to_dict(sol) -> dict:
    return {
        "coordinates": {k: list(v) for k, v in sol.coordinates.items()},
        "circles": {
            k: {"center": list(v["center"]), "radius": v["radius"]}
            for k, v in sol.circles.items()
        },
        "residual": sol.residual,
        "method": sol.method,
    }


def _pick_provider_chain(name: str | None) -> list[LLMProvider]:
    """获取 fallback chain。

    - 测试覆盖（chat_module._provider_override 不为 None）时返回 [override]，禁用 fallback
    - 否则用 LLMRouter.get_fallback_chain(name)，name 显式时排第一
    """
    if chat_module._provider_override is not None:
        return [chat_module._provider_override]
    return get_router().get_fallback_chain(name)


async def _extract_with_fallback_streaming(
    chain: list[LLMProvider],
    nl: str,
    current_dsl: DSL | None,
) -> AsyncIterator[dict]:
    """LLM 阶段：尝试 chain 中每个 provider，第一个出错就 fallback 到下一个。

    yield 事件：
    - {"type": "token", "text": ...}
    - {"type": "object_seen", "id": ..., "kind": ...}
    - {"type": "fallback", "from": "volcengine", "to": "deepseek", "reason": "..."}
    - {"type": "done", "result": ExtractResult}
    - {"type": "error", "error": LLMError}  — 所有 provider 都失败
    """
    last_err: Exception | None = None
    for i, provider in enumerate(chain):
        if i > 0:
            yield {
                "type": "fallback",
                "from": chain[i - 1].name,
                "to": provider.name,
                "reason": str(last_err)[:200] if last_err else "",
            }
        try:
            async for evt in extract_dsl_streaming(provider, nl, current_dsl=current_dsl):
                if evt["type"] == "error":
                    last_err = evt["error"]
                    if not is_retryable(last_err):
                        # 不可重试的错误（如 4xx 业务错误）直接返回
                        yield evt
                        return
                    break  # 切到下一个 provider
                yield evt
                if evt["type"] == "done":
                    return
            else:
                # for-else：extract_dsl_streaming 正常结束但没 yield done
                return
        except LLMError as e:
            last_err = e
            if not is_retryable(e):
                yield {"type": "error", "error": e}
                return
            continue

    # 所有 provider 都失败
    if last_err is not None:
        yield {"type": "error", "error": last_err}
    else:
        yield {"type": "error", "error": LLMError("none", None, "no provider available")}


async def _run_chat_stream(
    sid: str, req: ChatReq, db: AsyncSession,
    user: CurrentUser | None = None,
    ent=None,
) -> AsyncIterator[str]:
    """主流程生成器：每个阶段 yield SSE 帧。"""
    await require_session(db, sid)
    chain = _pick_provider_chain(req.provider)
    if not chain:
        yield _sse("error", {"code": "no_provider", "message": "没有可用的 LLM provider"})
        await asyncio.sleep(0)
        return

    active_provider = chain[0]

    # 1. 记录 user 消息
    await repo_mod.add_message(db, sid, role="user", content=req.nl)

    # 2. 取当前 DSL（用于 patch 模式）
    cur = await repo_mod.current_snapshot(db, sid)
    current_dsl = cur.dsl if cur else None

    # 3. 调 LLM（阶段 1）— V2-E 升级：自动 fallback chain
    yield _sse("stage", {"stage": "llm", "status": "start", "provider": active_provider.name})
    await asyncio.sleep(0)
    result: ExtractResult | None = None
    used_provider_name: str | None = None
    fallback_chain_used: list[dict] = []  # [{from, to, reason}]

    async for evt in _extract_with_fallback_streaming(chain, req.nl, current_dsl):
        if evt["type"] == "token":
            yield _sse("token", {"text": evt["text"]})
            await asyncio.sleep(0)
        elif evt["type"] == "object_seen":
            yield _sse("object_seen", {"id": evt["id"], "kind": evt["kind"]})
            await asyncio.sleep(0)
        elif evt["type"] == "fallback":
            used_provider_name = evt["to"]
            fallback_chain_used.append({
                "from": evt["from"], "to": evt["to"], "reason": evt["reason"],
            })
            yield _sse("stage", {
                "stage": "fallback",
                "status": "start",
                "provider": evt["to"],
                "from": evt["from"],
                "reason": evt["reason"],
            })
            await asyncio.sleep(0)
        elif evt["type"] == "error":
            fe = classify(evt["error"])
            await repo_mod.add_message(
                db, sid, role="assistant", content=fe.message,
                llm_provider=active_provider.name,
                error_kind="network",
            )
            yield _sse("error", to_dict(fe))
            await asyncio.sleep(0)
            return
        elif evt["type"] == "done":
            result = evt["result"]
            if used_provider_name is None:
                used_provider_name = result.provider
            break

    assert result is not None

    if result.error:
        # LLM 主动拒绝
        product_msg = _make_refuse_message(result.error)
        await repo_mod.add_message(
            db, sid, role="assistant", content=product_msg,
            llm_provider=result.provider,
            error_kind="refuse",
        )
        yield _sse("done", {
            "ok": False,
            "error_kind": "refuse",
            "error": product_msg,
            "raw_reason": result.error,
            "provider": result.provider,
            "fallback_chain": fallback_chain_used or None,
        })
        await asyncio.sleep(0)
        return

    # 4. patch / fallback（阶段 2）— W10 patch fallback 保留
    yield _sse("stage", {"stage": "patch", "status": "start"})
    await asyncio.sleep(0)
    fallback_used = False
    fallback_reason: str | None = None
    if result.patch is not None:
        if current_dsl is None:
            yield _sse("error", {"code": "patch_no_dsl",
                                  "message": "收到 patch 但当前没有 DSL"})
            await asyncio.sleep(0)
            return
        try:
            new_dsl = apply_patch(current_dsl, result.patch)
            patch_for_log = json.dumps(result.patch, ensure_ascii=False)
        except DSLPatchError as e:
            # W10：patch 不合法时 fallback 重画
            patch_err = str(e)
            try:
                fb_result = await extract_dsl(active_provider, req.nl, current_dsl=None)
            except LLMError as e2:
                fe = classify(e2)
                await repo_mod.add_message(
                    db, sid, role="assistant", content=fe.message,
                    llm_provider=active_provider.name,
                    error_kind="network",
                )
                yield _sse("error", to_dict(fe))
                await asyncio.sleep(0)
                return

            if fb_result.error or fb_result.dsl is None:
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
                yield _sse("error", to_dict(fe))
                await asyncio.sleep(0)
                return

            new_dsl = fb_result.dsl
            fallback_used = True
            fallback_reason = patch_err
            patch_for_log = None
    else:
        assert result.dsl is not None
        new_dsl = result.dsl
        patch_for_log = None

    # 5. 求解（阶段 3）— solve() 是同步阻塞但通常 <1ms，复杂题也才 ~1s
    yield _sse("stage", {"stage": "solve", "status": "start"})
    await asyncio.sleep(0)
    solve_repaired = False
    solve_repair_reason: str | None = None
    try:
        sol = solve(new_dsl, seed=0, restarts=20, restarts_extra=40)
    except SolveError as e:
        original_err = e
        residual = getattr(e, "residual", float("nan"))
        diagnosis = getattr(e, "worst_constraint", "")

        should_repair = residual == residual and residual > 1e-2
        if should_repair:
            # 阶段 4：solve_repair（V2-D 升级：流式）
            yield _sse("stage", {"stage": "repair", "status": "start"})
            await asyncio.sleep(0)
            repair_dsl = None
            async for evt in _repair_solve_with_llm_streaming(
                active_provider, req.nl, residual, diagnosis
            ):
                if evt["type"] == "token":
                    yield _sse("token", {"text": evt["text"]})
                    await asyncio.sleep(0)
                elif evt["type"] == "object_seen":
                    yield _sse("object_seen", {"id": evt["id"], "kind": evt["kind"]})
                    await asyncio.sleep(0)
                elif evt["type"] == "done":
                    repair_dsl = evt["dsl"]
                    break

            if repair_dsl is not None:
                try:
                    sol = solve(repair_dsl, seed=0, restarts=20, restarts_extra=40)
                    new_dsl = repair_dsl
                    patch_for_log = None
                    solve_repaired = True
                    solve_repair_reason = f"原残差 {residual:.2e}，{diagnosis[:100]}"
                except SolveError:
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
                    yield _sse("error", to_dict(fe))
                    await asyncio.sleep(0)
                    return
            else:
                fe = classify(original_err)
                await repo_mod.add_message(
                    db, sid, role="assistant", content=fe.message,
                    dsl_patch_json=patch_for_log,
                    llm_provider=result.provider,
                    error_kind="solve",
                )
                yield _sse("error", to_dict(fe))
                await asyncio.sleep(0)
                return
        else:
            fe = classify(original_err)
            await repo_mod.add_message(
                db, sid, role="assistant", content=fe.message,
                dsl_patch_json=patch_for_log,
                llm_provider=result.provider,
                error_kind="solve",
            )
            yield _sse("error", to_dict(fe))
            await asyncio.sleep(0)
            return

    # 6. 渲染（阶段 5）
    yield _sse("stage", {"stage": "render", "status": "start"})
    await asyncio.sleep(0)
    svg = render_svg(new_dsl, sol)
    sol_dict = _sol_to_dict(sol)

    # 7. 保存 snapshot + assistant 消息
    snap = await repo_mod.push_snapshot(db, sid, new_dsl, solution=sol_dict)
    await repo_mod.add_message(
        db, sid, role="assistant",
        content=json.dumps(new_dsl.to_json_dict(), ensure_ascii=False),
        dsl_patch_json=patch_for_log,
        llm_provider=result.provider,
        fallback=True if fallback_used else None,
    )

    # 8. done
    yield _sse("done", {
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
        "fallback_chain": fallback_chain_used or None,
    })
    await asyncio.sleep(0)

    # V2-F.2：审计 chat.send（fire-and-forget，含配额信息）
    if user is not None:
        audit_repo.fire_and_forget(
            actions.CHAT_SEND,
            actor_id=user.id,
            actor_email=user.email,
            target_type="session",
            target_id=sid,
            metadata={
                "nl_length": len(req.nl),
                "provider": result.provider,
                "plan": ent.plan_code if ent else "unknown",
                "used_today": (ent.used_today + 1) if ent else 0,
                "daily_limit": ent.daily_limit if ent else 0,
            },
        )


@router.post("/session/{sid}/chat/stream")
async def chat_stream(
    sid: str,
    req: ChatReq,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(db_dep),
) -> StreamingResponse:
    """SSE 流式 chat：每阶段进度推送给前端。"""
    # V2-F.2：配额检查（在开始流式前同步执行）
    try:
        ent = await ensure_user_can_send_chat(db, user.id)
    except QuotaExceededError as e:
        fe = classify(e)
        raise HTTPException(422, detail=to_dict(fe))

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def producer():
        try:
            async for chunk in _run_chat_stream(sid, req, db, user, ent):
                await queue.put(chunk)
        except Exception as e:
            await queue.put(_sse("error", {"code": "unknown", "message": str(e)[:200]}))
        finally:
            await queue.put(None)

    async def consumer():
        task = asyncio.create_task(producer())
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        consumer(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
