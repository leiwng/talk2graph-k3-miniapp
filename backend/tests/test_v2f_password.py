"""V2-F.1 密码哈希测试（4 个）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_test_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


from app.auth.password import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    plain = "my-secret-pwd-123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_invalid_hash():
    # 损坏的 hash 字符串不应抛异常，返回 False
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", None) is False  # type: ignore[arg-type]


def test_hash_salt_uniqueness():
    """同密码两次 hash 结果不同（bcrypt 自带随机 salt）。"""
    plain = "same-password"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2
    # 但都能 verify
    assert verify_password(plain, h1) is True
    assert verify_password(plain, h2) is True
