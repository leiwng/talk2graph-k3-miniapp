"""阿里云百炼（DashScope）— OpenAI 兼容端点。

默认 base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
默认 model: qwen-max（改 BAILIAN_MODEL 或在 T2G_FALLBACK_PROVIDERS 里用 bailian:<model> 指定）
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class BailianProvider(OpenAICompatProvider):
    name = "bailian"
    _api_key_env = "BAILIAN_API_KEY"

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv(
                "BAILIAN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        if not self.model:
            self.model = os.getenv("BAILIAN_MODEL", "qwen-max")
