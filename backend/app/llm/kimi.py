"""Kimi (Moonshot AI) — OpenAI 兼容。

默认 base_url: https://api.moonshot.cn/v1
支持模型: kimi-k2.6 / kimi-k2.7-code / kimi-k2.7-code-highspeed

kimi-k2.6 / k2.7 系列均为思考模型，temperature 不可修改（不传此字段）。
其中 kimi-k2.6 默认开启 thinking，复杂 prompt 推理时间长（>120s）易超时；
画图 DSL 是结构化输出，无需深度推理，对 k2.6 传 thinking.type=disabled 关闭思考。
kimi-k2.7-code 始终 thinking 且无法关闭（传 disabled 会报错），不处理。

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
        payload = super()._build_payload(
            messages,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Kimi k2.6 / k2.7 系列 temperature 不可修改，移除避免 400 错误
        payload.pop("temperature", None)
        # kimi-k2.6 默认开启 thinking，复杂 prompt 推理时间长易超时（>120s）；
        # 画图 DSL 是结构化输出，无需深度推理，关闭 thinking 保证响应速度。
        # kimi-k2.7-code 始终 thinking 且无法关闭（传 disabled 会报错），不处理。
        if self.model == "kimi-k2.6":
            payload["thinking"] = {"type": "disabled"}
        return payload
