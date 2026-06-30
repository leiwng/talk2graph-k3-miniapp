"""会话仓库：封装 session / message / snapshot 的 CRUD + 撤销/重做。

撤销/重做语义：
- 每个会话维护 snapshot 序列 (seq=1,2,3,…)
- 同时维护 "current seq"（指针），保存在 session.meta_json 里
- undo：current_seq -> current_seq - 1（若有）
- redo：current_seq -> current_seq + 1（若存在）
- 当 current_seq 不在末端时再 push 新 snapshot：截断之后的（典型撤销→改→新分支语义）
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dsl import DSL
from ..db.models import DSLSnapshot, Feedback, Message, Session


@dataclass
class SnapshotView:
    seq: int
    dsl: DSL
    solution: dict | None


def _load_meta(s: Session) -> dict:
    if not s.meta_json:
        return {}
    try:
        return json.loads(s.meta_json)
    except json.JSONDecodeError:
        return {}


def _save_meta(s: Session, meta: dict) -> None:
    s.meta_json = json.dumps(meta, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

async def create_session(
    db: AsyncSession, *, llm_provider: str | None = None, title: str | None = None
) -> Session:
    sid = uuid.uuid4().hex
    s = Session(id=sid, llm_provider=llm_provider, title=title)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def get_session_by_id(db: AsyncSession, sid: str) -> Session | None:
    return await db.get(Session, sid)


async def list_sessions(db: AsyncSession, limit: int = 50) -> list[Session]:
    stmt = select(Session).order_by(Session.updated_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars())


async def delete_session(db: AsyncSession, sid: str) -> bool:
    s = await db.get(Session, sid)
    if not s:
        return False
    await db.delete(s)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def add_message(
    db: AsyncSession,
    sid: str,
    *,
    role: str,
    content: str,
    dsl_patch_json: str | None = None,
    llm_provider: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
    error_kind: str | None = None,
    fallback: bool | None = None,
) -> Message:
    m = Message(
        session_id=sid,
        role=role,
        content=content,
        dsl_patch_json=dsl_patch_json,
        llm_provider=llm_provider,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        error_kind=error_kind,
        fallback=fallback,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def list_messages(db: AsyncSession, sid: str) -> list[Message]:
    stmt = (
        select(Message).where(Message.session_id == sid).order_by(Message.id.asc())
    )
    res = await db.execute(stmt)
    return list(res.scalars())


# ---------------------------------------------------------------------------
# Snapshots & undo/redo
# ---------------------------------------------------------------------------

async def _max_seq(db: AsyncSession, sid: str) -> int:
    stmt = select(DSLSnapshot.seq).where(DSLSnapshot.session_id == sid).order_by(
        DSLSnapshot.seq.desc()
    ).limit(1)
    res = await db.execute(stmt)
    v = res.scalar_one_or_none()
    return int(v) if v else 0


async def _snapshot_at(
    db: AsyncSession, sid: str, seq: int
) -> DSLSnapshot | None:
    stmt = select(DSLSnapshot).where(
        DSLSnapshot.session_id == sid, DSLSnapshot.seq == seq
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def push_snapshot(
    db: AsyncSession, sid: str, dsl: DSL, *, solution: dict | None = None
) -> SnapshotView:
    """新增 snapshot。若当前指针不在末端，先截断之后的（典型 undo→改 分支）。"""
    s = await db.get(Session, sid)
    if s is None:
        raise KeyError(f"session not found: {sid}")
    meta = _load_meta(s)
    cur = int(meta.get("current_seq", 0))
    max_seq = await _max_seq(db, sid)

    # 截断 (cur+1 .. max_seq]
    if cur < max_seq:
        await db.execute(
            delete(DSLSnapshot).where(
                DSLSnapshot.session_id == sid, DSLSnapshot.seq > cur
            )
        )

    new_seq = cur + 1
    snap = DSLSnapshot(
        session_id=sid,
        seq=new_seq,
        dsl_json=json.dumps(dsl.to_json_dict(), ensure_ascii=False),
        solution_json=json.dumps(solution, ensure_ascii=False) if solution else None,
    )
    db.add(snap)

    meta["current_seq"] = new_seq
    _save_meta(s, meta)

    await db.commit()
    return SnapshotView(seq=new_seq, dsl=dsl, solution=solution)


def _to_view(snap: DSLSnapshot) -> SnapshotView:
    return SnapshotView(
        seq=snap.seq,
        dsl=DSL.model_validate_json(snap.dsl_json),
        solution=json.loads(snap.solution_json) if snap.solution_json else None,
    )


async def current_snapshot(db: AsyncSession, sid: str) -> Optional[SnapshotView]:
    s = await db.get(Session, sid)
    if s is None:
        return None
    meta = _load_meta(s)
    cur = int(meta.get("current_seq", 0))
    if cur <= 0:
        return None
    snap = await _snapshot_at(db, sid, cur)
    return _to_view(snap) if snap else None


async def undo(db: AsyncSession, sid: str) -> Optional[SnapshotView]:
    s = await db.get(Session, sid)
    if s is None:
        return None
    meta = _load_meta(s)
    cur = int(meta.get("current_seq", 0))
    if cur <= 1:
        # cur==1 时回到空（cur=0），返回 None
        if cur == 1:
            meta["current_seq"] = 0
            _save_meta(s, meta)
            await db.commit()
        return None
    new_cur = cur - 1
    snap = await _snapshot_at(db, sid, new_cur)
    if snap is None:
        return None
    meta["current_seq"] = new_cur
    _save_meta(s, meta)
    await db.commit()
    return _to_view(snap)


async def redo(db: AsyncSession, sid: str) -> Optional[SnapshotView]:
    s = await db.get(Session, sid)
    if s is None:
        return None
    meta = _load_meta(s)
    cur = int(meta.get("current_seq", 0))
    max_seq = await _max_seq(db, sid)
    if cur >= max_seq:
        return None
    new_cur = cur + 1
    snap = await _snapshot_at(db, sid, new_cur)
    if snap is None:
        return None
    meta["current_seq"] = new_cur
    _save_meta(s, meta)
    await db.commit()
    return _to_view(snap)


async def history(db: AsyncSession, sid: str) -> list[int]:
    stmt = select(DSLSnapshot.seq).where(DSLSnapshot.session_id == sid).order_by(
        DSLSnapshot.seq.asc()
    )
    res = await db.execute(stmt)
    return [int(v) for v in res.scalars()]


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

async def add_feedback(
    db: AsyncSession,
    sid: str,
    *,
    rating: str,
    snapshot_seq: int | None = None,
    comment: str | None = None,
    nl: str | None = None,
    dsl_json: str | None = None,
    llm_provider: str | None = None,
) -> Feedback:
    if rating not in ("good", "bad"):
        raise ValueError(f"invalid rating: {rating!r}")
    fb = Feedback(
        session_id=sid,
        snapshot_seq=snapshot_seq,
        rating=rating,
        comment=comment,
        nl=nl,
        dsl_json=dsl_json,
        llm_provider=llm_provider,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb


async def list_feedback(
    db: AsyncSession, *, since=None, limit: int = 1000
) -> list[Feedback]:
    stmt = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    if since is not None:
        stmt = select(Feedback).where(Feedback.created_at >= since).order_by(
            Feedback.created_at.desc()
        ).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars())
