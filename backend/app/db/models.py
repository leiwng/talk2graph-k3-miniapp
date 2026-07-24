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
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | disabled | pending_email_verification
    # 改密后更新；JWT 用 auth_version = password_changed_at || updated_at || created_at 让旧 token 失效
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    # P1 V2-F.3：邮箱验证 + 微信 OAuth
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    wechat_openid: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, default=None)
    wechat_unionid: Mapped[Optional[str]] = mapped_column(String(128), index=True, default=None)
    wechat_nickname: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    wechat_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), default=None)
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


# ============================================================================
# V2-F.2：付费 + 配额限流
# ============================================================================


class SubscriptionPlan(Base):
    """订阅套餐定义。

    admin 可通过 SQL 修改 daily_graph_limit 调整配额（不需要改代码 + 重新部署）。
    启动时若表为空，会 seed 3 个默认 plan（free / pro / enterprise），幂等。
    """

    __tablename__ = "subscription_plan"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)  # 'free'|'pro'|'enterprise'
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    feature_bullets_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of strings
    price_cents: Mapped[int] = mapped_column(Integer, default=0)  # 分（避免浮点）
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    period: Mapped[str] = mapped_column(String(20))  # 'free' | 'calendar_month' | 'contract'
    # 每日画图配额上限。0 = 无限。free=5, pro=0（无限）, enterprise=0
    daily_graph_limit: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="active")  # 'active' | 'archived'
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class SubscriptionOrder(Base):
    """订阅订单。

    状态机：pending -> paid（webhook 验签通过）-> expired（15min 未支付自动过期）/ closed（用户主动关闭）
    幂等：webhook 重复通知时通过 provider_payload.subscription_applied 标记避免重复激活
    """

    __tablename__ = "subscription_order"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("subscription_plan.code"))
    plan_code: Mapped[str] = mapped_column(String(32))  # 反规范化，便于查询
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|paid|expired|closed|refunded|failed
    provider: Mapped[str] = mapped_column(String(20), default="alipay")
    # 商户订单号（UNIQUE）：T2G{timestamp}{uuid8}
    provider_out_trade_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(String(128))
    # 完整 webhook 通知 payload + 幂等标记 {subscription_applied: bool}
    provider_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64))
    failure_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    paid_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    expires_at: Mapped[Optional[datetime]] = mapped_column(default=None)  # 15 分钟未支付过期
    closed_at: Mapped[Optional[datetime]] = mapped_column(default=None)


class UserSubscription(Base):
    """用户当前订阅状态。

    每个用户最多 1 条记录。无记录 = free 用户（用 plan 默认配额）。
    daily_graph_limit_override 用于 per-user 配额覆盖（admin 可调，营销用）：
      - None：用 plan 的 daily_graph_limit
      - 非 None：覆盖 plan 的值（如给某用户 30 次/天但仍是 free）
    """

    __tablename__ = "user_subscription"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), unique=True, index=True
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("subscription_plan.code"))
    plan_code: Mapped[str] = mapped_column(String(32))  # 反规范化
    status: Mapped[str] = mapped_column(String(20), default="free")  # 'free' | 'active' | 'expired'
    # per-user 配额覆盖（admin 可调）。None=用 plan 默认值
    daily_graph_limit_override: Mapped[Optional[int]] = mapped_column(default=None)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(default=None)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(default=None)
    source_order_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("subscription_order.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


# ============================================================================
# P1 V2-F.3：邮箱验证码 + 密码重置令牌
# ============================================================================


class EmailVerificationCode(Base):
    """邮箱验证码（6 位数字）。

    用途：注册时验证邮箱归属。
    有效期 15 分钟；同一邮箱 60s 内只能发 1 次（防滥发）。
    """

    __tablename__ = "email_verification_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    code_hash: Mapped[str] = mapped_column(String(200))  # bcrypt hash，不存明文
    purpose: Mapped[str] = mapped_column(String(32), default="register")  # register | reset
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp(), index=True)


class PasswordResetToken(Base):
    """密码重置令牌（一次性 uuid 链接）。

    用途：忘记密码时生成一次性 token，通过邮件发送链接 `/reset-password?token=xxx`。
    有效期 30 分钟；使用后 consumed=True；改密后旧 token 全部失效。
    """

    __tablename__ = "password_reset_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(200), unique=True, index=True)  # sha256 hash
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp(), index=True)
