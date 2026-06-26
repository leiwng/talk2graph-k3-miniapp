"""SQLAlchemy ORM 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    meta_json: Mapped[Optional[str]] = mapped_column(Text)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["DSLSnapshot"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("session.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    dsl_patch_json: Mapped[Optional[str]] = mapped_column(Text)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32))
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # 错误分类（仅 assistant 消息可能有值）：
    #   None       = 正常成功
    #   "refuse"   = LLM 主动拒绝（超出 MVP 范围）
    #   "solve"    = 求解失败（约束矛盾）
    #   "patch"    = patch 应用失败
    #   "network"  = LLM 网络/鉴权错误
    error_kind: Mapped[Optional[str]] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())

    session: Mapped[Session] = relationship(back_populates="messages")


class DSLSnapshot(Base):
    __tablename__ = "dsl_snapshot"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("session.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    dsl_json: Mapped[str] = mapped_column(Text)
    solution_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())

    session: Mapped[Session] = relationship(back_populates="snapshots")


class Feedback(Base):
    """老师点击 👍/👎 时记录。"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("session.id", ondelete="CASCADE"), index=True
    )
    snapshot_seq: Mapped[Optional[int]] = mapped_column(Integer)
    rating: Mapped[str] = mapped_column(String(8))  # "good" | "bad"
    comment: Mapped[Optional[str]] = mapped_column(Text)
    nl: Mapped[Optional[str]] = mapped_column(Text)  # 该轮老师输入的 NL（便于复盘）
    dsl_json: Mapped[Optional[str]] = mapped_column(Text)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
