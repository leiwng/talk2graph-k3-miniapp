"""会话管理路由：创建 / 列表 / 获取 / 删除 / 撤销 / 重做 / 当前 DSL。

V2-F.1：登录用户只能访问自己的 session（cross-user 返回 404 防探测）；
未登录用户创建的 session 归属 anonymous，任何人持 sid 可访问（保留试用体验）。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import CurrentUser, get_current_user_optional
from ..db.models import ANONYMOUS_USER_ID
from ..render import render_svg
from ..session import repo as repo_mod
from ..solver.engine import Solution
from .deps import db_dep, require_session

router = APIRouter(prefix="/api", tags=["session"])


class CreateSessionReq(BaseModel):
    llm_provider: str | None = None
    title: str | None = None


class SessionOut(BaseModel):
    id: str
    title: str | None
    llm_provider: str | None
    created_at: str
    updated_at: str


def _to_out(s) -> SessionOut:
    return SessionOut(
        id=s.id,
        title=s.title,
        llm_provider=s.llm_provider,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


async def _require_session_with_owner(
    db: AsyncSession, sid: str, user: Optional[CurrentUser]
):
    """加载 session 并校验归属：

    - session 不存在 → 404
    - session.user_id == current_user.id → 通过
    - session.user_id == ANONYMOUS_USER_ID → 通过（任何人都能访问匿名会话）
    - 其他 → 404（不是 403，防探测）
    """
    s = await require_session(db, sid)  # 内部已 404
    if s.user_id is None or s.user_id == ANONYMOUS_USER_ID:
        # 匿名会话：任何人都能访问（保留试用体验）
        return s
    if user is not None and s.user_id == user.id:
        return s
    # 不是自己的也不是匿名的 → 404 防探测
    raise HTTPException(404, detail=f"session not found: {sid}")


@router.post("/session", response_model=SessionOut)
async def create_session(
    req: CreateSessionReq,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> SessionOut:
    """创建 session。登录用户归属自己；未登录归属 anonymous。"""
    uid = user.id if user is not None else ANONYMOUS_USER_ID
    s = await repo_mod.create_session(
        db, llm_provider=req.llm_provider, title=req.title, user_id=uid
    )
    return _to_out(s)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> list[SessionOut]:
    """列出 session。登录用户只看到自己的（含 anonymous 的）；未登录看到 anonymous 的。"""
    uid = user.id if user is not None else ANONYMOUS_USER_ID
    items = await repo_mod.list_sessions(db, user_id=uid)
    return [_to_out(s) for s in items]


@router.get("/session/{sid}", response_model=SessionOut)
async def get_session(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> SessionOut:
    s = await _require_session_with_owner(db, sid, user)
    return _to_out(s)


@router.delete("/session/{sid}")
async def delete_session(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict:
    s = await _require_session_with_owner(db, sid, user)
    ok = await repo_mod.delete_session(db, s.id)
    if not ok:
        raise HTTPException(404, detail="session not found")
    return {"deleted": sid}


@router.get("/session/{sid}/dsl")
async def get_current_dsl(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict[str, Any]:
    await _require_session_with_owner(db, sid, user)
    snap = await repo_mod.current_snapshot(db, sid)
    if snap is None:
        return {"seq": 0, "dsl": None, "solution": None, "svg": None}
    svg = _render_svg(snap.dsl, snap.solution)
    return {
        "seq": snap.seq,
        "dsl": snap.dsl.to_json_dict(),
        "solution": snap.solution,
        "svg": svg,
    }


@router.get("/session/{sid}/messages")
async def list_messages(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> list[dict]:
    await _require_session_with_owner(db, sid, user)
    msgs = await repo_mod.list_messages(db, sid)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "dsl_patch": m.dsl_patch_json,
            "llm_provider": m.llm_provider,
            "tokens_in": m.tokens_in,
            "tokens_out": m.tokens_out,
            "latency_ms": m.latency_ms,
            "error_kind": m.error_kind,
            "fallback": m.fallback,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]


@router.get("/session/{sid}/history")
async def history(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict:
    await _require_session_with_owner(db, sid, user)
    seqs = await repo_mod.history(db, sid)
    cur = await repo_mod.current_snapshot(db, sid)
    return {"seqs": seqs, "current": cur.seq if cur else 0}


@router.post("/session/{sid}/undo")
async def undo(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict:
    await _require_session_with_owner(db, sid, user)
    snap = await repo_mod.undo(db, sid)
    if snap is None:
        return {"seq": 0, "dsl": None, "solution": None, "svg": None}
    svg = _render_svg(snap.dsl, snap.solution)
    return {"seq": snap.seq, "dsl": snap.dsl.to_json_dict(), "solution": snap.solution, "svg": svg}


@router.post("/session/{sid}/redo")
async def redo(
    sid: str,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict:
    await _require_session_with_owner(db, sid, user)
    snap = await repo_mod.redo(db, sid)
    if snap is None:
        return {"seq": 0, "dsl": None, "solution": None, "svg": None}
    svg = _render_svg(snap.dsl, snap.solution)
    return {"seq": snap.seq, "dsl": snap.dsl.to_json_dict(), "solution": snap.solution, "svg": svg}


class FeedbackReq(BaseModel):
    rating: str       # "good" | "bad"
    comment: str | None = None


@router.post("/session/{sid}/feedback")
async def submit_feedback(
    sid: str,
    req: FeedbackReq,
    user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(db_dep),
) -> dict:
    await _require_session_with_owner(db, sid, user)
    if req.rating not in ("good", "bad"):
        raise HTTPException(400, detail="rating 必须是 good 或 bad")

    snap = await repo_mod.current_snapshot(db, sid)
    snapshot_seq = snap.seq if snap else None
    dsl_json = None
    if snap and snap.dsl:
        import json as _json
        dsl_json = _json.dumps(snap.dsl.to_json_dict(), ensure_ascii=False)

    msgs = await repo_mod.list_messages(db, sid)
    last_user_nl = None
    last_provider = None
    for m in reversed(msgs):
        if m.role == "user" and last_user_nl is None:
            last_user_nl = m.content
        if m.llm_provider and last_provider is None:
            last_provider = m.llm_provider
        if last_user_nl and last_provider:
            break

    fb = await repo_mod.add_feedback(
        db, sid,
        rating=req.rating,
        snapshot_seq=snapshot_seq,
        comment=req.comment,
        nl=last_user_nl,
        dsl_json=dsl_json,
        llm_provider=last_provider,
    )
    return {"id": fb.id, "rating": fb.rating, "created_at": fb.created_at.isoformat()}


def _render_svg(dsl, solution_dict):
    """从持久化的 solution dict 重建 Solution 并渲染。"""
    if not solution_dict:
        return None
    coords = {k: tuple(v) for k, v in solution_dict.get("coordinates", {}).items()}
    circles = {
        k: {"center": tuple(v["center"]), "radius": v["radius"]}
        for k, v in solution_dict.get("circles", {}).items()
    }
    sol = Solution(
        coordinates=coords,
        circles=circles,
        residual=solution_dict.get("residual", 0.0),
        method=solution_dict.get("method", "numeric"),
        iterations=0,
    )
    return render_svg(dsl, sol)
