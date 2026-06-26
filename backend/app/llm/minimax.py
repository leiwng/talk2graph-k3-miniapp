"""MiniMax MiniMax-M3 / abab 系列 — OpenAI 兼容。

默认 base_url: https://api.minimaxi.com/v1
默认 model: MiniMax-M3

环境变量：
  MINIMAX_API_KEY=...
  MINIMAX_MODEL=MiniMax-M3   # 可换成其他 MiniMax 模型
  MINIMAX_BASE_URL=...
"""
from __future__ import annotations

import os

from .base import OpenAICompatProvider


class MiniMaxProvider(OpenAICompatProvider):
    name = "minimax"
    _api_key_env = "MINIMAX_API_KEY"

    def __init__(self, **kw):
        super().__init__(**kw)
        if not self.base_url:
            self.base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
        if not self.model:
            self.model = os.getenv("MINIMAX_MODEL", "MiniMax-M3")
