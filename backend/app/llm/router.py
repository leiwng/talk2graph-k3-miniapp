"""LLM Provider 路由 & 降级。

- 注册全部 Provider；按 name 查找
- `default` 取 env DEFAULT_PROVIDER，缺省 "zhipu"
- 调用失败可在 fallback_chain 中顺序降级
"""
from __future__ import annotations

import os

from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .minimax import MiniMaxProvider
from .volcengine import VolcengineProvider
from .zhipu import ZhipuProvider


class LLMRouter:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {
            "zhipu": ZhipuProvider(),
            "volcengine": VolcengineProvider(),
            "deepseek": DeepSeekProvider(),
            "minimax": MiniMaxProvider(),
        }
        self.default = os.getenv("DEFAULT_PROVIDER", "zhipu")
        self.fallback_chain = ["zhipu", "volcengine", "deepseek", "minimax"]

    def register(self, p: LLMProvider) -> None:
        self._providers[p.name] = p

    def get(self, name: str | None = None) -> LLMProvider:
        key = name or self.default
        if key not in self._providers:
            raise KeyError(f"unknown provider: {key}")
        return self._providers[key]

    def list_available(self) -> list[dict]:
        out = []
        for name, p in self._providers.items():
            out.append({
                "name": name,
                "model": getattr(p, "model", ""),
                "enabled": bool(getattr(p, "enabled", False)),
                "is_default": name == self.default,
            })
        return out


# 全局单例
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
