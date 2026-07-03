"""Kimi (Moonshot AI) — OpenAI 兼容。

默认 base_url: https://api.moonshot.cn/v1
支持模型: kimi-k2.6 / kimi-k2.7-code / kimi-k2.7-code-highspeed

环境变量：
  MOONSHOT_API_KEY=...
  MOONSHOT_MODEL=kimi-k2.6    # 可选：覆盖默认模型
  MOONSHOT_BASE_URL=...       # 可选
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class KimiProvider(OpenAICompatProvider):
    name = "kimi"
    _api_key_env = "MOONSHOT_API_KEY"

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv(
                "MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"
            )
        if not self.model:
            self.model = os.getenv("MOONSHOT_MODEL", "kimi-k2.6")

    def _build_payload(self, messages, *, json_mode, temperature, max_tokens):
        # Kimi k2.6 / k2.7 系列部分模型仅支持 temperature=1，不传此字段让 API 用默认值
        payload = super()._build_payload(
            messages,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # 移除 temperature，避免 400 错误
        payload.pop("temperature", None)
        return payload
