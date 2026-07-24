"""微信开放平台 PC 扫码登录 OAuth 流程。

文档：https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/WeChat_Login.html

流程：
1. 前端打开 https://open.weixin.qq.com/connect/qrconnect?appid=xxx&redirect_uri=xxx&response_type=code&scope=snsapi_login&state=xxx
2. 用户扫码确认
3. 微信回调后端 /api/auth/wechat/callback?code=xxx&state=xxx
4. 后端用 code 换 access_token + openid
5. 用 access_token 拉用户信息（nickname / avatar）
6. 根据 openid 找/建用户 -> 颁 JWT -> 重定向前端
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx

from ..config import settings

log = logging.getLogger(__name__)


WECHAT_AUTH_URL = "https://open.weixin.qq.com/connect/qrconnect"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


def build_qrconnect_url(state: str) -> str:
    """构造微信扫码登录页 URL（前端打开）。"""
    params = {
        "appid": settings.wechat_app_id,
        "redirect_uri": settings.wechat_redirect_uri,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    return f"{WECHAT_AUTH_URL}?{urlencode(params)}#wechat_redirect"


def gen_state() -> str:
    """生成 state 防 CSRF。"""
    return secrets.token_urlsafe(16)


class WechatError(Exception):
    """微信 OAuth 错误。"""

    def __init__(self, code: Optional[int], message: str):
        self.code = code
        self.message = message
        super().__init__(f"wechat error: code={code} message={message}")


@dataclass
class WechatUserInfo:
    """微信用户信息。"""

    openid: str
    unionid: Optional[str]
    nickname: str
    headimgurl: Optional[str]


async def exchange_code_for_user(code: str) -> WechatUserInfo:
    """用 code 换 access_token + 拉用户信息。

    返回 WechatUserInfo；失败抛 WechatError。
    """
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise WechatError(-1, "WECHAT_APP_ID / WECHAT_APP_SECRET not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: code -> access_token + openid
        token_resp = await client.get(
            WECHAT_TOKEN_URL,
            params={
                "appid": settings.wechat_app_id,
                "secret": settings.wechat_app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()
        if "errcode" in token_data and token_data["errcode"] != 0:
            raise WechatError(token_data.get("errcode"), token_data.get("errmsg", "unknown"))
        access_token = token_data.get("access_token")
        openid = token_data.get("openid")
        unionid = token_data.get("unionid")
        if not access_token or not openid:
            raise WechatError(-2, f"invalid token response: {token_data}")

        # Step 2: access_token + openid -> 用户信息
        info_resp = await client.get(
            WECHAT_USERINFO_URL,
            params={
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN",
            },
        )
        info_data = info_resp.json()
        if "errcode" in info_data and info_data["errcode"] != 0:
            raise WechatError(info_data.get("errcode"), info_data.get("errmsg", "unknown"))
        return WechatUserInfo(
            openid=openid,
            unionid=unionid,
            nickname=info_data.get("nickname", ""),
            headimgurl=info_data.get("headimgurl"),
        )
        token_data = token_resp.json()
        if "errcode" in token_data and token_data["errcode"] != 0:
            raise WechatError(token_data.get("errcode"), token_data.get("errmsg", "unknown"))
        access_token = token_data.get("access_token")
        openid = token_data.get("openid")
        unionid = token_data.get("unionid")
        if not access_token or not openid:
            raise WechatError(-2, f"invalid token response: {token_data}")

        # Step 2: access_token + openid -> 用户信息
        info_resp = await client.get(
            WECHAT_USERINFO_URL,
            params={
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN",
            },
        )
        info_data = info_resp.json()
        if "errcode" in info_data and info_data["errcode"] != 0:
            raise WechatError(info_data.get("errcode"), info_data.get("errmsg", "unknown"))
        return WechatUserInfo(
            openid=openid,
            unionid=unionid,
            nickname=info_data.get("nickname", ""),
            headimgurl=info_data.get("headimgurl"),
        )
