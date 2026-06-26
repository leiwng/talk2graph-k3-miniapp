"""离线测试用的 MockProvider。

不依赖网络。通过 handler 函数返回 LLM 应当输出的字符串。
"""
from __future__ import annotations

import time
from typing import Callable

from .base import ChatMessage, ChatResponse, ChatUsage, LLMError


class MockProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self, handler: Callable[[list[ChatMessage]], str] | None = None):
        self._handler = handler

    @property
    def enabled(self) -> bool:
        return True

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> ChatResponse:
        if self._handler is None:
            raise LLMError(self.name, None, "no handler configured")
        t0 = time.perf_counter()
        content = self._handler(messages)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return ChatResponse(
            content=content,
            usage=ChatUsage(prompt_tokens=10, completion_tokens=50),
            latency_ms=latency_ms,
            provider=self.name,
            model=self.model,
        )
