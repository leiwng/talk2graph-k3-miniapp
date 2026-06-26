"""DeepSeek — 原生 OpenAI 兼容。

默认 base_url: https://api.deepseek.com
默认 model: deepseek-chat（V4 Pro 发布后改 DEEPSEEK_MODEL 即可）
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class DeepSeekProvider(OpenAICompatProvider):
    name = "deepseek"
    _api_key_env = "DEEPSEEK_API_KEY"

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not self.model:
            self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
