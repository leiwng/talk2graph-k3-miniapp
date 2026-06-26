"""智谱 GLM 系列 — OpenAI 兼容 endpoint。

默认 base_url: https://open.bigmodel.cn/api/paas/v4
默认 model: glm-4.5（GLM-5.2 上线后改 ZHIPU_MODEL 环境变量即可）

可通过环境变量覆盖：
  ZHIPU_BASE_URL=...
  ZHIPU_MODEL=glm-5.2
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class ZhipuProvider(OpenAICompatProvider):
    name = "zhipu"
    _api_key_env = "ZHIPU_API_KEY"

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv(
                "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
            )
        if not self.model:
            self.model = os.getenv("ZHIPU_MODEL", "glm-4.5")
