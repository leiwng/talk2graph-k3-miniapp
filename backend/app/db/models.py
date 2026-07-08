"""SQLAlchemy ORM 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# V2-F.1：固定 ID 的匿名用户，承载未登录用户的会话（保留试用体验）
ANONYMOUS_USER_ID = "00000000-0000-0000-0000-anonymous"


class User(Base):
    """用户账号。

    F.1 阶段：邮箱+密码登录，role ∈ {user, admin}，status ∈ {active, disabled}。
    后续 F.3 接 WeChat OAuth 时会扩展 wechat_openid / wechat_unionid 等字段。
    """

    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | disabled
    # 改密后更新；JWT 用 auth_version = password_changed_at || updated_at || created_at 让旧 token 失效
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32))
    # V2-F.1：会话归属。未登录用户创建的会话归属 anonymous_user；登录用户创建的归属自己
    # 列 nullable 保留向后兼容（开发期 ensure_schema 自动加列；老 session.user_id=NULL 也算 anonymous）
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
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


class AuditLog(Base):
    """审计日志。

    所有敏感操作（登录/登出/改密/每次 chat 作图）都会写入；写入走 fire-and-forget，
    失败仅 logger.warning，永不阻塞主流程。借鉴 Lumiton 的 best-effort 模式。
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(200))  # 反规范化，防用户删除后丢失
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(50))
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), index=True
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
    # W10：patch 失败自动 fallback 重画时为 True，便于前端显示"已重新理解为重画"小提示
    fallback: Mapped[Optional[bool]] = mapped_column(Boolean)
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
