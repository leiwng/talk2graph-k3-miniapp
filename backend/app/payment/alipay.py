"""Alipay 电脑网站支付（alipay.trade.page.pay）。

- RSA2 签名 / 验签（SHA256withRSA PKCS1v15）
- 构造跳转 URL（GET 方式，浏览器直接跳转）
- webhook 异步通知验签

密钥从文件读取（借鉴 Lumiton alipay_service.py 的 _pem_block 兼容裸 key/PEM）。
"""
from __future__ import annotations

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any

from ..config import settings

log = logging.getLogger(__name__)

# Alipay 网关公共参数
_COMMON_PARAMS = {
    "format": "JSON",
    "version": "1.0",
    "sign_type": "RSA2",
    "charset": "utf-8",
    "product_code": "FAST_INSTANT_TRADE_PAY",
}


def _read_key(path: str, *, is_private: bool) -> str:
    """读取密钥文件内容。支持 PEM 格式（含 BEGIN/END 头）和裸 base64 字符串。

    is_private: True=私钥，False=公钥。用于裸 base64 时正确包装 PEM 头。
    - 私钥裸 base64 统一用 PKCS#8 格式（-----BEGIN PRIVATE KEY-----）
      Alipay 密钥工具生成的私钥是 PKCS#8（非 PKCS#1）
    - 公钥裸 base64 用 X.509 SubjectPublicKeyInfo 格式（-----BEGIN PUBLIC KEY-----）
    """
    content = Path(path).read_text(encoding="utf-8").strip()
    if "BEGIN" not in content:
        # 裸 base64 -> 包装成 PEM 格式
        if is_private:
            content = "-----BEGIN PRIVATE KEY-----\n" + content + "\n-----END PRIVATE KEY-----"
        else:
            content = "-----BEGIN PUBLIC KEY-----\n" + content + "\n-----END PUBLIC KEY-----"
    return content


def _get_app_private_key() -> str:
    if not settings.alipay_app_private_key_file:
        raise RuntimeError("ALIPAY_APP_PRIVATE_KEY_FILE 未配置")
    return _read_key(settings.alipay_app_private_key_file, is_private=True)


def _get_alipay_public_key() -> str:
    if not settings.alipay_public_key_file:
        raise RuntimeError("ALIPAY_PUBLIC_KEY_FILE 未配置")
    return _read_key(settings.alipay_public_key_file, is_private=False)


def _sign(data: str) -> str:
    """用应用私钥对 data 做 RSA2 签名。返回 base64 字符串。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(
        _get_app_private_key().encode("utf-8"), password=None
    )
    signature = private_key.sign(
        data.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    import base64
    return base64.b64encode(signature).decode("utf-8")


def _verify(signature_b64: str, data: str) -> bool:
    """用支付宝公钥验证签名。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature

    try:
        public_key = serialization.load_pem_public_key(
            _get_alipay_public_key().encode("utf-8")
        )
        import base64
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError, TypeError) as e:
        log.warning("[alipay] verify signature failed: %s", e)
        return False


def _build_sign_string(params: dict[str, str]) -> str:
    """按 key 字典序排列 + & 连接，空值不参与签名。"""
    sorted_items = sorted((k, v) for k, v in params.items() if v)
    return "&".join(f"{k}={v}" for k, v in sorted_items)


def build_pay_url(
    *,
    out_trade_no: str,
    total_amount: str,  # 元（字符串，避免浮点）
    subject: str,
    body: str = "",
) -> str:
    """构造 alipay.trade.page.pay 跳转 URL。

    返回完整的 GET URL，前端用 window.location.href 跳转。
    """
    params: dict[str, str] = {
        **_COMMON_PARAMS,
        "app_id": settings.alipay_app_id,
        "method": "alipay.trade.page.pay",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "notify_url": settings.alipay_notify_url,
        "return_url": settings.alipay_return_url,
        "biz_content": (
            f'{{"out_trade_no":"{out_trade_no}",'
            f'"total_amount":"{total_amount}",'
            f'"subject":"{subject}",'
            f'"body":"{body}",'
            f'"product_code":"FAST_INSTANT_TRADE_PAY"}}'
        ),
    }
    sign_string = _build_sign_string(params)
    sign = _sign(sign_string)
    params["sign"] = sign
    # URL encode 后拼到 gateway
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{settings.alipay_gateway_url}?{query}"


def verify_notification(notify_data: dict[str, str]) -> bool:
    """验证 Alipay webhook 异步通知签名。

    notify_data 是 Alipay POST 过来的所有参数（key=value）。
    验签时排除 sign + sign_type，其余按字典序拼接待验。
    """
    sign = notify_data.get("sign", "")
    if not sign:
        return False
    # 排除 sign 和 sign_type
    params_to_sign = {
        k: v for k, v in notify_data.items() if k not in ("sign", "sign_type")
    }
    sign_string = _build_sign_string(params_to_sign)
    return _verify(sign, sign_string)
