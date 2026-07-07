"""离线测试用的 MockProvider。

不依赖网络。通过 handler 函数返回 LLM 应当输出的字符串。
"""
from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Callable

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

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ) -> AsyncIterator[str]:
        """流式模拟：把 handler 返回的字符串切成 ~10 字一块 yield。

        每块之间 await asyncio.sleep(0) 让出控制权，模拟真实 SSE 流式节奏。
        测试不需要真实延迟，0ms 让出足够验证流式行为。
        """
        if self._handler is None:
            raise LLMError(self.name, None, "no handler configured")
        content = self._handler(messages)
        # 切成 ~10 字一块（最后一个块可能更短）
        chunk_size = 10
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]
            await asyncio.sleep(0)
