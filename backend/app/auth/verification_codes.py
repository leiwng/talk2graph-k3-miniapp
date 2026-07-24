"""邮箱验证码 + 密码重置令牌的仓储。

验证码 6 位数字，bcrypt hash 存 DB（不存明文）；
密码重置令牌是 uuid，sha256 hash 存 DB（不存明文）。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password, verify_password
from ..db.models import EmailVerificationCode, PasswordResetToken, User

# 验证码有效期 15 分钟；同一邮箱 60s 内只能发 1 次
CODE_TTL_MINUTES = 15
CODE_RESEND_COOLDOWN_SECONDS = 60

# 重置令牌有效期 30 分钟
RESET_TOKEN_TTL_MINUTES = 30


# ============================================================================
# 验证码
# ============================================================================


def _gen_6digit_code() -> str:
    """生成 6 位数字验证码。"""
    return f"{secrets.randbelow(1_000_000):06d}"


async def get_latest_code(db: AsyncSession, email: str, purpose: str) -> Optional[EmailVerificationCode]:
    """取最新的未消费验证码（按时间倒序）。"""
    res = await db.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email, EmailVerificationCode.purpose == purpose)
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    return res.scalars().first()


async def create_verification_code(
    db: AsyncSession, email: str, purpose: str = "register"
) -> tuple[str, EmailVerificationCode]:
    """创建验证码。返回 (明文 code, db record)。

    如果距离上一条 < 60s，抛 ValueError（调用方返回 429）。
    """
    latest = await get_latest_code(db, email, purpose)
    if latest is not None:
        age = (datetime.now(timezone.utc) - latest.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        if age < CODE_RESEND_COOLDOWN_SECONDS:
            raise ValueError(f"请 {int(CODE_RESEND_COOLDOWN_SECONDS - age)} 秒后再试")

    code = _gen_6digit_code()
    rec = EmailVerificationCode(
        email=email,
        code_hash=hash_password(code),
        purpose=purpose,
        consumed=False,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return code, rec


async def verify_code(db: AsyncSession, email: str, code: str, purpose: str = "register") -> bool:
    """校验验证码。成功后消费（不可重放）。"""
    rec = await get_latest_code(db, email, purpose)
    if rec is None:
        return False
    if rec.consumed:
        return False
    if datetime.now(timezone.utc) > rec.expires_at.replace(tzinfo=timezone.utc):
        return False
    if not verify_password(code, rec.code_hash):
        return False
    # 消费
    rec.consumed = True
    await db.commit()
    return True


async def invalidate_all_codes(db: AsyncSession, email: str) -> None:
    """使某邮箱所有验证码失效（注册成功后调用）。"""
    await db.execute(
        update(EmailVerificationCode)
        .where(EmailVerificationCode.email == email)
        .values(consumed=True)
    )
    await db.commit()


# ============================================================================
# 密码重置令牌
# ============================================================================


def _hash_token(token: str) -> str:
    """sha256 hash token。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_reset_token(db: AsyncSession, user: User) -> str:
    """创建一次性密码重置令牌。返回明文 token（用于拼链接）。"""
    token = secrets.token_urlsafe(32)
    rec = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(token),
        consumed=False,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.add(rec)
    await db.commit()
    return token


async def consume_reset_token(db: AsyncSession, token: str) -> Optional[User]:
    """消费密码重置令牌。返回对应 User 或 None（无效/过期/已消费）。"""
    token_hash = _hash_token(token)
    res = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash, PasswordResetToken.consumed == False)
        .limit(1)
    )
    rec = res.scalars().first()
    if rec is None:
        return None
    if datetime.now(timezone.utc) > rec.expires_at.replace(tzinfo=timezone.utc):
        return None

    user = await db.get(User, rec.user_id)
    if user is None:
        return None

    rec.consumed = True
    await db.commit()
    return user


async def invalidate_all_reset_tokens(db: AsyncSession, user_id: str) -> None:
    """使某用户所有重置令牌失效（改密成功后调用）。"""
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.consumed == False)
        .values(consumed=True)
    )
    await db.commit()
