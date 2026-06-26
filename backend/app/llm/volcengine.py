"""火山引擎方舟（Ark） — OpenAI 兼容。

火山可以承载多种模型（含 GLM 系列、DeepSeek、豆包等），具体模型由"接入点 ID"决定。
你需要先在火山方舟控制台创建一个 endpoint（比如把 GLM-5.2 接入），拿到 ep-xxxx，
然后把它写进 VOLCENGINE_ENDPOINT_ID。

默认 base_url: https://ark.cn-beijing.volces.com/api/v3
环境变量：
  VOLCENGINE_API_KEY=...        # 鉴权
  VOLCENGINE_ENDPOINT_ID=ep-... # 实际充当 OpenAI 的 `model` 字段
  VOLCENGINE_BASE_URL=...       # 可选：海外/华南节点
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class VolcengineProvider(OpenAICompatProvider):
    name = "volcengine"
    _api_key_env = "VOLCENGINE_API_KEY"
    # 火山部分 endpoint（如 GLM-5.2 coding 接入点）不支持 response_format=json_object
    supports_json_mode = False

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv(
                "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
            )
        # 火山的 "model" 字段填 Endpoint ID（如 ep-xxxx）
        if not self.model:
            self.model = os.getenv("VOLCENGINE_ENDPOINT_ID", "")

    @property
    def enabled(self) -> bool:
        return bool(self._api_key) and bool(self.model)
