"""LLM Provider 抽象基类。

设计目标：
- 三家（智谱 / 火山 / DeepSeek）都走 OpenAI 兼容 chat completions
- 统一 retry / 限流 / token 计费 / 错误归一
- 关键能力：`extract_dsl(nl, current_dsl)` — 把自然语言转 DSL（或 DSL diff）
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ChatResponse:
    content: str
    usage: ChatUsage = field(default_factory=ChatUsage)
    latency_ms: int = 0
    provider: str = ""
    model: str = ""


class LLMError(RuntimeError):
    """Provider 调用失败（网络 / 鉴权 / 限流 / 内部错误）。"""

    def __init__(self, provider: str, status: int | None, message: str):
        super().__init__(f"[{provider}] {status}: {message}")
        self.provider = provider
        self.status = status
        self.message = message


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    @property
    def enabled(self) -> bool: ...

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> ChatResponse: ...


class OpenAICompatProvider:
    """OpenAI 兼容 chat completions Provider 基类。

    子类覆盖：name / model / base_url / _api_key / 可选的 _build_payload。
    """

    name: str = "openai"
    model: str = ""
    base_url: str = ""
    _api_key_env: str = ""
    # 部分模型（如 GLM-5.2 在火山 coding endpoint）不支持 response_format=json_object，
    # 此时通过 prompt 约束 JSON 而非显式 response_format。
    supports_json_mode: bool = True

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None):
        self._api_key = api_key or os.getenv(self._api_key_env, "")
        if model:
            self.model = model
        if base_url:
            self.base_url = base_url

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode and self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> ChatResponse:
        if not self.enabled:
            raise LLMError(self.name, None, "API key not configured")
        payload = self._build_payload(
            messages,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        t0 = time.perf_counter()
        url = self.base_url.rstrip("/") + "/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, headers=self._headers(), json=payload)
        except httpx.HTTPError as e:
            raise LLMError(self.name, None, f"network error: {e}") from e
        latency_ms = int((time.perf_counter() - t0) * 1000)

        if r.status_code >= 400:
            raise LLMError(self.name, r.status_code, r.text[:300])
        try:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            usage_raw = data.get("usage") or {}
            usage = ChatUsage(
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
                completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise LLMError(self.name, r.status_code, f"malformed response: {e}") from e

        log.info(
            "llm.chat.ok",
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        return ChatResponse(
            content=content,
            usage=usage,
            latency_ms=latency_ms,
            provider=self.name,
            model=self.model,
        )


def parse_json_response(content: str) -> Any:
    """容错解析 LLM 输出的 JSON：
    1. 直接 json.loads
    2. 剥离 ```json ... ``` 代码块
    3. 找到第一个 `{` 与最后一个 `}` 截取
    """
    s = content.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 剥 fences
    if "```" in s:
        # 取第一个代码块内部
        parts = s.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            if block.startswith("json"):
                block = block[4:]
            block = block.strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

    # 截取大括号
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"cannot parse JSON from LLM output: {content[:200]}")
