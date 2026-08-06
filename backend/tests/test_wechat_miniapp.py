"""微信小程序登录（POST /api/auth/wechat/miniapp）测试。

jscode2session 走 mock，不发真实网络请求。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    tmp = tempfile.mkdtemp(prefix="t2g_miniapp_")
    db_path = Path(tmp) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def client():
    from app.db.session import init_db, override_database_url
    from app.main import create_app

    tmp = tempfile.mkdtemp(prefix="t2g_miniapp_test_")
    db_path = Path(tmp) / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url
    override_database_url(url)

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # 在同一事件循环内销毁引擎，避免 aiosqlite 线程泄漏到后续测试文件
    from app.db.session import get_engine
    await get_engine().dispose()


def _fake_session(openid: str = "oMiniappTest123", unionid: str | None = "uUnion1"):
    from app.auth.wechat_miniapp import MiniappSession

    return MiniappSession(openid=openid, unionid=unionid, session_key="sk")


@pytest.mark.asyncio
async def test_miniapp_login_creates_user(client, monkeypatch):
    """新 openid -> 自动建号，返回 token + 已验证用户。"""
    # 注意：patch auth 路由实际持有的 settings 实例
    # （test_v2f_auth 等会 importlib.reload(config)，from app.config import 拿到的可能是新实例）
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_id", "wx_miniapp_test")
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_secret", "secret")

    with patch(
        "app.api.auth.jscode2session", new=AsyncMock(return_value=_fake_session())
    ):
        r = await client.post("/api/auth/wechat/miniapp", json={"code": "fake_code"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["token"]
    user = data["user"]
    assert user["status"] == "active"
    assert user["email_verified"] is True  # 微信建号视为已验证，chat 闸门不挡
    assert user["wechat_nickname"]
    assert user["email"].endswith("@wechat.local")


@pytest.mark.asyncio
async def test_miniapp_login_reuses_user(client, monkeypatch):
    """同 openid 再次登录 -> 复用同一账号。"""
    # 注意：patch auth 路由实际持有的 settings 实例
    # （test_v2f_auth 等会 importlib.reload(config)，from app.config import 拿到的可能是新实例）
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_id", "wx_miniapp_test")
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_secret", "secret")

    with patch(
        "app.api.auth.jscode2session", new=AsyncMock(return_value=_fake_session())
    ):
        r1 = await client.post("/api/auth/wechat/miniapp", json={"code": "c1"})
        r2 = await client.post("/api/auth/wechat/miniapp", json={"code": "c2"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["user"]["id"] == r2.json()["user"]["id"]


@pytest.mark.asyncio
async def test_miniapp_login_wechat_error(client, monkeypatch):
    """微信接口报错 -> 502。"""
    from app.auth.wechat import WechatError
    # 注意：patch auth 路由实际持有的 settings 实例
    # （test_v2f_auth 等会 importlib.reload(config)，from app.config import 拿到的可能是新实例）
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_id", "wx_miniapp_test")
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_secret", "secret")

    with patch(
        "app.api.auth.jscode2session",
        new=AsyncMock(side_effect=WechatError(40029, "invalid code")),
    ):
        r = await client.post("/api/auth/wechat/miniapp", json={"code": "bad"})
    assert r.status_code == 502, r.text
    assert "invalid code" in r.text


@pytest.mark.asyncio
async def test_miniapp_login_not_configured(client, monkeypatch):
    """未配置小程序 AppID -> 503。"""
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "wechat_miniapp_app_id", "")

    r = await client.post("/api/auth/wechat/miniapp", json={"code": "x"})
    assert r.status_code == 503, r.text
