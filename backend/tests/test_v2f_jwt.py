"""V2-F.1 JWT token 测试（5 个）。"""
from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_test_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


from app.auth import jwt_token
from app.auth.jwt_token import (
    TokenExpiredError,
    TokenInvalidError,
    auth_version,
    create_access_token,
    decode_token,
    decode_token_unsafe,
)
from app.config import settings
from app.db.models import User


def _make_user(
    *,
    id: str = "u1",
    email: str = "alice@example.com",
    role: str = "user",
    status: str = "active",
    password_changed_at: datetime | None = None,
    updated_at: datetime | None = None,
    created_at: datetime | None = None,
) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=id,
        email=email,
        username="alice",
        hashed_password="$2b$12$dummy",
        role=role,
        status=status,
        password_changed_at=password_changed_at,
        updated_at=updated_at or now,
        created_at=created_at or now,
    )


def test_create_and_decode_token():
    user = _make_user()
    token = create_access_token(user)
    assert isinstance(token, str) and len(token) > 20

    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["email"] == "alice@example.com"
    assert payload["role"] == "user"
    assert payload["status"] == "active"
    assert "auth_version" in payload
    assert "iat" in payload and "exp" in payload


def test_expired_token_rejected():
    user = _make_user()
    # 手动签一个 1 秒前过期的 token
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "auth_version": auth_version(user),
        "iat": now - 100,
        "exp": now - 1,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=jwt_token.ALGORITHM)
    with pytest.raises(TokenExpiredError):
        decode_token(token)


def test_invalid_signature_rejected():
    user = _make_user()
    payload = {
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "auth_version": auth_version(user),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, "wrong-secret-with-at-least-32-chars-xxx", algorithm=jwt_token.ALGORITHM)
    with pytest.raises(TokenInvalidError):
        decode_token(token)


def test_auth_version_invalidation():
    """改密后 auth_version 变化，旧 token 失效。"""
    # 初始状态：无 password_changed_at → version 来自 created_at
    user_v1 = _make_user(
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        password_changed_at=None,
    )
    token_v1 = create_access_token(user_v1)
    # 旧 token 解码成功
    decode_token(token_v1, expected_auth_version=auth_version(user_v1))

    # 用户改密：password_changed_at 更新到 2025 年 → auth_version 变化
    user_v2 = _make_user(
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        password_changed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    new_version = auth_version(user_v2)
    assert new_version != auth_version(user_v1)
    # 旧 token 用新 version 校验 → 失败
    with pytest.raises(TokenInvalidError):
        decode_token(token_v1, expected_auth_version=new_version)


def test_token_contains_claims():
    user = _make_user(id="abc", email="x@y.com", role="admin", status="active")
    token = create_access_token(user)
    payload = decode_token(token)
    # 必备 claims
    assert set(["sub", "email", "username", "role", "status", "auth_version", "iat", "exp"]).issubset(payload.keys())
    assert payload["sub"] == "abc"
    assert payload["email"] == "x@y.com"
    assert payload["role"] == "admin"
    # decode_token_unsafe 不抛
    decoded = decode_token_unsafe(token)
    assert decoded is not None
    assert decoded["sub"] == "abc"
    # 错 token 返回 None
    assert decode_token_unsafe("garbage") is None
