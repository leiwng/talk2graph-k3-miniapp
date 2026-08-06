"""微信小程序登录（wx.login code -> openid）。

文档：https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html

流程：
1. 小程序端 wx.login() 拿到临时 code
2. POST /api/auth/wechat/miniapp {code}
3. 后端调 jscode2session 换 openid（+ unionid，若绑定开放平台）
4. 按 openid 找/建用户 -> 颁 JWT（复用扫码登录的 user_repo 函数）

注意：小程序 AppID 与 PC 扫码的开放平台 AppID 是两个不同的应用，
用 WECHAT_MINIAPP_APP_ID / WECHAT_MINIAPP_APP_SECRET 配置。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import settings
from .wechat import WechatError

log = logging.getLogger(__name__)

JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


@dataclass
class MiniappSession:
    """jscode2session 返回的会话信息。"""

    openid: str
    unionid: Optional[str]
    session_key: str


async def jscode2session(code: str) -> MiniappSession:
    """用 wx.login 的 code 换 openid。失败抛 WechatError。"""
    if not settings.wechat_miniapp_app_id or not settings.wechat_miniapp_app_secret:
        raise WechatError(-1, "WECHAT_MINIAPP_APP_ID / WECHAT_MINIAPP_APP_SECRET not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            JSCODE2SESSION_URL,
            params={
                "appid": settings.wechat_miniapp_app_id,
                "secret": settings.wechat_miniapp_app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        raise WechatError(data.get("errcode"), data.get("errmsg", "unknown"))
    openid = data.get("openid")
    session_key = data.get("session_key")
    if not openid or not session_key:
        raise WechatError(-2, f"invalid jscode2session response: {data}")
    return MiniappSession(
        openid=openid,
        unionid=data.get("unionid"),
        session_key=session_key,
    )
